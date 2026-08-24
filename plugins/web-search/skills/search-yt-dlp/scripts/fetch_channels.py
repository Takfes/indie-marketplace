#!/usr/bin/env python3
"""Concurrent tracked-channel fetch + thumbnail pre-fetch for search-yt-dlp channel mode.

Usage:
    python3 fetch_channels.py --reference path/to/youtube-tracked-channels.md \\
        --days 7 --fetch-per-channel 10 --max 15 \\
        --out /tmp/yt_dlp_results_TS.json --thumbs-out /tmp/yt_dlp_thumbs_TS.json

Reads channel_id/uploads-playlist directly from the reference table (no live
ytsearch1: name-resolution — see that file's own "Known resolution pitfalls"
section), fetches every channel's uploads playlist concurrently via a thread
pool, then fetches+embeds a thumbnail for every video that survives the date
filter, in the same pass. Two files are written: the deduplicated video
metadata JSON (same shape search-yt-dlp always returned) and a sibling
thumbnail cache JSON keyed by video ID, ready for render-digest-html's
--thumbs-cache flag.
"""
import argparse
import base64
import json
import subprocess
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class Channel:
    name: str
    channel_id: str
    uploads_id: str


def split_row(line: str) -> list[str]:
    """Split a markdown table row into cells, honoring `\\|`-escaped literal pipes.

    Args:
        line: A single `| a | b | c |` table row, escaped pipes included.

    Returns:
        The row's cell values, unescaped and stripped.
    """
    line = line.strip()
    inner = line[1:-1].replace("\\|", "\x00PIPE\x00")
    return [c.replace("\x00PIPE\x00", "|").strip() for c in inner.split("|")]


def parse_reference_table(path: Path) -> list[Channel]:
    """Extract tracked channels from the youtube-tracked-channels.md table.

    Args:
        path: Path to the reference markdown file (Channel | channel_id |
            Uploads playlist columns).

    Returns:
        One Channel per data row, in table order.
    """
    channels = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = split_row(line)
        if len(cells) != 3:
            continue
        name, channel_id, uploads_id = cells
        if not channel_id.startswith("UC"):
            continue  # header row, separator row, or malformed
        channels.append(Channel(name=name, channel_id=channel_id, uploads_id=uploads_id))
    return channels


