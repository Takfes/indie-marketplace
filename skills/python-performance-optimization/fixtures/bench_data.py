"""Companion bench-data module for compare_benchmarks.py.

Supplies test inputs via benchmark_data_<function_name>() -- one per function
shared between baseline_funcs.py and optimized_funcs.py.
"""

from __future__ import annotations


def benchmark_data_find_duplicates() -> tuple:
    items = [i % 100 for i in range(200)]
    return (items,)


def benchmark_data_join_lines() -> tuple:
    return (500,)
