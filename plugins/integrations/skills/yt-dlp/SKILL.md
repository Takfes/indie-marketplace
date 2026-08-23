---
name: yt-dlp
description: Search YouTube and look up video metadata (title, channel, views, likes, upload date, duration, description) via the yt-dlp CLI, with optional auto-generated transcript fetch for a specific video. Use when the user wants to find YouTube videos on a topic, look up details for a YouTube URL, or get a video's transcript/captions. Requires the yt-dlp CLI installed separately — no API key, no MCP server.
---

# yt-dlp

Search YouTube and pull structured video metadata via the [yt-dlp](https://github.com/yt-dlp/yt-dlp) CLI. No API key, no MCP server — yt-dlp talks to YouTube directly.

## Prerequisites

yt-dlp must be installed and on PATH. Check with:

```bash
yt-dlp --version
```

If missing, install one way (pick what fits the environment):

```bash
brew install yt-dlp        # macOS
pipx install yt-dlp        # cross-platform, isolated
pip install -U yt-dlp      # cross-platform
```

This skill only documents the CLI — nothing here installs it.

## Search by query

Returns up to N candidate videos for a query. `--dump-json` (not `--flat-playlist`) is required to get `upload_date`, `view_count`, `like_count`, and full descriptions — flat-playlist omits them.

```bash
timeout 90 yt-dlp "ytsearch25:QUERY" --dump-json --no-warnings --socket-timeout 15 2>/dev/null \
  | python3 scripts/filter_results.py --days 0 --max 15
```

- `ytsearchN:` — N is how many candidates yt-dlp fetches before `filter_results.py`'s `--max` cap is applied; over-fetch a bit if also filtering by `--days`.
- `--days N` — keep only videos uploaded in the last N days. `0` (default) = no filter.
- `--max N` — cap on results kept, applied after date filtering. Default 15.
- Expect roughly 1–2s per candidate fetched (full page fetch, not flat-playlist) — budget accordingly for large N.
- yt-dlp occasionally stalls on a slow/flaky connection without erroring; the outer `timeout` plus `--socket-timeout 15` bounds that so one bad call fails fast instead of hanging the whole run.

Output is a compact JSON array:

```json
[
  {
    "id": "abc123",
    "title": "...",
    "channel": "...",
    "url": "https://www.youtube.com/watch?v=abc123",
    "view_count": 45200,
    "like_count": 1832,
    "upload_date": "20260621",
    "duration": "12:34",
    "description": "..."
  }
]
```

## Look up a specific video

Have a URL or video ID already? Fetch its metadata directly instead of searching:

```bash
timeout 20 yt-dlp "VIDEO_URL_OR_ID" --dump-json --no-warnings --socket-timeout 15 2>/dev/null \
  | python3 scripts/filter_results.py --max 1
```

## Transcript (auto-generated captions)

Only fetch when the task actually needs the spoken content (summarizing, quoting, searching within a video) — it's a second network round-trip per video.

```bash
timeout 30 yt-dlp "VIDEO_URL" \
  --write-auto-sub --sub-lang en --skip-download --no-warnings --socket-timeout 15 \
  -o "/tmp/yt_transcript_VIDEO_ID" 2>/dev/null

python3 scripts/parse_vtt.py "/tmp/yt_transcript_VIDEO_ID.en.vtt" 4000
```

- `--sub-lang` — transcript language code, default `en`.
- `parse_vtt.py`'s second argument caps output length in characters (default 4000 if omitted).
- If the `.vtt` file wasn't created, the video has no auto-captions in that language — report that rather than retrying.
- `parse_vtt.py` strips WEBVTT headers, timing cues, and HTML tags, and collapses the stutter auto-captions produce from repeated cue overlap.

## Resources

- `scripts/filter_results.py` — trims yt-dlp's line-delimited `--dump-json` output to the fields above, with optional `--days` cutoff and `--max` cap. Stdlib-only.
- `scripts/parse_vtt.py` — turns a downloaded `.vtt` caption file into plain text. Stdlib-only.
