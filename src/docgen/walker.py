"""Walk a repo directory and yield root-relative POSIX file paths, honouring excludes."""

from __future__ import annotations

from pathlib import Path, PurePath
from typing import Iterator

from .config import Config, load_config


def walk_repo(config: Config, repo_root: str | Path = ".") -> Iterator[str]:
    """Walk the repository and yield root-relative POSIX paths for Python files.

    Args:
        config: Configuration containing root, source_root, and exclude patterns.
        repo_root: The root directory of the repository (default: current directory).

    Yields:
        Root-relative POSIX paths (forward slashes) of .py files that are not excluded.
    """
    repo_root = Path(repo_root).resolve()
    root_dir = (repo_root / config.root).resolve()

    if not root_dir.exists():
        return

    # Build exclude patterns as absolute paths for matching
    exclude_dirs = set()
    for pattern in config.exclude:
        # Try to resolve each exclude pattern relative to repo_root
        try:
            exclude_path = (repo_root / pattern).resolve()
            if exclude_path.exists():
                exclude_dirs.add(exclude_path)
        except (OSError, ValueError):
            # Pattern might be a glob or non-existent; skip for dir matching
            pass

    for py_file in root_dir.rglob("*.py"):
        # Skip if file is in an excluded directory
        try:
            file_path = py_file.resolve()
        except OSError:
            continue

        # Check if any parent directory is in exclude_dirs
        is_excluded = False
        for parent in file_path.parents:
            if parent in exclude_dirs:
                is_excluded = True
                break
        if is_excluded:
            continue

        # Check if the file path itself matches any exclude pattern (substring)
        file_str = str(file_path)
        if any(pattern in file_str for pattern in config.exclude if pattern):
            continue

        # Yield root-relative POSIX path
        try:
            rel = file_path.relative_to(repo_root)
        except ValueError:
            # File is not under repo_root (shouldn't happen), skip
            continue

        yield PurePath(rel).as_posix()


def walk_repo_from_toml(
    config_path: str | Path = "docgen.toml",
    repo_root: str | Path = "."
) -> Iterator[str]:
    """Convenience function: load config and walk the repo in one call.

    Args:
        config_path: Path to the docgen.toml file.
        repo_root: The root directory of the repository.

    Yields:
        Root-relative POSIX paths of .py files that are not excluded.
    """
    config = load_config(config_path)
    yield from walk_repo(config, repo_root)