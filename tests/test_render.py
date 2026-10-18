"""Tests for the render package: index page, module pages, Mermaid diagram, API table."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from docgen.facts.schema import Edge, EdgeType, FactGraph, Node, NodeType, Unresolved


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pkg(pkg_id: str) -> Node:
    return Node(
        id=pkg_id,
        type=NodeType.PACKAGE,
        file="",
        lines=(0, 0),
        hash_struct="hs_" + pkg_id.replace("/", "_"),
        hash_source="",
        name=pkg_id.split("/")[-1],
    )


def _make_mod(mod_id: str, name: str = "") -> Node:
    return Node(
        id=mod_id,
        type=NodeType.MODULE,
        file=mod_id,
        lines=(1, 10),
        hash_struct="hs_" + mod_id.replace("/", "_"),
        hash_source="src_" + mod_id.replace("/", "_"),
        name=name or mod_id.split("/")[-1].replace(".py", ""),
    )


def _make_func(func_id: str, name: str = "") -> Node:
    return Node(
        id=func_id,
        type=NodeType.FUNCTION,
        file=func_id.split("::")[0],
        lines=(1, 5),
        hash_struct="hs_func",
        hash_source="src_func",
        name=name or func_id.rsplit("::", 1)[-1],
        signature="def greet() -> None",
    )


def _make_route(route_id: str, method: str = "GET", path: str = "/items") -> Node:
    return Node(
        id=route_id,
        type=NodeType.ROUTE,
        file="",
        lines=(0, 0),
        hash_struct="hs_route",
        hash_source="",
        method=method,
        full_path=path,
        status_code=200,
        name=route_id,
    )


def _simple_graph() -> FactGraph:
    """A minimal graph: one package, one module, one function."""
    pkg = _make_pkg("myapp")
    mod = _make_mod("myapp/utils.py", "utils")
    func = _make_func("myapp/utils.py::greet", "greet")
    edges = (
        Edge(type=EdgeType.CONTAINS, from_id="myapp", to_id="myapp/utils.py"),
        Edge(type=EdgeType.CONTAINS, from_id="myapp/utils.py", to_id="myapp/utils.py::greet"),
    )
    return FactGraph(nodes=(pkg, mod, func), edges=edges, unresolved=())


def _summaries(graph: FactGraph) -> dict[str, str]:
    return {n.id: f"Summary of {n.id}." for n in graph.nodes}


# ---------------------------------------------------------------------------
# Test 1: index page contains system summary
# ---------------------------------------------------------------------------

def test_render_index_contains_system_summary() -> None:
    """render_index embeds the system-level summary text."""
    from docgen.render.markdown import render_index

    graph = _simple_graph()
    summaries = _summaries(graph)
    summaries["system"] = "This is the overall system summary."

    text, record = render_index(graph, summaries)
    assert "This is the overall system summary." in text
    assert "system" in record.fact_ids


# ---------------------------------------------------------------------------
# Test 2: index page contains a Mermaid fenced block
# ---------------------------------------------------------------------------

def test_render_index_contains_mermaid_block() -> None:
    """render_index includes a ```mermaid code fence."""
    from docgen.render.markdown import render_index

    graph = _simple_graph()
    text, _ = render_index(graph, _summaries(graph))
    assert "```mermaid" in text


# ---------------------------------------------------------------------------
# Test 3: Mermaid block contains only package nodes (no .py paths)
# ---------------------------------------------------------------------------

def test_render_mermaid_packages_only() -> None:
    """render_mermaid_diagram never emits .py file IDs inside the diagram."""
    from docgen.render.mermaid import render_mermaid_diagram

    pkg_a = _make_pkg("myapp")
    pkg_b = _make_pkg("myapp/db")
    mod = _make_mod("myapp/db/models.py")
    edges = (
        Edge(type=EdgeType.CONTAINS, from_id="myapp", to_id="myapp/db"),
        Edge(type=EdgeType.CONTAINS, from_id="myapp/db", to_id="myapp/db/models.py"),
    )
    graph = FactGraph(nodes=(pkg_a, pkg_b, mod), edges=edges, unresolved=())

    diagram = render_mermaid_diagram(graph)
    assert "```mermaid" in diagram
    assert ".py" not in diagram
    # Both package labels should appear
    assert "myapp" in diagram
    assert "db" in diagram


