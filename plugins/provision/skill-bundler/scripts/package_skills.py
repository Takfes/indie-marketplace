#!/usr/bin/env python3
"""
Package Claude skills into zip archives.

Copies skill folders from source locations to a destination directory and creates
zip archives of each skill, preserving the originals.

Usage:
    python package_skills.py /path/to/skill1 /path/to/skill2 --dest /output/dir
    python package_skills.py /path/to/skill1 --dest /output/dir --keep-dirs
    python package_skills.py --list /path/to/skills/directory
    python package_skills.py /path/to/skill1 --dest /output/dir --dry-run
"""

import argparse
import shutil
import sys
from pathlib import Path
from typing import List


def validate_skill_dir(skill_path: Path) -> bool:
    """
    Validate that a directory is a valid Claude skill.

    A valid skill must contain a SKILL.md file.

    Args:
        skill_path: Path to the skill directory

    Returns:
        True if valid, False otherwise
    """
    return (skill_path / "SKILL.md").exists()


def validate_skill_structure(skill_path: Path) -> tuple[list[str], dict]:
    """
    Check that SKILL.md has required frontmatter fields.

    Parses YAML frontmatter to properly extract metadata without external dependencies.

    Args:
        skill_path: Path to the skill directory

    Returns:
        Tuple of (missing_fields, frontmatter_dict). Missing_fields is empty if all present.
    """
    skill_md = skill_path / "SKILL.md"
    content = skill_md.read_text()

    # Extract YAML frontmatter (between --- delimiters)
    if not content.startswith("---"):
        return ["name", "description"], {}

    try:
        parts = content.split("---", 2)
        if len(parts) < 3:
            return ["name", "description"], {}

        frontmatter_text = parts[1]
        frontmatter = {}

        # Simple YAML parsing for key: value pairs
        for line in frontmatter_text.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip().strip('"\'')
                frontmatter[key] = value

        missing = []
        for field in ("name", "description"):
            if field not in frontmatter:
                missing.append(field)

        return missing, frontmatter
    except Exception:
        return ["name", "description"], {}


def count_files_and_size(skill_dir: Path) -> tuple[int, int]:
    """
    Count files and calculate total size of a skill directory.

    Args:
        skill_dir: Path to the skill directory

    Returns:
        Tuple of (file_count, total_size_bytes)
    """
    file_count = 0
    total_size = 0
    for file_path in skill_dir.rglob("*"):
        if file_path.is_file():
            file_count += 1
            total_size += file_path.stat().st_size
    return file_count, total_size


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def list_skills(skills_dir: str) -> None:
    """List all valid skill directories in a given directory."""
    dir_path = Path(skills_dir).expanduser().absolute()
    if not dir_path.exists():
        print(f"❌ Directory does not exist: {dir_path}")
        sys.exit(1)

    skills = [d for d in sorted(dir_path.iterdir())
              if d.is_dir() and validate_skill_dir(d)]

    if not skills:
        print(f"No valid skills found in {dir_path}")
        return

    print(f"\n📚 Skills in {dir_path} ({len(skills)} found):\n")
    for skill in skills:
        print(f"  • {skill.name}")
    print()


def copy_skill(src: Path, dest_dir: Path) -> Path:
    """
    Copy a skill directory to the destination.

    Args:
        src: Source skill directory path
        dest_dir: Destination parent directory

    Returns:
        Path to the copied skill directory
    """
    dest_skill = dest_dir / src.name

    if dest_skill.exists():
        print(f"  ⚠️  {dest_skill.name}/ already exists, skipping copy")
        return dest_skill

    shutil.copytree(src, dest_skill)
    print(f"  ✅ Copied {src.name}/ → {dest_skill.name}/")
    return dest_skill


def zip_skill(skill_dir: Path, output_dir: Path) -> Path:
    """
    Create a zip archive of a skill directory.

    The zip file is created in the output directory with the skill name.
    If the zip already exists, skip creation.

    Args:
        skill_dir: Path to the skill directory
        output_dir: Directory where the zip will be created

    Returns:
        Path to the created zip file
    """
    zip_path = output_dir / f"{skill_dir.name}.zip"

    if zip_path.exists():
        print(f"  ⏭️  {skill_dir.name}.zip already exists, skipping")
        return zip_path

    # Use the parent of skill_dir as base_dir so paths inside zip are relative
    shutil.make_archive(
        str(zip_path.with_suffix('')),  # Remove .zip, make_archive adds it
        'zip',
        root_dir=skill_dir.parent,
        base_dir=skill_dir.name
    )

    print(f"  📦 Created {skill_dir.name}.zip")
    return zip_path


