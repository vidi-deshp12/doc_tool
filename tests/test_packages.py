"""Tests for extract/packages.py — synthesize_packages."""

from __future__ import annotations

from pathlib import Path

import pytest

from docgen.extract.packages import synthesize_packages
from docgen.facts.schema import Edge, EdgeType, Node, NodeType
from docgen.summarize.hierarchy import topological_order, build_contains_index
from docgen.facts.schema import FactGraph


def _mod(id: str) -> Node:
    """Minimal MODULE node."""
    return Node(
        id=id, type=NodeType.MODULE, file=id,
        lines=(1, 10), hash_struct="hs", hash_source="hsrc",
    )


# ---------------------------------------------------------------------------
# Test 1: Two modules in the same directory → one package + two CONTAINS edges
# ---------------------------------------------------------------------------

def test_single_directory_two_modules() -> None:
    modules = [_mod("target/app/routes.py"), _mod("target/app/models.py")]
    pkg_nodes, pkg_edges = synthesize_packages(modules, source_root="target")

    pkg_ids = {n.id for n in pkg_nodes}
    assert "target/app" in pkg_ids, f"Expected package target/app, got {pkg_ids}"

    contains = [e for e in pkg_edges if e.from_id == "target/app" and e.type == EdgeType.CONTAINS]
    child_ids = {e.to_id for e in contains}
    assert child_ids == {"target/app/routes.py", "target/app/models.py"}


# ---------------------------------------------------------------------------
# Test 2: Nested directories → parent CONTAINS child package
# ---------------------------------------------------------------------------

def test_nested_directories() -> None:
    modules = [
        _mod("target/app/db/queries.py"),
        _mod("target/app/db/models.py"),
        _mod("target/app/routes.py"),
    ]
    pkg_nodes, pkg_edges = synthesize_packages(modules, source_root="target")

    pkg_ids = {n.id for n in pkg_nodes}
    assert "target/app/db" in pkg_ids
    assert "target/app" in pkg_ids

    # target/app must CONTAIN target/app/db (not just target/app/routes.py)
    app_contains = {e.to_id for e in pkg_edges if e.from_id == "target/app"}
    assert "target/app/db" in app_contains, (
        f"target/app should contain target/app/db; got {app_contains}"
    )
    assert "target/app/routes.py" in app_contains


# ---------------------------------------------------------------------------
# Test 3: Module in root source directory → no package for the source root
# ---------------------------------------------------------------------------

def test_no_package_for_source_root() -> None:
    """Modules directly under source_root must not produce a package node for source_root."""
    modules = [_mod("target/main.py"), _mod("target/config.py")]
    pkg_nodes, pkg_edges = synthesize_packages(modules, source_root="target")

    pkg_ids = {n.id for n in pkg_nodes}
    assert "target" not in pkg_ids, (
        "Source root directory must not be synthesized as a package"
    )
    # No package nodes at all since all modules are directly under source_root
    assert pkg_nodes == []


# ---------------------------------------------------------------------------
# Test 4: hash_struct changes when a module is added
# ---------------------------------------------------------------------------

def test_hash_struct_changes_on_new_module() -> None:
    modules_v1 = [_mod("target/app/a.py")]
    modules_v2 = [_mod("target/app/a.py"), _mod("target/app/b.py")]

    pkgs_v1, _ = synthesize_packages(modules_v1, source_root="target")
    pkgs_v2, _ = synthesize_packages(modules_v2, source_root="target")

    pkg_v1 = next(n for n in pkgs_v1 if n.id == "target/app")
    pkg_v2 = next(n for n in pkgs_v2 if n.id == "target/app")

    assert pkg_v1.hash_struct != pkg_v2.hash_struct, (
        "Adding a module must change the package hash_struct"
    )


# ---------------------------------------------------------------------------
# Test 5: topological_order places package nodes after their modules
# ---------------------------------------------------------------------------

def test_topological_order_packages_after_modules() -> None:
    """Packages must come after the modules they contain in topological order."""
    mod_node = _mod("target/app/routes.py")
    pkg_nodes, pkg_edges = synthesize_packages([mod_node], source_root="target")

    all_nodes = [mod_node] + pkg_nodes
    all_edges = pkg_edges

    graph = FactGraph(
        nodes=tuple(all_nodes),
        edges=tuple(all_edges),
        unresolved=(),
    )
    index = build_contains_index(graph)
    order = topological_order(graph, index)

    order_ids = [n.id for n in order]
    assert "target/app/routes.py" in order_ids
    assert "target/app" in order_ids

    mod_pos = order_ids.index("target/app/routes.py")
    pkg_pos = order_ids.index("target/app")
    assert mod_pos < pkg_pos, (
        f"Module (pos {mod_pos}) must come before its package (pos {pkg_pos})"
    )
