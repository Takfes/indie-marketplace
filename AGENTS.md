# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Add durable project-specific notes here as they are discovered through real work.
- Config and generation: `bundles.yaml` is the single source of truth for plugins; `./build.py` (see its docstring and `bundles.yaml`'s own header comments) regenerates `plugins/*/`, `.claude-plugin/marketplace.json`, `.env.example`, `.mcp.json`, and `vscode-mcp.json` from it — never hand-edit those generated files.
- When making a scoped change (e.g. renaming or editing one plugin), run `./build.py --plugin <name>` rather than a bare `./build.py`: the full build re-fetches every non-cached community skill from upstream, which can pull unrelated upstream drift into your diff. If you do run a full build by accident, `git status` and revert any plugin directories you didn't mean to touch.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
