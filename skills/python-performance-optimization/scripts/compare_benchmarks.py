#!/usr/bin/env python3
"""Compare timing between a baseline and an optimized version of the same code.

Ported from python-refactor's benchmark_changes.py (before/after-refactoring
comparison) for this skill's own baseline -> optimize -> re-benchmark ->
compare workflow step. Same pattern, reframed: "before" is the pre-optimization
baseline, "after" is the code once the approved change from the propose step
has been applied.

A companion module supplies each function's test input via a
`benchmark_data_<function_name>()` (returns args as a tuple) or
`benchmark_setup_<function_name>()` (returns a dict, list/tuple, or single
positional value) function. Functions with neither are called with no arguments.

Usage:
    python compare_benchmarks.py <baseline_file> <optimized_file> <bench_data_module> [--threshold 10]
"""

import argparse
import importlib.util
import json
import sys
import timeit
from pathlib import Path
from typing import Any, Callable


def load_module_from_file(file_path: Path, module_name: str):
    """Dynamically load a Python module from a file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def discover_benchmarkable_functions(module) -> list[tuple[str, Callable]]:
    """Discover public functions defined in a module that can be benchmarked."""
    functions = []

    for name in dir(module):
        if name.startswith('_'):
            continue

        obj = getattr(module, name)
        if callable(obj) and hasattr(obj, '__module__') and obj.__module__ == module.__name__:
            functions.append((name, obj))

    return functions


def create_benchmark_wrapper(func: Callable, bench_data_module) -> Callable:
    """Wrap a function with the test input the bench-data module provides for it."""
    func_name = func.__name__

    data_provider_name = f"benchmark_data_{func_name}"
    setup_provider_name = f"benchmark_setup_{func_name}"

    if hasattr(bench_data_module, data_provider_name):
        data_provider = getattr(bench_data_module, data_provider_name)
        return lambda: func(*data_provider())

    if hasattr(bench_data_module, setup_provider_name):
        setup_provider = getattr(bench_data_module, setup_provider_name)
        setup_data = setup_provider()

        if isinstance(setup_data, dict):
            return lambda: func(**setup_data)
        if isinstance(setup_data, (list, tuple)):
            return lambda: func(*setup_data)
        return lambda: func(setup_data)

    return lambda: func()


def benchmark_function(func: Callable, number: int = 1000, repeat: int = 5) -> dict[str, float] | None:
    """Time a function and return min/max/mean/median seconds-per-call."""
    try:
        func()  # warm up

        times = timeit.repeat(func, number=number, repeat=repeat)
        times = [t / number for t in times]

        return {
            'min': min(times),
            'max': max(times),
            'mean': sum(times) / len(times),
            'median': sorted(times)[len(times) // 2],
        }
    except Exception as e:
        print(f"  Error benchmarking function: {e}", file=sys.stderr)
        return None


def compare_benchmarks(
    baseline_results: dict[str, float] | None,
    optimized_results: dict[str, float] | None,
    threshold_pct: float = 10.0,
) -> dict[str, Any]:
    """Compare baseline vs. optimized timing and flag a regression past the threshold."""
    if baseline_results is None or optimized_results is None:
        return {'regression': None, 'error': 'Benchmark failed'}

    baseline_time = baseline_results['median']
    optimized_time = optimized_results['median']

    pct_change = ((optimized_time - baseline_time) / baseline_time) * 100 if baseline_time > 0 else 0.0
    has_regression = pct_change > threshold_pct

    return {
        'baseline_median': baseline_time,
        'optimized_median': optimized_time,
        'pct_change': round(pct_change, 2),
        'threshold_pct': threshold_pct,
        'regression': has_regression,
        'faster': pct_change < 0,
    }


def format_time(t: float) -> str:
    if t < 1e-6:
        return f"{t * 1e9:.2f} ns"
    if t < 1e-3:
        return f"{t * 1e6:.2f} µs"
    if t < 1:
        return f"{t * 1e3:.2f} ms"
    return f"{t:.2f} s"


def print_benchmark_results(func_name: str, comparison: dict[str, Any]) -> None:
    print(f"\n  Function: {func_name}")
    print(f"  {'-' * 66}")

    if comparison.get('error'):
        print(f"  x {comparison['error']}")
        return

    baseline_time = comparison['baseline_median']
    optimized_time = comparison['optimized_median']
    pct_change = comparison['pct_change']
    threshold = comparison['threshold_pct']

    print(f"  Baseline:  {format_time(baseline_time)} (median)")
    print(f"  Optimized: {format_time(optimized_time)} (median)")

    if comparison['faster']:
        print(f"  Change: {pct_change:+.1f}% FASTER")
    elif comparison['regression']:
        print(f"  Change: {pct_change:+.1f}% REGRESSION (threshold: {threshold}%)")
    else:
        print(f"  Change: {pct_change:+.1f}% within threshold")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare timing between a baseline and an optimized version of the same code"
    )
    parser.add_argument("baseline_file", type=Path, help="Path to the pre-optimization file")
    parser.add_argument("optimized_file", type=Path, help="Path to the optimized file")
    parser.add_argument("bench_data_module", type=Path, help="Path to a benchmark-data module")
    parser.add_argument("--threshold", type=float, default=10.0, help="Regression threshold in percent (default: 10)")
    parser.add_argument("--number", type=int, default=1000, help="Executions per timing (default: 1000)")
    parser.add_argument("--repeat", type=int, default=5, help="Timing repeats (default: 5)")
    parser.add_argument("--json", action="store_true", help="Output JSON format")

    args = parser.parse_args()

    for file_path in [args.baseline_file, args.optimized_file, args.bench_data_module]:
        if not file_path.exists():
            print(f"Error: File not found: {file_path}", file=sys.stderr)
            sys.exit(1)
        if file_path.suffix != '.py':
            print(f"Error: File must be a Python file (.py): {file_path}", file=sys.stderr)
            sys.exit(1)

    try:
        baseline_module = load_module_from_file(args.baseline_file, "baseline_module")
        optimized_module = load_module_from_file(args.optimized_file, "optimized_module")
        bench_data_module = load_module_from_file(args.bench_data_module, "bench_data_module")
    except Exception as e:
        print(f"Error loading modules: {e}", file=sys.stderr)
        sys.exit(1)

    baseline_functions = discover_benchmarkable_functions(baseline_module)
    optimized_functions = discover_benchmarkable_functions(optimized_module)

    baseline_names = {name for name, _ in baseline_functions}
    optimized_names = {name for name, _ in optimized_functions}
    common_names = baseline_names & optimized_names

    if not common_names:
        print("Error: No common functions found between baseline and optimized versions", file=sys.stderr)
        sys.exit(1)

    results: dict[str, Any] = {}
    regressions_found = False

    if not args.json:
        print(f"\n{'=' * 70}")
        print("Performance Benchmark Comparison")
        print(f"{'=' * 70}")
        print(f"\nBenchmarking {len(common_names)} function(s)...")

    for func_name in sorted(common_names):
        baseline_func = next(f for name, f in baseline_functions if name == func_name)
        optimized_func = next(f for name, f in optimized_functions if name == func_name)

        try:
            baseline_wrapper = create_benchmark_wrapper(baseline_func, bench_data_module)
            optimized_wrapper = create_benchmark_wrapper(optimized_func, bench_data_module)
        except Exception as e:
            print(f"\n  Error creating benchmark for {func_name}: {e}", file=sys.stderr)
            continue

        baseline_results = benchmark_function(baseline_wrapper, args.number, args.repeat)
        optimized_results = benchmark_function(optimized_wrapper, args.number, args.repeat)
        comparison = compare_benchmarks(baseline_results, optimized_results, args.threshold)

        results[func_name] = {
            'baseline': baseline_results,
            'optimized': optimized_results,
            'comparison': comparison,
        }

        if not args.json:
            print_benchmark_results(func_name, comparison)

        if comparison.get('regression'):
            regressions_found = True

    if not args.json:
        print(f"\n{'=' * 70}")
        print("Summary:")
        print(f"{'=' * 70}")

        total = len(results)
        faster = sum(1 for r in results.values() if r['comparison'].get('faster'))
        regressed = sum(1 for r in results.values() if r['comparison'].get('regression'))
        within_threshold = total - faster - regressed

        print(f"  Total functions: {total}")
        print(f"  Faster: {faster}")
        print(f"  Within threshold: {within_threshold}")
        print(f"  Regressions: {regressed}")

        if regressions_found:
            print("\nPerformance regressions detected!")
            sys.exit(1)
        else:
            print("\nNo significant performance regressions")
    else:
        print(json.dumps(results, indent=2))

    sys.exit(0)


if __name__ == "__main__":
    main()