# ---------------------------------------------------------------------------
# Test 4: module page is written at the mirrored path
# ---------------------------------------------------------------------------

def test_render_module_page_mirrored_path(tmp_path: Path) -> None:
    """render_module_page writes the page at the mirrored path under generated/pages/."""
    from docgen.render.markdown import render_module_page, write_pages

    mod = _make_mod("target/app/utils.py", "utils")
    func = _make_func("target/app/utils.py::helper", "helper")
    edges = (Edge(type=EdgeType.CONTAINS, from_id="target/app/utils.py", to_id="target/app/utils.py::helper"),)
    graph = FactGraph(nodes=(mod, func), edges=edges, unresolved=())

    text, record = render_module_page(mod, graph, {})
    assert record.page_path == "generated/pages/target/app/utils.md"

    write_pages([(record.page_path, text)], tmp_path)
    expected = tmp_path / "generated" / "pages" / "target" / "app" / "utils.md"
    assert expected.exists()


# ---------------------------------------------------------------------------
# Test 5: module page contains the module summary
# ---------------------------------------------------------------------------

def test_render_module_page_contains_summary() -> None:
    """render_module_page embeds the module-level summary."""
    from docgen.render.markdown import render_module_page

    mod = _make_mod("myapp/core.py", "core")
    graph = FactGraph(nodes=(mod,), edges=(), unresolved=())
    summaries = {"myapp/core.py": "Handles core logic for the application."}

    text, record = render_module_page(mod, graph, summaries)
    assert "Handles core logic for the application." in text
    assert "myapp/core.py" in record.fact_ids


# ---------------------------------------------------------------------------
# Test 6: API table has one data row per ROUTE node
# ---------------------------------------------------------------------------

def test_render_api_table_has_all_routes() -> None:
    """render_api_table produces one table data row for each ROUTE node."""
    from docgen.render.api_table import render_api_table

    route1 = _make_route("route::GET/items", "GET", "/items")
    route2 = _make_route("route::POST/items", "POST", "/items")
    graph = FactGraph(nodes=(route1, route2), edges=(), unresolved=())

    text, fact_ids = render_api_table(graph, {})
    # Two data rows (not counting the header rows)
    data_rows = [line for line in text.splitlines() if line.startswith("|") and "Method" not in line and "---" not in line]
    assert len(data_rows) == 2
    assert "GET" in text
    assert "POST" in text


# ---------------------------------------------------------------------------
# Test 7: missing summary → placeholder, no crash
# ---------------------------------------------------------------------------

def test_render_missing_summary_graceful() -> None:
    """Absent summary for any node → '_(no summary yet)_' placeholder, no exception."""
    from docgen.render.markdown import render_module_page

    mod = _make_mod("myapp/missing.py", "missing")
    func = _make_func("myapp/missing.py::do_thing", "do_thing")
    edges = (Edge(type=EdgeType.CONTAINS, from_id="myapp/missing.py", to_id="myapp/missing.py::do_thing"),)
    graph = FactGraph(nodes=(mod, func), edges=edges, unresolved=())

    # Pass an empty summaries map — no summary for either node
    text, _ = render_module_page(mod, graph, {})
    assert "_(no summary yet)_" in text


# ---------------------------------------------------------------------------
# Test 8: render output is deterministic
# ---------------------------------------------------------------------------

def test_render_output_is_deterministic() -> None:
    """Calling render_all twice on the same inputs produces byte-identical pages."""
    from docgen.render.markdown import render_all

    graph = _simple_graph()
    summaries = _summaries(graph)

    records1, pages1 = render_all(graph, summaries)
    records2, pages2 = render_all(graph, summaries)

    pages_dict1 = {path: text for path, text in pages1}
    pages_dict2 = {path: text for path, text in pages2}

    assert pages_dict1 == pages_dict2
    # Record page paths match too
    assert [r.page_path for r in records1] == [r.page_path for r in records2]
