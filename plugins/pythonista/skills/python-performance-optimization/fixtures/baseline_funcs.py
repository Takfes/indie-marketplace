"""Baseline ("before") versions for compare_benchmarks.py."""

from __future__ import annotations


def find_duplicates(items: list[int]) -> list[int]:
    duplicates: list[int] = []
    for i, a in enumerate(items):
        for b in items[i + 1 :]:
            if a == b and a not in duplicates:
                duplicates.append(a)
    return duplicates


def join_lines(n: int) -> str:
    report = ""
    for i in range(n):
        report += f"line {i}\n"
    return report
