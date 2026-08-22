---
name: skill-bundler
description: Package Claude skills into distributable zip archives for sharing, backup, and distribution. Use when backing up personal skills, preparing to move skills to another Claude setup, sharing a skill with a teammate, or consolidating multiple skills into a portable format. Supports single or batch packaging with dry-run preview, proper YAML validation, and detailed packaging summaries.
---

# Skills Package

## Overview

This skill automates the process of packaging Claude skills into zip archives. It copies skill folders from their source locations to a destination directory and creates compressed archives of each skill, leaving originals untouched.

Use this skill when you want to:
- **Distribute skills** - Create shareable skill packages
- **Back up skills** - Generate compressed backups of skill directories
- **Prepare deployment** - Batch package multiple skills at once
- **Archive versions** - Create timestamped archives for version control
- **Share via Claude Projects** — Package skills to share with teammates using claude.ai Projects or distribute across different Claude Code setups

## Default Destination

The default output folder is `zip-skills/` in the current project root.

**Before calling the script, check whether `zip-skills/` exists:**
- If it exists → pass it as `--dest` (or omit `--dest` and let the script use the default).
- If it does not exist → ask the user: "The `zip-skills/` folder doesn't exist. Should I create it, or would you prefer a different destination?" Then act on their answer before invoking the script.

Never auto-create `zip-skills/` without the user's knowledge.

## Quick Start

**Preview what will be packaged (no files created):**
```bash
python package_skills.py /path/to/skill1 /path/to/skill2 --dry-run
```

Shows file counts, sizes, and what will be created without executing. Perfect for verifying before packaging.

**Basic usage (uses `zip-skills/` by default):**
```bash
python package_skills.py /path/to/skill1 /path/to/skill2
```

**Explicit destination:**
```bash
python package_skills.py /path/to/skill1 /path/to/skill2 --dest /output/directory
```

This will:
1. Copy `skill1/` and `skill2/` to `/output/directory/`
2. Create `skill1.zip` and `skill2.zip` in `/output/directory/`
3. Remove the temporary copied directories
4. Leave originals untouched
5. Display a summary showing total files and archive sizes

**Keep copied directories:**
```bash
python package_skills.py /path/to/skill1 --dest /output --keep-dirs
```

Preserves both the copied folders and zip archives in the destination. Use this if you want to inspect the copied skill before cleanup or migrate skills to a new location.

**List all skills available for packaging (no execution):**
```bash
python package_skills.py --list /path/to/skills/directory
```

## How It Works

**Without `--dry-run`:**
The skill performs these steps for each input skill:

0. **Validate structure** (optional) — Parses YAML frontmatter and warns if name or description fields are missing. This is a warning only, not a failure.
1. **Validate** - Confirms the directory contains a valid `SKILL.md` file
2. **Copy** - Recursively copies the skill directory to the destination
3. **Zip** - Creates a compressed archive using the skill name
4. **Summary** - Displays file count, archive size, and packaging summary
5. **Cleanup** - Removes the temporary copied directory (unless `--keep-dirs` is specified)

The zip archive preserves the full skill structure including scripts, references, and assets directories.

**With `--dry-run`:**
Shows what would be packaged (file counts, sizes) without creating any files. Perfect for validation before committing to the operation.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `skills` | Yes* | One or more paths to skill directories to package |
| `--dest` | No | Destination directory (default: `zip-skills/` in current directory) |
| `--dry-run` | No | Show what would be packaged without executing (no files created) |
| `--keep-dirs` | No | Keep copied skill directories after zipping (default: delete) |
| `--list` | No* | List all valid skills in a directory without packaging them |
| `--no-validate` | No | Skip SKILL.md structure validation warnings |

*: Either `skills` (for packaging) or `--list` (for discovery) is required

## Examples

**Dry-run to preview single skill:**
```bash
python package_skills.py /Users/user/.claude/skills/my-skill --dest ./my-skills-repo --dry-run
```

Output shows file count and size without creating anything. Perfect for validation before packaging.

**Single skill:**
```bash
python package_skills.py /Users/user/.claude/skills/my-skill --dest ./my-skills-repo
```

**Multiple skills in batch:**
```bash
python package_skills.py \
  /Users/user/.claude/skills/skill-1 \
  /Users/user/.claude/skills/skill-2 \
  /Users/user/.claude/skills/skill-3 \
  --dest ./skill-archive
```

Displays summary of packaged skills with file counts and total size.

**Dry-run with multiple skills:**
```bash
python package_skills.py \
  /Users/user/.claude/skills/skill-1 \
  /Users/user/.claude/skills/skill-2 \
  --dest ./skill-archive \
  --dry-run
```

**Preserve copied directories:**
```bash
python package_skills.py /Users/user/.claude/skills/my-skill --dest ./repo --keep-dirs
```

Both copied folders and zip archives remain in destination. Use this if you want to inspect the copied skill structure or migrate skills to a new location.

## Skill Structure Validation

Before zipping, the script optionally checks that each SKILL.md has the required YAML frontmatter fields:
- `name` — skill identifier used to invoke it
- `description` — one-line trigger description for the skill system

The validation properly parses YAML frontmatter (content between `---` delimiters), so it only flags actual missing fields in the front matter, not elsewhere in the file.

If any field is missing, a warning is printed but packaging continues. To suppress warnings, pass `--no-validate`.

## Distribution & Sharing

The zip archives produced by this skill are compatible with:
- **Claude Projects** — Import skill archives via project file upload
- **Local install** — Unzip directly into `~/.claude/skills/` or project `.claude/skills/`
- **Team sharing** — Distribute zip files for teammates to install in their own Claude Code setups

Each zip preserves the full skill structure (`SKILL.md`, `references/`, `scripts/`, etc.) with the skill directory name as the archive root.

## Verification

After packaging, verify the zip contains the correct structure:
```bash
unzip -l /path/to/skill-name.zip
```

The zip should show the complete skill directory including `SKILL.md` and any bundled resources.

## Resources

**Script:** `scripts/package_skills.py`
- Main executable for packaging skills
- Validates skill directories, copies recursively, and creates zip archives
- Supports `--list` to enumerate valid skills without packaging and `--no-validate` to suppress frontmatter warnings
- Executable without reading into context (can be called directly)
