"""Tests for task 2b.4: citation validator.

All tests are offline: no LLM, no network, no filesystem I/O except for the two
end-to-end CLI tests that use tmp_path.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from docgen.summarize.base import SummaryResult
from docgen.summarize.citations import (
    CitationError,
    _split_sentences,
    format_report,
    validate_summaries,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _result(node_id: str, text: str) -> SummaryResult:
    return SummaryResult(node_id=node_id, text=text, backend="stub", hash_input="h")


# ---------------------------------------------------------------------------
# Test 1: fully valid summary produces no errors
# ---------------------------------------------------------------------------

def test_valid_summary_no_errors() -> None:
    summaries = [
        _result("mod.py::f", "Does a thing [[mod.py::f]]. Returns a value [[mod.py::f]]."),
    ]
    errors = validate_summaries(summaries, known_ids={"mod.py::f"})
    assert errors == []


# ---------------------------------------------------------------------------
# Test 2: unknown [[id]] is detected
# ---------------------------------------------------------------------------

def test_unknown_id_detected() -> None:
    summaries = [
        _result("mod.py::f", "Does a thing [[nonexistent.py::g]]."),
    ]
    errors = validate_summaries(summaries, known_ids={"mod.py::f"})
    assert len(errors) == 1
    assert errors[0].kind == "unknown_id"
    assert errors[0].node_id == "mod.py::f"
    assert errors[0].detail == "nonexistent.py::g"


# ---------------------------------------------------------------------------
# Test 3: uncited sentence is detected
# ---------------------------------------------------------------------------

def test_uncited_sentence_detected() -> None:
    summaries = [
        _result("mod.py::f", "Does a thing [[mod.py::f]]. This sentence has no citation."),
    ]
    errors = validate_summaries(summaries, known_ids={"mod.py::f"})
    assert len(errors) == 1
    assert errors[0].kind == "uncited_sentence"
    assert errors[0].node_id == "mod.py::f"
    assert "This sentence has no citation" in errors[0].detail


# ---------------------------------------------------------------------------
# Test 4: multiple errors in one summary (unknown id + uncited sentence)
# ---------------------------------------------------------------------------

def test_multiple_errors_in_one_summary() -> None:
    summaries = [
        _result(
            "mod.py::f",
            "Uses [[ghost.py::x]] which is unknown. No citation here at all.",
        )
    ]
    errors = validate_summaries(summaries, known_ids={"mod.py::f"})
    kinds = {e.kind for e in errors}
    assert "unknown_id" in kinds
    assert "uncited_sentence" in kinds
    assert len(errors) == 2


# ---------------------------------------------------------------------------
# Test 5: system node self-citation is valid
# ---------------------------------------------------------------------------

def test_system_node_self_cite_is_valid() -> None:
    """The stub produces [[system]] for the system summary; it must not trigger unknown_id."""
    summaries = [
        _result("system", "Stub summary for system [[system]]"),
    ]
    errors = validate_summaries(summaries, known_ids={"system"})
    assert errors == []


# ---------------------------------------------------------------------------
# Test 6: format_report with no errors
# ---------------------------------------------------------------------------

def test_format_report_no_errors() -> None:
    assert format_report([]) == "No citation errors.\n"


# ---------------------------------------------------------------------------
# Test 7: format_report with errors produces correct lines + count
# ---------------------------------------------------------------------------

def test_format_report_with_errors() -> None:
    errors = [
        CitationError(node_id="mod.py::f", kind="unknown_id", detail="ghost.py::x"),
        CitationError(node_id="mod.py::f", kind="uncited_sentence", detail="No citation."),
    ]
    report = format_report(errors)
    assert "ERROR [unknown_id] mod.py::f: ghost.py::x" in report
    assert "ERROR [uncited_sentence] mod.py::f: No citation." in report
    assert "2 citation errors found." in report


# ---------------------------------------------------------------------------
# Test 8: detail is truncated to 120 chars for long sentences
# ---------------------------------------------------------------------------

def test_detail_truncated_to_120_chars() -> None:
    long_sentence = "A" * 200
    summaries = [_result("mod.py", long_sentence)]
    errors = validate_summaries(summaries, known_ids={"mod.py"})
    # The sentence has no citation and no call exemption → uncited_sentence error.
    uncited = [e for e in errors if e.kind == "uncited_sentence"]
    assert len(uncited) == 1
    assert len(uncited[0].detail) <= 120


# ---------------------------------------------------------------------------
# Test 9: calls exemption — sentence mentioning a call target is exempt
# ---------------------------------------------------------------------------

def test_calls_exemption_exempts_sentence() -> None:
    """A sentence that mentions a raw call name is exempt from the citation rule."""
    summaries = [
        _result(
            "mod.py::f",
            "Calls articles_repo.create_article to persist data.",
        )
    ]
    calls_by_node = {"mod.py::f": {"articles_repo.create_article"}}
    errors = validate_summaries(summaries, known_ids={"mod.py::f"}, calls_by_node=calls_by_node)
    # No uncited_sentence error: the sentence mentions the call name.
    assert not any(e.kind == "uncited_sentence" for e in errors)


# ---------------------------------------------------------------------------
# Test 10: calls exemption does NOT suppress unknown_id errors
# ---------------------------------------------------------------------------

def test_calls_exemption_does_not_suppress_unknown_id() -> None:
    """The calls exemption only skips uncited_sentence; unknown IDs are still reported."""
    summaries = [
        _result(
            "mod.py::f",
            "Calls articles_repo.create_article [[nonexistent.py::g]].",
        )
    ]
    calls_by_node = {"mod.py::f": {"articles_repo.create_article"}}
    errors = validate_summaries(summaries, known_ids={"mod.py::f"}, calls_by_node=calls_by_node)
    assert any(e.kind == "unknown_id" and e.detail == "nonexistent.py::g" for e in errors)


# ---------------------------------------------------------------------------
# Test 11: sentence splitter handles multiple sentences correctly
# ---------------------------------------------------------------------------

def test_split_sentences_basic() -> None:
    text = "First sentence. Second sentence! Third sentence?"
    parts = _split_sentences(text)
    assert len(parts) == 3
    assert parts[0] == "First sentence."
    assert parts[1] == "Second sentence!"
    assert parts[2] == "Third sentence?"


def test_split_sentences_canonical_format() -> None:
    """Citations placed before the period (canonical format) stay with their sentence."""
    text = "Does a thing [[mod.py::f]]. Returns a value [[mod.py::f]]."
    parts = _split_sentences(text)
    assert len(parts) == 2
    assert "[[mod.py::f]]" in parts[0]
    assert "[[mod.py::f]]" in parts[1]


def test_split_sentences_empty_and_punctuation_only() -> None:
    assert _split_sentences("") == []
    assert _split_sentences("   ") == []
    # A fragment with no word characters is dropped.
    assert _split_sentences("... !!!") == []


# ---------------------------------------------------------------------------
# Test 12 & 13: CLI end-to-end tests
# ---------------------------------------------------------------------------

def _write_fixture(
    tmp_path: Path,
    summary_text: str,
    node_id: str = "mod.py::f",
) -> Path:
    """Write a minimal facts.json + summaries.json to tmp_path/out/ and return toml path."""
    (tmp_path / "mod.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    toml = (
        "[repo]\n"
        'root = "."\n'
        'source_root = "."\n'
        "exclude = []\n"
        "\n[adapter]\n"
        'name = "none"\n'
        "\n[output]\n"
        'dir = "out"\n'
    )
    toml_path = tmp_path / "docgen.toml"
    toml_path.write_text(toml, encoding="utf-8")

    from docgen.facts.schema import FactGraph, Node, NodeType
    from docgen.facts.store import write_facts
    from docgen.summarize.store import write_summaries

    func = Node(
        id=node_id,
        type=NodeType.FUNCTION,
        file="mod.py",
        lines=(1, 2),
        hash_struct="hs",
        hash_source="hsrc",
    )
    graph = FactGraph(nodes=(func,), edges=(), unresolved=())
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_facts(graph, out_dir / "facts.json")

    results = [SummaryResult(node_id=node_id, text=summary_text, backend="stub", hash_input="h")]
    write_summaries(results, out_dir / "summaries.json")

    return toml_path


def test_cli_validate_exits_0_on_clean(tmp_path: Path) -> None:
    """A fully-cited summary (canonical format) produces no errors and no SystemExit."""
    toml_path = _write_fixture(tmp_path, "Does a thing [[mod.py::f]].")

    from docgen.cli import _run_validate
    # Should not raise.
    _run_validate(argparse.Namespace(config=str(toml_path)))


def test_cli_validate_exits_1_on_errors(tmp_path: Path) -> None:
    """A summary with an uncited sentence causes SystemExit(1)."""
    toml_path = _write_fixture(tmp_path, "This sentence has no citation at all.")

    from docgen.cli import _run_validate
    with pytest.raises(SystemExit) as exc_info:
        _run_validate(argparse.Namespace(config=str(toml_path)))
    assert exc_info.value.code == 1
