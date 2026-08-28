# Deep-Module Vocabulary

Harvested from `mattpocock/codebase-design` (`https://github.com/mattpocock/skills`,
`skills/engineering/codebase-design`) -- glossary, the deletion test, and the two principles
this skill applies directly. Everything else in that skill (deepening a cluster, designing an
interface twice via parallel sub-agents, `CONTEXT.md`/ADR integration) is out of scope for this
harvest -- see `python-architecture/SKILL.md`'s Explicit boundaries for why.

## Glossary

Use these terms exactly -- don't substitute "component," "service," "API," or "boundary."

- **Module** -- anything with an interface and an implementation. Deliberately scale-agnostic: a
  function, class, package, or tier-spanning slice. *Avoid*: unit, component, service.
- **Interface** -- everything a caller must know to use the module correctly: the type
  signature, but also invariants, ordering constraints, error modes, required configuration, and
  performance characteristics. *Avoid*: API, signature (too narrow -- these refer only to the
  type-level surface).
- **Implementation** -- what's inside a module, its body of code. Distinct from **Adapter**: a
  thing can be a small adapter with a large implementation (a Postgres repo) or a large adapter
  with a small implementation (an in-memory fake). Reach for "adapter" when the seam is the
  topic, "implementation" otherwise.
- **Depth** -- leverage at the interface: the amount of behaviour a caller (or test) can exercise
  per unit of interface they have to learn. A module is **deep** when a large amount of
  behaviour sits behind a small interface, **shallow** when the interface is nearly as complex
  as the implementation.
- **Seam** *(Michael Feathers)* -- a place where you can alter behaviour without editing in that
  place; the *location* at which a module's interface lives. Where to put the seam is its own
  design decision, distinct from what goes behind it. *Avoid*: boundary (overloaded with DDD's
  bounded context).
- **Adapter** -- a concrete thing that satisfies an interface at a seam. Describes *role* (what
  slot it fills), not substance (what's inside).
- **Leverage** -- what callers get from depth: more capability per unit of interface they learn.
  One implementation pays back across N call sites and M tests.
- **Locality** -- what maintainers get from depth: change, bugs, knowledge, and verification
  concentrate in one place rather than spreading across callers. Fix once, fixed everywhere.

## Deep vs. shallow

**Deep module** = small interface + lots of implementation:

```
+---------------------+
|   Small Interface   |  <- Few methods, simple params
+---------------------+
|                      |
|  Deep Implementation |  <- Complex logic hidden
|                      |
+----------------------+
```

**Shallow module** = large interface + little implementation (avoid):

```
+-----------------------------------+
|          Large Interface          |  <- Many methods, complex params
+------------------------------------+
|  Thin Implementation              |  <- Just passes through
+------------------------------------+
```

## The three principles this skill applies

- **The deletion test.** Imagine deleting the module. If complexity vanishes, it was a
  pass-through -- shallow, cut it. If complexity reappears across N callers, it was earning its
  keep -- deep, keep it.
- **The interface is the test surface.** Callers and tests cross the same seam. If you want to
  test *past* the interface, the module is probably the wrong shape.
- **One adapter means a hypothetical seam. Two adapters means a real one.** Don't credit a seam
  as load-bearing unless something actually varies across it today.

## Rejected framings (carried over from the source)

- **Depth as ratio of implementation-lines to interface-lines** (Ousterhout): rewards padding
  the implementation. Use depth-as-leverage instead.
- **"Interface" as a language keyword or a class's public methods**: too narrow -- interface
  here includes every fact a caller must know.
- **"Boundary"**: overloaded with DDD's bounded context. Say **seam** or **interface**.
