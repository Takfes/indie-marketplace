---
name: search-yt-dlp
description: Generic YouTube search and channel-fetch primitive via yt-dlp. Returns structured JSON with video metadata (title, channel, URL, views, likes, upload_date, duration, description, source). Accepts one or more search queries and/or --channels (channel names/handles, fetches each channel's latest uploads directly) plus optional flags including --days N for date filtering, --transcripts to fetch auto-generated transcripts for collection-pattern videos, and --max N to cap results. When channels come from a reference file with channel_id/uploads-playlist columns, fetch_channels.py fetches all of them concurrently and pre-fetches thumbnails in the same pass. Use this skill as a primitive; define what to search for and what to do with results in a calling prompt.
---

# search-yt-dlp

A generic YouTube search and channel-fetch primitive. Takes queries and/or channel names plus
flags, returns structured JSON. What to search for and how to use the results is the caller's
responsibility.

---

## Input format

Args are a plain string. Parse them as follows:

- **Queries** — any text that is not a flag. Separate multiple queries with ` | ` (pipe).
  Example: `"Claude Code skills 2026 | NotebookLM Claude workflow 2026"`
- **`--channels`** — one or more channel names or handles, pipe-separated (same syntax as
  queries). Example: `--channels "Nate Herk | AI Automation | Simon Scrapes | Kun Chen"`.
  Each channel is resolved to its uploads playlist and its latest videos are fetched directly
  (not searched). Can be combined with plain queries in the same invocation — both result sets
  are merged, tagged by `source_type`, and deduplicated together (see Step 2b).
- **`--days N`** — only return videos published within the last N days. `0` = no date filter.
  Default: `0` (no filter). Set to match the calling digest's cadence (e.g. `7` for weekly).
  Applies to both query results and channel results.
- **`--transcripts`** — fetch auto-generated transcripts for collection-pattern videos.
- **`--max N`** — max results to return per query or per channel after date filtering
  (default: 15, max: 50). Note: query mode fetches 25 candidates internally as a buffer for
  date filtering; channel mode fetches `--fetch-per-channel` candidates for the same reason.
- **`--fetch-per-channel N`** — how many latest uploads to over-fetch per channel before date
  filtering (default: 10). Channel mode's equivalent of the 25-candidate search buffer — set
  higher for high-frequency channels or wide `--days` windows.
- **`--lang LANG`** — transcript language code (default: `en`)

---

## Step 1 — Compute date cutoff

If `--days N` is set and N > 0, compute the cutoff date string in Python:

```bash
python3 -c "
from datetime import datetime, timedelta
print((datetime.now() - timedelta(days=N)).strftime('%Y%m%d'))
"
```

Store this as `CUTOFF_DATE` (format: `YYYYMMDD`). If `--days 0` or flag absent, set `CUTOFF_DATE=""`.

---

## Step 2a — Run yt-dlp search (query mode)

For each query, run via Bash. Note: `--flat-playlist` is intentionally omitted so that
`upload_date` and full descriptions are returned. Expect ~1–2s per result fetched.

```bash
timeout 90 yt-dlp "ytsearch25:QUERY" --dump-json --no-warnings --socket-timeout 15 2>/dev/null \
  | python3 -c "
import sys, json

cutoff = 'CUTOFF_DATE'   # substitute computed value; empty string = no filter
max_results = MAX        # substitute --max value

results = []
for line in sys.stdin:
    try:
        v = json.loads(line)
        upload_date = v.get('upload_date') or ''
        # Apply date filter if cutoff is set
        if cutoff and upload_date and upload_date < cutoff:
            continue
        vid_id = v.get('id', '')
        results.append({
            'id': vid_id,
            'title': v.get('title', ''),
            'channel': v.get('channel') or v.get('uploader', ''),
            'url': v.get('webpage_url') or f'https://www.youtube.com/watch?v={vid_id}',
            'view_count': v.get('view_count'),
            'like_count': v.get('like_count'),
            'upload_date': upload_date,  # YYYYMMDD or empty
            'duration': v.get('duration_string') or str(v.get('duration', '')),
            'description': (v.get('description') or '')[:400],
            'source_type': 'query',
            'source_value': 'QUERY',
        })
        if len(results) >= max_results:
            break
    except Exception:
        pass

for r in results:
    print(json.dumps(r))
"
```

Wait 3 seconds between queries to avoid YouTube throttling:
```bash
sleep 3
```

---

## Step 2b — Run yt-dlp channel fetch (channel mode, only if `--channels` is set)

**Primary path — channels sourced from a reference file** (e.g.
`agents.io/reference/youtube-tracked-channels.md`, which has `Channel | channel_id | Uploads
playlist` columns already populated). Run `fetch_channels.py` once for the whole channel list
instead of looping per channel:

```bash
python3 .claude/skills/search-yt-dlp/scripts/fetch_channels.py \
  --reference agents.io/reference/youtube-tracked-channels.md \
  --days N --fetch-per-channel FETCH_PER_CHANNEL --max MAX --workers 6 \
  --out /tmp/yt_dlp_results_{timestamp}.json \
  --thumbs-out /tmp/yt_dlp_thumbs_{timestamp}.json
```

This does three things a hand-rolled bash loop can't do cleanly in one pass:

1. **Reads `channel_id`/uploads-playlist straight from the reference table** — no live
   `ytsearch1:` name resolution, so it's immune to the failure mode that file's own "Known
   resolution pitfalls" section documents (two channel names that resolved to an entirely
   different, wrong channel).