def fetch_channel(
    channel: Channel, cutoff: str, fetch_per_channel: int, max_results: int
) -> tuple[str, list[dict], str | None]:
    """Fetch one channel's latest uploads within the date window.

    Args:
        channel: The channel to fetch (uploads playlist ID already known).
        cutoff: `YYYYMMDD` cutoff, or empty string for no date filter.
        fetch_per_channel: How many latest uploads to pull before filtering.
        max_results: Cap on results kept per channel after filtering.

    Returns:
        (channel name, list of video-metadata dicts, error string or None).
        Never raises — a stalled or failing channel reports its error instead
        of taking down the rest of the batch.
    """
    url = f"https://www.youtube.com/playlist?list={channel.uploads_id}"
    try:
        proc = subprocess.run(
            [
                "yt-dlp",
                url,
                "--dump-json",
                "--playlist-end",
                str(fetch_per_channel),
                "--no-warnings",
                "--socket-timeout",
                "15",
            ],
            capture_output=True,
            text=True,
            timeout=75,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return channel.name, [], f"fetch failed: {exc}"

    results = []
    for line in proc.stdout.splitlines():
        try:
            v = json.loads(line)
        except json.JSONDecodeError:
            continue
        upload_date = v.get("upload_date") or ""
        if cutoff and upload_date and upload_date < cutoff:
            continue
        vid_id = v.get("id", "")
        results.append(
            {
                "id": vid_id,
                "title": v.get("title", ""),
                "channel": v.get("channel") or v.get("uploader", "") or channel.name,
                "url": v.get("webpage_url") or f"https://www.youtube.com/watch?v={vid_id}",
                "view_count": v.get("view_count"),
                "like_count": v.get("like_count"),
                "upload_date": upload_date,
                "duration": v.get("duration_string") or str(v.get("duration", "")),
                "description": (v.get("description") or "")[:400],
                "source_type": "channel",
                "source_value": channel.name,
            }
        )
        if len(results) >= max_results:
            break

    err = None
    if proc.returncode != 0 and not results:
        err = (proc.stderr or "non-zero exit, no results").strip()[:200]
    return channel.name, results, err


def fetch_thumbnail(video_id: str) -> tuple[str, str | None]:
    """Fetch and base64-embed one video's default thumbnail.

    Args:
        video_id: YouTube video ID.

    Returns:
        (video_id, data URI) on success, (video_id, None) on any failure —
        thumbnail fetch failures degrade gracefully, they never raise.
    """
    url = f"https://i.ytimg.com/vi/{video_id}/default.jpg"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
        if len(raw) < 500:
            return video_id, None
        return video_id, "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return video_id, None


def dedup_by_id(records: list[dict]) -> list[dict]:
    """Keep the first occurrence of each video ID.

    Args:
        records: Video-metadata dicts, possibly containing duplicate IDs
            (the same video can appear via more than one channel fetch only
            in edge cases, but dedup is cheap insurance regardless).

    Returns:
        Deduplicated list, original order preserved.
    """
    seen: set[str] = set()
    deduped = []
    for r in records:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        deduped.append(r)
    return deduped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reference", type=Path, required=True, help="path to youtube-tracked-channels.md")
    parser.add_argument("--days", type=int, default=0, help="date-filter window; 0 = no filter")
    parser.add_argument("--fetch-per-channel", type=int, default=10, help="latest uploads to pull per channel before filtering")
    parser.add_argument("--max", type=int, default=15, help="cap on kept results per channel after filtering")
    parser.add_argument("--workers", type=int, default=6, help="concurrent channel fetches")
    parser.add_argument("--out", type=Path, required=True, help="output path for deduplicated video metadata JSON")
    parser.add_argument("--thumbs-out", type=Path, required=True, help="output path for the thumbnail cache JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    cutoff = ""
    if args.days > 0:
        # --days N means an N-calendar-day window ending today (inclusive), so
        # offset by N-1: --days 3 run on the 19th keeps 17/18/19, not 16-19.
        cutoff = (datetime.now() - timedelta(days=args.days - 1)).strftime("%Y%m%d")

    channels = parse_reference_table(args.reference)
    if not channels:
        print(f"error: no channels parsed from {args.reference}", file=sys.stderr)
        sys.exit(1)

    all_results: list[dict] = []
    channel_errors: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(fetch_channel, ch, cutoff, args.fetch_per_channel, args.max): ch.name
            for ch in channels
        }
        for fut in as_completed(futures):
            name, results, err = fut.result()
            all_results.extend(results)
            if err:
                channel_errors.append((name, err))
            print(f"  {name}: {len(results)} in window" + (f" — ERROR: {err}" if err else ""), file=sys.stderr)

    deduped = dedup_by_id(all_results)
    args.out.write_text(json.dumps(deduped, indent=2), encoding="utf-8")

    thumbs: dict[str, str] = {}
    failed_thumbs: list[str] = []
    thumb_workers = min(16, max(1, len(deduped)))
    with ThreadPoolExecutor(max_workers=thumb_workers) as pool:
        futures = {pool.submit(fetch_thumbnail, r["id"]): r["id"] for r in deduped}
        for fut in as_completed(futures):
            vid_id, data_uri = fut.result()
            if data_uri:
                thumbs[vid_id] = data_uri
            else:
                failed_thumbs.append(vid_id)

    args.thumbs_out.write_text(
        json.dumps({"thumbs": thumbs, "failed": failed_thumbs}, indent=2), encoding="utf-8"
    )

    print(file=sys.stderr)
    print(f"Channels: {len(channels)} queried, {len(channel_errors)} errored", file=sys.stderr)
    print(f"Videos: {len(all_results)} fetched -> {len(deduped)} after dedup", file=sys.stderr)
    print(
        f"Thumbnails: {len(thumbs)}/{len(deduped)} fetched, {len(failed_thumbs)} failed"
        + (f" ({failed_thumbs})" if failed_thumbs else ""),
        file=sys.stderr,
    )
    print(str(args.out))
    print(str(args.thumbs_out))


if __name__ == "__main__":
    main()
