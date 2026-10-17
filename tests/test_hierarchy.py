"""Tests for task 2b.3: hierarchy driver and summary cache.

All tests are offline: they use StubSummarizer, in-memory FactGraph fixtures, and
tmp_path for any filesystem I/O. No LLM calls are made.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from docgen.facts.schema import Edge, EdgeType, FactGraph, Node, NodeType
from docgen.summarize.base import StubSummarizer, SummaryRequest, SummaryResult
from docgen.summarize.hierarchy import (
    SYSTEM_NODE_ID,
    build_contains_index,
    hash_input_with_children,
    run_hierarchy,
    topological_order,
)

# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------

PROMPT_V = "test-v1"


def _node(
    id: str,
    type: NodeType = NodeType.FUNCTION,
    file: str = "mod.py",
    parent_class: str = "",
    hash_struct: str = "hs",
    hash_source: str = "hsrc",
) -> Node:
    return Node(
        id=id,
        type=type,
        file=file,
        lines=(1, 2),
        hash_struct=hash_struct,
        hash_source=hash_source,
        parent_class=parent_class,
    )


def _contains(parent: str, child: str) -> Edge:
    return Edge(type=EdgeType.CONTAINS, from_id=parent, to_id=child)


def _make_graph(*nodes: Node, edges: tuple[Edge, ...] = ()) -> FactGraph:
    return FactGraph(nodes=nodes, edges=edges, unresolved=())


class CountingSummarizer:
    """Wraps StubSummarizer but counts how many times it is called."""

    def __init__(self) -> None:
        self.call_count = 0
        self._inner = StubSummarizer()

    def summarize(self, req: SummaryRequest) -> SummaryResult:
        self.call_count += 1
        return self._inner.summarize(req)


# ---------------------------------------------------------------------------
# Test 1: children before parents in topological order
# ---------------------------------------------------------------------------

def test_topological_order_children_before_parents() -> None:
    """A 3-node graph: package → module → function. Function must appear first."""
    pkg = _node("pkg", NodeType.PACKAGE)
    mod = _node("pkg/mod.py", NodeType.MODULE)
    func = _node("pkg/mod.py::f", NodeType.FUNCTION)
    graph = _make_graph(
        pkg, mod, func,
        edges=(
            _contains("pkg", "pkg/mod.py"),
            _contains("pkg/mod.py", "pkg/mod.py::f"),
        ),
    )
    index = build_contains_index(graph)
    order = topological_order(graph, index)

    ids = [n.id for n in order]
    assert ids.index("pkg/mod.py::f") < ids.index("pkg/mod.py")
    assert ids.index("pkg/mod.py") < ids.index("pkg")


# ---------------------------------------------------------------------------
# Test 2: class with a method — method's result passed as child summary
# ---------------------------------------------------------------------------

class RecordingSummarizer:
    """Captures every SummaryRequest it receives."""

    def __init__(self) -> None:
        self.requests: list[SummaryRequest] = []
        self._inner = StubSummarizer()

    def summarize(self, req: SummaryRequest) -> SummaryResult:
        self.requests.append(req)
        return self._inner.summarize(req)


def test_run_hierarchy_passes_child_summaries(tmp_path: Path) -> None:
    """The class's SummaryRequest.child_summaries contains the method's result."""
    cls_node = _node("mod.py::Cls", NodeType.CLASS, file="mod.py")
    method_node = _node(
        "mod.py::Cls::do_it", NodeType.FUNCTION, file="mod.py", parent_class="mod.py::Cls"
    )
    mod_node = _node("mod.py", NodeType.MODULE, file="mod.py")
    graph = _make_graph(
        mod_node, cls_node, method_node,
        edges=(
            _contains("mod.py", "mod.py::Cls"),
            _contains("mod.py::Cls", "mod.py::Cls::do_it"),
        ),
    )

    rec = RecordingSummarizer()
    run_hierarchy(graph, rec, tmp_path, existing_cache={}, prompt_version=PROMPT_V)

    cls_req = next(r for r in rec.requests if r.node_id == "mod.py::Cls")
    child_ids = [c.node_id for c in cls_req.child_summaries]
    assert "mod.py::Cls::do_it" in child_ids


# ---------------------------------------------------------------------------
# Test 3: zero summarizer calls on re-run with unchanged facts
# ---------------------------------------------------------------------------

def test_run_hierarchy_zero_calls_on_rerun(tmp_path: Path) -> None:
    """Second run with the first run's results as the cache makes 0 calls."""
    mod = _node("mod.py", NodeType.MODULE, file="mod.py")
    func = _node("mod.py::f", NodeType.FUNCTION, file="mod.py")
    graph = _make_graph(mod, func, edges=(_contains("mod.py", "mod.py::f"),))

    first_summarizer = CountingSummarizer()
    first_results = run_hierarchy(
        graph, first_summarizer, tmp_path, existing_cache={}, prompt_version=PROMPT_V
    )
    first_calls = first_summarizer.call_count
    assert first_calls > 0  # sanity: something was called on the first run

    # Build cache from first run results.
    cache = {r.node_id: r for r in first_results}

    second_summarizer = CountingSummarizer()
    run_hierarchy(
        graph, second_summarizer, tmp_path, existing_cache=cache, prompt_version=PROMPT_V
    )
    assert second_summarizer.call_count == 0, (
        f"Expected 0 calls on re-run with unchanged cache, got {second_summarizer.call_count}"
    )


