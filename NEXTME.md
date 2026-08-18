# NEXTME — Deferred / Future Work

Backlog items surfaced while designing and developing the current project. Not blocking the current build — revisit each when relevant.

- **mcporter** (`steipete/mcporter`) — explicitly excluded from `essentials` this round. No plugin home decided yet. Candidate: `provision`, alongside the installer skill.
- **google-workspace** bundle (`taylorwilsdon/google_workspace_mcp` vs `gws` CLI) — deferred, review later.
- **ml** bundle (MLflow MCP — official traces-only + `kkruglik/mlflow-mcp` for experiments/registry — + Hugging Face MCP) — deprioritized this round.
- **security** bundle (Semgrep Guardian — note it needs account auth, unlike the bare `semgrep-mcp`) — deprioritized this round.
- **evaluate** `clarity`, `plan-and-critique`, `prd` in `steering` — user flagged these for a challenge/re-evaluation pass, not yet done.
- setup **github actions** to re-build and deploy plugins on a regular schedule (e.g., nightly) — not yet done, but would be nice to have.
