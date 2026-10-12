"""Tests for task 2b.2: per-level prompts and the [[fact_id]] citation format.

All tests are offline and deterministic: no LLM, no network, no filesystem I/O.
"""

from __future__ import annotations

from docgen.summarize.base import NodeLevel, SummaryRequest, SummaryResult
from docgen.summarize.prompts import (
    CITATION_RE,
    LEVEL_INSTRUCTIONS,
    SYSTEM_PREAMBLE,
    allowed_fact_ids,
    build_prompt,
    extract_citations,
    format_citation,
    render_edges,
)


def _child(node_id: str, text: str = "child text") -> SummaryResult:
    return SummaryResult(node_id=node_id, text=text, backend="stub", hash_input="h")


def _make_request(**overrides) -> SummaryRequest:
    fields = dict(
        node_id="pkg/mod.py::f",
        level="function",
        facts={"file": "pkg/mod.py", "hash_struct": "hs", "hash_source": "hsrc"},
        source_text="def f():\n    return 1\n",
        child_summaries=[],
        edges=[],
    )
    fields.update(overrides)
    return SummaryRequest(**fields)


# ---------------------------------------------------------------------------
# Test 1: core sections are present
# ---------------------------------------------------------------------------

def test_build_prompt_includes_core_sections() -> None:
    prompt = build_prompt(_make_request())

    assert "PROMPT_VERSION:" in prompt
    assert "You are documenting a Python codebase" in prompt  # system preamble
    assert "## Your task" in prompt
    assert "## Citation rules" in prompt
    assert "## Allowed fact IDs" in prompt
    assert "## Node facts" in prompt
    assert "## Source" in prompt
    assert "## Output" in prompt
    # The shared grounding rule is present.
    assert "omit it rather than guess" in prompt


# ---------------------------------------------------------------------------
# Test 2: allowed ids are unioned, filtered, sorted, de-duplicated
# ---------------------------------------------------------------------------

def test_build_prompt_lists_allowed_ids_sorted() -> None:
    req = _make_request(
        node_id="pkg/mod.py::f",
        facts={"file": "pkg/mod.py", "parent_class": "pkg/mod.py::Cls"},
        child_summaries=[_child("pkg/mod.py::g")],
        edges=[
            {"type": "depends_on", "from": "pkg/mod.py::f", "to": "pkg/dep.py::d"},
            {"type": "inherits", "from": "pkg/mod.py::f", "to": "pkg/base.py::B"},
            {"type": "raises", "from": "pkg/mod.py::f", "to": "external:ValueError"},
            {"type": "calls", "from": "pkg/mod.py::f", "to": "Depends"},
        ],
    )

    assert allowed_fact_ids(req) == [
        "pkg/base.py::B",
        "pkg/dep.py::d",
        "pkg/mod.py",
        "pkg/mod.py::Cls",
        "pkg/mod.py::f",
        "pkg/mod.py::g",
    ]

    # Excluded: external: targets and bare call names.
    allowed = allowed_fact_ids(req)
    assert "external:ValueError" not in allowed
    assert "Depends" not in allowed


# ---------------------------------------------------------------------------
# Test 3: every level is distinct and used by build_prompt
# ---------------------------------------------------------------------------

def test_build_prompt_per_level_distinct() -> None:
    levels: list[NodeLevel] = [
        "function",
        "method",
        "class",
        "module",
        "package",
        "system",
    ]
    assert set(LEVEL_INSTRUCTIONS) == set(levels)
    assert len(set(LEVEL_INSTRUCTIONS.values())) == len(levels)

    for level in levels:
        prompt = build_prompt(_make_request(level=level))
        assert LEVEL_INSTRUCTIONS[level] in prompt


# ---------------------------------------------------------------------------
# Test 4: deterministic output
# ---------------------------------------------------------------------------

def test_build_prompt_deterministic() -> None:
    req = _make_request(
        child_summaries=[_child("pkg/mod.py::g")],
        edges=[{"type": "calls", "from": "pkg/mod.py::f", "to": "print"}],
    )
    assert build_prompt(req) == build_prompt(req)


# ---------------------------------------------------------------------------
# Test 5: child summaries are rendered sorted by node_id
# ---------------------------------------------------------------------------

def test_build_prompt_child_summaries_sorted() -> None:
    req = _make_request(
        child_summaries=[
            _child("pkg/mod.py::zeta", "Z"),
            _child("pkg/mod.py::alpha", "A"),
        ]
    )
    prompt = build_prompt(req)

    assert prompt.index("### pkg/mod.py::alpha") < prompt.index("### pkg/mod.py::zeta")


# ---------------------------------------------------------------------------
# Test 6: relational facts rendered; calls are context, not citable
# ---------------------------------------------------------------------------

def test_build_prompt_renders_edges() -> None:
    req = _make_request(
        edges=[
            {"type": "raises", "from": "pkg/mod.py::f", "to": "external:ValueError"},
            {"type": "depends_on", "from": "pkg/mod.py::f", "to": "pkg/dep.py::d"},
            {"type": "calls", "from": "pkg/mod.py::f", "to": "get_repository"},
            {"type": "inherits", "from": "pkg/mod.py::f", "to": "pkg/base.py::B"},
        ]
    )
    prompt = build_prompt(req)

    assert "## Relational facts" in prompt
    for line in (
        "- raises: external:ValueError",
        "- depends_on: pkg/dep.py::d",
        "- calls: get_repository",
        "- inherits: pkg/base.py::B",
    ):
        assert line in prompt

    # The bare call name is context only.
    assert "calls: get_repository" in render_edges(req.edges)
    assert "get_repository" not in allowed_fact_ids(req)


# ---------------------------------------------------------------------------
# Test 7: empty optional sections are omitted
# ---------------------------------------------------------------------------

def test_build_prompt_omits_empty_blocks() -> None:
    prompt = build_prompt(_make_request(source_text="", child_summaries=[], edges=[]))

    assert "## Relational facts" not in prompt
    assert "## Source" not in prompt
    assert "## Child summaries" not in prompt


# ---------------------------------------------------------------------------
# Test 8: format -> extract round-trip
# ---------------------------------------------------------------------------

def test_citation_roundtrip() -> None:
    fact_id = "pkg/mod.py::f"
    assert extract_citations(f"Does a thing. {format_citation(fact_id)}") == [fact_id]


# ---------------------------------------------------------------------------
# Test 9: multiple citations, de-duplication, malformed spans ignored
# ---------------------------------------------------------------------------

def test_extract_citations_multiple_and_dedup() -> None:
    text = "First [[a]] and [[b]]. Second [[a]] again. Bad [] and [[unclosed."
    assert extract_citations(text) == ["a", "b"]
    assert CITATION_RE.findall("[[a]] [[b]]") == ["a", "b"]
