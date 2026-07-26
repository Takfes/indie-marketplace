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

Two stdlib-only scripts turn profiling from manual pstats-reading into a report or
a live view, no third-party dependencies required.

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