2. **Fetches every channel concurrently** (`--workers`, default 6) instead of one at a time —
   wall-clock for the whole batch is now bounded by the slowest channel in a batch of 6, not
   the sum of all 18.
3. **Fetches and embeds a thumbnail for every video that survives the date filter, in the same
   pass** — thumbnails no longer wait until the HTML render step. Pass `--thumbs-out`'s path
   straight through to `render-digest-html`'s `--thumbs-cache` flag in Step 10 so a thumbnail
   is never fetched over the network twice.

The script already writes the deduplicated metadata array to `--out` and the thumbnail cache
to `--thumbs-out` — for a channel-only run (no query mode), that **is** Step 3, nothing further
to save. A channel that fails to fetch (timeout, bad connection) reports its own error to
stderr and is skipped; it does not block the rest of the batch.

**Fallback path — a channel name not present in any reference file** (no cached
`channel_id` to read). Resolve it the old way, one at a time:

```bash
CHANNEL_ID=$(timeout 20 yt-dlp "ytsearch1:CHANNEL_NAME" --dump-json --no-warnings --socket-timeout 15 2>/dev/null \
  | python3 -c "
import sys, json
v = json.loads(sys.stdin.readline())
print(v.get('channel_id', ''))
print(v.get('channel', ''), file=sys.stderr)
")
```

Sanity check: print the resolved display name (stderr above) next to `CHANNEL_NAME` so a
mismatch is visible during the run — don't silently proceed on an obviously wrong resolution.
If `CHANNEL_ID` is empty, skip this channel, note it in the Step 3 report, and move on. Then
fetch its uploads playlist the same way `fetch_channels.py` does internally (swap `UC` → `UU`,
`--dump-json --playlist-end FETCH_PER_CHANNEL`), tag results `source_type: channel`.

`youtube-channel-scan.md`'s Step 2 always uses the primary path — Step 1 already reads the
full tracked list from `agents.io/reference/youtube-tracked-channels.md`, so there's never a
channel without a cached ID in that pipeline.

**Process order:** run `--channels` before plain queries. If both modes ran in the same
invocation, collect channel-mode's saved array plus query-mode's results, then **deduplicate
by `id`, keeping first occurrence** — a video found via both a tracked channel and a discovery
query keeps its `channel` source tag, since that's the more authoritative origin for the same
video. Re-save the merged array to the same `--out` path. (Query-mode-only videos won't be in
the thumbnail cache yet — `render-digest-html` falls back to a live fetch for anything missing
from `--thumbs-cache`, so this degrades gracefully rather than failing.)

