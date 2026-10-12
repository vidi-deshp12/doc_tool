"""Tests for task 2b.1: Summarizer interface, Stub/Manual backends, store, CLI.

All tests are offline: the only backend exercised is the deterministic
StubSummarizer (plus ManualSummarizer over a temp folder).
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import pytest

from docgen.summarize.base import (
    MissingSummaryError,
    StubSummarizer,
    SummaryRequest,
    SummaryResult,
)
from docgen.summarize.manual import ManualSummarizer
from docgen.summarize.store import read_summaries, write_summaries


def _make_request(node_id: str = "pkg/mod.py::func", **overrides) -> SummaryRequest:
    fields = dict(
        node_id=node_id,
        level="function",
        facts={"hash_struct": "hs-1", "hash_source": "hsrc-1"},
        source_text="def func():\n    return 1\n",
        child_summaries=[],
    )
    fields.update(overrides)
    return SummaryRequest(**fields)


# ---------------------------------------------------------------------------
# Test 1: StubSummarizer returns a fully-populated SummaryResult
# ---------------------------------------------------------------------------

def test_stub_summarizer_returns_result() -> None:
    req = _make_request()

    result = StubSummarizer().summarize(req)

    assert isinstance(result, SummaryResult)
    assert result.node_id == "pkg/mod.py::func"
    assert result.text == "Stub summary for pkg/mod.py::func [[pkg/mod.py::func]]"
    assert result.backend == "stub"
    assert isinstance(result.hash_input, str)
    assert len(result.hash_input) == 64  # sha256 hex digest


# ---------------------------------------------------------------------------
# Test 2: StubSummarizer is deterministic
# ---------------------------------------------------------------------------

def test_stub_summarizer_deterministic() -> None:
    req = _make_request()

    first = StubSummarizer().summarize(req)
    second = StubSummarizer().summarize(req)

    assert first == second
    assert first.hash_input == second.hash_input


# ---------------------------------------------------------------------------
# Test 3: ManualSummarizer reads the matching file
# ---------------------------------------------------------------------------

def test_manual_summarizer_reads_file(tmp_path: Path) -> None:
    folder = tmp_path / "manual_summaries"
    folder.mkdir()

    node_id = "pkg/mod.py::func"
    safe_name = node_id.replace("/", "_").replace("::", "__").replace(":", "_")
    body = "# My function\n\nDoes a thing. [[pkg/mod.py::func]]\n"
    (folder / f"{safe_name}.md").write_text(body, encoding="utf-8")

    result = ManualSummarizer(folder).summarize(_make_request(node_id))

    assert result.node_id == node_id
    assert result.text == body
    assert result.backend == "manual"
    assert len(result.hash_input) == 64


# ---------------------------------------------------------------------------
# Test 4: ManualSummarizer raises MissingSummaryError when no file exists
# ---------------------------------------------------------------------------

def test_manual_summarizer_missing_file(tmp_path: Path) -> None:
    folder = tmp_path / "manual_summaries"
    folder.mkdir()

    with pytest.raises(MissingSummaryError) as excinfo:
        ManualSummarizer(folder).summarize(_make_request("pkg/mod.py::absent"))

    assert excinfo.value.node_id == "pkg/mod.py::absent"


# ---------------------------------------------------------------------------
# Test 5: write then read round-trips exactly
# ---------------------------------------------------------------------------

def test_write_read_summaries_roundtrip(tmp_path: Path) -> None:
    results = [
        SummaryResult(node_id="a.py", text="A. [[a.py]]", backend="stub", hash_input="h-a"),
        SummaryResult(node_id="a.py::f", text="F. [[a.py::f]]", backend="stub", hash_input="h-f"),
    ]
    path = tmp_path / "summaries.json"

    write_summaries(results, path)
    read_back = read_summaries(path)

    assert read_back == results


# ---------------------------------------------------------------------------
# Test 6: writing the same list twice is byte-identical
# ---------------------------------------------------------------------------

def test_write_summaries_stable(tmp_path: Path) -> None:
    results = [
        SummaryResult(node_id="a.py::f", text="F. [[a.py::f]]", backend="stub", hash_input="h-f"),
        SummaryResult(node_id="a.py::g", text="G. [[a.py::g]]", backend="stub", hash_input="h-g"),
    ]
    path1 = tmp_path / "s1.json"
    path2 = tmp_path / "s2.json"

    write_summaries(results, path1)
    write_summaries(results, path2)

    assert path1.read_bytes() == path2.read_bytes()


# ---------------------------------------------------------------------------
# CLI fixture helpers
# ---------------------------------------------------------------------------

def _make_fixture_repo(tmp_path: Path, edges: tuple = ()) -> Path:
    """Create a minimal repo with a source file, docgen.toml, and facts.json.

    `edges` are additional fact-graph edges to include (for the edge-enrichment test).
    """
    (tmp_path / "mod.py").write_text(
        "def f():\n"
        "    return 1\n"
        "\n"
        "def g():\n"
        "    return 2\n",
        encoding="utf-8",
    )

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

    # Write a facts.json with a MODULE node and one FUNCTION node.
    from docgen.facts.schema import FactGraph, Node, NodeType
    from docgen.facts.store import write_facts

    module = Node(
        id="mod.py",
        type=NodeType.MODULE,
        file="mod.py",
        lines=(1, 5),
        hash_struct="mod-struct",
        hash_source="mod-source",
        dotted_name="mod",
    )
    func = Node(
        id="mod.py::f",
        type=NodeType.FUNCTION,
        file="mod.py",
        lines=(1, 2),
        hash_struct="f-struct",
        hash_source="f-source",
        signature="()",
    )
    graph = FactGraph(nodes=(module, func), edges=edges, unresolved=())

    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_facts(graph, out_dir / "facts.json")
    return toml_path


# ---------------------------------------------------------------------------
# Test 7: `docgen summarize` end-to-end with the stub backend
# ---------------------------------------------------------------------------

def test_cli_summarize_stub_e2e(tmp_path: Path) -> None:
    import json

    toml_path = _make_fixture_repo(tmp_path)

    from docgen.cli import _run_summarize

    _run_summarize(argparse.Namespace(config=str(toml_path), backend="stub"))

    summaries_path = tmp_path / "out" / "summaries.json"
    assert summaries_path.exists(), "summaries.json was not created"

    data = json.loads(summaries_path.read_text(encoding="utf-8"))
    assert len(data["summaries"]) == 2

    node_ids = {s["node_id"] for s in data["summaries"]}
    assert node_ids == {"mod.py", "mod.py::f"}
    for entry in data["summaries"]:
        assert entry["node_id"] in entry["text"]


# ---------------------------------------------------------------------------
# Test 8: the CLI passes non-empty source_text for a known FUNCTION node
# ---------------------------------------------------------------------------

def test_cli_summarize_source_text_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    toml_path = _make_fixture_repo(tmp_path)

    import docgen.summarize.base as base

    captured: list[SummaryRequest] = []

    class RecordingSummarizer:
        def summarize(self, req: SummaryRequest) -> SummaryResult:
            captured.append(req)
            return SummaryResult(
                node_id=req.node_id,
                text="rec",
                backend="rec",
                hash_input="h",
            )

    monkeypatch.setattr(base, "StubSummarizer", RecordingSummarizer)

    from docgen.cli import _run_summarize

    _run_summarize(argparse.Namespace(config=str(toml_path), backend="stub"))

    func_reqs = [r for r in captured if r.node_id == "mod.py::f"]
    assert len(func_reqs) == 1
    assert func_reqs[0].source_text.strip() != ""
    assert "def f" in func_reqs[0].source_text

    module_reqs = [r for r in captured if r.node_id == "mod.py"]
    assert len(module_reqs) == 1
    assert "def g" in module_reqs[0].source_text


# ---------------------------------------------------------------------------
# Test 9: the CLI enriches SummaryRequest with the node's relational edges
# ---------------------------------------------------------------------------

def test_cli_summarize_passes_relevant_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from docgen.facts.schema import Edge, EdgeType

    edges = (
        Edge(type=EdgeType.RAISES, from_id="mod.py::f", to_id="external:ValueError"),
        Edge(type=EdgeType.CALLS, from_id="mod.py::f", to_id="external:print"),
        Edge(type=EdgeType.DEPENDS_ON, from_id="mod.py::f", to_id="external:dep"),
        Edge(type=EdgeType.INHERITS, from_id="mod.py::f", to_id="external:Base"),
        # Non-relational edges must NOT be handed to the summarizer.
        Edge(type=EdgeType.CONTAINS, from_id="mod.py", to_id="mod.py::f"),
        Edge(type=EdgeType.IMPORTS, from_id="mod.py", to_id="external:os"),
    )
    toml_path = _make_fixture_repo(tmp_path, edges=edges)

    import docgen.summarize.base as base

    captured: list[SummaryRequest] = []

    class RecordingSummarizer:
        def summarize(self, req: SummaryRequest) -> SummaryResult:
            captured.append(req)
            return SummaryResult(
                node_id=req.node_id, text="rec", backend="rec", hash_input="h"
            )

    monkeypatch.setattr(base, "StubSummarizer", RecordingSummarizer)

    from docgen.cli import _run_summarize

    _run_summarize(argparse.Namespace(config=str(toml_path), backend="stub"))

    func_req = [r for r in captured if r.node_id == "mod.py::f"][0]
    func_types = {e["type"] for e in func_req.edges}
    assert func_types == {"raises", "calls", "depends_on", "inherits"}
    assert all(e["from"] == "mod.py::f" for e in func_req.edges)

    # The module node only emits `contains`/`imports`, so it gets no edges.
    module_req = [r for r in captured if r.node_id == "mod.py"][0]
    assert module_req.edges == []


# ---------------------------------------------------------------------------
# Test 10: SummaryRequest.edges defaults to empty and round-trips supplied edges
# ---------------------------------------------------------------------------

def test_summary_request_edges_field() -> None:
    bare = SummaryRequest(node_id="x", level="function", facts={}, source_text="")
    assert bare.edges == []

    with_edges = SummaryRequest(
        node_id="x",
        level="function",
        facts={},
        source_text="",
        edges=[{"type": "raises", "from": "x", "to": "external:ValueError"}],
    )
    assert with_edges.edges == [{"type": "raises", "from": "x", "to": "external:ValueError"}]
