import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skills" / "python-scan" / "scripts"
ANALYZE_ALL = SCRIPTS_DIR / "analyze_all.py"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "known_bad_module.py"

# Ground truth for FIXTURE, captured by running analyze_all.py against it — every
# analyzer here is pure-AST/stdlib, so these counts are deterministic regardless
# of environment. `complexity` stays 0 either way: radon/complexipy aren't a
# declared project dependency, and analyze_all.py degrades a missing analyzer to
# an empty issue list rather than failing the whole report.
EXPECTED_BY_CATEGORY = {
    "complexity": 0,
    "documentation": 7,
    "code_smells": 3,
    "overengineering": 0,
    "dead_code": 10,
    "unpythonic": 6,
    "coupling": 0,
    "duplicates": 1,
}


def run_scan(*args):
    return subprocess.run(
        [sys.executable, str(ANALYZE_ALL), *args],
        capture_output=True,
        text=True,
    )


def test_scan_matches_golden_fixture_counts():
    result = run_scan(str(FIXTURE), "--format", "json")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)

    assert report["summary"]["by_category"] == EXPECTED_BY_CATEGORY
    assert report["summary"]["total_issues"] == sum(EXPECTED_BY_CATEGORY.values())
    assert report["meta"]["analyzed_path"] == str(FIXTURE)


def test_scan_finds_missing_docstring_and_type_hints():
    result = run_scan(str(FIXTURE), "--format", "json")
    report = json.loads(result.stdout)

    doc_types = {issue["issue_type"] for issue in report["categories"]["documentation"]["issues"]}
    assert doc_types == {"missing_module_docstring", "missing_docstring", "missing_type_hints"}


def test_scan_finds_dead_code():
    result = run_scan(str(FIXTURE), "--format", "json")
    report = json.loads(result.stdout)

    dead_types = {issue["issue_type"] for issue in report["categories"]["dead_code"]["issues"]}
    assert "unused_import" in dead_types
    assert "unused_function" in dead_types
    assert "unused_parameter" in dead_types


def test_scan_finds_unpythonic_patterns():
    result = run_scan(str(FIXTURE), "--format", "json")
    report = json.loads(result.stdout)

    patterns = {issue["pattern_type"] for issue in report["categories"]["unpythonic"]["issues"]}
    assert "range_len_loop" in patterns
    assert "compare_to_true" in patterns


def test_scan_finds_the_duplicate_pair():
    result = run_scan(str(FIXTURE), "--format", "json")
    report = json.loads(result.stdout)

    duplicates = report["categories"]["duplicates"]["issues"]
    assert len(duplicates) == 1
    assert duplicates[0]["similarity"] == 1.0
    names = {occ["name"] for occ in duplicates[0]["occurrences"]}
    assert names == {"compute_total_a", "compute_total_b"}


def test_code_smells_drops_mutable_default_and_type_comparison():
    """Regression test for this rework: mutable-default and type()-comparison checks
    are dropped from find_code_smells.py because ruff already covers them (B006,
    E721). FIXTURE deliberately contains both (a `items=[]` default and a
    `type(data) == list` comparison) to prove neither is flagged here anymore."""
    result = run_scan(str(FIXTURE), "--format", "json")
    report = json.loads(result.stdout)

    smell_types = {issue["smell_type"] for issue in report["categories"]["code_smells"]["issues"]}
    assert smell_types == {"bare_except", "long_parameter_list", "magic_number"}
    assert "mutable_default" not in smell_types
    assert "type_comparison" not in smell_types


def test_scan_runs_on_a_directory():
    result = run_scan(str(FIXTURE.parent), "--format", "json")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["meta"]["analyzed_path"] == str(FIXTURE.parent)


def test_scan_text_format_does_not_crash():
    result = run_scan(str(FIXTURE), "--format", "text")
    assert result.returncode == 0, result.stderr
    assert "PYTHON CODE ANALYSIS REPORT" in result.stdout
