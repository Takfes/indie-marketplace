# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Config and generation: `bundles.yaml` is the single source of truth for plugins; `./build.py` (see its docstring and `bundles.yaml`'s own header comments) regenerates `plugins/*/`, `.claude-plugin/marketplace.json`, `.env.example`, `.mcp.json`, `vscode-mcp.json`, and `deps.json` from it — never hand-edit those generated files. The header documents every top-level block: `skills:`, `mcp:`, `env:`, `deps:`, `hooks:`.
- When making a scoped change (e.g. renaming or editing one plugin), run `./build.py --plugin <name>` rather than a bare `./build.py`: the full build re-fetches every non-cached community skill from upstream, which can pull unrelated upstream drift into your diff. If you do run a full build by accident, `git status` and revert any plugin directories you didn't mean to touch.
- Two more caching gotchas found while refreshing vendored plugins: a plugin's `hooks:` block (single-path fetch, e.g. `superpowers`) is cache-aware like a single skill and only re-fetches with `--fetch` — a bare `./build.py`, or even an unscoped `--fetch`, does not touch it unless you target `--plugin <name> --fetch`. A wildcard `skills:` group fetch (`path: "*"` or `"dir/*"`) always re-clones, but its `shutil.copytree` only adds/overwrites — it never deletes a locally-vendored file whose upstream source was renamed or removed. After any wildcard refresh, diff the plugin's file list against a fresh upstream clone to catch orphans before committing.
- `skills/toolchain-doctor` (installed as the `provision` plugin's doctor skill) reports missing runtimes (from `mcp:` commands) and missing catalog CLI deps (from `deps:` entries, e.g. `research`'s `notebooklm-mcp-cli`) that installed plugins need. It is stdlib-only Python and deliberately never runs automatically at session start — see its `SKILL.md` for the full contract.
- If a branch adds a `plugins/<old-name>/skills/<new-skill>/` build output concurrently with another branch renaming that plugin (`bundles.yaml`'s `- name:` and its directory both change), `git rebase` does not relocate the new skill into the renamed directory — it silently resurrects the old plugin directory containing only the new skill. `bundles.yaml` itself merges fine (it's text); only the generated `plugins/` output needs the fix: delete the resurrected old directory and rerun `./build.py --plugin <new-name>` to regenerate the new skill under the correct plugin path before committing.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
