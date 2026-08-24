# python-performance-optimization — modern tooling (2026)

The core patterns in `details.md` and `advanced-patterns.md` (cProfile, line_profiler,
memory_profiler, py-spy) still work, but the tooling landscape has moved on. This file
covers what to reach for now, plus two language-level changes (PEP 669, free-threading)
that affect *how* you profile and parallelize on current Python.

`memory_profiler` (Pattern 3 in `details.md`) is effectively unmaintained — prefer the
stdlib `tracemalloc` or `memray` below for anything beyond a quick line-by-line sanity check.

## Choosing a profiler

| Tool | Best for | Overhead | Code changes | Output |
|------|----------|----------|---------------|--------|
| `cProfile` | Deterministic CPU profiling in dev | Medium-high | None | pstats / snakeviz |
| `line_profiler` | Line-level CPU detail on a known-slow function | High | `@profile` decorator | Per-line table |
| **Scalene** | CPU *and* memory, line-level, one command | Low (sampling) | None | Terminal + HTML |
| **memray** | Memory allocations, flame graphs, leak hunting | Low-medium | None | Flame graph / table |
| **viztracer** | Timelines for async/threaded code, call sequencing | Low-medium | None | Chrome-trace JSON (vizviewer) |
| **austin** | Zero-overhead-ish sampling, attach to a running PID | Very low | None | speedscope / flamegraph |
| `py-spy` | Production processes you can't restart or modify | Very low | None | top / flamegraph / dump |

Typical investigation order: py-spy or Scalene first to find the hot path with near-zero
setup cost, then line_profiler on the specific function once you know where to look.

### Pattern 21: Scalene — combined CPU + GPU + memory profiler

```bash
# Install: pip install scalene

# Profile a script — opens an interactive HTML report by default
scalene my_script.py

# CPU only, plain text in the terminal
scalene --cpu --cli my_script.py

# Memory only
scalene --memory --cli my_script.py
```

Scalene attributes time to Python code vs. native code vs. system calls *per line*,
and separately reports memory copy volume — useful for spotting hidden C-extension
costs (e.g. pandas operations) that cProfile just lumps into one opaque call.

### Pattern 22: memray — memory profiler with flame graphs

```bash
# Install: pip install memray

# Record allocations
memray run -o output.bin my_script.py

# Turn the recording into a flame graph (HTML)
memray flamegraph output.bin

# Watch allocations live, like top but for memory
memray run --live my_script.py
```

Reaches for actual C-level allocators, so it also sees memory used by native
extensions (NumPy, pandas, etc.) that `tracemalloc` — which only tracks
Python-level allocations — cannot.

### Pattern 23: viztracer — timelines for async and threaded code

```bash
# Install: pip install viztracer

viztracer my_script.py     # writes result.json
vizviewer result.json      # opens an interactive timeline in the browser
```

cProfile and Scalene report aggregate time per function; they don't show *when*
things happened relative to each other. For a program with threads, asyncio
tasks, or multiprocessing workers, a timeline is what actually reveals
contention (e.g. every worker blocked waiting on the same lock at once).

### Pattern 24: austin — zero-code sampling profiler

```bash
# Install: pip install austin-python (or the standalone austin binary)

# Profile a script
austin -i 1ms -o profile.austin python my_script.py

# Attach to a running production process (needs appropriate permissions)
austin -p 12345

# Convert to speedscope format for interactive flame graphs at speedscope.app
austin2speedscope profile.austin profile.speedscope.json
```

Like py-spy, austin samples from outside the process, so it doesn't need
`@profile` decorators or any modification of the target — good for a process
already running in production.

### Pattern 25: sys.monitoring (PEP 669) — low-overhead custom instrumentation

