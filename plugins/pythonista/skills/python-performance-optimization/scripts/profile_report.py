#!/usr/bin/env python3
"""Profile a Python script and generate a Markdown report of its pain points.

Runs the target script under cProfile (CPU) and tracemalloc (memory) — each in
its own fresh subprocess — then turns the raw stats into a prioritized,
human-readable report: top hotspots, a one-line explanation of what is likely
going on, and a concrete proposal to fix it. The explanations are heuristic
(pattern + threshold based on the actual numbers) — treat them as a starting
point, not a verdict.

Usage:
    python scripts/profile_report.py target_script.py [script_args...]
    python scripts/profile_report.py --output report.md --top 15 target_script.py [script_args...]

Note: --output/--top must come before target_script.py — everything after it
(flags included) is passed through as arguments to the target script.

The target runs twice, once per profiler, each in a fresh subprocess: running
cProfile and tracemalloc in the same process would have each pollute the
other (a concurrent sampler thread shows up in cProfile's own stats as if it
were part of the program), and reusing one process for both passes would
hide any import-time cost/allocation in the second pass since the modules
are already cached. If the target has side effects, expect them twice.

Stdlib only — no third-party dependencies required.
"""

from __future__ import annotations

import argparse
import json
import runpy
import subprocess
import sys
import tempfile
import threading
import time
import tracemalloc
from cProfile import Profile
from dataclasses import dataclass
from pathlib import Path
from pstats import Stats

try:
    import resource

    HAS_RESOURCE = True
except ImportError:  # Windows has no `resource` module
    HAS_RESOURCE = False

THIS_FILE = Path(__file__).resolve()


@dataclass
class CpuStat:
    """One row from cProfile's stats table, ready for reporting."""

    filename: str
    lineno: int
    funcname: str
    ncalls: int
    tottime: float
    cumtime: float

    @property
    def display(self) -> str:
        short = Path(self.filename).name if self.filename not in ("~", "<string>") else self.filename
        return f"{short}:{self.lineno}({self.funcname})"

    @property
    def percall_tot(self) -> float:
        return self.tottime / self.ncalls if self.ncalls else 0.0

    @property
    def self_share(self) -> float:
        """Fraction of cumulative time spent in this function itself vs. its callees."""
        return self.tottime / self.cumtime if self.cumtime else 0.0


@dataclass
class MemStat:
    """One row from a tracemalloc snapshot, ready for reporting."""

    location: str
    size_kb: float
    count: int


@dataclass
class Finding:
    title: str
    metric: str
    explanation: str
    proposal: str


# Checked first: these are wall-clock waits, not CPU cost — cProfile counts
# blocked time as self time, which otherwise gets misreported as a hot path.
BLOCKING_HINTS: list[tuple[str, str, str]] = [
    ("sleep", "Wall-clock wait (e.g. time.sleep), not CPU cost.",
     "cProfile measures elapsed time, so blocked/waiting time is counted as self time. This isn't a CPU optimization target; if the wait matters, look at overlapping it with other work (async/threading) or shortening the wait itself."),
    ("acquire", "Likely a lock/synchronization wait, not CPU cost.",
     "If this is unexpected contention, shrink the critical section or lock granularity; if it's an intentional wait, it isn't a CPU optimization target."),
    ("select", "I/O wait (select/poll), not CPU cost.",
     "This is blocked waiting on a file descriptor or socket — look at the I/O source (network/disk), not this function."),
    ("poll", "I/O wait (select/poll), not CPU cost.",
     "This is blocked waiting on a file descriptor or socket — look at the I/O source (network/disk), not this function."),
]

# Matched against the function's path tokens (directory names + file stem),
# so this survives stdlib layout differences (e.g. `re` as a single file vs.
# a package) and doesn't depend on the shortened display name.
MODULE_HINTS: list[tuple[str, str, str]] = [
    ("json", "JSON encode/decode is on the hot path.",
     "Consider a faster codec for hot paths (e.g. orjson/msgspec), or reduce payload size before serializing."),
    ("re", "Regex matching/compilation is on the hot path.",
     "Precompile patterns with re.compile() outside the loop; for simple cases, plain str methods (str.split, in, startswith) are faster than regex."),
    ("sqlite3", "Database calls dominate this path.",
     "Batch writes with executemany() and a single commit, add an index for the filtered/joined columns, or fetch only the needed columns."),
    ("urllib", "Network I/O dominates this path.",
     "This is an I/O-bound wait, not a CPU cost — switch to asyncio/concurrent requests or batch calls rather than micro-optimizing the function body."),
    ("http", "Network I/O dominates this path.",
     "This is an I/O-bound wait, not a CPU cost — switch to asyncio/concurrent requests or batch calls rather than micro-optimizing the function body."),
    ("socket", "Network I/O dominates this path.",
     "This is an I/O-bound wait, not a CPU cost — switch to asyncio/concurrent requests or batch calls rather than micro-optimizing the function body."),
    ("hashlib", "Cryptographic hashing dominates this path.",
     "hashlib is already C-optimized; the fix is usually reducing call volume (cache digests, hash less data) rather than micro-optimizing the call."),
]