---

## Step 3 — Save metadata JSON

Channel-mode-only runs: already done by `fetch_channels.py` above. Combined channel + query
runs: save the merged, deduplicated array to `/tmp/yt_dlp_results_{timestamp}.json` per the
merge note above.

Report: total candidates fetched (broken out by channel vs query mode), how many passed date
filter, how many after dedup.

---

## Step 4 — Transcript fetch (only if --transcripts flag is set)

Identify **collection videos** from the result set — entries whose title (case-insensitive) matches:
- `\d+\s+(plugins?|skills?|tricks?|hacks?|features?|tools?|mcp)`
- `top\s+\d+`
- `\d+\s+i\s+(use|can.t live without)`
- `\d+\s+(hidden|must.know|best)`

For each collection video (limit: 4 per run to keep runtime reasonable):

```bash
timeout 30 yt-dlp "VIDEO_URL" \
  --write-auto-sub --sub-lang LANG --skip-download --no-warnings --socket-timeout 15 \
  -o "/tmp/yt_transcript_VIDEO_ID" 2>/dev/null
```

If `/tmp/yt_transcript_VIDEO_ID.en.vtt` was created, parse it:

```bash
python3 .claude/skills/search-yt-dlp/scripts/parse-vtt.py \
  /tmp/yt_transcript_VIDEO_ID.en.vtt 4000
```

Add `"transcript"` field to that entry (parsed text string, or `null` if failed).
Add `"transcript_error": true` if download failed.

---

## Output

Return the final JSON array with all fields populated. Example entry shape:

```json
{
  "id": "abc123",
  "title": "17 Claude Code Plugins You Need",
  "channel": "Some Channel",
  "url": "https://www.youtube.com/watch?v=abc123",
  "view_count": 45200,
  "like_count": 1832,
  "upload_date": "20260621",
  "duration": "12:34",
  "description": "In this video I cover the top 17 plugins...",
  "source_type": "channel",
  "source_value": "Some Channel",
  "transcript": "today we are going over seventeen plugins...",
  "transcript_error": false
}
```

**Runtime note:** Without `--flat-playlist`, expect ~1–2s per candidate video fetched.

- Query mode: 25 candidates × N queries — e.g. 3 queries = ~75 fetches, budget 2–4 minutes
  (still sequential — no concurrency added here, since query mode is deferred pending the
  New Discoveries reliability blocker, see `youtube-channel-scan.md`'s open design questions).
- Channel mode via `fetch_channels.py`: `--fetch-per-channel` fetches per channel, but batched
  `--workers` at a time instead of one at a time — e.g. 18 channels at 6 workers is 3 batches,
  each bounded by its slowest channel (~10-20s typically), not the sum of all 18. Thumbnails
  are fetched in the same run, concurrently, adding well under a minute on top even for a
  ~40-70-video batch.
- Combined runs (channel + query mode): budget query mode's sequential time on top of channel
  mode's concurrent time — they don't overlap unless run in parallel processes.

Full page fetches (not `--flat-playlist`) are intentional — `upload_date` and `like_count`
require them, and date filtering (not query/channel stability) is the primary mechanism for
preventing repeat results across recurring runs.

**Reliability note:** individual yt-dlp calls can occasionally stall on a slow/bad connection
without erroring out (observed during testing — a resolve call hung past 2 minutes once, then
completed in seconds on retry). Every yt-dlp invocation above is wrapped in an outer `timeout`
plus `--socket-timeout 15` (or, in `fetch_channels.py`, Python's own `subprocess` timeout —
same guarantee, no dependency on the external `timeout` binary, which isn't part of a stock
macOS install) so one bad call fails fast and skips cleanly instead of blocking the whole batch.
