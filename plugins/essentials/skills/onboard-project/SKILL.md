---
name: onboard-project
description: Fill in a project's Stack, Commands, and Documentation sections in .claude/rules/workspace.md (and set up a data/ folder if relevant) when bootstrapping a new project from the CLAUDE.md template, or when an existing project's workspace.md is still empty/placeholder. Use when the user says "set up this project", "onboard this repo", "fill in workspace.md", or when workspace.md sections are found empty during a session.
---

# Onboard Project

Fills in `.claude/rules/workspace.md`'s Stack, Commands, and Documentation sections, and sets up a `data/` folder if the project involves data. Infer first, ask only what can't be inferred.

## Steps

1. **Infer Stack.** Check for lockfiles/manifests in the project root: `uv.lock`/`pyproject.toml` (Python/uv), `package-lock.json`/`package.json` (npm), `pnpm-lock.yaml`, `yarn.lock`, `Cargo.toml` (Rust), `go.mod` (Go), `Gemfile.lock` (Ruby). Note runtime, framework (from manifest dependencies), and package manager. Don't ask about anything readable directly.

2. **Infer Commands.** Check for a `Makefile` or `justfile`; if found, list its targets — those are canonical. If neither exists, check the manifest's own script/task definitions (`package.json` "scripts", `pyproject.toml` tool sections). Only ask if nothing codifies the commands anywhere.

3. **Ask what can't be inferred**, via AskUserQuestion — genuine gaps only, not confirmation theater:
   - What does this project do (one line, for Documentation)?
   - Where does existing documentation live, if any (README, docs/, wiki, none)?
   - Does this project involve a dataset?

4. **If data is involved, investigate — don't interview.** Look for a data folder or connection config. Read schema files, sample the data structure, draft a short summary (what the data is, how to access/query it, key tables/fields). Show the draft for confirmation before writing anything.
   - If no `data/` folder exists yet, propose creating one.
   - Write the confirmed summary to `data/README.md` (or `data/SCHEMA.md` if primarily schema-shaped).
   - If the content is substantial, add `.claude/rules/data.md` with `paths:` frontmatter scoped to `data/**` and relevant file types (`**/*.sql`, `**/*.ipynb`), pointing at the data folder rather than duplicating its content.

5. **Write the results** into `.claude/rules/workspace.md`'s `## Stack`, `## Commands`, and `## Documentation` sections, replacing placeholder text. Show what was written before considering the task done.

## Principles

- Infer before asking — a lockfile is faster and more accurate than a question the user might misremember.
- Data gets investigated, not interviewed — schemas and query patterns are discovered by reading, not recited from memory.
- Never invent commands or stack details. If something can't be inferred or confirmed, ask — don't guess.