# Matched against the exact function name.
FUNC_HINTS: list[tuple[str, str, str]] = [
    ("<listcomp>", "A comprehension is the hot spot.",
     "Check for an O(n^2) pattern inside it (e.g. `x in a_list` per iteration) — swap the inner container for a set/dict for O(1) membership."),
    ("<dictcomp>", "A comprehension is the hot spot.",
     "Check for an O(n^2) pattern inside it (e.g. `x in a_list` per iteration) — swap the inner container for a set/dict for O(1) membership."),
    ("<genexpr>", "A generator expression is the hot spot.",
     "Confirm it's actually needed lazily; if it's immediately consumed into a list anyway, a plain comprehension avoids generator overhead."),
]

CALL_COUNT_THRESHOLD = 50_000
CALL_COST_THRESHOLD_S = 5e-6  # 5 microseconds per call
ORCHESTRATOR_SELF_SHARE = 0.1

SCAFFOLD_FILENAME_MARKERS = ("runpy", "<frozen")


def is_scaffolding(filename: str, funcname: str) -> bool:
    """True for frames that belong to the profiling harness itself (runpy,
    frozen importlib, this script) rather than the target — always thin
    pass-throughs, never useful to report as a "hotspot".
    """
    if any(marker in filename for marker in SCAFFOLD_FILENAME_MARKERS):
        return True
    if filename in ("~", "<string>") and "exec" in funcname:
        return True
    try:
        return Path(filename).resolve() == THIS_FILE
    except OSError:
        return False


def path_tokens(filename: str) -> set[str]:
    p = Path(filename)
    return set(p.parts) | {p.stem}


def escape_md(text: str) -> str:
    return str(text).replace("|", "\\|")


class PeakMemoryTracker:
    """Samples tracemalloc in a background thread and keeps a snapshot taken
    close to the highest traced-memory point seen (within `growth_factor`).

    A single snapshot taken after the target script returns only sees what's
    still alive at that instant — anything allocated and freed mid-run (e.g. a
    large list built, used, and dropped) would otherwise be invisible. Only
    re-snapshotting on each new record would also make runs with steady
    monotonic growth take a `take_snapshot()` call (expensive: proportional to
    live block count) on every sampling tick; `growth_factor` throttles that to
    roughly log(range) snapshots while `peak_size`/`true_peak_size` stay exact.
    """

    def __init__(self, interval: float = 0.05, growth_factor: float = 1.05) -> None:
        self.interval = interval
        self.growth_factor = growth_factor
        self.peak_size = 0
        self.true_peak_size = 0
        self.peak_snapshot: tracemalloc.Snapshot | None = None
        self._next_snapshot_threshold = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _sample(self) -> None:
        current, _peak = tracemalloc.get_traced_memory()
        if current > self.peak_size:
            self.peak_size = current
        if current >= self._next_snapshot_threshold:
            self.peak_snapshot = tracemalloc.take_snapshot()
            self._next_snapshot_threshold = max(current * self.growth_factor, 1)

    def _run(self) -> None:
        while not self._stop.is_set():
            self._sample()
            self._stop.wait(self.interval)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> tracemalloc.Snapshot:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
        current, true_peak = tracemalloc.get_traced_memory()
        self.true_peak_size = true_peak
        if current >= self.peak_size:
            self.peak_size = current
            self.peak_snapshot = tracemalloc.take_snapshot()
        return self.peak_snapshot or tracemalloc.take_snapshot()


def _run_target(target: Path) -> tuple[int | str | None, str | None]:
    """Execute `target` as __main__. Returns (exit_code, error): error is None
    on a clean run or a normal sys.exit(), otherwise a short repr of whatever
    exception the target raised (the partial profile/memory data collected up
    to that point is still reported).
    """
    sys.path.insert(0, str(target.parent.resolve()))
    try:
        runpy.run_path(str(target), run_name="__main__")
    except SystemExit as e:
        return e.code, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    return None, None


