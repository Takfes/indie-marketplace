#!/usr/bin/env python3
"""
Deterministic Python quality fix loop: ruff format, ruff check --fix, mypy,
secret scan, dependency audit. Every tool runs through `uvx`, which installs
it into an ephemeral cache on first use -- no separate bootstrap step.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 180, input_text: str | None = None) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, input=input_text)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def uvx(*args: str, cwd: Path | None = None, timeout: int = 180, input_text: str | None = None) -> subprocess.CompletedProcess | None:
    return run(['uvx', *args], cwd=cwd, timeout=timeout, input_text=input_text)


def check_uv() -> bool:
    return shutil.which('uv') is not None


def ruff_format(path: str) -> dict:
    """Run ruff's formatter in place. Idempotent, single pass -- no loop needed."""
    result = uvx('ruff', 'format', path)
    if result is None:
        return {'ran': False, 'error': 'ruff format failed to run'}
    tail = (result.stderr or result.stdout).strip().splitlines()
    return {
        'ran': True,
        'changed': 'reformatted' in (result.stderr + result.stdout).lower(),
        'summary': tail[-1] if tail else '',
    }


def ruff_lint_count(path: str) -> int | None:
    result = uvx('ruff', 'check', path, '--output-format', 'json')
    if result is None:
        return None
    try:
        return len(json.loads(result.stdout or '[]'))
    except json.JSONDecodeError:
        return None


def ruff_fix_loop(path: str, max_iterations: int = 5) -> dict:
    """Detect -> fix -> rerun until the issue count hits zero or stops dropping."""
    history: list[int] = []
    for _ in range(max_iterations):
        count = ruff_lint_count(path)
        if count is None:
            return {'ran': False, 'error': 'ruff check failed to run', 'history': history}
        history.append(count)
        if count == 0 or (len(history) >= 2 and history[-1] == history[-2]):
            break
        uvx('ruff', 'check', path, '--fix', '--exit-zero')

    final = uvx('ruff', 'check', path, '--output-format', 'json')
    remaining = []
    if final is not None:
        try:
            remaining = json.loads(final.stdout or '[]')
        except json.JSONDecodeError:
            remaining = []

    return {
        'ran': True,
        'issue_count_history': history,
        'converged': history[-1] == 0 or (len(history) >= 2 and history[-1] == history[-2]),
        'remaining_unfixable': [
            {
                'file': r.get('filename'),
                'line': (r.get('location') or {}).get('row'),
                'code': r.get('code'),
                'message': r.get('message'),
            }
            for r in remaining
        ],
    }


def _has_mypy_config(start: Path) -> bool:
    directory = start if start.is_dir() else start.parent
    for parent in [directory, *list(directory.parents)[:10]]:
        if (parent / 'mypy.ini').exists() or (parent / '.mypy.ini').exists():
            return True
        pyproject = parent / 'pyproject.toml'
        if pyproject.exists() and '[tool.mypy]' in pyproject.read_text(errors='ignore'):
            return True
        if (parent / '.git').exists():
            break
    return False


def type_check(path: str) -> dict:
    """mypy has no --fix; findings are reported as unresolved, not applied."""
    target = Path(path).resolve()
    args = ['mypy', path, '--no-error-summary']
    if not _has_mypy_config(target):
        args.append('--ignore-missing-imports')
    result = uvx(*args)
    if result is None:
        return {'ran': False, 'error': 'mypy failed to run'}
    errors = [line for line in (result.stdout or '').splitlines() if ': error:' in line]
    return {'ran': True, 'error_count': len(errors), 'errors': errors[:50]}


def secret_scan(path: str) -> dict:
    """detect-secrets never auto-remediates -- any hit is always unresolved."""
    result = uvx('detect-secrets', 'scan', path)
    if result is None:
        return {'ran': False, 'error': 'detect-secrets failed to run'}
    try:
        data = json.loads(result.stdout or '{}')
    except json.JSONDecodeError:
        return {'ran': False, 'error': 'could not parse detect-secrets output'}
    findings = data.get('results', {})
    total = sum(len(hits) for hits in findings.values())
    return {
        'ran': True,
        'secrets_found': total,
        'files': {f: [hit.get('type') for hit in hits] for f, hits in findings.items()},
    }


def _find_project_root(start: Path) -> Path | None:
    directory = start if start.is_dir() else start.parent
    for parent in [directory, *list(directory.parents)[:10]]:
        if (parent / 'pyproject.toml').exists() or (parent / 'requirements.txt').exists():
            return parent
        if (parent / '.git').exists():
            break
    return None


def dependency_audit(path: str) -> dict:
    """pip-audit never auto-remediates -- any hit is always unresolved."""
    root = _find_project_root(Path(path).resolve())
    if root is None:
        return {'ran': False, 'skipped': True, 'reason': 'no pyproject.toml or requirements.txt found in path or its ancestors'}

    if (root / 'uv.lock').exists():
        export = run(['uv', 'export', '--format', 'requirements-txt', '--no-hashes'], cwd=root)
        if export is None or export.returncode != 0:
            return {'ran': False, 'error': 'uv export failed', 'root': str(root)}
        audit = uvx('pip-audit', '-r', '-', '--format', 'json', '--progress-spinner', 'off', cwd=root, input_text=export.stdout)
    elif (root / 'requirements.txt').exists():
        audit = uvx('pip-audit', '-r', 'requirements.txt', '--format', 'json', '--progress-spinner', 'off', cwd=root)
    else:
        audit = uvx('pip-audit', '--format', 'json', '--progress-spinner', 'off', cwd=root)

    if audit is None:
        return {'ran': False, 'error': 'pip-audit failed to run', 'root': str(root)}
    try:
        data = json.loads(audit.stdout or '{}')
    except json.JSONDecodeError:
        return {'ran': False, 'error': 'could not parse pip-audit output', 'raw': (audit.stdout or audit.stderr or '')[:500]}

    deps = data.get('dependencies', data if isinstance(data, list) else [])
    deps = deps if isinstance(deps, list) else []
    vulnerable = [d for d in deps if d.get('vulns')]
    return {'ran': True, 'root': str(root), 'vulnerable_count': len(vulnerable), 'vulnerable': vulnerable}


