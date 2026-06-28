# Skill Downloader - FAQ & Troubleshooting

## Common Questions

### How do I run the script?

**Python (recommended):**
```bash
python3 ~/.claude/skills/skill-downloader/scripts/download_repo.py
```

**Bash (fallback):**
```bash
bash ~/.claude/skills/skill-downloader/scripts/download_repo.sh
```

### What's the difference between the Python and Bash versions?

Both do the exact same thing. The Python version is more robust and provides better error messages. The Bash version is available as a fallback if Python isn't installed.

### Can I specify inputs without interactive prompts?

The current version uses interactive prompts for safety and clarity. If you want to script it programmatically, you can modify the scripts or source the Python module directly.

### What if I want to download from a private GitHub repository?

The script uses `git ls-remote`, which respects your git credentials. Make sure you've authenticated with GitHub using one of these methods:
- SSH key configured in ~/.ssh/
- GitHub CLI (`gh auth login`)
- Git credential helper configured

### How long does a download take?

It depends on:
- Repository size (sparse checkout only downloads requested files)
- Your internet connection
- Branch size

Typically: 5-30 seconds for most repositories.

### Can I cancel the process mid-way?

Yes. Press `Ctrl+C` at any time. The script will clean up the temporary workspace on exit.

## Troubleshooting

### Git is not installed

**Error:** `Git is not installed or not in PATH`

**Solution:** Install git:
- macOS: `brew install git`
- Ubuntu/Debian: `sudo apt-get install git`
- Windows: Download from https://git-scm.com/

### Repository not found

**Error:** `Repository not found or not accessible`

**Causes:**
- URL is incorrect
- Repository is private and you're not authenticated
- Repository doesn't exist

**Solution:**
1. Double-check the URL
2. For private repos, ensure git credentials are configured
3. Test: `git ls-remote https://github.com/user/repo.git`

### Path not found in repository

**Error:** `Path 'xyz' not found in repository or branch 'main'`

**Causes:**
- Path doesn't exist in the repository
- Path exists but in a different branch
- Typo in the path name

**Solution:**
1. Verify the path exists by browsing the GitHub repository
2. Check if it's in a different branch
3. Ensure the branch name is correct (often `main` or `master`)

### Timeout during pull

**Error:** `Pull operation timed out`

**Causes:**
- Slow internet connection
- Repository is very large
- Network connectivity issues

**Solution:**
1. Check your internet connection
2. Try again (sometimes temporary)
3. Consider downloading during off-peak hours

### Destination already exists

**Warning:** `Destination already exists: /path/to/folder`

**Causes:**
- You've downloaded this folder before
- Folder exists from another source

**Solution:**
When prompted:
- Choose "y" to overwrite (replaces the folder)
- Choose "n" to cancel (choose a different destination next time)

### Permission denied

**Error:** `Permission denied` when creating destination

**Causes:**
- Destination directory requires elevated permissions
- You don't own the parent directory

**Solution:**
1. Choose a destination you have write access to
2. Or: `sudo chown -R $(whoami) /path/to/parent/`

### Python not found or version too old

**Error:** `python3: command not found` or similar

**Causes:**
- Python 3 not installed
- Python not in PATH
- Wrong Python version

**Solution:**
1. Install Python 3.7+:
   - macOS: `brew install python3`
   - Ubuntu: `sudo apt-get install python3`
2. Or use the Bash version instead

### Temporary workspace cleanup failed

**Warning:** `Could not fully clean temporary workspace`

**Causes:**
- File permissions issue
- File was still in use

**Solution:**
- This is usually harmless; the temp directory will be cleaned up by the OS
- To manually clean: `rm -rf /tmp/skill_download_*`

## Advanced Issues

### The script created git artifacts I didn't expect

**Cause:** Unexpected files from the source repository

**Solution:** The cleanup process should remove:
- All `.git/` directories
- `.gitignore`, `.gitattributes`, `.gitmodules`
- `.github/` directories
- `CODEOWNERS`
- Empty directories

If you still see git files, they may be tracked in the repository itself (not git metadata).

### I want to debug what's happening

**Python version:** The script prints detailed messages at each step. If something fails, read the error message carefully — it usually explains the issue.

**Bash version:** Same as above. For more detail, add `set -x` near the top of the script to see each command executed.

### Can I modify the scripts?

Yes! They're in the `scripts/` directory. Both are self-contained and don't depend on external libraries (Python version uses only standard library).

### What about security?

The script:
- Validates repository accessibility before downloading
- Uses git's native sparse-checkout (no custom cloning logic)
- Removes git artifacts automatically
- Cleans up temporary files completely
- Only downloads from repositories you explicitly specify

Always verify the repository URL and path before running.

## Frequently Needed Paths

Common repository paths to download:

### Anthropic Superpowers
- **Repo:** `https://github.com/anthropics/superpowers.git`
- **Paths:**
  - `skills/brainstorming` — Brainstorming skill
  - `skills/writing-plans` — Writing plans skill
  - `skills/code-reviewer` — Code review skill

### Claude Code Official Plugins
- **Repo:** `https://github.com/anthropics/claude-code-plugins.git`
- **Paths:** Varies; check repository structure

### Custom Projects
Adjust the repository URL and path for your own projects.

## Getting Help

If you encounter an issue not listed here:

1. **Check the error message** — they're designed to be helpful
2. **Test git manually:** `git ls-remote <repo-url>`
3. **Verify the path:** Browse the repository on GitHub
4. **Check internet connection:** `ping github.com`
5. **Try the Bash version** if the Python version fails
