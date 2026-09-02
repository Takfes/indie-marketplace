"""Deliberately inefficient demo script for exercising the pythonista plugin's
python-performance-optimization skill (profile_report.py, live_dashboard.py).

Not production code -- every function here has an intentional anti-pattern to
profile and fix:
  - find_duplicates_slow: O(n^2) nested loop, re-slices the list each pass,
    plus a linear `in` check against a growing list. ~1.5-2s at n=15000.
  - build_dataset_slow: materializes the whole dataset into memory instead of
    streaming/generating it -- a fast but memory-heavy allocation spike
    (~150MB at n=200000), meant to show up on live_dashboard.py's RSS trace
    and tracemalloc's top allocations in profile_report.py.
"""

from __future__ import annotations

import time


def find_duplicates_slow(items: list[int]) -> list[int]:
    duplicates: list[int] = []
    for i, a in enumerate(items):
        for b in items[i + 1 :]:
            if a == b and a not in duplicates:
                duplicates.append(a)
    return duplicates


def build_dataset_slow(n: int) -> list[dict]:
    return [{"id": i, "payload": "x" * 500} for i in range(n)]


def main() -> None:
    items = [i % 7500 for i in range(15000)]
    dupes = find_duplicates_slow(items)
    time.sleep(0.5)  # gives live_dashboard.py a clean gap between the two phases
    dataset = build_dataset_slow(200000)
    print(f"found {len(dupes)} duplicates")
    print(f"built dataset of {len(dataset)} records")


if __name__ == "__main__":
    main()
