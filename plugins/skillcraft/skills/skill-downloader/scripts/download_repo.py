#!/usr/bin/env python3
"""
Skill Downloader - Sparse checkout utility for downloading specific folders from GitHub repos.

This script automates the process of downloading individual directories from a Git repository
using sparse-checkout, cleaning up all git artifacts, and organizing the result in a
user-specified destination.
"""

import argparse
import os
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple


class RepoDownloader:
    """Handles downloading and organizing specific repo folders."""

    # Default destination options
    DESTINATION_DEFAULTS = {
        "1": (".claude/skills", ".claude/skills"),
        "2": (".gemini/skills", ".gemini/skills"),
        "3": (".agents/", ".agents/"),
        "4": (None, None),  # Custom option
    }

    def __init__(self, project_dir: Optional[Path] = None):
        # Anchor to project root immediately, before anything can change CWD.
        # Caller can pass --project-dir explicitly; otherwise we use CWD at
        # script start, which is correct when invoked from the project root.
        self.project_dir = project_dir or Path.cwd()
        self.repo_url = None
        self.repo_path = None
        self.branch = "main"
        self.destination = None
        self.temp_dir = None
        self.work_dir = None

    def log(self, message: str, level: str = "INFO") -> None:
        """Print formatted log message."""
        prefix = {
            "INFO": "ℹ️ ",
            "SUCCESS": "✓ ",
            "WARNING": "⚠️ ",
            "ERROR": "✗ ",
        }.get(level, "")
        print(f"{prefix}{message}")

    def prompt_for_input(self, prompt_text: str, default: Optional[str] = None) -> str:
        """Prompt user for input with optional default."""
        if default:
            prompt_text = f"{prompt_text} [{default}]: "
        else:
            prompt_text = f"{prompt_text}: "

        user_input = input(prompt_text).strip()
        return user_input if user_input else default

    def get_repo_details(self) -> bool:
        """Prompt user for repository details."""
        self.log("📦 Repository Details", "INFO")
        print()

        # Get repo URL
        self.repo_url = self.prompt_for_input(
            "GitHub repository URL\n  (e.g., https://github.com/anthropics/superpowers.git)"
        )
        if not self.repo_url:
            self.log("Repository URL is required", "ERROR")
            return False

        # Normalize URL
        if not self.repo_url.endswith(".git"):
            self.repo_url = self.repo_url + ".git"

        # Get path in repo
        self.repo_path = self.prompt_for_input(
            "Path in repository\n  (e.g., skills/brainstorming)"
        )
        if not self.repo_path:
            self.log("Repository path is required", "ERROR")
            return False

        # Get branch (optional)
        branch_input = self.prompt_for_input(
            "Branch name (press Enter for 'main')", default="main"
        )
        self.branch = branch_input if branch_input else "main"

        return True

    def select_destination(self) -> bool:
        """Prompt user to select or specify destination."""
        self.log("📂 Destination", "INFO")
        print()

        print("Select destination for downloaded files:")
        print("  1) .claude/skills       (Default)")
        print("  2) .gemini/skills")
        print("  3) .agents/")
        print("  4) Custom path")
        print()

        choice = self.prompt_for_input("Choose [1-4]", default="1").strip()

        if choice in self.DESTINATION_DEFAULTS:
            default_path, dest = self.DESTINATION_DEFAULTS[choice]
            if dest is None:  # Custom option
                custom_path = self.prompt_for_input("Enter custom destination path")
                if not custom_path:
                    self.log("Destination path cannot be empty", "ERROR")
                    return False
                self.destination = custom_path
            else:
                self.destination = dest
                self.log(f"Destination: {dest}", "INFO")
        else:
            self.log(f"Invalid choice: {choice}. Please choose 1-4.", "ERROR")
            return False

        return True

    def validate_repo(self) -> bool:
        """Validate that the repository exists and path is accessible."""
        self.log("🔍 Validating repository...", "INFO")

        try:
            # Check if repo exists and is accessible
            result = subprocess.run(
                ["git", "ls-remote", "--heads", self.repo_url, self.branch],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                if "not found" in result.stderr.lower() or "not a repository" in result.stderr.lower():
                    self.log(
                        f"Repository not found or not accessible: {self.repo_url}",
                        "ERROR",
                    )
                else:
                    self.log(f"Failed to access repository: {result.stderr.strip()}", "ERROR")
                return False

            self.log(f"✓ Repository accessible", "SUCCESS")

            # Validation of path will happen during checkout
            return True

        except subprocess.TimeoutExpired:
            self.log("Repository validation timed out. Check your internet connection.", "ERROR")
            return False
        except FileNotFoundError:
            self.log(
                "Git is not installed or not in PATH. "
                "Please install git to use this skill.",
                "ERROR",
            )
            return False

    def setup_temp_workspace(self) -> bool:
        """Create isolated temporary workspace."""
        self.log("🔧 Setting up temporary workspace...", "INFO")

        try:
            self.temp_dir = tempfile.mkdtemp(prefix="skill_download_")
            self.work_dir = Path(self.temp_dir)
            self.log(f"Workspace created: {self.temp_dir}", "INFO")
            return True
        except Exception as e:
            self.log(f"Failed to create temporary directory: {e}", "ERROR")
            return False

    def init_sparse_checkout(self) -> bool:
        """Initialize Git repo with sparse-checkout."""
        self.log("📥 Initializing sparse checkout...", "INFO")

        try:
            # Initialize git
            subprocess.run(
                ["git", "init"],
                cwd=self.work_dir,
                capture_output=True,
                check=True,
            )

            # Add remote
            subprocess.run(
                ["git", "remote", "add", "origin", self.repo_url],
                cwd=self.work_dir,
                capture_output=True,
                check=True,
            )

            # Enable sparse-checkout
            subprocess.run(
                ["git", "config", "core.sparseCheckout", "true"],
                cwd=self.work_dir,
                capture_output=True,
                check=True,
            )

            # Configure sparse-checkout file
            sparse_file = self.work_dir / ".git" / "info" / "sparse-checkout"
            sparse_file.parent.mkdir(parents=True, exist_ok=True)
            sparse_file.write_text(f"{self.repo_path}/*\n")

            self.log("Sparse checkout configured", "INFO")
            return True

        except subprocess.CalledProcessError as e:
            self.log(f"Git configuration failed: {e.stderr.decode() if e.stderr else e}", "ERROR")
            return False

    def pull_content(self) -> bool:
        """Fetch the specific directory."""
        self.log(f"📡 Pulling {self.repo_path} from {self.branch}...", "INFO")

        try:
            result = subprocess.run(
                ["git", "pull", "origin", self.branch],
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                if "does not have" in result.stderr or "not found" in result.stderr:
                    self.log(
                        f"Path '{self.repo_path}' not found in repository or branch '{self.branch}'.",
                        "ERROR",
                    )
                else:
                    self.log(f"Pull failed: {result.stderr.strip()}", "ERROR")
                return False

            self.log("Content pulled successfully", "SUCCESS")
            return True

        except subprocess.TimeoutExpired:
            self.log("Pull operation timed out. Check your internet connection.", "ERROR")
            return False
        except Exception as e:
            self.log(f"Unexpected error during pull: {e}", "ERROR")
            return False

    def _resolve_dest(self) -> Path:
        """Resolve destination to an absolute path anchored to project_dir."""
        dest = Path(self.destination).expanduser()
        if not dest.is_absolute():
            dest = self.project_dir / dest
        return dest

    def extract_and_move(self) -> bool:
        """Extract downloaded content and move to destination."""
        self.log("📦 Extracting content...", "INFO")

        try:
            # Find the source directory
            source = self.work_dir / self.repo_path
            if not source.exists():
                self.log(f"Extracted path not found: {source}", "ERROR")
                return False

            # Prepare destination — always resolved to an absolute path so
            # the result is independent of the shell's current working directory.
            dest_path = self._resolve_dest()
            if not dest_path.exists():
                dest_path.mkdir(parents=True, exist_ok=True)
                self.log(f"Created destination directory: {dest_path}", "INFO")

            # Get folder name
            folder_name = source.name

            # Check if destination already exists
            final_dest = dest_path / folder_name
            if final_dest.exists():
                self.log(
                    f"Destination already exists: {final_dest}",
                    "WARNING",
                )
                response = (
                    input("Overwrite? (y/n) [n]: ").strip().lower()
                )
                if response != "y":
                    self.log("Download cancelled", "INFO")
                    return False
                shutil.rmtree(final_dest)
                self.log(f"Removed existing: {final_dest}", "INFO")

            # Copy content
            shutil.copytree(source, final_dest)
            self.log(f"Extracted to: {final_dest}", "SUCCESS")
            return True

        except Exception as e:
            self.log(f"Extraction failed: {e}", "ERROR")
            return False

    def cleanup_git_artifacts(self) -> bool:
        """Remove all git-related files and directories."""
        self.log("🧹 Cleaning git artifacts...", "INFO")

        try:
            dest_path = self._resolve_dest()
            folder_name = Path(self.repo_path).name
            target = dest_path / folder_name

            removed_count = 0

            # Remove .git directories
            for git_dir in target.rglob(".git"):
                shutil.rmtree(git_dir)
                removed_count += 1

            # Remove git-related files
            git_files = [
                ".gitignore",
                ".gitattributes",
                ".gitmodules",
                ".github",
                "CODEOWNERS",
                ".gitkeep",
            ]

            for git_file in git_files:
                for item in target.rglob(git_file):
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                    removed_count += 1

            if removed_count > 0:
                self.log(f"Removed {removed_count} git-related items", "SUCCESS")
            else:
                self.log("No git artifacts found (expected for clean content)", "INFO")
            return True

        except Exception as e:
            self.log(f"Warning during artifact cleanup: {e}", "WARNING")
            # Don't fail on cleanup issues, as the essential content is there
            return True

    def cleanup_empty_directories(self) -> bool:
        """Remove empty directories."""
        self.log("🧹 Cleaning empty directories...", "INFO")

        try:
            dest_path = self._resolve_dest()
            folder_name = Path(self.repo_path).name
            target = dest_path / folder_name

            removed_count = 0

            # Remove empty directories (bottom-up)
            for dirpath in sorted(target.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                if dirpath.is_dir() and not list(dirpath.iterdir()):
                    dirpath.rmdir()
                    removed_count += 1

            if removed_count > 0:
                self.log(f"Removed {removed_count} empty directories", "INFO")
            return True

        except Exception as e:
            self.log(f"Warning during directory cleanup: {e}", "WARNING")
            return True

    def cleanup_temp_workspace(self) -> bool:
        """Remove temporary workspace."""
        self.log("🗑️  Removing temporary workspace...", "INFO")

        try:
            if self.temp_dir and Path(self.temp_dir).exists():
                shutil.rmtree(self.temp_dir)
                self.log("Temporary workspace cleaned up", "SUCCESS")
            return True
        except Exception as e:
            self.log(f"Warning: Could not fully clean temporary workspace: {e}", "WARNING")
            return True

    def run(self) -> bool:
        """Execute the full download process."""
        print("\n" + "=" * 60)
        print("🎯 Skill Downloader - GitHub Repository Download Utility")
        print("=" * 60 + "\n")

        # Get user input
        if not self.get_repo_details():
            return False

        print()
        if not self.select_destination():
            return False

        print()
        if not self.validate_repo():
            return False

        print()
        if not self.setup_temp_workspace():
            return False

        print()
        if not self.init_sparse_checkout():
            self.cleanup_temp_workspace()
            return False

        print()
        if not self.pull_content():
            self.cleanup_temp_workspace()
            return False

        print()
        if not self.extract_and_move():
            self.cleanup_temp_workspace()
            return False

        print()
        self.cleanup_git_artifacts()

        print()
        self.cleanup_empty_directories()

        print()
        self.cleanup_temp_workspace()

        # Success summary
        print()
        print("=" * 60)
        self.log("Download completed successfully!", "SUCCESS")
        print("=" * 60)
        dest_path = self._resolve_dest()
        folder_name = Path(self.repo_path).name
        final_location = dest_path / folder_name
        self.log(f"Content available at: {final_location}", "INFO")
        print()
        return True


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Download a specific folder from a GitHub repository."
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=None,
        help=(
            "Absolute path to the project root. Relative destination paths "
            "(e.g. .claude/skills) are resolved against this directory. "
            "Defaults to the current working directory at invocation time."
        ),
    )
    args = parser.parse_args()

    downloader = RepoDownloader(project_dir=args.project_dir)
    success = downloader.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
