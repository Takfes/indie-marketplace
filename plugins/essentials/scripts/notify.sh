#!/bin/bash
f=/tmp/.claude-tink
now=$(date +%s)
[ -f "$f" ] && [ $((now - $(cat "$f"))) -lt 2 ] && exit 0
echo "$now" > "$f"
afplay /System/Library/Sounds/Tink.aiff 2>/dev/null || true
