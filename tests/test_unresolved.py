"""Tests for extract/unresolved.py — star_import, dynamic_import, getattr_dynamic detection."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from docgen.extract.modules import build_module_index
from docgen.extract.unresolved import scan_for_unresolved


def _write(tmp_path: Path, rel: str, src: str) -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(src), encoding="utf-8")
    return p


def _scan(tmp_path: Path, files: list[str]) -> list:
    dotted_to_path, path_to_info = build_module_index(files, tmp_path, source_root="")
    return scan_for_unresolved(files, path_to_info, tmp_path)


# ---------------------------------------------------------------------------
# Test 1: star_import detected
# ---------------------------------------------------------------------------

def test_star_import_detected(tmp_path: Path) -> None:
    """from os import * → one star_import Unresolved entry."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/mod.py", """
        from os import *
        from os.path import join
    """)
    entries = _scan(tmp_path, ["pkg/__init__.py", "pkg/mod.py"])
    star = [e for e in entries if e.what == "star_import"]
    assert len(star) == 1
    assert "from os import *" in star[0].why
    assert "pkg/mod.py" in star[0].where


# ---------------------------------------------------------------------------
# Test 2: __import__ detected as dynamic_import
# ---------------------------------------------------------------------------

def test_dunder_import_detected(tmp_path: Path) -> None:
    """__import__('x') → one dynamic_import entry."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/mod.py", """
        def load(name):
            mod = __import__(name)
            return mod
    """)
    entries = _scan(tmp_path, ["pkg/__init__.py", "pkg/mod.py"])
    dyn = [e for e in entries if e.what == "dynamic_import"]
    assert len(dyn) == 1
    assert "__import__" in dyn[0].why


# ---------------------------------------------------------------------------
# Test 3: importlib.import_module detected as dynamic_import
# ---------------------------------------------------------------------------

def test_importlib_import_module_detected(tmp_path: Path) -> None:
    """importlib.import_module('y') → one dynamic_import entry."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/mod.py", """
        import importlib

        def load(name):
            return importlib.import_module(name)
    """)
    entries = _scan(tmp_path, ["pkg/__init__.py", "pkg/mod.py"])
    dyn = [e for e in entries if e.what == "dynamic_import"]
    assert len(dyn) == 1
    assert "importlib.import_module" in dyn[0].why


# ---------------------------------------------------------------------------
# Test 4: getattr with non-literal name → getattr_dynamic
# ---------------------------------------------------------------------------

def test_getattr_dynamic_variable_name(tmp_path: Path) -> None:
    """getattr(obj, name_var) where name_var is not a literal → getattr_dynamic."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/mod.py", """
        def get_attr(obj, attr_name):
            return getattr(obj, attr_name)
    """)
    entries = _scan(tmp_path, ["pkg/__init__.py", "pkg/mod.py"])
    ga = [e for e in entries if e.what == "getattr_dynamic"]
    assert len(ga) == 1
    assert "getattr" in ga[0].why


# ---------------------------------------------------------------------------
# Test 5: getattr with string literal → NOT flagged
# ---------------------------------------------------------------------------

def test_getattr_literal_not_flagged(tmp_path: Path) -> None:
    """getattr(obj, 'literal') → no getattr_dynamic entry."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/mod.py", """
        def get_x(obj):
            return getattr(obj, 'x')
    """)
    entries = _scan(tmp_path, ["pkg/__init__.py", "pkg/mod.py"])
    ga = [e for e in entries if e.what == "getattr_dynamic"]
    assert ga == []


# ---------------------------------------------------------------------------
# Test 6: clean file → empty list
# ---------------------------------------------------------------------------

def test_clean_file_no_entries(tmp_path: Path) -> None:
    """A file with no dynamic patterns produces no unresolved entries."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/mod.py", """
        from os.path import join

        def greet(name: str) -> str:
            return join('hello', name)
    """)
    entries = _scan(tmp_path, ["pkg/__init__.py", "pkg/mod.py"])
    assert entries == []


# ---------------------------------------------------------------------------
# Test 7: Integration — real target/ repo scan doesn't crash
# ---------------------------------------------------------------------------

def test_real_repo_scan_does_not_crash() -> None:
    """scan_for_unresolved on the real target/ repo completes without error."""
    repo_root = Path(__file__).parent.parent
    if not (repo_root / "target").exists():
        pytest.skip("target/ repo not present")

    from docgen.config import load_config
    from docgen.walker import walk_repo

    config = load_config(repo_root / "docgen.toml")
    module_paths = list(walk_repo(config, repo_root=repo_root))
    _, path_to_info = build_module_index(
        module_paths, repo_root, source_root=config.source_root
    )
    entries = scan_for_unresolved(module_paths, path_to_info, repo_root)
    # Target is clean — just assert no crash and result is a list
    assert isinstance(entries, list)
