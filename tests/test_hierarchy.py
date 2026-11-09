"""Tests for task 2b.3: hierarchy driver and summary cache.

All tests are offline: they use StubSummarizer, in-memory FactGraph fixtures, and
tmp_path for any filesystem I/O. No LLM calls are made.
"""

from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path

import pytest

from docgen.facts.schema import Edge, EdgeType, FactGraph, Node, NodeType
from docgen.summarize.base import StubSummarizer, SummaryRequest, SummaryResult
from docgen.summarize.hierarchy import (
    SYSTEM_NODE_ID,
    _prompt_facts,
    batched_topological_order,
    build_contains_index,
    hash_prompt,
    read_residual_source,
    run_hierarchy,
    topological_order,
)
from docgen.summarize.prompts import build_prompt

# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------


def _node(
    id: str,
    type: NodeType = NodeType.FUNCTION,
    file: str = "mod.py",
    parent_class: str = "",
    hash_struct: str = "hs",
    hash_source: str = "hsrc",
    lines: tuple[int, int] = (1, 2),
    signature: str = "",
) -> Node:
    return Node(
        id=id,
        type=type,
        file=file,
        lines=lines,
        hash_struct=hash_struct,
        hash_source=hash_source,
        parent_class=parent_class,
        signature=signature,
    )


def _contains(parent: str, child: str) -> Edge:
    return Edge(type=EdgeType.CONTAINS, from_id=parent, to_id=child)


def _make_graph(*nodes: Node, edges: tuple[Edge, ...] = ()) -> FactGraph:
    return FactGraph(nodes=nodes, edges=edges, unresolved=())


class CountingSummarizer:
    """Wraps StubSummarizer but counts how many times it is called."""

    # Same backend identity as the stub it delegates to: it is part of the cache key.
    name = "stub"

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

    name = "stub"

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
    run_hierarchy(graph, rec, tmp_path, existing_cache={})

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
        graph, first_summarizer, tmp_path, existing_cache={}
    )
    first_calls = first_summarizer.call_count
    assert first_calls > 0  # sanity: something was called on the first run

    # Build cache from first run results.
    cache = {r.node_id: r for r in first_results}

    second_summarizer = CountingSummarizer()
    run_hierarchy(
        graph, second_summarizer, tmp_path, existing_cache=cache
    )
    assert second_summarizer.call_count == 0, (
        f"Expected 0 calls on re-run with unchanged cache, got {second_summarizer.call_count}"
    )


# ---------------------------------------------------------------------------
# Test 4: changing a node's hash_struct forces that node + its ancestors to re-run
# ---------------------------------------------------------------------------

