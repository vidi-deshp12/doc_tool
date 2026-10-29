"""Tests for the FastAPI adapter (task 2a.8a)."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from docgen.extract.adapters.fastapi import (
    IntrospectionError,
    _extract_status_code,
    _find_class_node,
    _openapi_to_facts,
    _qualname_to_node_id,
    extract,
)
from docgen.extract.adapters.base import AdapterResult
from docgen.facts.schema import Edge, EdgeType, Node, NodeType


# ---------------------------------------------------------------------------
# Test 1: _extract_status_code picks first 2xx key
# ---------------------------------------------------------------------------

def test_extract_status_code_picks_2xx() -> None:
    assert _extract_status_code({"200": {}, "422": {}}) == 200
    assert _extract_status_code({"201": {}, "422": {}}) == 201
    assert _extract_status_code({"422": {}}) == 200  # default
    assert _extract_status_code({}) == 200


# ---------------------------------------------------------------------------
# Test 2: _openapi_to_facts on a minimal OpenAPI dict
# ---------------------------------------------------------------------------

def _make_func_node(name: str, file: str = "app/routes.py") -> Node:
    return Node(
        id=f"{file}::{name}",
        type=NodeType.FUNCTION,
        file=file,
        lines=(1, 10),
        hash_struct="x",
        hash_source="x",
        name=name,
    )


def test_openapi_to_facts_single_route() -> None:
    """Minimal OpenAPI with 1 route → 1 ROUTE node + 1 HANDLES edge."""
    openapi_dict = {
        "paths": {
            "/items": {
                "get": {
                    "responses": {"200": {"description": "OK"}},
                }
            }
        }
    }
    handler_map = {
        "GET /items": {
            "handler": "list_items",
            "module": "app.routes",
            "qualname": "list_items",
            "name": "items:list",
        },
    }
    func_node = _make_func_node("list_items")
    all_nodes = [func_node]

    route_nodes, edges, unresolved = _openapi_to_facts(
        openapi_dict, handler_map, all_nodes, Path("."),
        dotted_to_path={"app.routes": "app/routes.py"},
    )

    assert len(route_nodes) == 1
    r = route_nodes[0]
    assert r.id == "route:GET /items"
    assert r.method == "GET"
    assert r.full_path == "/items"
    assert r.name == "items:list"
    assert r.status_code == 200

    handles = [e for e in edges if e.type == EdgeType.HANDLES]
    assert len(handles) == 1
    assert handles[0].from_id == "route:GET /items"
    assert handles[0].to_id == func_node.id


# ---------------------------------------------------------------------------
# Test 3: Unmatched handler → Unresolved, not crash
# ---------------------------------------------------------------------------

def test_openapi_to_facts_unmatched_handler_emits_unresolved() -> None:
    openapi_dict = {
        "paths": {
            "/items": {
                "get": {"responses": {"200": {}}}
            }
        }
    }
    handler_map = {
        "GET /items": {
            "handler": "ghost_func",
            "module": "app.routes",
            "qualname": "ghost_func",
            "name": "",
        }
    }
    route_nodes, edges, unresolved = _openapi_to_facts(
        openapi_dict, handler_map, [], Path("."),
        dotted_to_path={"app.routes": "app/routes.py"},
    )

    assert len(route_nodes) == 1
    handles = [e for e in edges if e.type == EdgeType.HANDLES]
    assert handles == []  # no edge — handler not found
    assert any("ghost_func" in u.what for u in unresolved)


# ---------------------------------------------------------------------------
# Test 4: IntrospectionError on bad app path
# ---------------------------------------------------------------------------

def test_introspection_error_on_bad_app_path(tmp_path: Path) -> None:
    """_run_app_introspection with a nonexistent module → IntrospectionError."""
    from docgen.extract.adapters.fastapi import _run_app_introspection

    with pytest.raises(IntrospectionError):
        _run_app_introspection(
            app_import_path="nonexistent_module.foo:app",
            repo_root=tmp_path,
            source_root=".",
            timeout=15,
        )


# ---------------------------------------------------------------------------
# Test 5: extract() on failure → AdapterResult with 1 unresolved, 0 nodes
# ---------------------------------------------------------------------------

def test_extract_fallback_on_failure(tmp_path: Path) -> None:
    """extract() on introspection failure returns empty result + 1 unresolved."""
    class FakeConfig:
        app = "no_such_module:app"
        source_root = "."
        adapter_name = "fastapi"

    result = extract([], [], FakeConfig(), tmp_path, dotted_to_path={})

    assert isinstance(result, AdapterResult)
    assert result.nodes == []
    assert result.edges == []
    assert len(result.unresolved) == 1
    assert result.unresolved[0].what == "adapter_import_failed"


# ---------------------------------------------------------------------------
# Test 6: Consistency check — 19 routes from real target/ repo
# ---------------------------------------------------------------------------

def test_real_repo_route_consistency() -> None:
    """Run the adapter on the real target/ repo and verify all 19 ground-truth routes appear."""
    repo_root = Path(__file__).parent.parent
    ground_truth_path = repo_root / "eval" / "ground_truth.json"
    if not ground_truth_path.exists():
        pytest.skip("eval/ground_truth.json not found")
    target_venv = repo_root / "target" / ".venv"
    if not target_venv.exists():
        pytest.skip("target/.venv not found — cannot run introspection")

    ground_truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    gt_pairs = {(r["method"], r["path"]) for r in ground_truth["routes"]}

    from docgen.config import load_config
    from docgen.extract.core import extract_file
    from docgen.extract.modules import build_module_index, resolve_imports
    from docgen.walker import walk_repo

    config = load_config(repo_root / "docgen.toml")
    module_paths = list(walk_repo(config, repo_root=repo_root))

    all_nodes: list = []
    all_edges: list = []
    for rel in module_paths:
        p = repo_root / rel
        if p.exists():
            nodes, edges, _ = extract_file(p, repo_root)
            all_nodes.extend(nodes)
            all_edges.extend(edges)

    dotted_to_path, path_to_info = build_module_index(
        module_paths, repo_root, source_root=config.source_root
    )
    _, _, ext_nodes = resolve_imports(dotted_to_path, path_to_info, repo_root, config.source_root)
    all_nodes.extend(ext_nodes)

    class FakeConfig:
        app = config.app
        source_root = config.source_root
        adapter_name = "fastapi"

    # Reverse the node order so resolution cannot pass by walk-order luck: the
    # repository methods that share a name with a route handler come first.
    result = extract(
        list(reversed(all_nodes)), all_edges, FakeConfig(), repo_root,
        dotted_to_path=dotted_to_path,
    )

    # Must not have produced the fallback unresolved entry
    import_failed = [u for u in result.unresolved if u.what == "adapter_import_failed"]
    assert import_failed == [], (
        f"Adapter import failed: {import_failed[0].why if import_failed else ''}"
    )

    extracted_pairs = {
        (n.method, n.full_path) for n in result.nodes if n.type == NodeType.ROUTE
    }

    missing = gt_pairs - extracted_pairs
    assert not missing, (
        f"Missing routes from ground truth: {missing}\n"
        f"Extracted: {sorted(extracted_pairs)}"
    )

    handles = [e for e in result.edges if e.type is EdgeType.HANDLES]

    # Test 8 — every HANDLES target is a module-level function.  A target with
    # parent_class set means the route was bound to a class method (e.g. a
    # repository method that happens to share the handler's name).
    node_map = {n.id: n for n in all_nodes}
    node_map.update({n.id: n for n in result.nodes})
    bad_targets: list[str] = []
    for edge in handles:
        target = node_map.get(edge.to_id)
        if target is None:
            bad_targets.append(f"{edge.from_id} -> {edge.to_id} (target node missing)")
        elif target.parent_class:
            bad_targets.append(f"{edge.from_id} -> {edge.to_id} (class method)")
    assert bad_targets == [], f"HANDLES targets are not module-level functions: {bad_targets}"

    # The embedded-Body route must have its request model resolved via the
    # unwrapped Body_ wrapper (or the handler AST).
    comment_req = {
        e.to_id for e in result.edges
        if e.type is EdgeType.REQUEST_MODEL
        and e.from_id == "route:POST /api/articles/{slug}/comments"
    }
    assert "target/app/models/schemas/comments.py::CommentInCreate" in comment_req, (
        f"Expected CommentInCreate request model, got {sorted(comment_req)}"
    )

    # Test 9 — the AST extractor (route decorators from source) and the
    # introspection adapter (__module__ + __qualname__ from the running app)
    # must agree on the full handler ID, not just the name.
    from docgen.extract.adapters.fastapi_ast import extract_ast_routes

    decls, _ = extract_ast_routes(module_paths, repo_root)
    route_nodes_by_id = {n.id: n for n in result.nodes}
    assert _cross_check_handles(handles, route_nodes_by_id, decls) == [], (
        "AST route declarations and introspected handlers disagree on handler IDs"
    )

    # Test 10 — the cross-check actually detects a wrong binding.
    comment_edge = next(
        e for e in handles if e.from_id == "route:POST /api/articles/{slug}/comments"
    )
    wrong_target = (
        "target/app/db/repositories/comments.py::CommentsRepository::create_comment_for_article"
    )
    assert comment_edge.to_id != wrong_target
    tampered = [Edge(
        type=comment_edge.type,
        from_id=comment_edge.from_id,
        to_id=wrong_target,
    )]
    assert _cross_check_handles(tampered, route_nodes_by_id, decls) != []


def _cross_check_handles(handles, route_nodes_by_id, decls) -> list[str]:
    """Return violations where a HANDLES edge disagrees with the AST RouteDecl.

    ``decls`` comes from the AST extractor, which never sees the introspection
    adapter's output — so agreement on the full ID (file + name) is an
    independent check.  Comparing against ``route.file`` instead would be
    circular: the route node's file is copied from the resolved handler node.
    """
    decls_by_key: dict[tuple[str, str], list] = {}
    for d in decls:
        decls_by_key.setdefault((d.method, d.handler_name), []).append(d)

    violations: list[str] = []
    for edge in handles:
        route = route_nodes_by_id.get(edge.from_id)
        if route is None:
            violations.append(f"{edge.from_id}: route node not found")
            continue
        func_name = edge.to_id.rsplit("::", 1)[-1]
        candidates = decls_by_key.get((route.method, func_name), [])
        if not candidates:
            violations.append(
                f"{edge.from_id} -> {edge.to_id}: no AST route declaration for "
                f"{route.method} {func_name}"
            )
            continue
        expected = {
            _qualname_to_node_id(d.file, d.handler_name) for d in candidates
        }
        if edge.to_id not in expected:
            violations.append(
                f"{edge.from_id} -> {edge.to_id}: AST declares {sorted(expected)}"
            )
    return violations


# ---------------------------------------------------------------------------
# Tests for E4: route nodes have non-empty hash_struct
# ---------------------------------------------------------------------------

def test_route_node_hash_struct_non_empty(tmp_path: Path) -> None:
    """Route nodes must have a non-empty hash_struct (E4)."""
    openapi_dict = {
        "paths": {
            "/items": {"get": {"responses": {"200": {"description": "OK"}}}}
        }
    }
    handler_map = {
        "GET /items": {
            "handler": "list_items",
            "module": "app.routes",
            "qualname": "list_items",
            "name": "",
        }
    }
    func_node = _make_func_node("list_items")

    route_nodes, _, _ = _openapi_to_facts(
        openapi_dict, handler_map, [func_node], tmp_path,
        dotted_to_path={"app.routes": "app/routes.py"},
    )

    assert route_nodes[0].hash_struct != "", "Route node must have non-empty hash_struct"
    assert route_nodes[0].hash_source != "", "Route node must have non-empty hash_source"


def test_route_hash_struct_changes_with_path(tmp_path: Path) -> None:
    """Changing the route path must change hash_struct (E4)."""
    def _make_openapi(path: str) -> dict:
        return {"paths": {path: {"get": {"responses": {"200": {}}}}}}

    handler_map = {
        "GET /a": {"handler": "fn", "module": "app.routes", "qualname": "fn", "name": ""},
        "GET /b": {"handler": "fn", "module": "app.routes", "qualname": "fn", "name": ""},
    }
    fn = _make_func_node("fn")
    dotted_to_path = {"app.routes": "app/routes.py"}

    nodes_a, _, _ = _openapi_to_facts(
        _make_openapi("/a"), {"GET /a": handler_map["GET /a"]}, [fn], tmp_path,
        dotted_to_path=dotted_to_path,
    )
    nodes_b, _, _ = _openapi_to_facts(
        _make_openapi("/b"), {"GET /b": handler_map["GET /b"]}, [fn], tmp_path,
        dotted_to_path=dotted_to_path,
    )

    assert nodes_a[0].hash_struct != nodes_b[0].hash_struct, (
        "Different paths must produce different hash_struct"
    )


# ---------------------------------------------------------------------------
# Tests for E5: request model edges use handler AST annotation
# ---------------------------------------------------------------------------

def _make_pydantic_node(name: str, file: str = "app/models.py") -> Node:
    return Node(
        id=f"{file}::{name}",
        type=NodeType.CLASS,
        file=file,
        lines=(1, 5),
        hash_struct="x",
        hash_source="x",
        name=name,
        is_pydantic_model=True,
    )


def test_request_model_explicit_body(tmp_path: Path) -> None:
    """Handler with explicit Body(...) parameter → REQUEST_MODEL to annotation class."""
    handler_file = tmp_path / "routes.py"
    handler_file.write_text(
        "from fastapi import Body\n"
        "from app.models import ArticleIn\n"
        "async def create(article: ArticleIn = Body(...)):\n"
        "    pass\n",
        encoding="utf-8",
    )
    func_node = Node(
        id="routes.py::create", type=NodeType.FUNCTION,
        file="routes.py", lines=(3, 4), hash_struct="x", hash_source="x", name="create",
    )
    model_node = _make_pydantic_node("ArticleIn", "app/models.py")
    openapi_dict = {
        "paths": {
            "/articles": {
                "post": {
                    "responses": {"201": {}},
                    "requestBody": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/Body_create_articles_post"}}}},
                }
            }
        }
    }
    handler_map = {
        "POST /articles": {"handler": "create", "module": "routes", "qualname": "create", "name": ""}
    }

    _, edges, _ = _openapi_to_facts(
        openapi_dict, handler_map, [func_node, model_node], tmp_path,
        dotted_to_path={"routes": "routes.py"},
    )

    req_edges = [e for e in edges if e.type == EdgeType.REQUEST_MODEL]
    assert len(req_edges) == 1
    assert req_edges[0].to_id == "app/models.py::ArticleIn", (
        f"Expected ArticleIn, got {req_edges[0].to_id}"
    )


def test_request_model_implicit_pydantic(tmp_path: Path) -> None:
    """Handler with bare Pydantic annotation (no Body default) → REQUEST_MODEL."""
    handler_file = tmp_path / "routes.py"
    handler_file.write_text(
        "async def update(item: MyModel):\n"
        "    pass\n",
        encoding="utf-8",
    )
    func_node = Node(
        id="routes.py::update", type=NodeType.FUNCTION,
        file="routes.py", lines=(1, 2), hash_struct="x", hash_source="x", name="update",
    )
    model_node = _make_pydantic_node("MyModel", "app/models.py")
    openapi_dict = {
        "paths": {"/items": {"put": {"responses": {"200": {}}}}}
    }
    handler_map = {
        "PUT /items": {"handler": "update", "module": "routes", "qualname": "update", "name": ""}
    }

    _, edges, _ = _openapi_to_facts(
        openapi_dict, handler_map, [func_node, model_node], tmp_path,
        dotted_to_path={"routes": "routes.py"},
    )

    req_edges = [e for e in edges if e.type == EdgeType.REQUEST_MODEL]
    assert len(req_edges) == 1
    assert req_edges[0].to_id == "app/models.py::MyModel"


def test_depends_param_not_treated_as_body(tmp_path: Path) -> None:
    """A parameter with Depends(...) default is NOT a request body."""
    handler_file = tmp_path / "routes.py"
    handler_file.write_text(
        "from fastapi import Depends\n"
        "async def get(user: UserModel = Depends(get_user)):\n"
        "    pass\n",
        encoding="utf-8",
    )
    func_node = Node(
        id="routes.py::get", type=NodeType.FUNCTION,
        file="routes.py", lines=(2, 3), hash_struct="x", hash_source="x", name="get",
    )
    model_node = _make_pydantic_node("UserModel", "app/models.py")
    openapi_dict = {"paths": {"/": {"get": {"responses": {"200": {}}}}}}
    handler_map = {
        "GET /": {"handler": "get", "module": "routes", "qualname": "get", "name": ""}
    }

    _, edges, _ = _openapi_to_facts(
        openapi_dict, handler_map, [func_node, model_node], tmp_path,
        dotted_to_path={"routes": "routes.py"},
    )

    req_edges = [e for e in edges if e.type == EdgeType.REQUEST_MODEL]
    assert req_edges == [], "Depends parameter must not produce REQUEST_MODEL edge"


def test_body_auto_name_filtered(tmp_path: Path) -> None:
    """A Body_... wrapper with no components entry cannot be unwrapped → no edge."""
    # No handler source file at tmp_path — AST extraction returns empty
    func_node = _make_func_node("create", "routes.py")  # file doesn't exist in tmp_path
    openapi_dict = {
        "paths": {
            "/x": {
                "post": {
                    "responses": {"200": {}},
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Body_create_x_post"}
                            }
                        }
                    },
                }
            }
        }
    }
    handler_map = {
        "POST /x": {"handler": "create", "module": "routes", "qualname": "create", "name": ""}
    }

    _, edges, _ = _openapi_to_facts(
        openapi_dict, handler_map, [func_node], tmp_path,
        dotted_to_path={"routes": "routes.py"},
    )

    req_edges = [e for e in edges if e.type == EdgeType.REQUEST_MODEL]
    assert req_edges == [], "Body_... auto-generated name must not become an edge"
