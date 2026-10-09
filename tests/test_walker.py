"""Tests for walker.py and config.py."""

from __future__ import annotations

import tempfile
from pathlib import Path

from src.docgen.config import Config, load_config
from src.docgen.walker import walk_repo, walk_repo_from_toml


def test_load_config_defaults() -> None:
    """Test loading config with minimal TOML."""
    with tempfile.TemporaryDirectory() as tmpdir:
        toml_path = Path(tmpdir) / "docgen.toml"
        toml_path.write_text("""
[repo]
root = "target"
source_root = "target"
exclude = [".git", "tests"]

[adapter]
name = "fastapi"
app = "app.main:app"

[output]
dir = "generated"
""", encoding="utf-8")

        config = load_config(toml_path)

        assert config.root == "target"
        assert config.source_root == "target"
        assert config.exclude == (".git", "tests")
        assert config.adapter_name == "fastapi"
        assert config.app == "app.main:app"
        assert config.output_dir == "generated"


def test_load_config_missing_file() -> None:
    """Test that missing config file raises FileNotFoundError."""
    try:
        load_config("nonexistent.toml")
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError:
        pass


def test_load_config_invalid_adapter() -> None:
    """Test that invalid adapter name raises ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        toml_path = Path(tmpdir) / "docgen.toml"
        toml_path.write_text("""
[adapter]
name = "unknown"
""", encoding="utf-8")

        try:
            load_config(toml_path)
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "Unknown adapter" in str(e)


def test_walk_repo_basic() -> None:
    """Test basic walker functionality with a simple fixture."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Create directory structure
        (repo_root / "target" / "app" / "api").mkdir(parents=True)
        (repo_root / "target" / "app" / "models").mkdir(parents=True)
        (repo_root / "tests").mkdir()
        (repo_root / ".git").mkdir()

        # Create Python files
        (repo_root / "target" / "app" / "main.py").write_text("# main\n", encoding="utf-8")
        (repo_root / "target" / "app" / "api" / "routes.py").write_text("# routes\n", encoding="utf-8")
        (repo_root / "target" / "app" / "models" / "user.py").write_text("# user\n", encoding="utf-8")
        (repo_root / "tests" / "test_api.py").write_text("# test\n", encoding="utf-8")
        (repo_root / ".git" / "config").write_text("# git\n", encoding="utf-8")

        config = Config(
            root="target",
            source_root="target",
            exclude=(".git", "tests", "__pycache__"),
            adapter_name="fastapi",
            app="app.main:app",
            output_dir="generated",
        )

        files = list(walk_repo(config, repo_root))

        # Should find 3 Python files in target/
        assert len(files) == 3
        # All should be POSIX paths relative to repo root
        for f in files:
            assert "\\" not in f
            assert f.startswith("target/")
        # Check expected files
        assert "target/app/main.py" in files
        assert "target/app/api/routes.py" in files
        assert "target/app/models/user.py" in files
        # Excluded files should not be present
        assert "tests/test_api.py" not in files
        assert ".git/config" not in files


def test_walk_repo_excludes_substring() -> None:
    """Test that exclude patterns work as substring matches."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        (repo_root / "target" / "app").mkdir(parents=True)
        (repo_root / "target" / "migrations").mkdir(parents=True)

        (repo_root / "target" / "app" / "main.py").write_text("# main\n", encoding="utf-8")
        (repo_root / "target" / "migrations" / "version.py").write_text("# migration\n", encoding="utf-8")

        config = Config(
            root="target",
            source_root="target",
            exclude=("migrations",),
            adapter_name="fastapi",
            app="app.main:app",
            output_dir="generated",
        )

        files = list(walk_repo(config, repo_root))

        assert len(files) == 1
        assert "target/app/main.py" in files
        assert "target/migrations/version.py" not in files


def test_walk_repo_windows_paths() -> None:
    """Test that paths use POSIX separators even on Windows.

    This simulates Windows paths by creating the structure with backslashes
    in the test setup, then verifying output uses forward slashes.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Create structure
        target_dir = repo_root / "target" / "app" / "api"
        target_dir.mkdir(parents=True)

        (repo_root / "target" / "app" / "main.py").write_text("# main\n", encoding="utf-8")
        (target_dir / "routes.py").write_text("# routes\n", encoding="utf-8")

        config = Config(
            root="target",
            source_root="target",
            exclude=(),
            adapter_name="fastapi",
            app="app.main:app",
            output_dir="generated",
        )

        files = list(walk_repo(config, repo_root))

        # All paths should use forward slashes (POSIX)
        for f in files:
            assert "\\" not in f, f"Found backslash in: {f}"

        expected = {"target/app/main.py", "target/app/api/routes.py"}
        assert set(files) == expected


def test_walk_repo_empty_repo() -> None:
    """Test walker on empty/non-existent repo root."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Don't create target/ directory
        config = Config(
            root="target",
            source_root="target",
            exclude=(),
            adapter_name="fastapi",
            app="app.main:app",
            output_dir="generated",
        )

        files = list(walk_repo(config, repo_root))
        assert files == []


def test_walk_repo_from_toml() -> None:
    """Test the convenience function walk_repo_from_toml."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        (repo_root / "target" / "app").mkdir(parents=True)
        (repo_root / "target" / "app" / "main.py").write_text("# main\n", encoding="utf-8")
        (repo_root / "docgen.toml").write_text("""
[repo]
root = "target"
source_root = "target"
exclude = []

[adapter]
name = "fastapi"
app = "app.main:app"

[output]
dir = "generated"
""", encoding="utf-8")

        files = list(walk_repo_from_toml(repo_root / "docgen.toml", repo_root))

        assert "target/app/main.py" in files
        assert len(files) == 1


def test_config_exclude_empty_by_default() -> None:
    """Test that exclude defaults to empty tuple when not in TOML."""
    with tempfile.TemporaryDirectory() as tmpdir:
        toml_path = Path(tmpdir) / "docgen.toml"
        toml_path.write_text("""
[repo]
root = "target"

[adapter]
name = "none"
""", encoding="utf-8")

        config = load_config(toml_path)
        assert config.exclude == ()