---
name: python-performance-optimization
description: Profile and optimize Python code using cProfile, tracemalloc, and modern tools (Scalene, memray, py-spy, viztracer), including generating an automated hotspot report and a live CPU/memory dashboard. Use when debugging slow Python code, optimizing bottlenecks, tracking memory/CPU while a script runs, or improving application performance.
---

# Python Performance Optimization

Comprehensive guide to profiling, analyzing, and optimizing Python code for better performance, including CPU profiling, memory optimization, and implementation best practices.

## When to Use This Skill

- Identifying performance bottlenecks in Python applications
- Reducing application latency and response times
- Optimizing CPU-intensive operations
- Reducing memory consumption and memory leaks
- Improving database query performance
- Optimizing I/O operations
- Speeding up data processing pipelines
- Implementing high-performance algorithms
- Profiling production applications

## Core Concepts

### 1. Profiling Types

- **CPU Profiling**: Identify time-consuming functions
- **Memory Profiling**: Track memory allocation and leaks
- **Line Profiling**: Profile at line-by-line granularity
- **Call Graph**: Visualize function call relationships

### 2. Performance Metrics

- **Execution Time**: How long operations take
- **Memory Usage**: Peak and average memory consumption
- **CPU Utilization**: Processor usage patterns
- **I/O Wait**: Time spent on I/O operations

### 3. Optimization Strategies

- **Algorithmic**: Better algorithms and data structures
- **Implementation**: More efficient code patterns
- **Parallelization**: Multi-threading/processing
- **Caching**: Avoid redundant computation
- **Native Extensions**: C/Rust for critical paths

## Workflow: Baseline -> Prove -> Profile -> Propose -> Approve -> Optimize -> Compare

This skill's discipline: never edit code to make it "faster" without evidence a real bottleneck
exists, and never past the approval gate without the user seeing the specific proposal first.

### 1. Baseline

Before touching anything, measure how the target performs today. Run it under
`scripts/profile_report.py` (or a `timeit` measurement, for a single expression) against
representative input, and record the number — this is what "improved" gets measured against
later, not a guess.

### 2. Prove there's a problem

The baseline must show a *named* bottleneck — a specific function, line, or allocation, not a
general feeling that something is slow. If profiling doesn't surface a hotspot proportionate to
the effort of optimizing, **stop here and say so**. Refusing to invent a problem to justify
optimizing is the point of this step, not a formality.

### 3. Profile

With a real problem confirmed, profile it in enough depth to name the exact hot path — pick the
tool from "Choosing a Profiler" below that answers the specific question (CPU vs. memory, dev vs.
production, function-level vs. line-level).

### 4. Propose

Write a short proposal before writing any code: what will change, which strategy from Best
Practices it draws on, and the expected win — referencing the exact function(s)/line(s) the
profile named. No edits yet.

### 5. Approve — hard gate

Wait for explicit approval of the step-4 proposal before changing anything. This is the enforced
gate this skill was missing: never optimize without first showing baseline evidence and getting
the specific change approved, not a general "go ahead."

### 6. Optimize

Apply exactly what was approved, one change at a time. No drive-by changes beyond the approved
proposal, and no "while I'm in here" cleanup — that's `python-patterns`'/`python-refactor`'s job,
not this skill's.

### 7. Re-benchmark

Re-run the same baseline measurement — same input, same conditions — against the optimized code.

### 8. Compare

Run `scripts/compare_benchmarks.py <baseline_file> <optimized_file> <bench_data_module>` to
quantify the win against a regression threshold (default 10%). Report the before/after numbers
and the verdict plainly, including a regression if the "optimization" made things worse. If no
test suite exists to confirm the optimized code is still correct, say so explicitly rather than
claiming behavior is unchanged.

## Quick Start

### Basic Timing

```python
import time

def measure_time():
    """Simple timing measurement."""
    start = time.perf_counter()  # monotonic, high-resolution — not time.time()

    # Your code here
    result = sum(range(1000000))

    elapsed = time.perf_counter() - start
    print(f"Execution time: {elapsed:.4f} seconds")
    return result

# Better: use timeit for accurate measurements
import timeit

execution_time = timeit.timeit(
    "sum(range(1000000))",
    number=100
)
print(f"Average time: {execution_time/100:.6f} seconds")
```

## Analysis Scripts

Three stdlib-only scripts turn profiling from manual pstats-reading into a report, a live
view, or a before/after verdict — no third-party dependencies required.

```bash
# Run a script under cProfile + tracemalloc and get a Markdown report of the
# top CPU and memory hotspots, each with a brief explanation and a proposal.
# Flags must come before the target — everything after it is passed through
# to the target script.
python scripts/profile_report.py --top 10 --output report.md my_script.py [script_args...]

# Watch memory/CPU/elapsed time update live while a command runs. Works for
# any command, not just Python. The wrapped command's own output is
# redirected to a log file (path printed at the end) so it doesn't tear up
# the redrawing dashboard.
python scripts/live_dashboard.py --interval 0.5 --log samples.json -- python my_script.py [args...]

# Workflow step 8 (Compare): time the same function(s) in a baseline file and
# an optimized file, using a companion module for each function's test input,
# and flag a regression past the threshold.
python scripts/compare_benchmarks.py baseline.py optimized.py bench_data.py --threshold 10
```

`profile_report.py` runs the target twice — once under cProfile, once under
tracemalloc with a peak-tracking sampler — because interleaving both in one
pass would have each pollute the other's numbers (a concurrent sampler thread
shows up in cProfile's own stats as if it were part of the program). If the
target has side effects, expect them twice.

## Choosing a Profiler

