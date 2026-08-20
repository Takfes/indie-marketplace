# NEXTME — Deferred / Future Work

Backlog items surfaced while designing and developing the current project. Not blocking the current build — revisit each when relevant.

- **mcporter** (`steipete/mcporter`) — explicitly excluded from `essentials` this round. No plugin home decided yet. Candidate: `provision`, alongside the installer skill.
- **google-workspace** bundle (`taylorwilsdon/google_workspace_mcp` vs `gws` CLI) — deferred, review later.
- **ml** bundle (MLflow MCP — official traces-only + `kkruglik/mlflow-mcp` for experiments/registry — + Hugging Face MCP) — deprioritized this round.
- **security** bundle (Semgrep Guardian — note it needs account auth, unlike the bare `semgrep-mcp`) — deprioritized this round.
- **evaluate** `clarity`, `plan-and-critique`, `prd` in `steering` — user flagged these for a challenge/re-evaluation pass, not yet done.
- setup **github actions** to re-build and deploy plugins on a regular schedule (e.g., nightly) — not yet done, but would be nice to have.
- **Review how MCP server setup works for a global (non-dev-checkout) installation** — specifically how each server's declared `env:` values land in the installed copy, and how the installing user is meant to discover and fill in those values (today's `.env.example` generation assumes a local dev checkout with a sibling `.env`).
- **Revisit the `database` plugin's MCP servers, starting with pgquery's Docker-only install.** `pgquery` (`crystaldba/postgres-mcp`) currently only runs via `docker run` — `uvx postgres-mcp` fails with `ModuleNotFoundError: No module named 'mcp.server.fastmcp'` (confirmed real upstream bug, not a cache issue — reproduced with `uvx --refresh`), and there's no `npm`/`npx` path at all (it's a Python package). This is now a shipped fact, not a risk note: the `database` plugin's `pgquery` entry defaults to `docker run`, a heavier runtime dependency (Docker daemon) than every other plugin currently requires. Revisit periodically — watch upstream for the packaging fix, or accept Docker as a permanent prerequisite. Relevant to both this repo (the shipped plugin config) and `stack-database-mcp` (https://github.com/Takfes/stack-database-mcp — where the bug was originally found and where its own NEXTME.md tracks the same item from the testing side).