def _cpu_worker(target: Path, script_args: list[str], out_path: Path, meta_path: Path) -> None:
    sys.argv = [str(target), *script_args]
    profiler = Profile()
    start = time.perf_counter()
    profiler.enable()
    exit_code, error = _run_target(target)
    profiler.disable()
    elapsed = time.perf_counter() - start
    profiler.dump_stats(str(out_path))
    meta_path.write_text(
        json.dumps({"elapsed": elapsed, "exit_code": exit_code, "error": error}),
        encoding="utf-8",
    )


def _mem_worker(target: Path, script_args: list[str], out_path: Path, meta_path: Path) -> None:
    sys.argv = [str(target), *script_args]
    tracemalloc.start()
    tracker = PeakMemoryTracker()
    tracker.start()
    start = time.perf_counter()
    exit_code, error = _run_target(target)
    elapsed = time.perf_counter() - start
    snapshot = tracker.stop()
    tracemalloc.stop()
    snapshot.dump(str(out_path))
    meta_path.write_text(
        json.dumps({
            "elapsed": elapsed,
            "exit_code": exit_code,
            "error": error,
            "peak_size": tracker.peak_size,
            "true_peak_size": tracker.true_peak_size,
        }),
        encoding="utf-8",
    )


def _spawn_worker(mode: str, target: Path, script_args: list[str], tmp_dir: Path) -> dict:
    out_path = tmp_dir / f"{mode}.out"
    meta_path = tmp_dir / f"{mode}.json"
    subprocess.run(
        [
            sys.executable, str(THIS_FILE),
            "--_worker", mode,
            "--_worker-out", str(out_path),
            "--_worker-meta", str(meta_path),
            str(target), *script_args,
        ],
        check=False,
    )
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["_out_path"] = out_path
    return meta


def run_cpu_pass(target: Path, script_args: list[str], tmp_dir: Path) -> tuple[Stats, dict]:
    meta = _spawn_worker("cpu", target, script_args, tmp_dir)
    return Stats(str(meta["_out_path"])), meta


def run_memory_pass(target: Path, script_args: list[str], tmp_dir: Path) -> tuple[tracemalloc.Snapshot, dict]:
    meta = _spawn_worker("mem", target, script_args, tmp_dir)
    return tracemalloc.Snapshot.load(str(meta["_out_path"])), meta


def top_cpu_stats(stats: Stats, n: int, sort_key: str) -> list[CpuStat]:
    """Pull the top `n` functions out of raw pstats data, sorted by tottime or
    cumtime, excluding profiling-harness scaffolding frames.
    """
    rows = []
    for (filename, lineno, funcname), (_cc, nc, tt, ct, _callers) in stats.stats.items():
        if is_scaffolding(filename, funcname):
            continue
        rows.append(CpuStat(filename=filename, lineno=lineno, funcname=funcname, ncalls=nc, tottime=tt, cumtime=ct))
    key = (lambda r: r.tottime) if sort_key == "tottime" else (lambda r: r.cumtime)
    return sorted(rows, key=key, reverse=True)[:n]


def top_mem_stats(snapshot: tracemalloc.Snapshot, n: int) -> list[MemStat]:
    stats = snapshot.statistics("lineno")[:n]
    return [MemStat(location=str(s.traceback), size_kb=s.size / 1024, count=s.count) for s in stats]


