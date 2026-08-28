---
name: python-packaging
description: Create distributable Python packages with proper project structure, setup.py/pyproject.toml, and publishing to PyPI -- plus CLI surface design (argument ergonomics: positionals vs. options, subcommands, exit codes, output format), not just entry-point wiring. Use when packaging Python libraries, designing or building CLI tools, or distributing Python code.
---

# Python Packaging

Comprehensive guide to creating, structuring, and distributing Python packages using modern packaging tools, pyproject.toml, and publishing to PyPI.

## When to Use This Skill

- Creating Python libraries for distribution
- Building command-line tools with entry points
- Publishing packages to PyPI or private repositories
- Setting up Python project structure
- Creating installable packages with dependencies
- Building wheels and source distributions
- Versioning and releasing Python packages
- Creating namespace packages
- Implementing package metadata and classifiers

## Core Concepts

### 1. Package Structure

- **Source layout**: `src/package_name/` (recommended)
- **Flat layout**: `package_name/` (simpler but less flexible)
- **Package metadata**: pyproject.toml, setup.py, or setup.cfg
- **Distribution formats**: wheel (.whl) and source distribution (.tar.gz)

### 2. Modern Packaging Standards

- **PEP 517/518**: Build system requirements
- **PEP 621**: Metadata in pyproject.toml
- **PEP 660**: Editable installs
- **pyproject.toml**: Single source of configuration

### 3. Build Backends

- **setuptools**: Traditional, widely used
- **hatchling**: Modern, opinionated
- **flit**: Lightweight, for pure Python
- **poetry**: Dependency management + packaging

### 4. Distribution

- **PyPI**: Python Package Index (public)
- **TestPyPI**: Testing before production
- **Private repositories**: JFrog, AWS CodeArtifact, etc.

## Quick Start

### Minimal Package Structure

```
my-package/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── my_package/
│       ├── __init__.py
│       └── module.py
└── tests/
    └── test_module.py
```

### Minimal pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "my-package"
version = "0.1.0"
description = "A short description"
authors = [{name = "Your Name", email = "you@example.com"}]
readme = "README.md"
requires-python = ">=3.8"
dependencies = [
    "requests>=2.28.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "black>=22.0",
]
```

## Package Structure Patterns

### Pattern 1: Source Layout (Recommended)

```
my-package/
├── pyproject.toml
├── README.md
├── LICENSE
├── .gitignore
├── src/
│   └── my_package/
│       ├── __init__.py
│       ├── core.py
│       ├── utils.py
│       └── py.typed          # For type hints
├── tests/
│   ├── __init__.py
│   ├── test_core.py
│   └── test_utils.py
└── docs/
    └── index.md
```

**Advantages:**

- Prevents accidentally importing from source
- Cleaner test imports
- Better isolation

**pyproject.toml for source layout:**

```toml
[tool.setuptools.packages.find]
where = ["src"]
```

### Pattern 2: Flat Layout

```
my-package/
├── pyproject.toml
├── README.md
├── my_package/
│   ├── __init__.py
│   └── module.py
└── tests/
    └── test_module.py
```

**Simpler but:**

- Can import package without installing
- Less professional for libraries

### Pattern 3: Multi-Package Project

```
project/
├── pyproject.toml
├── packages/
│   ├── package-a/
│   │   └── src/
│   │       └── package_a/
│   └── package-b/
│       └── src/
│           └── package_b/
└── tests/
```

## CLI Surface Design

Turning a script into a distributable tool is two separate decisions: how the entry point is
*wired* (Pattern 6/7 in `references/details.md` -- `[project.scripts]`, `click`/`argparse`
boilerplate) and how its arguments are *shaped* -- the part that decides whether the tool is
pleasant to use. Full guidance in `references/cli-design.md`; summary:

- **Positional vs. option vs. flag** -- positionals for the one or two unambiguous required
  inputs, options for everything else, flags named so "off" is the natural default.
- **Subcommands vs. flags** -- subcommands for genuinely different jobs sharing infrastructure;
  flags for variations on one job. A flag that reshapes the rest of the invocation is a
  subcommand in disguise.
- **Help, version, exit codes** -- `--help` at every subcommand level, `--version` sourced from
  the installed package (never hardcoded), `0` on success and non-zero on any failure.
- **Errors to stderr, output to stdout** -- what failed / why / what to try next, never mixed
  into the tool's actual output.
- **Human output by default, `--format json`/`--json` on request** -- this marketplace's own
  scripts (`python-scan`'s `analyze_all.py`, `python-quality-tools`'s `quality_loop.py`,
  `python-performance-optimization`'s `compare_benchmarks.py`) already follow this.
- **Config precedence, when more than one source exists**: CLI flag > env var > config file >
  default -- documented in `--help`, not just in prose.
- **`argparse` vs. `click` vs. `typer`** -- a decision table in `references/cli-design.md`.

## Detailed patterns and worked examples

Detailed pattern documentation lives in `references/details.md`. Read that file when the navigation tier above is insufficient.

