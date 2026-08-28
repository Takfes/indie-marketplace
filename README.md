# indie-marketplace

Personal Claude Code skill marketplace. All plugins are defined in `bundles.yaml` and built by `build.py`.

## Table of Contents

1. [Installing Plugins From This Marketplace](#installing-plugins) — add the marketplace and install a plugin
2. [What's Included — Plugins and Their Skills](#whats-included) — what each plugin contains
3. [How It Works — Architecture and Build Pipeline](#how-it-works) — how `bundles.yaml` and `build.py` fit together
4. [Maintaining the Marketplace](#maintaining) — how to add skills/plugins and test changes before pushing
5. [Credentials and Secrets](#credentials-and-secrets) — where credentials live and how to configure them

<a id="installing-plugins"></a>

## 1. Installing Plugins From This Marketplace

Add this repo as a marketplace, then install whichever plugins you want from it:

```
/plugin marketplace add Takfes/indie-marketplace
/plugin install skillcraft@indie-marketplace
```

Available plugins:

| Plugin | Install command |
|---|---|
| `essentials` | `/plugin install essentials@indie-marketplace` |
| `skillcraft` | `/plugin install skillcraft@indie-marketplace` |
| `pythonista` | `/plugin install pythonista@indie-marketplace` |
| `thinktank` | `/plugin install thinktank@indie-marketplace` |
| `mattpocock` | `/plugin install mattpocock@indie-marketplace` |
| `officetools` | `/plugin install officetools@indie-marketplace` |
| `frontend` | `/plugin install frontend@indie-marketplace` |
| `database` | `/plugin install database@indie-marketplace` |
| `azdevops` | `/plugin install azdevops@indie-marketplace` |
| `research` | `/plugin install research@indie-marketplace` |
| `web-search` | `/plugin install web-search@indie-marketplace` |
| `browser` | `/plugin install browser@indie-marketplace` |
| `codementor` | `/plugin install codementor@indie-marketplace` |
| `superpowers` | `/plugin install superpowers@indie-marketplace` |
| `codex` | `/plugin install codex@indie-marketplace` |

### Other Agents

The `.claude-plugin/` manifests in this repo are also directly compatible with Codex CLI and GitHub Copilot CLI — no separate build or manifest needed.

**Codex CLI:**
```
codex plugin marketplace add Takfes/indie-marketplace
codex plugin add skillcraft@indie-marketplace
```

**GitHub Copilot CLI:**
```
copilot plugin marketplace add Takfes/indie-marketplace
copilot plugin install skillcraft@indie-marketplace
```

<a id="whats-included"></a>

## 2. What's Included — Plugins and Their Skills

- [essentials](#plugin-essentials) — always-on baseline: session lifecycle hooks plus everyday grilling, handoff, onboarding, and terse-mode skills
- [skillcraft](#plugin-skillcraft) — meta-skills for managing, creating, and distributing skills and agents
- [pythonista](#plugin-pythonista) — Python development, packaging, testing, and refactoring skills
- [thinktank](#plugin-thinktank) — thinking, planning, and ideation skills
- [mattpocock](#plugin-mattpocock) — Matt Pocock's engineering skills — spec-driven development, TDD, code review, architecture
- [officetools](#plugin-officetools) — create and edit Office documents — docx, pdf, pptx, and xlsx
- [frontend](#plugin-frontend) — frontend design and UI craft skills — design, iterate, and critique frontend interfaces
- [database](#plugin-database) — SQL and data engineering skills — query review, optimization, Azure Kusto, and table profiling
- [azdevops](#plugin-azdevops) — DevOps and infrastructure skills — containers, Kubernetes, CI/CD, and Azure DevOps
- [research](#plugin-research) — research and reference MCP servers — Zotero library search and Google NotebookLM
- [web-search](#plugin-web-search) — web search, scraping, and discovery skills — Exa semantic search, Firecrawl, recent social discussion, and YouTube lookup
- [browser](#plugin-browser) — browser automation skill — general actions via the Playwright CLI
- [codementor](#plugin-codementor) — git workflow and code review skills — cleanup, commit hygiene, and review excellence
- [superpowers](#plugin-superpowers) — obra's methodology skills (TDD, debugging, brainstorming, code review, plans) with session-start skill-enforcement hook
- [codex](#plugin-codex) — OpenAI's Codex CLI integration — review, rescue, and related commands (vendored from openai/codex-plugin-cc)

<a id="plugin-essentials"></a>
<details>
<summary><strong>essentials</strong> — Always-on baseline — session lifecycle hooks plus everyday grilling, handoff, onboarding, and terse-mode skills</summary>

| Skill | Source | Description |
|---|---|---|
| `onboard-project` | local | Fill in a project's Stack, Commands, and Documentation sections in workspace.md |
| `grill-me` | community | A relentless interview to sharpen a plan or design |
| `grilling` | community | Grill the user relentlessly about a plan or design |
| `handoff` | community | Compact a conversation into a handoff document for another agent |
| `caveman` | community | Ultra-compressed communication mode — cuts output tokens while keeping technical accuracy |
| `teach` | community | Teach the user a new skill or concept, within this workspace |
| `hooks/notify` | local | Stop hook — sound alert when Claude finishes responding |
| `hooks/permission-alert` | local | Notification hook — sound alert when a permission prompt is waiting |

**CLI dependencies** (`deps:`):

| CLI | Install |
|---|---|
| `gh` | `brew install gh` |

</details>

<a id="plugin-skillcraft"></a>
<details>
<summary><strong>skillcraft</strong> — AI toolkit provisioning and meta-skills</summary>

| Skill | Source | Description |
|---|---|---|
| `skill-bundler` | local | Package skills into distributable zip archives for sharing or backup |
| `skill-downloader` | local | Sparse-checkout a specific skill folder from a GitHub repo |
| `skill-creator` | community | Create, edit, and evaluate new skills |
| `find-skills` | community | Discover and install skills matching a described need |
| `agent-development` | community | Guidance on building subagents for Claude Code |

</details>

<a id="plugin-pythonista"></a>
<details>
<summary><strong>pythonista</strong> — Python development, packaging, testing, and refactoring skills</summary>

**MCP servers:**

| Server | Credential(s) | Description |
|---|---|---|
| `context7` | none | Up-to-date, version-specific library documentation lookup |

**Skills:**

| Skill | Source | Description |
|---|---|---|
| `python-packaging` | community | Structure and publish distributable Python packages to PyPI |
| `python-performance-optimization` | local | Profile and optimize Python code with cProfile, tracemalloc, and modern tools — includes an automated hotspot report and a live CPU/memory dashboard |
| `python-refactor` | local | Restructure tangled code into a clear equivalent while preserving correctness — structural moves only |
| `python-testing-patterns` | local | Write a pytest suite for finished Python code — coverage planning, disciplined mocking, and testing anti-patterns |
| `uv-package-manager` | community | Manage dependencies, virtual environments, and workflows with uv |

</details>

<a id="plugin-thinktank"></a>
<details>
<summary><strong>thinktank</strong> — Thinking, planning, and ideation skills</summary>

| Skill | Source | Description |
|---|---|---|
| `clarity` | local | Untangle a sprawling conversation into a sequenced plan |
| `devils-advocate` | local | Stress-test reasoning on significant ideas and decisions |
| `plan-and-critique` | local | Brainstorm → draft → adversarial self-critique → revise cycle |
| `llm-council` | community | Run a decision through a council of 5 AI advisors for a synthesized verdict |
| `prd` | community | Generate Product Requirements Documents |
| `claude-handoff` | community | Hand off a conversation to a fresh background agent |
| `loop-me` | community | Grill me about specs for the workflows I want to build, within this workspace |
| `doc-coauthoring` | community | Structured workflow for co-authoring docs, proposals, specs, and decision docs |

</details>

<a id="plugin-mattpocock"></a>
<details>
<summary><strong>mattpocock</strong> — Matt Pocock's engineering skills — spec-driven development, TDD, code review, architecture</summary>

| Skill | Source | Description |
|---|---|---|
| `ask-matt` | community | Router that recommends which skill or flow fits your situation |
| `code-review` | community | Review changes since a commit/branch against coding standards and the original spec, in parallel |
| `codebase-design` | community | Shared vocabulary for designing deep, testable modules |
| `diagnosing-bugs` | community | Diagnosis loop for hard bugs and performance regressions |
| `domain-modeling` | community | Build and sharpen a project's domain model and ADRs |
| `grill-with-docs` | community | Relentless interview to sharpen a plan, generating ADRs and a glossary as you go |
| `implement` | community | Implement a piece of work from a spec or set of tickets |
| `improve-codebase-architecture` | community | Scan a codebase for deepening opportunities and present them as an HTML report |
| `prototype` | community | Build a throwaway prototype to sanity-check a design question |
| `research` | community | Investigate a question against primary sources and capture findings as a Markdown file |
| `resolving-merge-conflicts` | community | Resolve an in-progress git merge/rebase conflict |
| `setup-matt-pocock-skills` | community | One-time setup for issue tracker, triage labels, and domain doc layout |
| `tdd` | community | Test-driven development — red/green/refactor and integration tests |
| `to-spec` | community | Turn the current conversation into a spec published to the issue tracker |
| `to-tickets` | community | Break a plan or spec into tracer-bullet tickets with blocking edges |
| `triage` | community | Move issues and PRs through a categorise/verify/grill triage state machine |
| `wayfinder` | community | Plan and track work too large for one session as a map of investigation tickets |

</details>

<a id="plugin-officetools"></a>
<details>
<summary><strong>officetools</strong> — create and edit Office documents — docx, pdf, pptx, and xlsx</summary>

| Skill | Source | Description |
|---|---|---|
| `docx` | community | Create, read, edit, and manipulate Word documents (.docx/.dotx) |
| `pdf` | community | Read, merge, split, watermark, fill, encrypt, and OCR PDF files |
| `pptx` | community | Create, read, and edit slide decks and presentations (.pptx/.potx) |
| `xlsx` | community | Create, read, edit, and clean spreadsheets (.xlsx/.xlsm/.csv/.tsv) |

</details>

<a id="plugin-frontend"></a>
<details>
<summary><strong>frontend</strong> — frontend design and UI craft skills — design, iterate, and critique frontend interfaces</summary>

| Skill | Source | Description |
|---|---|---|
| `frontend-design` | community | Guidance for distinctive, intentional visual design on new or existing UI |
| `impeccable` | community | Design, critique, audit, and polish production-grade frontend interfaces |
| `design-taste-frontend` | community | Anti-slop design taste for landing pages, portfolios, and redesigns |

</details>

<a id="plugin-database"></a>
<details>
<summary><strong>database</strong> — SQL and data engineering skills — query review, optimization, Azure Kusto, and table profiling</summary>

**MCP servers:**

| Server | Credential(s) | Description |
|---|---|---|
| `pgquery` | `PGQUERY_URI` | Dedicated Postgres MCP server, read-only validator |
| `dbtools` | `DBTOOLS_CONFIG_PATH` | Multi-engine SQL server (Postgres/MySQL/MSSQL/BigQuery/...) |
| `mysql-mcp` | `MYSQL_MCP_HOST`/`USER`/`PASS`/`DB` | Dedicated MySQL server, app-level write gate |
| `mssql-mcp` | `MSSQL_MCP_HOST`/`DATABASE`/`USER`/`PASSWORD` | Dedicated MSSQL server, read-mostly |

**Skills:**

| Skill | Source | Description |
|---|---|---|
| `sql-code-review` | community | Review SQL for security, maintainability, and anti-patterns across MySQL, PostgreSQL, SQL Server, Oracle |
| `sql-optimization` | community | Tune SQL query performance — indexing strategies, execution plans, and batch operations |
| `azure-kusto` | community | Query and analyze data in Azure Data Explorer (Kusto/ADX) using KQL |
| `profiling-tables` | community | Deep-dive data profiling for a table — statistics, structure, and data quality |

</details>

<a id="plugin-azdevops"></a>
<details>
<summary><strong>azdevops</strong> — DevOps and infrastructure skills — containers, Kubernetes, CI/CD, and Azure DevOps</summary>

**MCP servers:**

| Server | Credential(s) | Description |
|---|---|---|
| `azcloud` | none (`az login`) | Official Azure MCP server, 40+ services |
| `azdevops` | `AZDEVOPS_ORG` | Official Azure DevOps MCP server |
| `azaks` | `AZAKS_BIN` | Official AKS MCP server (downloaded binary) |
| `azkusto` | `AZKUSTO_*` (5 vars) | Azure Data Explorer / Kusto, forced read-only |

**Skills:**

| Skill | Source | Description |
|---|---|---|
| `multi-stage-dockerfile` | community | Create optimized multi-stage Dockerfiles for any language or framework |
| `devcontainer-setup` | community | Create devcontainers with Claude Code, language-specific tooling, and persistent volumes |
| `helm-chart-scaffolding` | community | Design, organize, and manage Helm charts for templating Kubernetes applications |
| `kubernetes-specialist` | community | Deploy and manage Kubernetes workloads — manifests, RBAC, NetworkPolicies, GitOps |
| `ci-cd-and-automation` | community | Set up CI/CD pipelines, quality gates, test runners, and deployment strategies |
| `azure-devops-cli` | community | Azure DevOps CLI — repos, pipelines, builds, PRs, work items |

**CLI dependencies** (`deps:`):

| CLI | Install |
|---|---|
| `az` | `brew install azure-cli` |

</details>

<a id="plugin-research"></a>
<details>
<summary><strong>research</strong> — research and reference MCP servers — Zotero library search and Google NotebookLM</summary>

**MCP servers:**

| Server | Credential(s) | Description |
|---|---|---|
| `zotero` | optional (local mode needs none) | Zotero library search and reference lookup |
| `notebooklm` | none (`nlm login`) | CLI + MCP server for Google's Gemini Notebook (NotebookLM) |

</details>

<a id="plugin-web-search"></a>
<details>
<summary><strong>web-search</strong> — web search, scraping, and discovery skills — Exa semantic search, Firecrawl, recent social discussion, and YouTube lookup</summary>

**MCP servers:**

| Server | Credential(s) | Description |
|---|---|---|
| `exa` | `EXA_API_KEY` | Semantic web search and page fetch |

**Skills:**

| Skill | Source | Credential(s) | Description |
|---|---|---|---|
| `firecrawl` | community | none (`firecrawl login`) | Firecrawl CLI for scraping and crawling |
| `last30days` | community | `SCRAPECREATORS_API_KEY` | Recent public discussion across social platforms |
| `search-yt-dlp` | local | none | YouTube search/channel-fetch CLI primitive |

**CLI dependencies** (`deps:`):

| CLI | Install |
|---|---|
| `yt-dlp` | `brew install yt-dlp` |
| `firecrawl` | `npm install -g firecrawl-cli@latest` |

</details>

<a id="plugin-browser"></a>
<details>
<summary><strong>browser</strong> — browser automation skill — general actions via the Playwright CLI</summary>

| Skill | Source | Description |
|---|---|---|
| `playwright-cli` | community | General browser actions via the Playwright CLI |

**CLI dependencies** (`deps:`):

| CLI | Install |
|---|---|
| `playwright-cli` | `npm install -g @playwright/cli@latest` |

</details>

<a id="plugin-codementor"></a>
<details>
<summary><strong>codementor</strong> — git workflow and code review skills — cleanup, commit hygiene, and review excellence</summary>

| Skill | Source | Description |
|---|---|---|
| `git-cleanup` | community | Safely analyze and clean up local git branches and worktrees — merged, superseded, or active |
| `code-review-excellence` | community | Effective code review practices — constructive feedback, catching bugs early, mentoring |
| `git-commit` | community | Conventional commit message analysis, intelligent staging, and message generation |

</details>

<a id="plugin-superpowers"></a>
<details>
<summary><strong>superpowers</strong> — obra's methodology skills (TDD, debugging, brainstorming, code review, plans) with session-start skill-enforcement hook</summary>

| Skill | Source | Description |
|---|---|---|
| `brainstorming` | community | Explore intent, requirements, and design before creative or feature work |
| `dispatching-parallel-agents` | community | Dispatch 2+ independent tasks to parallel subagents |
| `executing-plans` | community | Execute a written implementation plan with review checkpoints |
| `finishing-a-development-branch` | community | Decide how to integrate finished work — merge, PR, or cleanup |
| `receiving-code-review` | community | Evaluate code review feedback with technical rigor before acting on it |
| `requesting-code-review` | community | Request a code review before merging or completing a task |
| `subagent-driven-development` | community | Execute an implementation plan's independent tasks via subagents |
| `systematic-debugging` | community | Systematic root-cause diagnosis for bugs and unexpected behavior |
| `test-driven-development` | community | Red/green/refactor — write the test before the implementation |
| `using-git-worktrees` | community | Isolate feature work in its own git worktree |
| `using-superpowers` | community | Session-start primer on discovering and invoking the right skill |
| `verification-before-completion` | community | Verify work actually passes before claiming it's done |
| `writing-plans` | community | Turn a spec into a written multi-step implementation plan |
| `writing-skills` | community | Create, edit, and validate new skills before deployment |
| `hooks/session-start` | community | SessionStart hook — injects the using-superpowers skill into every session/clear/compact |

</details>

<a id="plugin-codex"></a>
<details>
<summary><strong>codex</strong> — OpenAI's Codex CLI integration — review, rescue, and related commands (vendored from openai/codex-plugin-cc)</summary>

Vendored whole from [`openai/codex-plugin-cc`](https://github.com/openai/codex-plugin-cc) at `v1.0.6`, rather than built from this repo's usual skill entries — see [How It Works § Vendoring a Whole Plugin](#vendor-mechanism).

| Command / Agent | Description |
|---|---|
| `/codex:review` | Run a Codex code review against local git state |
| `/codex:adversarial-review` | Run a Codex review that challenges the implementation approach and design choices |
| `/codex:rescue` | Delegate investigation, an explicit fix request, or follow-up rescue work to the Codex rescue subagent |
| `/codex:transfer` | Transfer the current Claude Code session into a resumable Codex thread |
| `/codex:status` | Show active and recent Codex jobs for this repository, including review-gate status |
| `/codex:result` | Show the stored final output for a finished Codex job in this repository |
| `/codex:cancel` | Cancel an active background Codex job in this repository |
| `/codex:setup` | Check whether the local Codex CLI is ready and optionally toggle the stop-time review gate |
| `codex-rescue` (subagent) | Handles deeper root-cause investigation or hands a substantial coding task to Codex through the shared runtime |

**Prerequisites:** Node.js ≥18.18, and a separately-authenticated `codex` CLI (`codex login`) — unlike this marketplace's other plugins, this one runs its own `SessionStart`/`Stop` hooks on every session.

**Cost warning:** the optional review-gate (`/codex:setup --enable-review-gate`) can create a long Claude↔Codex loop that burns usage quickly, per OpenAI's own documented warning. Off by default.

</details>

<a id="how-it-works"></a>

## 3. How It Works — Architecture and Build Pipeline

- [Source of Truth: bundles.yaml](#source-of-truth)
- [Build Script: build.py](#build-script)
- [Repo Structure](#repo-structure)
- [Local vs. Community Skill Resolution](#skill-resolution)
- [Vendoring a Whole Plugin](#vendor-mechanism)

<a id="source-of-truth"></a>

### Source of Truth: `bundles.yaml`

Every plugin and every skill in this marketplace is declared in `bundles.yaml`. It defines, per plugin, a list of skills and where each one comes from:

- `source: local` — the skill lives in `skills/<name>/` in this repo, and you own it
- `source: community` — the skill is fetched at build time from a `repo:` (git URL) and `path:` (subdirectory inside that repo)

A plugin can also declare `mcp:` (hand-authored MCP servers), `env:` (credentials for a CLI a skill drives, with no server behind it), `deps:` (CLI tools tracked for install-status reporting), and `catalog: true` (generates a machine-readable summary of a plugin's `mcp:`/`skills:`/`deps:` entries). See `bundles.yaml`'s own header comments for the full field-by-field reference — `pythonista`, `database`, `azdevops`, `research`, `web-search`, and `browser` declare `catalog: true` today (all but `browser` also declare `mcp:`), and `azdevops`, `web-search`, `browser`, and `essentials` declare `deps:`.

Nothing outside `bundles.yaml` needs to be hand-edited to add, remove, or move a skill — `build.py` regenerates everything else from it.

<a id="build-script"></a>

### Build Script: `build.py`

`build.py` reads `bundles.yaml` and, per plugin:

1. Copies each `local` skill from `skills/<name>/` into the plugin
2. Clones the repo for each `community` skill, locates the skill directory inside it, and copies it into the plugin (writing a `SOURCE.md` alongside it with the repo, path, and fetch date for provenance)
3. Writes `.mcp.json`, `vscode-mcp.json`, and `.env.example` from `mcp:`/`env:`, `deps.json` from `deps:`, and `catalog.json` if `catalog: true`
4. Regenerates the plugin's `plugin.json` manifest
5. Regenerates the root `.claude-plugin/marketplace.json`, listing all plugins

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

<a id="vendor-mechanism"></a>

### Vendoring a Whole Plugin

A plugin's `vendor:` block is a different mechanism from `community` skills, and takes an entire third-party plugin wholesale instead of cherry-picking individual skills — see `superpowers` and `mattpocock` for the contrast: those curate a subset of skills from their upstream repos into a plugin of this repo's own, while `vendor:` clones a repo and copies one of its plugin directories in verbatim (its own `plugin.json`, `LICENSE`, `NOTICE`, and any other files) as one sealed unit, optionally pinned to a git tag/branch/sha.

Because the vendored copy's own manifest is authoritative, `build.py` skips its usual owner-stamping of `plugin.json` and any skill/hooks/mcp/deps/catalog dispatch for that plugin — the upstream author stays attributed and the vendored files are free to be hand-edited afterward without being clobbered by the next build. `codex` (vendored from `openai/codex-plugin-cc`) is the first plugin built this way.

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

<a id="credentials-and-secrets"></a>

## 5. Credentials and Secrets

Any plugin whose `mcp:`/`skills:`/`deps:` entries declare `env:` needs credentials to work — a Postgres connection string, an API key. Nothing is exported by hand and nothing is written into a project folder: every credential lives in one file, `~/.indie-marketplace/profiles.json` (mode `0600`), edited through a local browser UI, never through terminal prompts and never through a value passed to Claude.

**Open the editor.** Ask Claude to open the secrets manager (the skill ships with the `essentials` plugin) — it starts a local server and hands you a `127.0.0.1` link with a one-time token. Claude relays that link and nothing else; every value you type is read by your own browser, never by the model.

**Global vs. per-project.** Credentials are grouped into named **profiles**. `base` holds your defaults and applies everywhere. A project-specific profile (e.g. `client-a`) overrides only the variables that differ for it — a database URI, say — and inherits everything else from `base`. Bind a profile to a project directory once, and opening Claude Code inside that directory selects it automatically; no per-session typing required. Working outside a bound directory, or need to override one for a single session? `INDIE_PROFILE=client-a claude` — or add a shell function once, `cc() { INDIE_PROFILE="$1" claude; }`, and run `cc client-a`.

At session start, Claude gets a quiet, value-blind nudge about any tool that's *partially* configured (some but not all of its required variables set) — never about one you haven't touched at all.

Full design — store layout, resolution order, how the generated wrapper scripts keep secrets out of `argv`, and what was deliberately rejected — is documented in [`docs/secrets-architecture.md`](docs/secrets-architecture.md).