def explain_cpu_stat(stat: CpuStat, total_tottime: float) -> Finding:
    tokens = path_tokens(stat.filename)
    funcname_lower = stat.funcname.lower()

    for needle, explanation, proposal in BLOCKING_HINTS:
        if needle in funcname_lower:
            return Finding(
                title=stat.display,
                metric=f"{stat.tottime:.3f}s elapsed, {stat.ncalls:,} calls",
                explanation=explanation,
                proposal=proposal,
            )

    for needle, explanation, proposal in MODULE_HINTS:
        if needle in tokens:
            return Finding(
                title=stat.display,
                metric=f"{stat.tottime:.3f}s self time, {stat.ncalls:,} calls",
                explanation=explanation,
                proposal=proposal,
            )

    for needle, explanation, proposal in FUNC_HINTS:
        if stat.funcname == needle:
            return Finding(
                title=stat.display,
                metric=f"{stat.tottime:.3f}s self time, {stat.ncalls:,} calls",
                explanation=explanation,
                proposal=proposal,
            )

    if stat.ncalls > CALL_COUNT_THRESHOLD and stat.percall_tot < CALL_COST_THRESHOLD_S:
        return Finding(
            title=stat.display,
            metric=f"{stat.ncalls:,} calls at {stat.percall_tot * 1e6:.2f}µs each",
            explanation="Each call is cheap, but there are so many of them that interpreter/call overhead adds up.",
            proposal="Batch the work (vectorize with NumPy, or restructure the loop to avoid a Python-level call per item) instead of optimizing the function body itself.",
        )

    if stat.cumtime > 0 and stat.self_share < ORCHESTRATOR_SELF_SHARE:
        return Finding(
            title=stat.display,
            metric=f"{stat.cumtime:.3f}s cumulative, only {stat.self_share * 100:.0f}% in itself",
            explanation="This function is mostly a thin wrapper around other calls — the real cost is in its callees.",
            proposal='See the "Top call chains (by cumulative time)" section below for which child call is actually expensive, and optimize that one.',
        )

    share = stat.tottime / total_tottime if total_tottime else 0.0
    return Finding(
        title=stat.display,
        metric=f"{stat.tottime:.3f}s self time ({share * 100:.0f}% of profiled CPU time)",
        explanation="Genuine CPU hot path — time is spent in this function's own code, not delegated to callees.",
        proposal="Look for algorithmic complexity (nested loops, repeated linear scans) first; if the logic is already minimal, consider NumPy vectorization or a native extension.",
    )


def explain_mem_stat(stat: MemStat, total_size_kb: float) -> Finding:
    share = stat.size_kb / total_size_kb if total_size_kb else 0.0
    avg_kb = stat.size_kb / stat.count if stat.count else 0.0

    if stat.count > 1000 and avg_kb < 1:
        explanation = f"Many small objects ({stat.count:,} allocations, ~{avg_kb * 1024:.0f} bytes each)."
        proposal = "Add __slots__ to the class involved, or restructure as a generator/stream instead of materializing every object at once."
    elif stat.count < 50 and stat.size_kb > 1024:
        explanation = f"A few very large allocations ({stat.count} allocations, {stat.size_kb / 1024:.1f} MB total)."
        proposal = "Check whether the full dataset needs to be resident at once; consider chunking, generators, or streaming I/O instead."
    else:
        explanation = f"{stat.count:,} allocations averaging ~{avg_kb:.1f} KB each."
        proposal = "Confirm these objects are actually needed for the full run — a shorter-lived scope or explicit del may let the GC reclaim sooner."

    return Finding(
        title=stat.location,
        metric=f"{stat.size_kb / 1024:.2f} MB ({share * 100:.0f}% of traced memory)",
        explanation=explanation,
        proposal=proposal,
    )


def peak_child_rss_mb() -> float | None:
    """Peak RSS of the profiled subprocesses (not this orchestrator script)."""
    if not HAS_RESOURCE:
        return None
    ru_maxrss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    # macOS reports bytes, Linux reports KiB.
    return ru_maxrss / (1024 * 1024) if sys.platform == "darwin" else ru_maxrss / 1024


def _status_line(meta: dict) -> str:
    if meta.get("error"):
        return f"target raised {meta['error']} (partial data below)"
    exit_code = meta.get("exit_code")
    return "ok" if exit_code in (None, 0) else f"exit code {exit_code}"


