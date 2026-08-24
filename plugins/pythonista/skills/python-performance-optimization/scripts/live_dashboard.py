#!/usr/bin/env python3
"""Live terminal dashboard: watch memory and CPU while a command runs.

Spawns the given command as a subprocess, samples its RSS memory and CPU%
via `ps` at a fixed interval, and redraws an in-terminal dashboard (elapsed
time, current CPU/memory, a memory sparkline) until the process exits. Prints
a summary afterwards and can optionally dump the raw samples as JSON.

The child's own stdout/stderr are redirected to a file so they don't tear up
the redrawing dashboard; the file's path is printed in the summary. When
stdout isn't a terminal (e.g. piped or captured), the dashboard falls back to
one plain line per sample instead of redrawing with ANSI escapes.

Usage:
    python scripts/live_dashboard.py -- python my_script.py --arg value
    python scripts/live_dashboard.py --interval 0.2 --log samples.json -- python my_script.py

Stdlib only — no third-party dependencies required. Relies on the `ps`
command, so it works on macOS/Linux; there is no Windows support. Only the
command's direct process is sampled — child processes it spawns itself
(multiprocessing workers, `sh -c ...`) aren't included.

CPU% comes straight from `ps -o pcpu`, which is not an instantaneous reading:
on macOS it's a decayed recent average, on Linux it's averaged over the
process's entire lifetime so far. Treat it as directional, not exact.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path

SPARK_CHARS = "▁▂▃▄▅▆▇█"
IS_TTY = sys.stdout.isatty()


@dataclass
class Sample:
    elapsed_s: float
    rss_kb: float
    cpu_pct: float


def sample_process(pid: int) -> Sample | None:
    """Read RSS (KB) and CPU% for `pid` via `ps`. Returns None once the process is gone."""
    try:
        result = subprocess.run(
            ["ps", "-o", "rss=,pcpu=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    line = result.stdout.strip()
    if not line:
        return None
    parts = line.split()
    if len(parts) < 2:
        return None
    rss_kb, cpu_pct = float(parts[0]), float(parts[1])
    return Sample(elapsed_s=0.0, rss_kb=rss_kb, cpu_pct=cpu_pct)


def sparkline(values: deque[float], width: int) -> str:
    if not values:
        return ""
    vals = list(values)[-width:]
    lo, hi = min(vals), max(vals)
    span = hi - lo or 1.0
    scale = len(SPARK_CHARS) - 1
    return "".join(SPARK_CHARS[min(scale, int((v - lo) / span * scale))] for v in vals)


def render(elapsed: float, sample: Sample, history: deque[float], command: list[str], last_line_count: int) -> int:
    if not IS_TTY:
        print(f"[{elapsed:7.1f}s] CPU (ps avg) {sample.cpu_pct:5.1f}%  Memory {sample.rss_kb / 1024:8.1f} MB")
        return 0

    cols = shutil.get_terminal_size((80, 24)).columns
    width = max(10, min(60, cols - 20))
    lines = [
        f"Live dashboard — {' '.join(command)}"[:cols],
        "-" * min(cols, 70),
        f"Elapsed:      {elapsed:8.1f}s",
        f"CPU (ps avg): {sample.cpu_pct:7.1f}%",
        f"Memory:       {sample.rss_kb / 1024:8.1f} MB (RSS)",
        f"Mem trend:    {sparkline(history, width)}",
    ]
    if last_line_count:
        sys.stdout.write(f"\x1b[{last_line_count}F")
    for line in lines:
        sys.stdout.write("\x1b[K" + line + "\n")
    sys.stdout.flush()
    return len(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--interval", type=float, default=0.5, help="Sampling interval in seconds (default: 0.5)")
    parser.add_argument("--log", type=Path, default=None, help="Write sampled JSON to this path")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run, e.g. -- python script.py")
    args = parser.parse_args()

    if args.interval <= 0:
        parser.error("--interval must be greater than 0")

    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("no command given; usage: live_dashboard.py -- python script.py")

    fd, child_output_path = tempfile.mkstemp(prefix="live_dashboard_", suffix=".log")
    child_output = Path(child_output_path)
    start = time.perf_counter()
    history: deque[float] = deque(maxlen=200)
    samples: list[Sample] = []

    with os.fdopen(fd, "w") as output_file:
        try:
            proc = subprocess.Popen(command, stdout=output_file, stderr=subprocess.STDOUT)
        except OSError as e:
            print(f"Error: couldn't start command {command!r}: {e}", file=sys.stderr)
            sys.exit(1)

        last_line_count = 0
        try:
            while True:
                sample = sample_process(proc.pid)
                elapsed = time.perf_counter() - start
                if sample is not None:
                    sample.elapsed_s = elapsed
                    history.append(sample.rss_kb)
                    samples.append(sample)
                    last_line_count = render(elapsed, sample, history, command, last_line_count)
                try:
                    proc.wait(timeout=args.interval)
                    break
                except subprocess.TimeoutExpired:
                    continue
        except KeyboardInterrupt:
            proc.terminate()
            proc.wait()

    elapsed = time.perf_counter() - start

    if samples:
        peak_rss_mb = max(s.rss_kb for s in samples) / 1024
        avg_cpu = sum(s.cpu_pct for s in samples) / len(samples)
    else:
        peak_rss_mb = avg_cpu = 0.0

    print("\n--- Summary ---")
    print(f"Command:      {' '.join(command)}")
    print(f"Exit code:    {proc.returncode}")
    print(f"Wall time:    {elapsed:.2f}s")
    if samples:
        print(f"Peak memory:  {peak_rss_mb:.1f} MB (sampled every {args.interval}s — short spikes may be missed)")
        print(f"Avg CPU:      {avg_cpu:.1f}% (mean of ps's own averages, not a true time-weighted average)")
    else:
        print("No samples captured — the process may have exited before the first sample; try a smaller --interval.")
    print(f"Child output: {child_output}")

    if args.log:
        args.log.write_text(json.dumps([asdict(s) for s in samples], indent=2), encoding="utf-8")
        print(f"Samples:      {args.log}")

    exit_code = proc.returncode
    sys.exit(128 - exit_code if exit_code < 0 else exit_code)


if __name__ == "__main__":
    main()
