"""Freshness gate integration tests (task 3.5).

Tests run against the small fixture repo in tests/fixtures/freshness/ so they
never touch the real target/ directory.  All LLM calls are replaced by
StubSummarizer.

Scenarios:
    1. Fresh render → docgen check → exit 0 (no stale pages).
    2. Edit one source file (structural change) → re-extract → check → exit 1,
       names the correct page.
    3. docgen update → docgen check → exit 0.
    4. Harmless edit (comment only) → re-extract → check → exit 0 (no false positive).
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "freshness"


def _copy_fixture(tmp_path: Path) -> Path:
    """Copy the freshness fixture repo into tmp_path and return the toml path."""
    for src in FIXTURES_DIR.iterdir():
        dst = tmp_path / src.name
        if src.is_file():
            shutil.copy2(src, dst)
    return tmp_path / "docgen.toml"


def _extract(toml_path: Path) -> None:
    from docgen.cli import _run_extract
    _run_extract(argparse.Namespace(config=str(toml_path)))


def _summarize(toml_path: Path) -> None:
    from docgen.cli import _run_summarize
    _run_summarize(argparse.Namespace(config=str(toml_path), backend="stub", max_cost=2.0, max_turns=10))


def _render(toml_path: Path) -> None:
    from docgen.cli import _run_render
    _run_render(argparse.Namespace(config=str(toml_path)))


def _check(toml_path: Path) -> list[str]:
    """Run docgen check; return list of stale page paths (empty means exit 0)."""
    from docgen.check.drift import find_stale_pages
    from docgen.check.manifest import read_manifest
    from docgen.config import load_config
    from docgen.facts.store import read_facts

    config = load_config(toml_path)
    repo_root = toml_path.parent.resolve()
    output_dir = repo_root / config.output_dir

    graph = read_facts(output_dir / "facts.json")
    manifest = read_manifest(output_dir / "manifest.json")
    return find_stale_pages(manifest, graph)


def _update(toml_path: Path) -> None:
    from docgen.cli import _run_update
    _run_update(argparse.Namespace(config=str(toml_path), backend="stub"))


# ---------------------------------------------------------------------------
# Test 1: Fresh render → check passes (no stale pages)
# ---------------------------------------------------------------------------

def test_freshness_gate_fresh_run_passes(tmp_path: Path) -> None:
    """After a clean extract + summarize + render, docgen check finds no stale pages."""
    toml_path = _copy_fixture(tmp_path)
    _extract(toml_path)
    _summarize(toml_path)
    _render(toml_path)

    stale = _check(toml_path)
    assert stale == [], f"Expected no stale pages but got: {stale}"


# ---------------------------------------------------------------------------
# Test 2: Structural change → check fails, names the right page
# ---------------------------------------------------------------------------

def test_freshness_gate_structural_change_detected(tmp_path: Path) -> None:
    """Changing a function signature makes its module page stale (exit 1)."""
    toml_path = _copy_fixture(tmp_path)
    _extract(toml_path)
    _summarize(toml_path)
    _render(toml_path)

    # Mutate main.py: change the function signature (structural change → hash_struct changes)
    main_py = tmp_path / "main.py"
    original = main_py.read_text(encoding="utf-8")
    mutated = original.replace(
        "def farewell(name: str) -> str:",
        "def farewell(name: str, formal: bool = False) -> str:",
    )
    assert mutated != original, "Mutation did not change the file"
    main_py.write_text(mutated, encoding="utf-8")

    # Re-extract with the mutated file
    _extract(toml_path)

    stale = _check(toml_path)
    assert len(stale) > 0, "Expected at least one stale page after structural change"
    # The stale page must be main.py's page
    assert any("main" in p for p in stale), f"main page not in stale list: {stale}"


# ---------------------------------------------------------------------------
# Test 3: update rebuilds stale pages → check passes
# ---------------------------------------------------------------------------

def test_freshness_gate_update_fixes_staleness(tmp_path: Path) -> None:
    """After docgen update, docgen check finds no stale pages."""
    toml_path = _copy_fixture(tmp_path)
    _extract(toml_path)
    _summarize(toml_path)
    _render(toml_path)

    # Introduce the same structural change as test 2
    main_py = tmp_path / "main.py"
    original = main_py.read_text(encoding="utf-8")
    mutated = original.replace(
        "def farewell(name: str) -> str:",
        "def farewell(name: str, formal: bool = False) -> str:",
    )
    main_py.write_text(mutated, encoding="utf-8")
    _extract(toml_path)

    # Update must fix the staleness
    _update(toml_path)

    stale = _check(toml_path)
    assert stale == [], f"Expected no stale pages after update but got: {stale}"


# ---------------------------------------------------------------------------
# Test 4: Harmless comment edit → no false positive drift
# ---------------------------------------------------------------------------

def test_freshness_gate_comment_edit_no_drift(tmp_path: Path) -> None:
    """Adding a comment changes hash_source but not hash_struct → not stale."""
    toml_path = _copy_fixture(tmp_path)
    _extract(toml_path)
    _summarize(toml_path)
    _render(toml_path)

    # Add a comment line — only affects hash_source, not hash_struct
    main_py = tmp_path / "main.py"
    original = main_py.read_text(encoding="utf-8")
    with_comment = original + "\n# This is a harmless comment added to main.py\n"
    main_py.write_text(with_comment, encoding="utf-8")

    _extract(toml_path)

    stale = _check(toml_path)
    assert stale == [], (
        f"Comment-only edit should not cause drift, but got stale pages: {stale}"
    )
