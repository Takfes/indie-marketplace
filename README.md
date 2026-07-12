# indie-marketplace

Personal Claude Code skill marketplace. All plugins are defined in `bundles.yaml` and built by `build.py`.

## Table of Contents

1. [Installing Plugins From This Marketplace](#installing-plugins) — add the marketplace and install a plugin
2. [What's Included — Plugins and Their Skills](#whats-included) — what each plugin contains
3. [How It Works — Architecture and Build Pipeline](#how-it-works) — how `bundles.yaml` and `build.py` fit together
4. [Maintaining the Marketplace](#maintaining) — how to add skills/plugins and test changes before pushing

<a id="installing-plugins"></a>

## 1. Installing Plugins From This Marketplace

Add this repo as a marketplace, then install whichever plugins you want from it:

```
/plugin marketplace add Takfes/indie-marketplace
/plugin install provision@indie-marketplace
```

Available plugins:

| Plugin | Install command |
|---|---|
| `provision` | `/plugin install provision@indie-marketplace` |
| `python` | `/plugin install python@indie-marketplace` |
| `ideation` | `/plugin install ideation@indie-marketplace` |

> Looking for skills that live outside this marketplace (superpowers, ponytail, etc.)? See [`EXTERNAL-PLUGINS.md`](EXTERNAL-PLUGINS.md).

<a id="whats-included"></a>

## 2. What's Included — Plugins and Their Skills

- [provision](#plugin-provision) — meta-skills for managing, creating, and distributing skills and agents
- [python](#plugin-python) — Python development, packaging, testing, and refactoring skills
- [ideation](#plugin-ideation) — thinking, planning, and ideation skills

<a id="plugin-provision"></a>
<details>
<summary><strong>provision</strong> — AI toolkit provisioning and meta-skills</summary>

| Skill | Source | Description |
|---|---|---|
| `skill-bundler` | local | Package skills into distributable zip archives for sharing or backup |
| `skill-downloader` | local | Sparse-checkout a specific skill folder from a GitHub repo |
| `skill-creator` | community | Create, edit, and evaluate new skills |
| `find-skills` | community | Discover and install skills matching a described need |
| `agent-development` | community | Guidance on building subagents for Claude Code |

</details>

<a id="plugin-python"></a>
<details>
<summary><strong>python</strong> — Python development, packaging, testing, and refactoring skills</summary>

| Skill | Source | Description |
|---|---|---|
| `python-packaging` | community | Structure and publish distributable Python packages to PyPI |
| `python-performance-optimization` | community | Profile and optimize Python code with cProfile and memory profilers |
| `python-refactor` | community | Turn complex code into clear, maintainable code while preserving correctness |
| `python-simplifier` | community | Simplify overly complex code, flag code smells and duplication |
| `python-testing-patterns` | community | pytest strategies — fixtures, mocking, test-driven development |
| `uv-package-manager` | community | Manage dependencies, virtual environments, and workflows with uv |

</details>

<a id="plugin-ideation"></a>
<details>
<summary><strong>ideation</strong> — Thinking, planning, and ideation skills</summary>

| Skill | Source | Description |
|---|---|---|
| `clarity` | local | Untangle a sprawling conversation into a sequenced plan |
| `devils-advocate` | local | Stress-test reasoning on significant ideas and decisions |
| `plan-and-critique` | local | Brainstorm → draft → adversarial self-critique → revise cycle |
| `llm-council` | community | Run a decision through a council of 5 AI advisors for a synthesized verdict |
| `prd` | community | Generate Product Requirements Documents |
| `claude-handoff` | community | Hand off a conversation to a fresh background agent |
| `grill-me` | community | A relentless interview to sharpen a plan or design |
| `grilling` | community | Grill the user relentlessly about a plan or design |
| `handoff` | community | Compact a conversation into a handoff document for another agent |

</details>

<a id="how-it-works"></a>

## 3. How It Works — Architecture and Build Pipeline

- [Source of Truth: bundles.yaml](#source-of-truth)
- [Build Script: build.py](#build-script)
- [Repo Structure](#repo-structure)
- [Local vs. Community Skill Resolution](#skill-resolution)

<a id="source-of-truth"></a>

### Source of Truth: `bundles.yaml`

Every plugin and every skill in this marketplace is declared in `bundles.yaml`. It defines, per plugin, a list of skills and where each one comes from:

- `source: local` — the skill lives in `skills/<name>/` in this repo, and you own it
- `source: community` — the skill is fetched at build time from a `repo:` (git URL) and `path:` (subdirectory inside that repo)

Nothing outside `bundles.yaml` needs to be hand-edited to add, remove, or move a skill — `build.py` regenerates everything else from it.

<a id="build-script"></a>

### Build Script: `build.py`

`build.py` reads `bundles.yaml` and, per plugin:

1. Copies each `local` skill from `skills/<name>/` into the plugin
2. Clones the repo for each `community` skill, locates the skill directory inside it, and copies it into the plugin (writing a `SOURCE.md` alongside it with the repo, path, and fetch date for provenance)
3. Regenerates the plugin's `plugin.json` manifest
4. Regenerates the root `.claude-plugin/marketplace.json`, listing all plugins

Run it via `make` (see [Maintaining the Marketplace](#maintaining)) rather than calling it directly.

<a id="repo-structure"></a>

### Repo Structure

```
bundles.yaml                    ← config: skills → plugins (edit this)
build.py                        ← build script (run this via make)
.claude-plugin/marketplace.json ← generated manifest (commit after build)
skills/                         ← canonical source for custom skills (edit freely)
plugins/                        ← built output (commit after build)
```

<a id="skill-resolution"></a>

### Local vs. Community Skill Resolution

For a `community` skill, `build.py` first looks for the skill at the exact `path:` given in `bundles.yaml`. If that path doesn't contain a `SKILL.md`, it falls back to searching the whole cloned repo for a directory whose name matches the skill's `name`. The exact path is preferred — it fails loudly if upstream reorganizes their repo, rather than silently resolving to the wrong directory.

<a id="maintaining"></a>

## 4. Maintaining the Marketplace

- [Command Reference](#command-reference)
- [Add a Custom Skill](#add-custom-skill)
- [Add a Community Skill](#add-community-skill)
- [Add a New Plugin](#add-new-plugin)
- [Testing Changes](#testing-changes)

<a id="command-reference"></a>

### Command Reference

| Command | What it does |
|---|---|
| `make build` | Build all plugins using cached community skills |
| `make fetch` | Re-download all community skills (no build) |
| `make fetch-build` | Re-download community skills, then build everything |
| `make build <plugin>` | Build one plugin, use cache |
| `make fetch <plugin>` | Re-download community skills for one plugin only |
| `make fetch-build <plugin>` | Re-download + build one plugin |

<a id="add-custom-skill"></a>

### Add a Custom Skill

1. Put the skill directory in `skills/<name>/`
2. Add an entry under the plugin in `bundles.yaml` with `source: local`
3. Run `make build`

<a id="add-community-skill"></a>

### Add a Community Skill

1. Find the GitHub repo containing the skill, and the exact path to its `SKILL.md` within that repo
2. Add an entry in `bundles.yaml` with `source: community`, `repo:`, and `path:`
3. Run `make fetch` (clones the repo and copies the skill into the plugin)

<a id="add-new-plugin"></a>

### Add a New Plugin

1. Add a new block under `plugins:` in `bundles.yaml`
2. Run `make build`

<a id="testing-changes"></a>

### Testing Changes

Before pushing, verify the build output and try the plugin locally:

1. Run `make fetch-build` (or scope it to one plugin) and check the diff under `plugins/` and `.claude-plugin/marketplace.json` looks right
2. Add the local repo as a marketplace so Claude Code picks up your uncommitted changes:
   ```
   /plugin marketplace add /absolute/path/to/indie-marketplace
   /plugin install <plugin-name>@indie-marketplace
   ```
3. Invoke the skill in a session to confirm it triggers and behaves as expected
4. Once satisfied, commit and push