def test_run_hierarchy_reruns_only_the_node_whose_prompt_changed(tmp_path: Path) -> None:
    """A change the prompt renders re-summarizes that node and stops there.

    ``hash_struct``/``hash_source`` are no longer key inputs; what the node's prompt
    actually contains is. The parent module is *not* re-summarized because the child's
    prose is unchanged (early cutoff) — see test_child_text_change_reruns_parent for
    the positive case.
    """
    mod = _node("mod.py", NodeType.MODULE, file="mod.py")
    func = _node("mod.py::f", NodeType.FUNCTION, file="mod.py", signature="def f()")
    graph = _make_graph(mod, func, edges=(_contains("mod.py", "mod.py::f"),))

    # First run — populate cache.
    first = CountingSummarizer()
    first_results = run_hierarchy(graph, first, tmp_path, existing_cache={})
    cache = {r.node_id: r for r in first_results}

    # Same node, changed signature: the prompt differs, so the key does.
    func_changed = _node("mod.py::f", NodeType.FUNCTION, file="mod.py", signature="def f(x)")
    changed_graph = _make_graph(
        mod, func_changed, edges=(_contains("mod.py", "mod.py::f"),)
    )

    second = CountingSummarizer()
    run_hierarchy(changed_graph, second, tmp_path, existing_cache=cache)

    # The function itself is re-summarized; its text is unchanged, so the module
    # (and the system node) are skipped.
    assert second.call_count == 1, (
        f"Expected exactly 1 re-summarization (the changed function), got {second.call_count}"
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
    results = run_hierarchy(graph, rec, tmp_path, existing_cache={})

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
# Test 6: cache-key semantics — the key is the prompt, and the old key was blind
# ---------------------------------------------------------------------------

def _legacy_cache_key(req: SummaryRequest, prompt_version: str = "test-v1") -> str:
    """The retired key: node id + hash_struct + hash_source + version + child text.

    Reproduced here only as evidence of what it could not see; production code no
    longer contains this formula.
    """
    child_hashes = "".join(
        sorted(
            hashlib.sha256(c.text.encode("utf-8")).hexdigest()
            for c in req.child_summaries
        )
    )
    payload = (
        req.node_id
        + str(req.facts.get("hash_struct", ""))
        + str(req.facts.get("hash_source", ""))
        + prompt_version
        + child_hashes
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _prompt_key(req: SummaryRequest, identity: str = "stub") -> str:
    """What the driver computes: hash of (backend identity + exact prompt)."""
    return hash_prompt(identity + "\n" + build_prompt(req))


def _key_request(**overrides) -> SummaryRequest:
    fields = dict(
        node_id="mod.py::handler",
        level="function",
        facts={"id": "mod.py::handler", "file": "mod.py", "signature": "def handler()"},
        source_text="def handler():\n    return create()\n",
        child_summaries=[],
        edges=[],
    )
    fields.update(overrides)
    return SummaryRequest(**fields)


_MODEL_EDGE = {
    "type": "request_model",
    "from": "route:POST /api/items",
    "to": "mod.py::ItemIn",
}


def test_legacy_key_was_blind_to_edges() -> None:
    """The old key ignored req.edges; the prompt hash does not.

    This is the regression that justifies replacing the key at all: a new model edge
    changes the relational facts and the allowed id list, but the old key was equal
    before and after, so cached prose could cite an id it should not (or miss one it
    now may).
    """
    before = _key_request()
    after = _key_request(edges=[_MODEL_EDGE])

    # The prompt really did change...
    assert "mod.py::ItemIn" not in build_prompt(before)
    assert "mod.py::ItemIn" in build_prompt(after)

    # ...but the old key could not see it.
    assert _legacy_cache_key(before) == _legacy_cache_key(after)

    # The prompt hash does.
    assert _prompt_key(before) != _prompt_key(after)


def test_prompt_hash_changes_on_child_source_and_edges() -> None:
    """Child prose, own source, and relational facts each change the key."""
    base = _key_request()
    assert _prompt_key(base) == _prompt_key(_key_request())  # deterministic

    child_one = SummaryResult(
        node_id="mod.py::child",
        text="Does a thing [[mod.py::child]].",
        backend="stub",
        hash_input="",
    )
    child_two = SummaryResult(
        node_id="mod.py::child",
        text="Does another thing [[mod.py::child]].",
        backend="stub",
        hash_input="",
    )

    assert _prompt_key(_key_request(child_summaries=[child_one])) != _prompt_key(
        _key_request(child_summaries=[child_two])
    )
    assert _prompt_key(base) != _prompt_key(
        _key_request(source_text="def handler():\n    return update()\n")
    )
    assert _prompt_key(base) != _prompt_key(_key_request(edges=[_MODEL_EDGE]))


def test_prompt_hash_ignores_line_shift(tmp_path: Path) -> None:
    """A blank line inserted at the top of a file must invalidate nothing.

    The extractor's hashes are token-based, so they legitimately do not change on a
    line shift; the prompt hash must not turn one into a full re-summarization.
    """
    source = "def f():\n    return 1\n\ndef g():\n    return 2\n"
    path = tmp_path / "mod.py"
    path.write_text(source, encoding="utf-8")

    def build(
        mod_lines: tuple[int, int],
        f_lines: tuple[int, int],
        g_lines: tuple[int, int],
    ) -> FactGraph:
        return _make_graph(
            _node(
                "mod.py", NodeType.MODULE, file="mod.py",
                hash_struct="mod-hs", hash_source="mod-hsrc", lines=mod_lines,
            ),
            _node(
                "mod.py::f", NodeType.FUNCTION, file="mod.py",
                hash_struct="f-hs", hash_source="f-hsrc", lines=f_lines,
            ),
            _node(
                "mod.py::g", NodeType.FUNCTION, file="mod.py",
                hash_struct="g-hs", hash_source="g-hsrc", lines=g_lines,
            ),
            edges=(_contains("mod.py", "mod.py::f"), _contains("mod.py", "mod.py::g")),
        )

    first = CountingSummarizer()
    first_results = run_hierarchy(
        build((1, 5), (1, 2), (4, 5)), first, tmp_path, existing_cache={}
    )
    assert first.call_count == 4  # f, g, module, system
    cache = {r.node_id: r for r in first_results}

    # One blank line at the top: every span shifts by one, the content does not.
    path.write_text("\n" + source, encoding="utf-8")

    second = CountingSummarizer()
    run_hierarchy(build((2, 6), (2, 3), (5, 6)), second, tmp_path, existing_cache=cache)
    assert second.call_count == 0, (
        f"A line shift must not regenerate anything, got {second.call_count} calls"
    )

    # Same guard without the filesystem: "lines" never reaches the prompt.
    base_facts = {"id": "mod.py::f", "file": "mod.py", "signature": "def f()"}
    before = _key_request(facts=_prompt_facts({**base_facts, "lines": [3, 4]}))
    after = _key_request(facts=_prompt_facts({**base_facts, "lines": [4, 5]}))
    assert _prompt_key(before) == _prompt_key(after)


class _ProviderA(CountingSummarizer):
    name = "provider_a"


class _ProviderB(CountingSummarizer):
    name = "provider_b"


def test_key_includes_backend_name(tmp_path: Path) -> None:
    """Identical prompt, different backend → the cached prose is not reused."""
    graph = _make_graph(_node("mod.py::f"))

    first = _ProviderA()
    first_results = run_hierarchy(graph, first, tmp_path, existing_cache={})
    assert first.call_count == 2  # the function and the system summary
    cache = {r.node_id: r for r in first_results}

    same = _ProviderA()
    run_hierarchy(graph, same, tmp_path, existing_cache=cache)
    assert same.call_count == 0

    other = _ProviderB()
    run_hierarchy(graph, other, tmp_path, existing_cache=cache)
    assert other.call_count == 2, (
        f"Switching backend must regenerate, got {other.call_count} calls"
    )


# ---------------------------------------------------------------------------
# Test 7: system-level result is always produced and is last in the list
# ---------------------------------------------------------------------------

def test_run_hierarchy_always_produces_system_node(tmp_path: Path) -> None:
    """run_hierarchy always appends a system-level SummaryResult, even with one module."""
    mod = _node("mod.py", NodeType.MODULE, file="mod.py")
    graph = _make_graph(mod)

    results = run_hierarchy(
        graph, StubSummarizer(), tmp_path, existing_cache={}
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
    run_hierarchy(graph, rec, tmp_path, existing_cache={})

    handler_req = next(r for r in rec.requests if r.node_id == "mod.py::handler")
    handles_edges = [e for e in handler_req.edges if e.get("type") == "handles"]
    assert len(handles_edges) == 1, (
        f"Expected 1 handles edge in function req, got {handles_edges}"
    )
    assert handles_edges[0]["from"] == "route:POST /api/items"
    assert handles_edges[0]["to"] == "mod.py::handler"


# ---------------------------------------------------------------------------
# Test 10: a comment-only edit re-summarizes the child and stops there (early cutoff)
# ---------------------------------------------------------------------------

def test_child_text_unchanged_does_not_rerun_parent(tmp_path: Path) -> None:
    """The child's prompt changes but its prose does not → the parent is not re-run."""
    path = tmp_path / "mod.py"
    path.write_text("def f():\n    return 1\n", encoding="utf-8")

    mod = _node("mod.py", NodeType.MODULE, file="mod.py", lines=(1, 2))
    func = _node("mod.py::f", NodeType.FUNCTION, file="mod.py", lines=(1, 2))
    edges = (_contains("mod.py", "mod.py::f"),)
    graph = _make_graph(mod, func, edges=edges)

    first_results = run_hierarchy(graph, StubSummarizer(), tmp_path, existing_cache={})
    cache = {r.node_id: r for r in first_results}

    # A comment-only edit: the child's source, and therefore its prompt, changes.
    path.write_text("def f():\n    # note\n    return 1\n", encoding="utf-8")
    func_edited = _node("mod.py::f", NodeType.FUNCTION, file="mod.py", lines=(1, 3))
    edited_graph = _make_graph(mod, func_edited, edges=edges)

    second = RecordingSummarizer()
    run_hierarchy(edited_graph, second, tmp_path, existing_cache=cache)

    called = [r.node_id for r in second.requests]
    assert called == ["mod.py::f"], (
        f"Expected only the edited child to be re-summarized, got {called}"
    )


# ---------------------------------------------------------------------------
# Test 11: a changed child summary text does propagate to the parent
# ---------------------------------------------------------------------------

class SignatureEchoSummarizer:
    """Deterministic backend whose prose depends on the node's signature field."""

    def __init__(self) -> None:
        self.requests: list[SummaryRequest] = []

    def summarize(self, req: SummaryRequest) -> SummaryResult:
        self.requests.append(req)
        signature = req.facts.get("signature", "")
        return SummaryResult(
            node_id=req.node_id,
            text=f"{req.node_id} {signature} [[{req.node_id}]]",
            backend="signature_echo",
            hash_input="",
        )


def test_child_text_change_reruns_parent(tmp_path: Path) -> None:
    """When the child's prose changes, the parent's key changes and it re-runs."""
    mod = _node("mod.py", NodeType.MODULE, file="mod.py")
    func = Node(
        id="mod.py::f",
        type=NodeType.FUNCTION,
        file="mod.py",
        lines=(1, 2),
        hash_struct="orig-f",
        hash_source="hsrc",
        signature="def f()",
    )
    edges = (_contains("mod.py", "mod.py::f"),)

    first_results = run_hierarchy(
        _make_graph(mod, func, edges=edges),
        SignatureEchoSummarizer(),
        tmp_path,
        existing_cache={},
    )
    cache = {r.node_id: r for r in first_results}

    func_changed = Node(
        id="mod.py::f",
        type=NodeType.FUNCTION,
        file="mod.py",
        lines=(1, 2),
        hash_struct="changed-f",
        hash_source="hsrc",
        signature="def f(x)",
    )
    second = SignatureEchoSummarizer()
    run_hierarchy(
        _make_graph(mod, func_changed, edges=edges),
        second,
        tmp_path,
        existing_cache=cache,
    )

    called = [r.node_id for r in second.requests]
    assert called == ["mod.py::f", "mod.py"], (
        f"Expected the child then its parent, got {called}"
    )


# ---------------------------------------------------------------------------
# Test 12: internal fact fields are stripped from the summarizer's request
# ---------------------------------------------------------------------------

def test_prompt_facts_exclude_internal_fields(tmp_path: Path) -> None:
    """The facts dict handed to a backend has no pipeline-internal fields."""
    mod = _node("mod.py", NodeType.MODULE, file="mod.py")
    func = Node(
        id="mod.py::f",
        type=NodeType.FUNCTION,
        file="mod.py",
        lines=(3, 4),
        hash_struct="hs",
        hash_source="hsrc",
        signature="def f()",
        what="",
        why="",
        where="",
    )
    graph = _make_graph(mod, func, edges=(_contains("mod.py", "mod.py::f"),))

    rec = RecordingSummarizer()
    run_hierarchy(graph, rec, tmp_path, existing_cache={})

    req = next(r for r in rec.requests if r.node_id == "mod.py::f")
    dropped = {
        "type", "lines", "hash_struct", "hash_source",
        "what", "why", "where", "variable", "prefix",
    }
    assert dropped.isdisjoint(req.facts), (
        f"Internal fields leaked into the prompt facts: {sorted(dropped & set(req.facts))}"
    )

    # Doc-useful fields survive.
    assert req.facts["id"] == "mod.py::f"
    assert req.facts["file"] == "mod.py"
    assert req.facts["signature"] == "def f()"

    mod_req = next(r for r in rec.requests if r.node_id == "mod.py")
    assert "type" not in mod_req.facts
    assert mod_req.facts["id"] == "mod.py"


# ---------------------------------------------------------------------------
# Test 13: request/response model edges reach the handler (fix 6)
# ---------------------------------------------------------------------------

def test_request_model_edges_reach_handler(tmp_path: Path) -> None:
    """A route is never summarized, so its model edges must also reach the handler."""
    handler = _node("mod.py::create", NodeType.FUNCTION, file="mod.py")
    mod = _node("mod.py", NodeType.MODULE, file="mod.py")
    model = _node("mod.py::CommentInCreate", NodeType.CLASS, file="mod.py")
    route = Node(
        id="route:POST /api/comments",
        type=NodeType.ROUTE,
        file="mod.py",
        lines=(1, 5),
        hash_struct="rhs",
        hash_source="rhs",
        method="POST",
        full_path="/api/comments",
        status_code=201,
    )
    graph = FactGraph(
        nodes=(handler, mod, model, route),
        edges=(
            Edge(type=EdgeType.CONTAINS, from_id="mod.py", to_id="mod.py::create"),
            Edge(type=EdgeType.CONTAINS, from_id="mod.py", to_id="mod.py::CommentInCreate"),
            Edge(
                type=EdgeType.HANDLES,
                from_id="route:POST /api/comments",
                to_id="mod.py::create",
            ),
            Edge(
                type=EdgeType.REQUEST_MODEL,
                from_id="route:POST /api/comments",
                to_id="mod.py::CommentInCreate",
            ),
        ),
        unresolved=(),
    )

    rec = RecordingSummarizer()
    run_hierarchy(graph, rec, tmp_path, existing_cache={})

    handler_req = next(r for r in rec.requests if r.node_id == "mod.py::create")
    model_edges = [e for e in handler_req.edges if e.get("type") == "request_model"]
    assert len(model_edges) == 1, (
        f"Expected the request_model edge on the handler, got {handler_req.edges}"
    )
    assert model_edges[0]["to"] == "mod.py::CommentInCreate"


# ---------------------------------------------------------------------------
# Depth batching (sub-task 1)
# ---------------------------------------------------------------------------

def _batch_ids(batches: list[list[Node]]) -> list[list[str]]:
    return [[node.id for node in batch] for batch in batches]


def _nested_graph() -> FactGraph:
    """package → module → {class → method, function}."""
    return _make_graph(
        _node("pkg", NodeType.PACKAGE),
        _node("pkg/mod.py", NodeType.MODULE),
        _node("pkg/mod.py::Cls", NodeType.CLASS),
        _node("pkg/mod.py::Cls::m", NodeType.FUNCTION),
        _node("pkg/mod.py::f", NodeType.FUNCTION),
        edges=(
            _contains("pkg", "pkg/mod.py"),
            _contains("pkg/mod.py", "pkg/mod.py::Cls"),
            _contains("pkg/mod.py::Cls", "pkg/mod.py::Cls::m"),
            _contains("pkg/mod.py", "pkg/mod.py::f"),
        ),
    )


def test_batched_order_children_before_parents() -> None:
    """No batch contains a node whose child is in the same or a later batch."""
    graph = _nested_graph()
    index = build_contains_index(graph)
    batches = batched_topological_order(graph, index)
    batch_of = {
        node.id: depth for depth, batch in enumerate(batches) for node in batch
    }

    assert len(batches) >= 3
    for parent_id, children in index.items():
        for child in children:
            assert batch_of[child.id] < batch_of[parent_id], (
                f"{child.id} must be summarized before its parent {parent_id}"
            )

    # The method and the module-level function are both leaves.
    assert batch_of["pkg/mod.py::Cls::m"] == 0
    assert batch_of["pkg/mod.py::f"] == 0


def test_batched_order_is_deterministic() -> None:
    """Same graph → same batches, even if the node list is in a different order."""
    graph = _nested_graph()
    index = build_contains_index(graph)

    first = _batch_ids(batched_topological_order(graph, index))
    second = _batch_ids(batched_topological_order(graph, index))
    assert first == second

    reversed_graph = _make_graph(*reversed(graph.nodes), edges=graph.edges)
    assert _batch_ids(batched_topological_order(reversed_graph, index)) == first


def test_batched_order_covers_all_nodes() -> None:
    """Batching covers exactly the nodes the flat topological order covers."""
    graph = _nested_graph()
    index = build_contains_index(graph)

    batched = {node.id for batch in batched_topological_order(graph, index) for node in batch}
    flat = {node.id for node in topological_order(graph, index)}
    assert batched == flat


# ---------------------------------------------------------------------------
# Parallel execution (sub-task 3)
# ---------------------------------------------------------------------------

class SlowStubSummarizer:
    """Deterministic stub with a fixed delay, to observe real concurrency."""

    def __init__(self, delay: float = 0.05) -> None:
        self.delay = delay
        self._inner = StubSummarizer()

    def summarize(self, req: SummaryRequest) -> SummaryResult:
        time.sleep(self.delay)
        return self._inner.summarize(req)


class FailingStubSummarizer:
    """Raises on exactly one call, no matter which thread reaches it first."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.calls = 0
        self._inner = StubSummarizer()

    def summarize(self, req: SummaryRequest) -> SummaryResult:
        with self._lock:
            self.calls += 1
            call_number = self.calls
        if call_number == 1:
            raise RuntimeError("boom")
        return self._inner.summarize(req)


def _functions_graph(module_count: int, functions_per_module: int) -> FactGraph:
    """Build ``module_count`` modules, each containing ``functions_per_module`` functions."""
    nodes: list[Node] = []
    edges: list[Edge] = []
    for m in range(module_count):
        file = f"pkg/mod{m}.py"
        nodes.append(_node(file, NodeType.MODULE, file=file))
        for f in range(functions_per_module):
            func_id = f"{file}::f{f}"
            nodes.append(_node(func_id, NodeType.FUNCTION, file=file))
            edges.append(_contains(file, func_id))
    return _make_graph(*nodes, edges=tuple(edges))


def test_parallel_output_matches_sequential(tmp_path: Path) -> None:
    """Parallel output is identical to sequential output, element by element."""
    graph = _functions_graph(module_count=2, functions_per_module=4)

    sequential = run_hierarchy(
        graph, StubSummarizer(), tmp_path, {}, max_workers=1
    )
    parallel = run_hierarchy(
        graph, StubSummarizer(), tmp_path, {}, max_workers=4
    )

    assert parallel == sequential
    assert [r.node_id for r in parallel] == [r.node_id for r in sequential]


def test_parallel_batch_is_faster(tmp_path: Path) -> None:
    """Four workers finish 16 leaf nodes in well under the sequential time."""
    graph = _functions_graph(module_count=1, functions_per_module=16)

    start = time.perf_counter()
    run_hierarchy(
        graph, SlowStubSummarizer(), tmp_path, {}, max_workers=1
    )
    sequential = time.perf_counter() - start

    start = time.perf_counter()
    run_hierarchy(
        graph, SlowStubSummarizer(), tmp_path, {}, max_workers=4
    )
    parallel = time.perf_counter() - start

    assert parallel < sequential * 0.6, (
        f"Expected parallel (<{sequential * 0.6:.3f}s) to beat sequential "
        f"({sequential:.3f}s) by at least 1.67x, got {parallel:.3f}s"
    )


def test_parallel_exception_handling(tmp_path: Path) -> None:
    """One failing call becomes one needs_human_review result; the run continues."""
    functions = [
        _node(f"mod.py::f{i}", NodeType.FUNCTION, file="mod.py") for i in range(4)
    ]
    graph = _make_graph(*functions)

    results = run_hierarchy(
        graph, FailingStubSummarizer(), tmp_path, {}, max_workers=4
    )

    assert {r.node_id for r in results} == {f.id for f in functions} | {SYSTEM_NODE_ID}
    failed = [r for r in results if r.backend == "needs_human_review"]
    assert len(failed) == 1, f"Expected exactly one failed node, got {failed}"
    assert failed[0].hash_input == ""


def test_workers_below_one_is_sequential(tmp_path: Path) -> None:
    """max_workers=0 is clamped to 1 and produces the sequential output."""
    graph = _functions_graph(module_count=1, functions_per_module=4)

    zero = run_hierarchy(
        graph, StubSummarizer(), tmp_path, {}, max_workers=0
    )
    one = run_hierarchy(
        graph, StubSummarizer(), tmp_path, {}, max_workers=1
    )

    assert zero == one


# ---------------------------------------------------------------------------
# Residual source: a parent sees only the part of its span no child covers
# ---------------------------------------------------------------------------

def _write_module(tmp_path: Path, text: str) -> None:
    (tmp_path / "mod.py").write_text(text, encoding="utf-8")


def test_residual_source_masks_contiguous_children(tmp_path: Path) -> None:
    """A class body *is* its methods: only the header and docstring survive."""
    _write_module(
        tmp_path,
        "class Repo(Base):\n"
        '    """Doc."""\n'
        "    def a(self):\n"
        "        return 1\n"
        "\n"
        "    def b(self):\n"
        "        return 2\n"
        "\n"
        "    def c(self):\n"
        "        return 3\n",
    )
    cls = _node("mod.py::Repo", NodeType.CLASS, file="mod.py", lines=(1, 10))
    children = [
        _node("mod.py::Repo::a", NodeType.FUNCTION, file="mod.py", lines=(3, 4)),
        _node("mod.py::Repo::b", NodeType.FUNCTION, file="mod.py", lines=(6, 7)),
        _node("mod.py::Repo::c", NodeType.FUNCTION, file="mod.py", lines=(9, 10)),
    ]

    assert read_residual_source(tmp_path, cls, children) == (
        'class Repo(Base):\n    """Doc."""'
    )


def test_residual_source_keeps_class_level_statements(tmp_path: Path) -> None:
    """Statements between methods, and nested classes (no summary anywhere) stay."""
    _write_module(
        tmp_path,
        "class Repo(Base):\n"
        "    LIMIT = 10\n"
        "\n"
        "    class Nested:\n"
        "        def inner(self):\n"
        "            return 1\n"
        "\n"
        "    def a(self):\n"
        "        return 2\n",
    )
    cls = _node("mod.py::Repo", NodeType.CLASS, file="mod.py", lines=(1, 9))
    children = [
        _node("mod.py::Repo::a", NodeType.FUNCTION, file="mod.py", lines=(8, 9)),
    ]

    assert read_residual_source(tmp_path, cls, children) == (
        "class Repo(Base):\n"
        "    LIMIT = 10\n"
        "\n"
        "    class Nested:\n"
        "        def inner(self):\n"
        "            return 1"
    )


def test_residual_source_full_for_childless_class(tmp_path: Path) -> None:
    """A field-only model has no children, and its code *is* the evidence."""
    _write_module(tmp_path, 'class Model(BaseModel):\n    text: str = "x"\n')
    cls = _node("mod.py::Model", NodeType.CLASS, file="mod.py", lines=(1, 2))

    assert read_residual_source(tmp_path, cls, []) == (
        'class Model(BaseModel):\n    text: str = "x"'
    )


def test_residual_source_module_keeps_imports_and_constants(tmp_path: Path) -> None:
    """Imports are the module's own architectural signal; child bodies are masked."""
    _write_module(
        tmp_path,
        "from app.db import session\n"
        "\n"
        "LIMIT = 10\n"
        "\n"
        "\n"
        "class Thing:\n"
        "    def m(self):\n"
        "        return 1\n",
    )
    mod = _node("mod.py", NodeType.MODULE, file="mod.py", lines=(1, 8))
    children = [_node("mod.py::Thing", NodeType.CLASS, file="mod.py", lines=(6, 8))]

    assert read_residual_source(tmp_path, mod, children) == (
        "from app.db import session\n\nLIMIT = 10"
    )


def test_residual_source_empty_module_and_foreign_child(tmp_path: Path) -> None:
    """An empty span yields ""; a child in another file covers nothing."""
    _write_module(tmp_path, "def f():\n    return 1\n")

    empty = _node("mod.py", NodeType.MODULE, file="mod.py", lines=(1, 0))
    assert read_residual_source(tmp_path, empty, []) == ""

    func = _node("mod.py::f", NodeType.FUNCTION, file="mod.py", lines=(1, 2))
    foreign = _node(
        "other.py::g", NodeType.FUNCTION, file="other.py", lines=(1, 1)
    )
    assert read_residual_source(tmp_path, func, [foreign]) == "def f():\n    return 1"