| Question | Reach for |
|---|---|
| "Where does the CPU time go, in dev?" | `cProfile` (Pattern 1) or `scripts/profile_report.py` |
| "Which exact line is slow?" | `line_profiler` (Pattern 2) |
| "CPU *and* memory, one command, low overhead?" | Scalene (`references/modern-tools.md`) |
| "Where did this memory go?" | `tracemalloc` (Pattern 18) or memray (`references/modern-tools.md`) |
| "What's happening on a live production process?" | `py-spy` (Pattern 4) or austin (`references/modern-tools.md`) |
| "Why are my threads/async tasks stepping on each other?" | viztracer (`references/modern-tools.md`) |
| "Is memory/CPU trending up while it runs?" | `scripts/live_dashboard.py` |

## Detailed patterns and worked examples

Detailed pattern documentation lives in `references/details.md` and
`references/advanced-patterns.md`. For newer tooling (Scalene, memray,
viztracer, austin, `sys.monitoring`/PEP 669, free-threaded Python 3.13+, async
profiling), see `references/modern-tools.md`. Read these when the navigation
tier above is insufficient.

## Best Practices

1. **Profile before optimizing** - Measure to find real bottlenecks
2. **Focus on hot paths** - Optimize code that runs most frequently
3. **Use appropriate data structures** - Dict for lookups, set for membership
4. **Avoid premature optimization** - Clarity first, then optimize
5. **Use built-in functions** - They're implemented in C
6. **Cache expensive computations** - Use lru_cache
7. **Batch I/O operations** - Reduce system calls
8. **Use generators** for large datasets
9. **Consider NumPy** for numerical operations
10. **Profile production code** - Use py-spy for live systems
11. **Read self time, not just cumulative time** - cumulative time tells you which call chain is expensive; self (tot) time tells you which function is actually doing the work
12. **Match profiler overhead to the question** - sampling profilers (py-spy, Scalene, austin) for production or "just show me the shape"; deterministic profilers (cProfile) when you need exact call counts in dev

## Common Pitfalls

- Optimizing without profiling
- Using global variables unnecessarily
- Not using appropriate data structures
- Creating unnecessary copies of data
- Not using connection pooling for databases
- Ignoring algorithmic complexity
- Over-optimizing rare code paths
- Not considering memory usage
- Reading `time.sleep()` or lock waits in a cProfile report as if they were CPU cost — cProfile measures wall time, so blocking calls inflate self time without using any CPU
- Taking a single memory snapshot at the end of a run — anything allocated and freed mid-run (a large intermediate list, a batch that's since been GC'd) is invisible unless you sample or diff snapshots over the run

## Script Reference

| Script | What it does |
|--------|-----------------|
| `profile_report.py` | Runs a target script under cProfile + tracemalloc, produces a Markdown report of top CPU/memory hotspots with a rule-based explanation and proposal for each |
| `live_dashboard.py` | Spawns a command, samples its RSS memory and CPU% via `ps`, redraws a live terminal dashboard with a memory sparkline, prints a summary on exit |
| `compare_benchmarks.py` | Workflow step 8: times matching functions in a baseline file and an optimized file via a companion bench-data module, reports before/after and flags a regression past a threshold. Ported from `python-refactor`'s `benchmark_changes.py` |

## Self-check

`fixtures/` holds a small, deliberately inefficient script plus a before/after
function pair, so you can run all three scripts end to end and see for
yourself what a real hotspot report, live dashboard, and benchmark comparison
look like — before pointing them at real code. Run these from this skill's
directory (`plugins/pythonista/skills/python-performance-optimization/`).

**1. `profile_report.py` — hotspot attribution**

```bash
python3 scripts/profile_report.py --top 5 --output report.md fixtures/hotspot_demo.py
```

(Flags must come before the target — see the script's own usage note.)

Expect a Markdown report (`report.md`) whose "Top CPU hotspots" table ranks
`find_duplicates_slow` first, attributing roughly 70-80% of self time to it
(its `O(n^2)` nested loop dominates), with `time.sleep` correctly flagged as a
wall-clock wait rather than CPU cost. The "Top memory allocation sites" table
should list a line inside `build_dataset_slow` (the list-of-dicts
comprehension) as the largest allocation site. Exact percentages vary by
machine — the ranking and the wall-clock-wait callout should not.

**2. `live_dashboard.py` — live CPU/memory dashboard**

```bash
python3 scripts/live_dashboard.py --interval 0.3 -- python3 fixtures/hotspot_demo.py
```

Run this one in an actual terminal (not piped/captured) to see the
in-place-redrawing ANSI dashboard and memory sparkline; piped output falls
back to one plain sample line per interval instead. Expect CPU to climb
toward ~85-99% while `find_duplicates_slow` runs (the first 1.5-2s), then
drop off as it finishes. `build_dataset_slow`'s allocation is real (tens of
MB) but completes in well under 100ms, so whether the 0.3s sampler catches a
visible RSS jump in the last sample or two is timing-dependent — on a fast
machine it's common to see peak RSS stay in the 10-50MB range across
identical runs rather than a single, reliable jump. Treat a clear CPU-high
phase followed by process exit as the pass condition; a caught memory spike
is a bonus, not a requirement. Pass `--log samples.json` to get the exact
per-sample RSS/CPU trace if the live view is inconclusive.

**3. `compare_benchmarks.py` — before/after verdict**

```bash
python3 scripts/compare_benchmarks.py fixtures/baseline_funcs.py fixtures/optimized_funcs.py fixtures/bench_data.py --number 50 --repeat 3
```

Expect `find_duplicates` (the `O(n^2)` -> `set`-based rewrite) to report as
dramatically faster, typically 95%+ faster / >10x, and `join_lines` (repeated
string concatenation -> `str.join`) as modestly faster, typically 10-20%.
Summary should read "Faster: 2", "Regressions: 0".
