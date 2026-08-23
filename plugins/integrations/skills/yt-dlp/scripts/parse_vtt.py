#!/usr/bin/env python3
"""Parse a .vtt subtitle file into plain text for transcript analysis."""
import re
import sys

def parse_vtt(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        content = f.read()

    # Remove WEBVTT header block
    content = re.sub(r"^WEBVTT.*?\n\n", "", content, flags=re.DOTALL)
    # Remove timing lines (00:00:00.000 --> 00:00:00.000 ...)
    content = re.sub(r"\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}[^\n]*\n", "", content)
    # Remove sequence numbers on their own line
    content = re.sub(r"^\d+\s*$", "", content, flags=re.MULTILINE)
    # Remove HTML tags (<c>, </c>, <00:00:00.000>, etc.)
    content = re.sub(r"<[^>]+>", "", content)
    # Collapse whitespace
    content = re.sub(r"\n+", " ", content).strip()
    # Deduplicate repeated phrases (auto-captions stutter)
    words = content.split()
    deduped = [words[0]] if words else []
    for w in words[1:]:
        if w != deduped[-1]:
            deduped.append(w)
    return " ".join(deduped)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: parse_vtt.py <file.vtt> [max_chars]", file=sys.stderr)
        sys.exit(1)
    max_chars = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    print(parse_vtt(sys.argv[1])[:max_chars])
