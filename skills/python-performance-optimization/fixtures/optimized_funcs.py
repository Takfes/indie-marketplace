"""Optimized ("after") versions for compare_benchmarks.py -- same function
names/signatures as baseline_funcs.py, algorithmically improved."""

from __future__ import annotations


def find_duplicates(items: list[int]) -> list[int]:
    seen: set[int] = set()
    duplicates: set[int] = set()
    for a in items:
        if a in seen:
            duplicates.add(a)
        else:
            seen.add(a)
    return list(duplicates)


def join_lines(n: int) -> str:
    return "\n".join(f"line {i}" for i in range(n)) + "\n"
