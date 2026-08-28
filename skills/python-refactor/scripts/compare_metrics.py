#!/usr/bin/env python3
"""Compare code metrics before and after refactoring.

This script compares complexity and documentation metrics between two
versions of a file to quantify refactoring improvements. Metrics come from
python-scan's analyzers (shelled out to as subprocesses, the way
python-scan's own analyze_all.py fans out to its sibling scripts) rather
than from copies of those analyzers living in this skill.

Usage:
    python compare_metrics.py <before_file> <after_file> [--json]
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

SCAN_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "python-scan" / "scripts"


def run_scan_script(script_name: str, file_path: Path) -> Dict[str, Any]:
    """Run one python-scan analyzer against a single file and parse its JSON output."""
    script_path = SCAN_SCRIPTS / script_name
    if not script_path.exists():
        print(f"Error: python-scan script not found: {script_path}", file=sys.stderr)
        sys.exit(1)

    cmd = [sys.executable, str(script_path), str(file_path), "--format", "json"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error running {script_name} on {file_path}:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    return json.loads(result.stdout)


def get_complexity_metrics(file_path: Path) -> Dict[str, Any]:
    """Fetch a file's complexity/maintainability metrics from python-scan."""
    data = run_scan_script("analyze_multi_metrics.py", file_path)
    files = data.get("files", [])
    return files[0] if files else {}


def get_documentation_metrics(file_path: Path) -> Dict[str, Any]:
    """Fetch a file's documentation coverage metrics from python-scan."""
    data = run_scan_script("check_documentation.py", file_path)
    coverage = data.get("coverage", [])
    return coverage[0] if coverage else {}


def calculate_percentage_change(before: float, after: float) -> float:
    """Calculate percentage change (positive = improvement for metrics we want to decrease)."""
    if before == 0:
        return 0.0
    # For metrics we want to decrease (complexity), negative change is good
    return round(((before - after) / before) * 100, 1)


def calculate_percentage_increase(before: float, after: float) -> float:
    """Calculate percentage increase (positive = improvement for metrics we want to increase)."""
    if before == 0:
        if after > 0:
            return 100.0
        return 0.0
    # For metrics we want to increase (coverage, maintainability), positive change is good
    return round(((after - before) / before) * 100, 1)


def compare_complexity(before_file: Path, after_file: Path) -> Dict[str, Any]:
    """Compare complexity/maintainability metrics between two files."""
    before = get_complexity_metrics(before_file)
    after = get_complexity_metrics(after_file)

    comparison: Dict[str, Any] = {}

    # Lower is better
    for metric in ("avg_cyclomatic", "max_cyclomatic", "max_cognitive", "total_cognitive"):
        b, a = before.get(metric, 0), after.get(metric, 0)
        comparison[metric] = {
            "before": b,
            "after": a,
            "change": calculate_percentage_change(b, a),
            "improved": a <= b,
        }

    # Higher is better
    b, a = before.get("maintainability_index", 0.0), after.get("maintainability_index", 0.0)
    comparison["maintainability_index"] = {
        "before": b,
        "after": a,
        "change": calculate_percentage_increase(b, a),
        "improved": a >= b,
    }

    return comparison


def compare_documentation(before_file: Path, after_file: Path) -> Dict[str, Any]:
    """Compare documentation metrics between two files."""
    before = get_documentation_metrics(before_file)
    after = get_documentation_metrics(after_file)

    before_doc = before.get("docstring_coverage_pct", 0.0)
    after_doc = after.get("docstring_coverage_pct", 0.0)
    before_types = before.get("type_hint_coverage_pct", 0.0)
    after_types = after.get("type_hint_coverage_pct", 0.0)
    before_mod_doc = before.get("has_module_docstring", False)
    after_mod_doc = after.get("has_module_docstring", False)

    return {
        "module_docstring": {
            "before": before_mod_doc,
            "after": after_mod_doc,
            "improved": after_mod_doc and not before_mod_doc,
        },
        "docstring_coverage": {
            "before": before_doc,
            "after": after_doc,
            "change": calculate_percentage_increase(before_doc, after_doc),
            "improved": after_doc >= before_doc,
        },
        "type_hint_coverage": {
            "before": before_types,
            "after": after_types,
            "change": calculate_percentage_increase(before_types, after_types),
            "improved": after_types >= before_types,
        },
    }


