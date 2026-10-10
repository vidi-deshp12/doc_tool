"""Tests for the `docgen extract` CLI command."""

from __future__ import annotations

import json
import sys
import textwrap
from io import StringIO
from pathlib import Path

import pytest


def _write(tmp_path: Path, rel: str, src: str) -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(src), encoding="utf-8")
    return p


def _make_fixture_repo(tmp_path: Path) -> Path:
    """Create a minimal repo with docgen.toml and a couple of Python files."""
    # Python package
    _write(tmp_path, "myapp/__init__.py", "")
    _write(tmp_path, "myapp/utils.py", """
        def add(a: int, b: int) -> int:
            return a + b
    """)
    _write(tmp_path, "myapp/service.py", """
        from myapp.utils import add

        def double(x: int) -> int:
            return add(x, x)
    """)

    # docgen.toml pointing at tmp_path as the repo root
    toml = (
        "[repo]\n"
        f'root = "."\n'
        f'source_root = "."\n'
        'exclude = []\n'
        "\n[adapter]\n"
        'name = "none"\n'
        "\n[output]\n"
        f'dir = "out"\n'
    )
    toml_path = tmp_path / "docgen.toml"
    toml_path.write_text(toml, encoding="utf-8")
    return toml_path


# ---------------------------------------------------------------------------
# Test 1: extract writes facts.json with expected structure
# ---------------------------------------------------------------------------

def test_extract_writes_facts_json(tmp_path: Path) -> None:
    """docgen extract produces a valid facts.json with nodes, edges, unresolved."""
    toml_path = _make_fixture_repo(tmp_path)

    import argparse
    from docgen.cli import _run_extract

    args = argparse.Namespace(config=str(toml_path))
    _run_extract(args)

    facts_path = tmp_path / "out" / "facts.json"
    assert facts_path.exists(), "facts.json was not created"

    data = json.loads(facts_path.read_text(encoding="utf-8"))
    assert "nodes" in data
    assert "edges" in data
    assert "unresolved" in data
    assert isinstance(data["nodes"], list)
    assert len(data["nodes"]) > 0


# ---------------------------------------------------------------------------
# Test 2: extract prints unresolved summary to stdout
# ---------------------------------------------------------------------------

def test_extract_prints_unresolved_summary(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """docgen extract prints a count line to stdout."""
    toml_path = _make_fixture_repo(tmp_path)

    import argparse
    from docgen.cli import _run_extract

    args = argparse.Namespace(config=str(toml_path))
    _run_extract(args)

    captured = capsys.readouterr()
    # stdout must contain the count line
    assert "unresolved entr" in captured.out or "0 unresolved entries" in captured.out


# ---------------------------------------------------------------------------
# Test 3: extract with a star import produces WARN line in stdout
# ---------------------------------------------------------------------------

def test_extract_star_import_appears_in_summary(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """A file with `from os import *` → WARN [star_import] line in stdout."""
    _write(tmp_path, "myapp/__init__.py", "")
    _write(tmp_path, "myapp/bad.py", """
        from os import *

        def get_path():
            return getcwd()
    """)
    toml = (
        "[repo]\n"
        'root = "."\n'
        'source_root = "."\n'
        'exclude = []\n'
        "\n[adapter]\n"
        'name = "none"\n'
        "\n[output]\n"
        'dir = "out"\n'
    )
    (tmp_path / "docgen.toml").write_text(toml, encoding="utf-8")

    import argparse
    from docgen.cli import _run_extract

    args = argparse.Namespace(config=str(tmp_path / "docgen.toml"))
    _run_extract(args)

    captured = capsys.readouterr()
    assert "WARN [star_import]" in captured.out
    assert "star_import" in captured.out


# ---------------------------------------------------------------------------
# Test 4: _print_unresolved_summary formats correctly
# ---------------------------------------------------------------------------

def test_print_unresolved_summary_format(capsys: pytest.CaptureFixture) -> None:
    """_print_unresolved_summary produces the expected linter-style lines."""
    from docgen.cli import _print_unresolved_summary
    from docgen.facts.schema import Unresolved

    entries = [
        Unresolved(what="star_import", why="from os import *", where="foo.py:3"),
        Unresolved(what="dynamic_import", why="__import__('x')", where="bar.py:7"),
    ]
    _print_unresolved_summary(entries)

    out = capsys.readouterr().out
    assert "WARN [star_import] foo.py:3 — from os import *" in out
    assert "WARN [dynamic_import] bar.py:7 — __import__('x')" in out
    assert "2 unresolved entries" in out
    assert "1 dynamic_import" in out
    assert "1 star_import" in out


# ---------------------------------------------------------------------------
# Test 5: zero unresolved prints "0 unresolved entries"
# ---------------------------------------------------------------------------

def test_print_unresolved_summary_zero(capsys: pytest.CaptureFixture) -> None:
    """Empty unresolved list → prints '0 unresolved entries'."""
    from docgen.cli import _print_unresolved_summary

    _print_unresolved_summary([])
    out = capsys.readouterr().out
    assert "0 unresolved entries" in out
