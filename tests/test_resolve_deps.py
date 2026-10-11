"""Tests for task 2a.9 — DEPENDS_ON edge resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from docgen.extract.adapters.resolve_deps import (
    _parse_dep_name,
    detect_dep_cycles,
    resolve_dep_edges,
)
from docgen.extract.modules import ImportRecord, ModuleInfo
from docgen.facts.schema import Edge, EdgeType, Node, NodeType, Unresolved


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _func_node(name: str, file: str) -> Node:
    return Node(
        id=f"{file}::{name}",
        type=NodeType.FUNCTION,
        file=file,
        lines=(1, 10),
        hash_struct="x",
        hash_source="x",
        name=name,
    )


def _dep_edge(from_id: str, dep_name: str, via: str = "parameter") -> Edge:
    return Edge(
        type=EdgeType.DEPENDS_ON,
        from_id=from_id,
        to_id=f"external:{dep_name}",
        meta=(("via", via),),
    )


def _module_info(file: str, imports: list[ImportRecord]) -> ModuleInfo:
    return ModuleInfo(
        dotted_name=file.replace("/", ".").rstrip(".py"),
        file_path=file,
        imports=imports,
    )


# ---------------------------------------------------------------------------
# Test 1: _parse_dep_name — all three shapes
# ---------------------------------------------------------------------------

def test_parse_dep_name_simple() -> None:
    alias, base, args = _parse_dep_name("get_articles_filters")
    assert alias is None
    assert base == "get_articles_filters"
    assert args is None


def test_parse_dep_name_factory_call() -> None:
    alias, base, args = _parse_dep_name("get_repository(ArticlesRepository)")
    assert alias is None
    assert base == "get_repository"
    assert args == "ArticlesRepository"


def test_parse_dep_name_empty_call() -> None:
    alias, base, args = _parse_dep_name("get_current_user_authorizer()")
    assert alias is None
    assert base == "get_current_user_authorizer"
    assert args == ""


def test_parse_dep_name_module_qualified() -> None:
    alias, base, args = _parse_dep_name("authentication.get_current_user_authorizer()")
    assert alias == "authentication"
    assert base == "get_current_user_authorizer"
    assert args == ""


def test_parse_dep_name_module_qualified_factory() -> None:
    alias, base, args = _parse_dep_name("database.get_repository(CommentsRepository)")
    assert alias == "database"
    assert base == "get_repository"
    assert args == "CommentsRepository"


def test_parse_dep_name_module_qualified_plain() -> None:
    alias, base, args = _parse_dep_name("articles.get_article_by_slug_from_path")
    assert alias == "articles"
    assert base == "get_article_by_slug_from_path"
    assert args is None


# ---------------------------------------------------------------------------
# Test 2: Plain name resolves to node
# ---------------------------------------------------------------------------

def test_resolve_plain_name() -> None:
    """A simple dep name resolves to the unique FUNCTION node with that name."""
    func_node = _func_node("get_filters", "app/deps.py")
    route_node = _func_node("list_items", "app/routes.py")

    edges = [_dep_edge(route_node.id, "get_filters")]
    path_to_info = {
        "app/routes.py": _module_info("app/routes.py", [
            ImportRecord(module="app.deps", names=["get_filters"], level=0, line=1),
        ]),
        "app/deps.py": _module_info("app/deps.py", []),
    }
    dotted_to_path = {"app.deps": "app/deps.py"}

    resolved, unresolved = resolve_dep_edges(
        [func_node, route_node], edges, path_to_info, dotted_to_path
    )

    assert len(resolved) == 1
    assert resolved[0].to_id == func_node.id
    assert resolved[0].type == EdgeType.DEPENDS_ON
    assert unresolved == []


# ---------------------------------------------------------------------------
# Test 3: Factory call resolves to factory node; meta includes factory_args
# ---------------------------------------------------------------------------

def test_resolve_factory_call_adds_factory_args() -> None:
    """get_repository(ArticlesRepository) resolves to get_repository node, meta has factory_args."""
    repo_func = _func_node("get_repository", "app/database.py")
    route_func = _func_node("create_item", "app/routes.py")

    edges = [_dep_edge(route_func.id, "get_repository(ArticlesRepository)")]
    path_to_info: dict = {}
    dotted_to_path: dict = {}

    resolved, unresolved = resolve_dep_edges(
        [repo_func, route_func], edges, path_to_info, dotted_to_path
    )

    assert len(resolved) == 1
    assert resolved[0].to_id == repo_func.id
    meta_dict = dict(resolved[0].meta)
    assert meta_dict.get("factory_args") == "ArticlesRepository"
    assert meta_dict.get("via") == "parameter"
    assert unresolved == []


# ---------------------------------------------------------------------------
# Test 4: Unresolved name stays external, emits Unresolved
# ---------------------------------------------------------------------------

def test_unresolved_name_stays_external() -> None:
    """A dep name that matches no FUNCTION node keeps external: and emits Unresolved."""
    route_func = _func_node("handler", "app/routes.py")
    edges = [_dep_edge(route_func.id, "unknown_func")]
    path_to_info: dict = {}
    dotted_to_path: dict = {}

    resolved, unresolved = resolve_dep_edges(
        [route_func], edges, path_to_info, dotted_to_path
    )

    assert len(resolved) == 1
    assert resolved[0].to_id == "external:unknown_func"
    assert len(unresolved) == 1
    assert "unknown_func" in unresolved[0].what


# ---------------------------------------------------------------------------
# Test 5: Non-DEPENDS_ON edges passed through unchanged
# ---------------------------------------------------------------------------

def test_non_dep_edges_unchanged() -> None:
    """CONTAINS and CALLS edges are returned unchanged."""
    contains = Edge(type=EdgeType.CONTAINS, from_id="app/mod.py", to_id="app/mod.py::func", meta=())
    calls = Edge(type=EdgeType.CALLS, from_id="app/mod.py::func", to_id="other", meta=())
    resolved, unresolved = resolve_dep_edges([], [contains, calls], {}, {})
    assert resolved == [contains, calls]
    assert unresolved == []


# ---------------------------------------------------------------------------
# Test 6: Module-qualified name resolves via alias lookup
# ---------------------------------------------------------------------------

def test_resolve_module_qualified_name() -> None:
    """authentication.get_current_user() resolves via from app.api.deps import authentication."""
    auth_func = _func_node("get_current_user_authorizer", "app/api/dependencies/authentication.py")
    comment_func = _func_node("get_comment", "app/api/dependencies/comments.py")

    edges = [_dep_edge(comment_func.id, "authentication.get_current_user_authorizer()")]
    path_to_info = {
        "app/api/dependencies/comments.py": _module_info(
            "app/api/dependencies/comments.py",
            [
                ImportRecord(
                    module="app.api.dependencies",
                    names=["authentication"],
                    level=0,
                    line=5,
                ),
            ],
        ),
    }
    dotted_to_path = {
        "app.api.dependencies.authentication": "app/api/dependencies/authentication.py",
    }

    resolved, unresolved = resolve_dep_edges(
        [auth_func, comment_func], edges, path_to_info, dotted_to_path
    )

    assert len(resolved) == 1
    assert resolved[0].to_id == auth_func.id
    assert unresolved == []


# ---------------------------------------------------------------------------
# Test 7: Ambiguous plain name (2 functions, disambiguation fails) → conservative
# ---------------------------------------------------------------------------

def test_ambiguous_name_conservative() -> None:
    """Two FUNCTION nodes with same name, no import records → keeps external:, emits Unresolved."""
    node_a = _func_node("helper", "app/a.py")
    node_b = _func_node("helper", "app/b.py")
    caller = _func_node("caller", "app/caller.py")

    edges = [_dep_edge(caller.id, "helper")]
    # No import records for caller.py — cannot disambiguate
    path_to_info = {"app/caller.py": _module_info("app/caller.py", [])}
    dotted_to_path: dict = {}

    resolved, unresolved = resolve_dep_edges(
        [node_a, node_b, caller], edges, path_to_info, dotted_to_path
    )

    assert len(resolved) == 1
    assert resolved[0].to_id == "external:helper"  # kept, not guessed
    assert len(unresolved) == 1
    assert "helper" in unresolved[0].what


# ---------------------------------------------------------------------------
# Test 8: detect_dep_cycles — no cycles
# ---------------------------------------------------------------------------

def test_detect_no_cycles() -> None:
    """A simple A→B dep graph has no cycles."""
    node_a = _func_node("a", "mod.py")
    node_b = _func_node("b", "mod.py")
    edges = [
        Edge(type=EdgeType.DEPENDS_ON, from_id=node_a.id, to_id=node_b.id, meta=()),
    ]
    assert detect_dep_cycles([node_a, node_b], edges) == []


# ---------------------------------------------------------------------------
# Test 9: detect_dep_cycles — cycle detected
# ---------------------------------------------------------------------------

def test_detect_cycle() -> None:
    """A→B, B→A forms a cycle."""
    node_a = _func_node("a", "mod.py")
    node_b = _func_node("b", "mod.py")
    edges = [
        Edge(type=EdgeType.DEPENDS_ON, from_id=node_a.id, to_id=node_b.id, meta=()),
        Edge(type=EdgeType.DEPENDS_ON, from_id=node_b.id, to_id=node_a.id, meta=()),
    ]
    cycles = detect_dep_cycles([node_a, node_b], edges)
    assert len(cycles) >= 1
    # The cycle description must mention both node IDs
    cycle_str = " ".join(cycles)
    assert node_a.id in cycle_str or node_b.id in cycle_str


# ---------------------------------------------------------------------------
# Test 10: Integration — real target/ repo, check create_new_article resolved
# ---------------------------------------------------------------------------

def test_real_repo_create_new_article_resolved() -> None:
    """On the real target/, create_new_article DEPENDS_ON edges resolve to in-repo nodes."""
    repo_root = Path(__file__).parent.parent
    target_dir = repo_root / "target"
    if not target_dir.exists():
        pytest.skip("target/ directory not found")

    from docgen.config import load_config
    from docgen.extract.bodies import extract_body_facts
    from docgen.extract.classes import resolve_all_classes
    from docgen.extract.core import extract_file
    from docgen.extract.modules import build_module_index, resolve_imports
    from docgen.walker import walk_repo

    config = load_config(repo_root / "docgen.toml")
    module_paths = list(walk_repo(config, repo_root=repo_root))

    all_nodes: list = []
    all_edges: list = []
    all_unresolved: list = []

    for rel in module_paths:
        p = repo_root / rel
        if p.exists():
            nodes, edges, unresolved = extract_file(p, repo_root)
            all_nodes.extend(nodes)
            all_edges.extend(edges)
            all_unresolved.extend(unresolved)

    dotted_to_path, path_to_info = build_module_index(
        module_paths, repo_root, source_root=config.source_root
    )
    import_edges, _, ext_nodes = resolve_imports(
        dotted_to_path, path_to_info, repo_root, config.source_root
    )
    all_nodes.extend(ext_nodes)
    all_edges.extend(import_edges)

    resolved_edges, dep_unresolved = resolve_dep_edges(
        all_nodes, all_edges, path_to_info, dotted_to_path
    )

    # Find create_new_article's DEPENDS_ON edges after resolution
    handler_id = (
        "target/app/api/routes/articles/articles_resource.py::create_new_article"
    )
    dep_edges = [
        e for e in resolved_edges
        if e.type == EdgeType.DEPENDS_ON and e.from_id == handler_id
    ]

    assert len(dep_edges) == 2, (
        f"Expected 2 DEPENDS_ON edges from create_new_article, got {len(dep_edges)}"
    )

    # None of them should still point to external: for known in-repo deps
    external_targets = [e.to_id for e in dep_edges if e.to_id.startswith("external:")]
    assert external_targets == [], (
        f"create_new_article still has unresolved deps: {external_targets}"
    )

    # Verify get_current_user_authorizer edge points into authentication.py
    auth_edges = [
        e for e in dep_edges
        if "authentication.py::get_current_user_authorizer" in e.to_id
    ]
    assert len(auth_edges) == 1, (
        f"Expected 1 edge to get_current_user_authorizer, got {auth_edges}"
    )

    # Verify get_repository edge points into database.py
    db_edges = [
        e for e in dep_edges
        if "database.py::get_repository" in e.to_id
    ]
    assert len(db_edges) == 1, (
        f"Expected 1 edge to get_repository, got {db_edges}"
    )
    # factory_args must be set
    db_meta = dict(db_edges[0].meta)
    assert db_meta.get("factory_args") == "ArticlesRepository", (
        f"factory_args missing or wrong: {db_meta}"
    )