# ---------------------------------------------------------------------------
# Test 4: changing a node's hash_struct forces that node + its ancestors to re-run
# ---------------------------------------------------------------------------

def test_run_hierarchy_reruns_on_hash_change(tmp_path: Path) -> None:
    """Modifying one node's hash_struct causes that node and its parent to be re-summarized."""
    mod = _node("mod.py", NodeType.MODULE, file="mod.py", hash_struct="orig-mod")
    func = _node("mod.py::f", NodeType.FUNCTION, file="mod.py", hash_struct="orig-f")
    graph = _make_graph(mod, func, edges=(_contains("mod.py", "mod.py::f"),))

    # First run — populate cache.
    first = CountingSummarizer()
    first_results = run_hierarchy(graph, first, tmp_path, existing_cache={}, prompt_version=PROMPT_V)
    cache = {r.node_id: r for r in first_results}

    # Modify the function's hash_struct to simulate a source change.
    func_changed = _node("mod.py::f", NodeType.FUNCTION, file="mod.py", hash_struct="changed-f")
    changed_graph = _make_graph(
        mod, func_changed, edges=(_contains("mod.py", "mod.py::f"),)
    )

    second = CountingSummarizer()
    run_hierarchy(changed_graph, second, tmp_path, existing_cache=cache, prompt_version=PROMPT_V)

    # The function itself and its parent module must be re-summarized (≥2 calls).
    assert second.call_count >= 2, (
        f"Expected at least 2 re-summarizations (func + module), got {second.call_count}"
    )


# ---------------------------------------------------------------------------
# Test 5: PACKAGE nodes are included; package summary has module as child
# ---------------------------------------------------------------------------

def test_run_hierarchy_includes_package_nodes(tmp_path: Path) -> None:
    """A PACKAGE node containing a MODULE containing a FUNCTION; all three get summaries,
    and the package's child_summaries contains the module's result."""
    pkg = _node("pkg", NodeType.PACKAGE, file="pkg/__init__.py")
    mod = _node("pkg/mod.py", NodeType.MODULE, file="pkg/mod.py")
    func = _node("pkg/mod.py::f", NodeType.FUNCTION, file="pkg/mod.py")
    graph = _make_graph(
        pkg, mod, func,
        edges=(
            _contains("pkg", "pkg/mod.py"),
            _contains("pkg/mod.py", "pkg/mod.py::f"),
        ),
    )

    rec = RecordingSummarizer()
    results = run_hierarchy(graph, rec, tmp_path, existing_cache={}, prompt_version=PROMPT_V)

    result_ids = {r.node_id for r in results}
    assert "pkg" in result_ids
    assert "pkg/mod.py" in result_ids
    assert "pkg/mod.py::f" in result_ids
    assert SYSTEM_NODE_ID in result_ids

    # Package's request must have the module summary as a child.
    pkg_req = next(r for r in rec.requests if r.node_id == "pkg")
    assert any(c.node_id == "pkg/mod.py" for c in pkg_req.child_summaries)

    # System-level request must have the package summary as a child.
    system_req = next(r for r in rec.requests if r.node_id == SYSTEM_NODE_ID)
    assert any(c.node_id == "pkg" for c in system_req.child_summaries)


