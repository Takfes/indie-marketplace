#!/usr/bin/env python3
"""Filter yt-dlp's line-delimited --dump-json output into compact video metadata.

Reads yt-dlp's `--dump-json` output from stdin (one JSON object per line,
one per video) and writes a compact JSON array to stdout with only the
fields useful for search results, optionally filtered by upload date and
capped at a max count.

Usage:
    yt-dlp "ytsearch25:QUERY" --dump-json --no-warnings \\
      | python3 filter_results.py --days 7 --max 15
"""
import argparse
import json
import sys
from datetime import datetime, timedelta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=0, help="keep only videos uploaded in the last N days; 0 = no filter")
    parser.add_argument("--max", type=int, default=15, help="max results to keep after filtering")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    cutoff = ""
    if args.days > 0:
        cutoff = (datetime.now() - timedelta(days=args.days - 1)).strftime("%Y%m%d")

    results = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            v = json.loads(line)
        except json.JSONDecodeError:
            continue

        upload_date = v.get("upload_date") or ""
        if cutoff and upload_date and upload_date < cutoff:
            continue

        vid_id = v.get("id", "")
        results.append({
            "id": vid_id,
            "title": v.get("title", ""),
            "channel": v.get("channel") or v.get("uploader", ""),
            "url": v.get("webpage_url") or f"https://www.youtube.com/watch?v={vid_id}",
            "view_count": v.get("view_count"),
            "like_count": v.get("like_count"),
            "upload_date": upload_date,
            "duration": v.get("duration_string") or str(v.get("duration", "")),
            "description": (v.get("description") or "")[:400],
        })
        if len(results) >= args.max:
            break

    json.dump(results, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