def run_quality_loop(path: str, max_iterations: int = 5, skip: set[str] | None = None) -> dict:
    skip = skip or set()
    report: dict = {'meta': {'path': path}, 'stages': {}}

    if not check_uv():
        report['error'] = 'uv not found on PATH -- required to bootstrap ruff/mypy/detect-secrets/pip-audit (https://docs.astral.sh/uv/)'
        return report

    if 'format' not in skip:
        report['stages']['format'] = ruff_format(path)
    if 'lint' not in skip:
        report['stages']['lint'] = ruff_fix_loop(path, max_iterations)
    if 'types' not in skip:
        report['stages']['types'] = type_check(path)
    if 'secrets' not in skip:
        report['stages']['secrets'] = secret_scan(path)
    if 'deps' not in skip:
        report['stages']['dependencies'] = dependency_audit(path)

    unresolved = []
    lint = report['stages'].get('lint', {})
    if lint.get('remaining_unfixable'):
        unresolved.append(f"{len(lint['remaining_unfixable'])} ruff issue(s) --fix could not resolve")
    types = report['stages'].get('types', {})
    if types.get('error_count'):
        unresolved.append(f"{types['error_count']} mypy error(s)")
    secrets = report['stages'].get('secrets', {})
    if secrets.get('secrets_found'):
        unresolved.append(f"{secrets['secrets_found']} potential secret(s) -- flag for human review, never auto-remediate")
    deps = report['stages'].get('dependencies', {})
    if deps.get('vulnerable_count'):
        unresolved.append(f"{deps['vulnerable_count']} dependency vulnerability(ies)")

    report['unresolved'] = unresolved
    report['converged'] = lint.get('converged', True)
    return report


def print_text_report(report: dict) -> None:
    if 'error' in report:
        print(f"ERROR: {report['error']}", file=sys.stderr)
        return

    print("\n" + "=" * 70)
    print("PYTHON QUALITY LOOP")
    print("=" * 70)
    print(f"Path: {report['meta']['path']}")

    fmt = report['stages'].get('format')
    if fmt is not None:
        print(f"\nFormat:   {'reformatted' if fmt.get('changed') else 'already formatted'}")

    lint = report['stages'].get('lint')
    if lint is not None:
        history = lint.get('issue_count_history', [])
        print(f"Lint:     {' -> '.join(str(h) for h in history)} issues across {len(history)} iteration(s), converged={lint.get('converged')}")
        if lint.get('remaining_unfixable'):
            print(f"          {len(lint['remaining_unfixable'])} remaining (not auto-fixable):")
            for issue in lint['remaining_unfixable'][:10]:
                print(f"            {issue['file']}:{issue['line']} [{issue['code']}] {issue['message']}")

    types = report['stages'].get('types')
    if types is not None:
        print(f"Types:    {types.get('error_count', '?')} mypy error(s)")
        for line in types.get('errors', [])[:10]:
            print(f"            {line}")

    secrets = report['stages'].get('secrets')
    if secrets is not None:
        print(f"Secrets:  {secrets.get('secrets_found', '?')} potential secret(s)")

    deps = report['stages'].get('dependencies')
    if deps is not None:
        if deps.get('skipped'):
            print(f"Deps:     skipped ({deps.get('reason')})")
        else:
            print(f"Deps:     {deps.get('vulnerable_count', '?')} vulnerable dependency(ies)")

    print("\n" + "-" * 70)
    if report['unresolved']:
        print("UNRESOLVED (needs human review):")
        for item in report['unresolved']:
            print(f"  - {item}")
    else:
        print("Nothing left unresolved.")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic Python quality fix loop")
    parser.add_argument('path', nargs='?', default='.', help='File or directory')
    parser.add_argument('--format', choices=['text', 'json'], default='text', dest='output_format')
    parser.add_argument('--max-iterations', type=int, default=5)
    parser.add_argument('--skip', default='', help='Comma-separated stages to skip: format,lint,types,secrets,deps')
    parser.add_argument('--output', '-o', type=str, help='Output file')

    args = parser.parse_args()
    skip = {s.strip() for s in args.skip.split(',') if s.strip()}
    report = run_quality_loop(args.path, max_iterations=args.max_iterations, skip=skip)

    if args.output_format == 'json':
        output = json.dumps(report, indent=2)
    else:
        import io
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        print_text_report(report)
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout

    if args.output:
        Path(args.output).write_text(output)
        print(f"Report saved to {args.output}", file=sys.stderr)
    else:
        print(output)

    sys.exit(1 if report.get('unresolved') or 'error' in report else 0)


if __name__ == '__main__':
    main()