# ---------------------------------------------------------------------------
# Test 6: hash_input_with_children changes when prompt_version changes
# ---------------------------------------------------------------------------

def test_hash_input_with_children_changes_on_prompt_version() -> None:
    """Same SummaryRequest but different prompt_version strings → different hashes."""
    req = SummaryRequest(
        node_id="mod.py",
        level="module",
        facts={"hash_struct": "hs", "hash_source": "hsrc"},
        source_text="",
        child_summaries=[],
        edges=[],
    )
    h1 = hash_input_with_children(req, "v1")
    h2 = hash_input_with_children(req, "v2")
    assert h1 != h2


# ---------------------------------------------------------------------------
# Test 7: system-level result is always produced and is last in the list
# ---------------------------------------------------------------------------

def test_run_hierarchy_always_produces_system_node(tmp_path: Path) -> None:
    """run_hierarchy always appends a system-level SummaryResult, even with one module."""
    mod = _node("mod.py", NodeType.MODULE, file="mod.py")
    graph = _make_graph(mod)

    results = run_hierarchy(
        graph, StubSummarizer(), tmp_path, existing_cache={}, prompt_version=PROMPT_V
    )

    assert results[-1].node_id == SYSTEM_NODE_ID
    assert any(r.node_id == SYSTEM_NODE_ID for r in results)


# ---------------------------------------------------------------------------
# Test 8: CLI end-to-end still produces summaries.json with system node included
# ---------------------------------------------------------------------------

def test_cli_summarize_hierarchy_e2e(tmp_path: Path) -> None:
    """docgen summarize via the CLI writes summaries.json that includes the system node."""
    import argparse
    import json

    # Create a minimal repo.
    (tmp_path / "mod.py").write_text(
        "def f():\n    return 1\n", encoding="utf-8"
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

    from docgen.facts.schema import FactGraph, Node, NodeType
    from docgen.facts.store import write_facts

    mod_node = Node(
        id="mod.py",
        type=NodeType.MODULE,
        file="mod.py",
        lines=(1, 2),
        hash_struct="mod-hs",
        hash_source="mod-hsrc",
        dotted_name="mod",
    )
    graph = FactGraph(nodes=(mod_node,), edges=(), unresolved=())
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_facts(graph, out_dir / "facts.json")

    from docgen.cli import _run_summarize

    _run_summarize(argparse.Namespace(config=str(toml_path), backend="stub"))

    data = json.loads((out_dir / "summaries.json").read_text(encoding="utf-8"))
    node_ids = {s["node_id"] for s in data["summaries"]}
    assert "mod.py" in node_ids
    assert SYSTEM_NODE_ID in node_ids


# ---------------------------------------------------------------------------
# Test 9: HANDLES edge indexed by function — handler sees route in its edges (S4a)
# ---------------------------------------------------------------------------

def test_handles_edge_reaches_function(tmp_path: Path) -> None:
    """A FUNCTION node that is the target of a HANDLES edge must receive that edge
    in its SummaryRequest.edges."""
    from docgen.facts.schema import EdgeType, NodeType

    func = _node("mod.py::handler", NodeType.FUNCTION, file="mod.py")
    mod = _node("mod.py", NodeType.MODULE, file="mod.py")
    route = Node(
        id="route:POST /api/items",
        type=NodeType.ROUTE,
        file="mod.py",
        lines=(1, 5),
        hash_struct="rhs",
        hash_source="rhs",
        method="POST",
        full_path="/api/items",
        status_code=201,
    )
    graph = FactGraph(
        nodes=(func, mod, route),
        edges=(
            Edge(type=EdgeType.CONTAINS, from_id="mod.py", to_id="mod.py::handler"),
            Edge(type=EdgeType.HANDLES, from_id="route:POST /api/items", to_id="mod.py::handler"),
        ),
        unresolved=(),
    )

    rec = RecordingSummarizer()
    run_hierarchy(graph, rec, tmp_path, existing_cache={}, prompt_version=PROMPT_V)

    handler_req = next(r for r in rec.requests if r.node_id == "mod.py::handler")
    handles_edges = [e for e in handler_req.edges if e.get("type") == "handles"]
    assert len(handles_edges) == 1, (
        f"Expected 1 handles edge in function req, got {handles_edges}"
    )
    assert handles_edges[0]["from"] == "route:POST /api/items"
    assert handles_edges[0]["to"] == "mod.py::handler"