def render_report(
    target: Path,
    script_args: list[str],
    cpu_meta: dict,
    mem_meta: dict,
    cpu_by_tottime: list[CpuStat],
    cpu_by_cumtime: list[CpuStat],
    mem_stats: list[MemStat],
    total_tottime_all: float,
    total_mem_kb: float,
    total_calls: int,
) -> str:
    peak_rss = peak_child_rss_mb()

    lines = [
        f"# Performance report: {target.name}",
        "",
        f"- Command: `{target} {' '.join(script_args)}`".rstrip(),
        "- The target ran twice, once per profiler, each in a fresh subprocess — this keeps",
        "  cProfile, tracemalloc, and the memory-peak sampler thread from interfering with",
        "  each other, and avoids the second pass silently skipping import-time cost because",
        "  the first pass already cached the imports. If the script has side effects, expect",
        "  them twice.",
        f"- Wall time (cProfile pass): {cpu_meta['elapsed']:.3f}s",
        f"- Wall time (tracemalloc pass): {mem_meta['elapsed']:.3f}s",
        f"- CPU pass status: {_status_line(cpu_meta)}",
        f"- Memory pass status: {_status_line(mem_meta)}",
        f"- Total profiled calls: {total_calls:,}",
        f"- Peak RSS of the profiled process: {f'{peak_rss:.1f} MB' if peak_rss is not None else 'unavailable on this platform'}",
        f"- Peak traced Python memory (tracemalloc): {mem_meta['true_peak_size'] / (1024 * 1024):.1f} MB",
        "",
        "Heuristic report — each finding is generated from thresholds on the actual",
        "profile data, not a verdict. Verify before acting on it.",
        "",
        "## Top CPU hotspots (by self time)",
        "",
        "| # | Function | Self time / calls | What's likely going on | Proposal |",
        "|---|----------|--------------------|-----------------------|----------|",
    ]
    for i, stat in enumerate(cpu_by_tottime, 1):
        f = explain_cpu_stat(stat, total_tottime_all)
        lines.append(f"| {i} | `{escape_md(f.title)}` | {escape_md(f.metric)} | {escape_md(f.explanation)} | {escape_md(f.proposal)} |")

    lines += [
        "",
        "## Top call chains (by cumulative time)",
        "",
        "Cumulative time includes time spent in callees — use this to find *where*",
        "in the call tree the cost enters, then cross-reference the self-time table above.",
        "",
        "| # | Function | Cumulative time | Self-time share |",
        "|---|----------|------------------|------------------|",
    ]
    for i, stat in enumerate(cpu_by_cumtime, 1):
        lines.append(f"| {i} | `{escape_md(stat.display)}` | {stat.cumtime:.3f}s | {stat.self_share * 100:.0f}% |")

    lines += [
        "",
        "## Top memory allocation sites",
        "",
        "Attribution comes from a snapshot taken within ~5% of peak traced memory (see",
        "`PeakMemoryTracker`), not the exact peak instant — sizes may undercount slightly",
        "relative to the peak figure above.",
        "",
        "| # | Location | Size | What's likely going on | Proposal |",
        "|---|----------|------|-------------------------|----------|",
    ]
    if mem_stats:
        for i, stat in enumerate(mem_stats, 1):
            f = explain_mem_stat(stat, total_mem_kb)
            lines.append(f"| {i} | `{escape_md(f.title)}` | {escape_md(f.metric)} | {escape_md(f.explanation)} | {escape_md(f.proposal)} |")
    else:
        lines.append("| - | - | - | No allocations captured by tracemalloc | - |")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", type=Path, help="Python script to profile")
    parser.add_argument("script_args", nargs=argparse.REMAINDER, help="Arguments passed through to the target script")
    parser.add_argument("--output", type=Path, default=None, help="Report path (default: <target>.report.md)")
    parser.add_argument("--top", type=int, default=10, help="Number of hotspots to report per section (default: 10)")
    # Internal flags used to re-invoke this script as a profiling worker subprocess.
    parser.add_argument("--_worker", choices=("cpu", "mem"), default=None, help=argparse.SUPPRESS)
    parser.add_argument("--_worker-out", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--_worker-meta", type=Path, default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if not args.target.exists():
        parser.error(f"target script not found: {args.target}")

    if args._worker == "cpu":
        _cpu_worker(args.target, args.script_args, args._worker_out, args._worker_meta)
        return
    if args._worker == "mem":
        _mem_worker(args.target, args.script_args, args._worker_out, args._worker_meta)
        return

    with tempfile.TemporaryDirectory(prefix="profile_report_") as tmp:
        tmp_dir = Path(tmp)
        stats, cpu_meta = run_cpu_pass(args.target, args.script_args, tmp_dir)
        snapshot, mem_meta = run_memory_pass(args.target, args.script_args, tmp_dir)

        total_calls = sum(nc for (_cc, nc, _tt, _ct, _callers) in stats.stats.values())
        total_tottime_all = sum(tt for (_cc, _nc, tt, _ct, _callers) in stats.stats.values())
        total_mem_kb = mem_meta["true_peak_size"] / 1024

        report = render_report(
            target=args.target,
            script_args=args.script_args,
            cpu_meta=cpu_meta,
            mem_meta=mem_meta,
            cpu_by_tottime=top_cpu_stats(stats, args.top, "tottime"),
            cpu_by_cumtime=top_cpu_stats(stats, args.top, "cumtime"),
            mem_stats=top_mem_stats(snapshot, args.top),
            total_tottime_all=total_tottime_all,
            total_mem_kb=total_mem_kb,
            total_calls=total_calls,
        )

    output = args.output or args.target.with_suffix(".report.md")
    output.write_text(report, encoding="utf-8")
    print(f"Report written to {output}")


if __name__ == "__main__":
    main()