def package_skills(
    skill_paths: List[str],
    dest_dir: str,
    keep_dirs: bool = False,
    no_validate: bool = False,
    dry_run: bool = False
) -> None:
    """
    Package multiple skills into zip archives.

    Args:
        skill_paths: List of paths to skill directories
        dest_dir: Destination directory for copies and zips
        keep_dirs: If True, keep copied directories after zipping
        no_validate: If True, skip SKILL.md structure validation warnings
        dry_run: If True, show what would be packaged without executing
    """
    dest_path = Path(dest_dir).expanduser().absolute()
    if not dry_run:
        dest_path.mkdir(parents=True, exist_ok=True)

    mode_str = "(DRY RUN)" if dry_run else ""
    print(f"\n📂 Destination: {dest_path} {mode_str}\n")

    failed = []
    packaged = []

    for skill_path_str in skill_paths:
        skill_path = Path(skill_path_str).expanduser().absolute()

        if not skill_path.exists():
            print(f"❌ {skill_path} does not exist")
            failed.append(skill_path_str)
            continue

        if not skill_path.is_dir():
            print(f"❌ {skill_path} is not a directory")
            failed.append(skill_path_str)
            continue

        if not validate_skill_dir(skill_path):
            print(f"❌ {skill_path} is not a valid Claude skill (no SKILL.md)")
            failed.append(skill_path_str)
            continue

        # Skip entirely if destination zip already exists
        zip_path = dest_path / f"{skill_path.name}.zip"
        if zip_path.exists() and not dry_run:
            print(f"⏭️  {skill_path.name}: destination zip exists, skipping entirely")
            print()
            continue

        if not no_validate:
            missing_fields, frontmatter = validate_skill_structure(skill_path)
            if missing_fields:
                print(f"  ⚠️  Warning: SKILL.md missing fields: {', '.join(missing_fields)}")

        # Calculate skill size and file count
        file_count, skill_size = count_files_and_size(skill_path)

        print(f"📦 Processing {skill_path.name}...")
        print(f"   Files: {file_count} | Size: {format_size(skill_size)}")

        if dry_run:
            print(f"   (DRY RUN) Would create: {skill_path.name}.zip")
            print()
            packaged.append((skill_path.name, file_count, skill_size))
            continue

        # Copy skill
        copied_skill = copy_skill(skill_path, dest_path)

        # Create zip
        zip_result = zip_skill(copied_skill, dest_path)

        # Get actual zip size
        actual_zip_size = zip_result.stat().st_size if zip_result.exists() else 0

        # Remove copied directory if not keeping
        if not keep_dirs:
            shutil.rmtree(copied_skill)
            print(f"  🗑️  Removed temporary {skill_path.name}/ directory")

        print(f"   Archive: {format_size(actual_zip_size)}")
        packaged.append((skill_path.name, file_count, actual_zip_size))
        print()

    if failed:
        print(f"⚠️  {len(failed)} skill(s) failed to process:")
        for path in failed:
            print(f"  - {path}")
        if not dry_run:
            sys.exit(1)
        else:
            print("\n(Dry run: No skills were actually packaged)")
            sys.exit(1)

    if dry_run:
        print("✨ Dry run complete! Ready to package.")
        if packaged:
            print(f"\nWill package {len(packaged)} skill(s):")
            for name, count, size in packaged:
                print(f"  • {name}: {count} files → {format_size(size)}")
    else:
        print("✨ Packaging complete!")
        if packaged:
            print(f"\nPackaged {len(packaged)} skill(s):")
            total_files = sum(c for _, c, _ in packaged)
            total_size = sum(s for _, _, s in packaged)
            for name, count, size in packaged:
                print(f"  • {name}: {count} files → {format_size(size)}")
            print(f"\nTotal: {total_files} files → {format_size(total_size)}")


def main():
    parser = argparse.ArgumentParser(
        description="Package Claude skills into zip archives"
    )
    parser.add_argument(
        "skills",
        nargs="*",  # Changed from "+" to "*" to allow --list without positional args
        help="Paths to skill directories to package"
    )
    parser.add_argument(
        "--dest",
        required=False,
        default=None,
        help="Destination directory for zip files (default: zip-skills/ in current directory)"
    )
    parser.add_argument(
        "--keep-dirs",
        action="store_true",
        help="Keep copied skill directories (don't delete after zipping)"
    )
    parser.add_argument(
        "--list",
        metavar="DIR",
        help="List all valid skills in a directory without packaging"
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip SKILL.md structure validation warnings"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be packaged without executing"
    )

    args = parser.parse_args()

    if args.list:
        list_skills(args.list)
        return

    if not args.skills:
        parser.error("skills are required when not using --list")

    if args.dest is None:
        default_dest = Path("zip-skills")
        if not default_dest.exists() and not args.dry_run:
            print("❌ Default destination 'zip-skills/' does not exist in the current directory.")
            print("   Create it first, or specify a destination with --dest.")
            sys.exit(1)
        args.dest = str(default_dest)

    package_skills(args.skills, args.dest, args.keep_dirs, args.no_validate, args.dry_run)


if __name__ == "__main__":
    main()