Python 3.12 added `sys.monitoring`, a events API purpose-built for profilers and
debuggers. Unlike `sys.settrace` (which pays a cost for every line/call whether
or not anything is watching), you subscribe to only the events you need, so
tools built on it run close to full speed until something actually fires.
Debuggers rebuilt on it have measured multi-x speedups over `sys.settrace`
equivalents. Most people won't hand-roll this — Scalene, py-spy and friends are
already adopting it — but it's worth knowing about if you're building custom
instrumentation into a hot service rather than using an off-the-shelf profiler:

```python
import sys

CALL_COUNTER = sys.monitoring.PROFILER_ID  # or any free tool ID (0-5)
sys.monitoring.use_tool_id(CALL_COUNTER, "call-counter")

counts: dict[str, int] = {}

def on_call(code, instruction_offset, callable_, arg0):
    # `code` is the *caller's* code object; key on `callable_` to count callees.
    name = getattr(callable_, "__qualname__", repr(callable_))
    counts[name] = counts.get(name, 0) + 1

sys.monitoring.register_callback(CALL_COUNTER, sys.monitoring.events.CALL, on_call)
sys.monitoring.set_events(CALL_COUNTER, sys.monitoring.events.CALL)

# ... run the code you want to watch ...

sys.monitoring.set_events(CALL_COUNTER, sys.monitoring.events.NO_EVENTS)
sys.monitoring.free_tool_id(CALL_COUNTER)
```

### Pattern 26: Profiling asyncio code

The usual profilers show *which function* is slow; asyncio bugs are usually
about *what's blocking the event loop*, which is a different question.

```python
import asyncio

async def main():
    # Warn whenever a callback/coroutine step blocks the loop for too long.
    # Must be set on the running loop — asyncio.get_event_loop() outside a
    # running loop is deprecated and raises on current Python versions.
    loop = asyncio.get_running_loop()
    loop.slow_callback_duration = 0.1  # seconds

    ...

asyncio.run(main())

# Run with PYTHONASYNCIODEBUG=1 for extra loop-level diagnostics, e.g.:
#   PYTHONASYNCIODEBUG=1 python my_script.py
```

The most common asyncio performance bug is a synchronous, blocking call
(`requests.get`, a CPU-heavy loop, blocking file I/O) sitting inside an `async
def` — it doesn't raise an error, it just stalls every other task on the loop
for its duration. `viztracer` (Pattern 23) is the most direct way to *see* this:
the timeline shows one task's bar overlapping and blocking all the others
instead of them interleaving.

### Pattern 27: Free-threaded Python (3.13+) and the GIL

Since 3.13, CPython has an optional free-threaded build (`python3.13t`) with the
GIL disabled, stabilizing further in 3.14. This changes the calculus for
Pattern 14 (multiprocessing) and threading:

- **CPU-bound, multi-threaded workloads**: free-threaded builds have shown up
  to ~8x throughput gains over the GIL build, since threads can now run Python
  bytecode truly in parallel — multiprocessing's process-per-core workaround
  may no longer be necessary for new projects.
- **Single-threaded cost**: free-threaded builds carry a real single-thread
  penalty — around 40% slower on 3.13t, narrowing to roughly 5-10% on 3.14t as
  the implementation matures. Don't switch a mostly-single-threaded service to
  a `t` build without measuring.
- **Compatibility**: C extensions need to explicitly declare free-threading
  support; an extension that hasn't opted in silently re-enables the GIL for
  the whole process, silently erasing the expected parallelism. Check
  `sys._is_gil_enabled()` at runtime to confirm what you're actually getting.
- **Practical guidance**: if a CPU-bound hot path is a good multiprocessing
  candidate today because of the GIL, it's worth re-benchmarking on a
  free-threaded build before adding process-pool complexity — threading may
  now be enough, with no IPC/pickling overhead.

### Pattern 28: Import-time profiling for slow startup

A common real-world complaint ("this CLI feels slow") is import time, not
runtime — invisible to cProfile because it happens before `main()` even starts.

```bash
python -X importtime my_script.py 2> importtime.log

# Sort by cumulative time to find the heaviest import chain
sort -t'|' -k2 -n -r importtime.log | head -20
```