def print_comparison(complexity: Dict[str, Any], documentation: Dict[str, Any]):
    """Print comparison results in human-readable format."""
    print(f"\n{'='*70}")
    print(f"Refactoring Metrics Comparison")
    print(f"{'='*70}\n")

    print("Complexity Metrics:")
    print(f"{'─'*70}")

    for metric_name, data in complexity.items():
        metric_label = metric_name.replace('_', ' ').title()
        before = data['before']
        after = data['after']
        change = data['change']
        improved = data['improved']

        symbol = '✓' if improved else '✗'
        change_str = f"{change:+.1f}%" if change != 0 else "no change"

        print(f"  {metric_label}:")
        print(f"    Before: {before}, After: {after}, Change: {change_str} {symbol}")

    print(f"\nDocumentation Metrics:")
    print(f"{'─'*70}")

    # Module docstring
    mod_doc = documentation['module_docstring']
    if mod_doc['after'] and not mod_doc['before']:
        print(f"  Module Docstring: Added ✓")
    elif mod_doc['after']:
        print(f"  Module Docstring: Present ✓")
    else:
        print(f"  Module Docstring: Missing ✗")

    # Coverage metrics
    for metric_name, data in documentation.items():
        if metric_name == 'module_docstring':
            continue

        metric_label = metric_name.replace('_', ' ').title()
        before = data['before']
        after = data['after']
        change = data['change']
        improved = data['improved']

        symbol = '✓' if improved else '✗'
        change_str = f"{change:+.1f}%" if change != 0 else "no change"

        print(f"  {metric_label}:")
        print(f"    Before: {before}%, After: {after}%, Change: {change_str} {symbol}")

    # Overall assessment
    print(f"\nOverall Assessment:")
    print(f"{'─'*70}")

    complexity_improvements = sum(1 for data in complexity.values() if data['improved'])
    complexity_total = len(complexity)

    doc_improvements = sum(1 for data in documentation.values() if data['improved'])
    doc_total = len(documentation)

    print(f"  Complexity: {complexity_improvements}/{complexity_total} metrics improved")
    print(f"  Documentation: {doc_improvements}/{doc_total} metrics improved")

    if complexity_improvements == complexity_total and doc_improvements == doc_total:
        print(f"\n✓ All metrics improved or maintained!")
    elif complexity_improvements + doc_improvements > 0:
        print(f"\n⚠ Some metrics improved")
    else:
        print(f"\n✗ No improvements detected")


def main():
    parser = argparse.ArgumentParser(
        description="Compare code metrics before and after refactoring"
    )
    parser.add_argument("before_file", type=Path, help="Path to file before refactoring")
    parser.add_argument("after_file", type=Path, help="Path to file after refactoring")
    parser.add_argument("--json", action="store_true", help="Output JSON format")

    args = parser.parse_args()

    # Validate files
    for file_path in [args.before_file, args.after_file]:
        if not file_path.exists():
            print(f"Error: File not found: {file_path}", file=sys.stderr)
            sys.exit(1)
        if not file_path.suffix == '.py':
            print(f"Error: File must be a Python file (.py): {file_path}", file=sys.stderr)
            sys.exit(1)

    # Compare metrics
    complexity_comparison = compare_complexity(args.before_file, args.after_file)
    documentation_comparison = compare_documentation(args.before_file, args.after_file)

    if args.json:
        output = {
            'complexity': complexity_comparison,
            'documentation': documentation_comparison
        }
        print(json.dumps(output, indent=2))
    else:
        print_comparison(complexity_comparison, documentation_comparison)


if __name__ == "__main__":
    main()
