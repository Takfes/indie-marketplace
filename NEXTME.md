# NEXTME — Deferred / Future Work

Backlog items surfaced while designing and developing the current project. Not blocking the current build — revisit each when relevant.

- **mcporter** (`steipete/mcporter`) — explicitly excluded from `essentials` this round. No plugin home decided yet. Candidate: `provision`, alongside the installer skill.
- **google-workspace** bundle (`taylorwilsdon/google_workspace_mcp` vs `gws` CLI) — deferred, review later.
- **ml** bundle (MLflow MCP — official traces-only + `kkruglik/mlflow-mcp` for experiments/registry — + Hugging Face MCP) — deprioritized this round.
- **security** bundle (Semgrep Guardian — note it needs account auth, unlike the bare `semgrep-mcp`) — deprioritized this round.
- **evaluate** `clarity`, `plan-and-critique`, `prd` in `steering` — user flagged these for a challenge/re-evaluation pass, not yet done.
- setup **github actions** to re-build and deploy plugins on a regular schedule (e.g., nightly) — not yet done, but would be nice to have.
- **pgquery (`crystaldba/postgres-mcp`) only installs cleanly via Docker.** `uvx postgres-mcp` fails with `ModuleNotFoundError: No module named 'mcp.server.fastmcp'` (confirmed real upstream bug, not a cache issue — reproduced with `uvx --refresh`). No `npm`/`npx` path exists for it at all (it's a Python package). This matters for #16 (database plugin): the plugin's `mcp:` server declaration will need to default to a `docker run` command rather than `uvx`, which is a heavier runtime dependency (Docker daemon) than every other plugin in this marketplace currently requires. Revisit before #16 — either accept Docker as a hard prerequisite for the database plugin, or watch upstream for the packaging fix.
