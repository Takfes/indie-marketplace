---
name: skill-downloader
description: Download specific folders from GitHub repositories with automated sparse-checkout, interactive destination selection, and complete cleanup of git artifacts. Supports .claude/skills, .gemini/skills, .agents/, or custom paths. Use this skill whenever you need to fetch a specific directory from a monorepo on GitHub.
---

# Skill Downloader

Automated utility for downloading specific subdirectories from Git repositories without cloning the entire project. Features interactive prompts for configuration, comprehensive validation, and thorough cleanup of all git artifacts.

## When to Use This Skill

- **Partial Downloads**: You only need one folder from a large repository
- **Interactive Setup**: You want to specify destination options interactively
- **Clean Workspace**: You want all git artifacts and empty directories removed
- **Multiple Destinations**: You need flexibility between `.claude/skills`, `.gemini/skills`, `.agents/`, or custom paths
- **Validation**: You want the tool to verify repository and path accessibility before downloading

## How It Works

The skill provides an automated workflow that:

1. **Prompts for Details**: Asks for repository URL, path within repo, and branch
2. **Offers Destination Options**: Defaults to `.claude/skills` but allows `.gemini/skills`, `.agents/`, or custom paths
3. **Validates Everything**: Checks repository accessibility and path existence
4. **Sparse Checkout**: Downloads only the requested directory using git's sparse-checkout
5. **Cleans Up**: Removes `.git` directories, `.gitignore`, and other git artifacts
6. **Final Cleanup**: Removes empty directories and temporary files, leaving workspace pristine

## Using This Skill

### Automated Approach (Recommended)

Always invoke the Python script with `--project-dir` set to the current project root. This anchors all relative destination paths (e.g. `.claude/skills`) to the correct location regardless of shell CWD:

```bash
python3 /path/to/skills/skill-downloader/scripts/download_repo.py \
  --project-dir /absolute/path/to/your/project
```

When running via Claude Code's Bash tool, the safest form is:

```bash
python3 /path/to/skills/skill-downloader/scripts/download_repo.py \
  --project-dir "$(pwd)"
```

The script will guide you through:
- Repository URL entry
- Path specification within the repository
- Branch selection (defaults to `main`)
- Destination folder choice

### Bash Fallback

If Python isn't available, run the bash script **from the project root**. The script captures `pwd` at startup, so the working directory at invocation time determines where relative destinations resolve:

```bash
cd /absolute/path/to/your/project
bash /path/to/skills/skill-downloader/scripts/download_repo.sh
```

The workflow is identical, with the same interactive prompts.

## Destination Options

When prompted, choose your preferred destination:

| Option | Path | Use When |
|--------|------|----------|
| 1 (Default) | `.claude/skills` | You want Claude Code-specific skills |
| 2 | `.gemini/skills` | You want Gemini CLI-specific tools |
| 3 | `.agents/` | You want custom agents |
| 4 | Custom Path | You need a different location |

## Example Workflow

**Goal**: Download the `brainstorming` skill from the superpowers repository

```bash
$ python3 scripts/download_repo.py --project-dir "$(pwd)"

📦 Repository Details
GitHub repository URL: https://github.com/anthropics/superpowers.git
Path in repository: skills/brainstorming
Branch name (press Enter for 'main'): [press Enter]

📂 Destination
Select destination for downloaded files:
  1) .claude/skills       (Default)
  2) .gemini/skills
  3) .agents/
  4) Custom path

Choose [1-4] (default: 1): [press Enter]

🔍 Validating repository...
✓ Repository accessible

🔧 Setting up temporary workspace...
✓ Workspace created: /tmp/skill_download_XXXXXX

📥 Initializing sparse checkout...
✓ Sparse checkout configured

📡 Pulling skills/brainstorming from main...
✓ Content pulled successfully

📦 Extracting content...
✓ Extracted to: .claude/skills/brainstorming

🧹 Cleaning git artifacts...
✓ Removed X git-related items

🧹 Cleaning empty directories...
✓ Empty directories cleaned

🗑️  Removing temporary workspace...
✓ Temporary workspace cleaned up

============================================================
✓ Download completed successfully!
============================================================
Content available at: /absolute/path/to/your/project/.claude/skills/brainstorming
```

## Error Handling

The skill provides clear error messages for common issues:

| Error | Cause | Solution |
|-------|-------|----------|
| `Repository not found or not accessible` | Invalid URL or no internet | Check URL and connection |
| `Path not found in repository` | Incorrect path or branch | Verify path exists in branch |
| `Git not installed or not in PATH` | Git isn't available | Install git or use alternative approach |
| `Destination already exists` | Folder already present | Choose to overwrite or use different path |
| `Timeout` | Network issues | Check internet connection and retry |

## Safety Considerations

- **Repository Source**: Only download from trusted sources
- **Validation**: The tool automatically validates repository accessibility
- **Clean Workspace**: All git artifacts are automatically removed
- **Temporary Files**: Temporary workspace is completely removed after download
- **Path Verification**: Warns before overwriting existing destinations

## Advanced Usage

### Command-Line Arguments (Python Version)

Pass `--project-dir` to anchor all relative destination paths to a specific directory:

```bash
python3 scripts/download_repo.py --project-dir /path/to/project
```

You can also call it programmatically:

```python
from pathlib import Path
from download_repo import RepoDownloader

downloader = RepoDownloader(project_dir=Path("/path/to/project"))
downloader.repo_url = "https://github.com/your/repo.git"
downloader.repo_path = "path/to/folder"
downloader.branch = "main"
downloader.destination = ".claude/skills"
downloader.run()
```

## Troubleshooting

**Q: The script seems slow**
- A: Sparse checkout requires git to connect to the remote. Check your internet connection.

**Q: My destination is nested (e.g., `.claude/skills/category/skill`)**
- A: The script automatically creates parent directories, so just specify `.claude/skills` and the folder will be placed inside.

**Q: What gets removed from the downloaded content?**
- A: The tool removes: `.git/` directories, `.gitignore`, `.gitattributes`, `.gitmodules`, `.github/` directories, `CODEOWNERS`, and any empty directories created by the extraction process.

**Q: Can I download multiple paths from one repo?**
- A: Run the script multiple times, once for each path you need. Or use the sparse-checkout manual approach for advanced setups.
