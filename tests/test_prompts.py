"""Tests for task 2b.2: per-level prompts and the [[fact_id]] citation format.

All tests are offline and deterministic: no LLM, no network, no filesystem I/O.
"""

from __future__ import annotations

import hashlib

from docgen.summarize.base import NodeLevel, SummaryRequest, SummaryResult
from docgen.summarize.prompts import (
    CITATION_RE,
    CITATION_RULES,
    LEVEL_INSTRUCTIONS,
    OUTPUT_INSTRUCTION,
    PROMPT_VERSION,
    SYSTEM_PREAMBLE,
    _GROUNDING_RULE,
    _LEVEL_FOCUS,
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


# ---------------------------------------------------------------------------
# Test 10: handles edge makes route ID citeable (S4b)
# ---------------------------------------------------------------------------

def test_allowed_fact_ids_includes_handles_target() -> None:
    """A 'handles' edge must add the route id (in 'from') to allowed_fact_ids (S4b).

    hierarchy.py indexes HANDLES edges by to_id (the function), so the edge the
    function sees is {from: route_id, to: function_id}.  allowed_fact_ids must
    add edge['from'] for handles edges so the handler can cite its own route node.
    """
    req = _make_request(
        node_id="mod.py::create",
        edges=[
            {
                "type": "handles",
                "from": "route:POST /api/articles",
                "to": "mod.py::create",
            }
        ]
    )
    ids = allowed_fact_ids(req)
    assert "route:POST /api/articles" in ids, (
        f"Route id must be in allowed_fact_ids when a handles edge is present; got {ids}"
    )

    # The rendered line must show the route ("from"), not the function's own id
    # ("to"), which the handler already knows.
    rendered = render_edges(req.edges)
    assert "- handles: route:POST /api/articles" in rendered
    assert "mod.py::create" not in rendered


# ---------------------------------------------------------------------------
# Test 11: request/response model edges are rendered and citeable (fix 6)
# ---------------------------------------------------------------------------

def test_build_prompt_renders_model_edges_and_allows_them() -> None:
    req = _make_request(
        node_id="mod.py::create",
        edges=[
            {
                "type": "request_model",
                "from": "route:POST /api/comments",
                "to": "mod.py::CommentInCreate",
            },
            {
                "type": "response_model",
                "from": "route:POST /api/comments",
                "to": "mod.py::CommentInResponse",
            },
        ],
    )
    prompt = build_prompt(req)

    assert "## Relational facts" in prompt
    assert "- request_model: mod.py::CommentInCreate" in prompt
    assert "- response_model: mod.py::CommentInResponse" in prompt

    # Predictable order: request_model before response_model.
    assert prompt.index("- request_model:") < prompt.index("- response_model:")

    ids = allowed_fact_ids(req)
    assert "mod.py::CommentInCreate" in ids
    assert "mod.py::CommentInResponse" in ids


# ---------------------------------------------------------------------------
# Test 12: the citation example never shows a forbidden (external) id (fix 2)
# ---------------------------------------------------------------------------

def test_citation_rules_do_not_offer_external_ids() -> None:
    """The rules say "cite only allowed ids", so the example must not be external."""
    assert "external:" not in CITATION_RULES
    assert "[[target/app/db/errors.py::EntityDoesNotExist]]" in CITATION_RULES

    prompt = build_prompt(_make_request())
    rules_section = prompt.split("## Citation rules")[1].split("## Allowed fact IDs")[0]
    assert "external:" not in rules_section


# ---------------------------------------------------------------------------
# Test 13: PROMPT_VERSION is derived from the template text (fix: auto-version)
# ---------------------------------------------------------------------------

def test_prompt_version_derived_from_template_content() -> None:
    assert len(PROMPT_VERSION) == 16
    assert PROMPT_VERSION.isalnum()

    expected = hashlib.sha256(
        (
            SYSTEM_PREAMBLE
            + CITATION_RULES
            + OUTPUT_INSTRUCTION
            + _GROUNDING_RULE
            + "".join(_LEVEL_FOCUS.values())
        ).encode("utf-8")
    ).hexdigest()[:16]
    assert PROMPT_VERSION == expected

