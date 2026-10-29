"""Unit tests for exact handler resolution in the FastAPI adapter.

Covers docs/plan-handler-resolution-fix.md sub-task 4, tests 1-7.  Every test
builds the fact graph directly and calls ``_openapi_to_facts`` with fixture
handler maps — no subprocess, no real target repo.
"""

from __future__ import annotations

from pathlib import Path

from docgen.extract.adapters.fastapi import (
    _find_class_node,
    _openapi_to_facts,
    _qualname_to_node_id,
    _resolve_handler,
    _run_app_introspection,
)
from docgen.facts.schema import EdgeType, Node, NodeType


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _func(
    name: str,
    file: str,
    parent_class: str = "",
) -> Node:
    """Build a FUNCTION node.  ``parent_class`` marks a class method."""
    node_id = (
        f"{file}::{parent_class.rsplit('::', 1)[-1]}::{name}"
        if parent_class
        else f"{file}::{name}"
    )
    return Node(
        id=node_id,
        type=NodeType.FUNCTION,
        file=file,
        lines=(1, 10),
        hash_struct="x",
        hash_source="x",
        name=name,
        parent_class=parent_class,
    )


def _class(name: str, file: str, is_pydantic: bool = True) -> Node:
    return Node(
        id=f"{file}::{name}",
        type=NodeType.CLASS,
        file=file,
        lines=(1, 5),
        hash_struct="x",
        hash_source="x",
        name=name,
        is_pydantic_model=is_pydantic,
    )


def _simple_openapi(
    path: str = "/items",
    method: str = "get",
    response_schema: str | None = None,
) -> dict:
    operation: dict = {"responses": {"200": {"description": "OK"}}}
    if response_schema is not None:
        operation["responses"]["200"]["content"] = {
            "application/json": {
                "schema": {"$ref": f"#/components/schemas/{response_schema}"}
            }
        }
    return {"paths": {path: {method: operation}}}


def _handles(edges):
    return [e for e in edges if e.type is EdgeType.HANDLES]


def _edges_of(edges, edge_type):
    return [e for e in edges if e.type is edge_type]


# ---------------------------------------------------------------------------
# Test 1 — same name, handler vs repository method, order-independent
# ---------------------------------------------------------------------------

def test_same_name_handler_vs_method_is_order_independent() -> None:
    route_fn = _func("create", "routes.py")
    repo_method = _func("create", "repo.py", parent_class="repo.py::Repo")

    handler_map = {
        "GET /items": {
            "handler": "create",
            "module": "routes",
            "qualname": "create",
            "name": "items:create",
        }
    }
    dotted_to_path = {"routes": "routes.py"}

    for nodes in ([route_fn, repo_method], [repo_method, route_fn]):
        _, edges, unresolved = _openapi_to_facts(
            _simple_openapi(), handler_map, nodes, Path("."),
            dotted_to_path=dotted_to_path,
        )
        handles = _handles(edges)
        assert len(handles) == 1
        assert handles[0].to_id == "routes.py::create"
        assert unresolved == []


# ---------------------------------------------------------------------------
# Test 2 — same handler name in two route files
# ---------------------------------------------------------------------------

def test_same_name_in_two_route_files_resolves_per_module() -> None:
    fn_a = _func("list_items", "routes_a.py")
    fn_b = _func("list_items", "routes_b.py")

    openapi_dict = {
        "paths": {
            "/a": {"get": {"responses": {"200": {}}}},
            "/b": {"get": {"responses": {"200": {}}}},
        }
    }
    handler_map = {
        "GET /a": {"handler": "list_items", "module": "routes_a", "qualname": "list_items", "name": ""},
        "GET /b": {"handler": "list_items", "module": "routes_b", "qualname": "list_items", "name": ""},
    }
    dotted_to_path = {"routes_a": "routes_a.py", "routes_b": "routes_b.py"}

    _, edges, unresolved = _openapi_to_facts(
        openapi_dict, handler_map, [fn_a, fn_b], Path("."),
        dotted_to_path=dotted_to_path,
    )

    targets = {e.from_id: e.to_id for e in _handles(edges)}
    assert targets["route:GET /a"] == "routes_a.py::list_items"
    assert targets["route:GET /b"] == "routes_b.py::list_items"
    assert unresolved == []


# ---------------------------------------------------------------------------
# Test 3 — handler defined in defining module, registered via re-export
# ---------------------------------------------------------------------------

def test_handler_resolves_to_defining_module_not_route_file() -> None:
    # The route lives in routes.py but the function object was defined in utils.py
    # (re-exported), so __module__ points at utils.
    helper = _func("helper", "utils.py")

    handler_map = {
        "GET /items": {
            "handler": "helper",
            "module": "utils",
            "qualname": "helper",
            "name": "items:list",
        }
    }
    dotted_to_path = {"utils": "utils.py", "routes": "routes.py"}

    route_nodes, edges, unresolved = _openapi_to_facts(
        _simple_openapi(), handler_map, [helper], Path("."),
        dotted_to_path=dotted_to_path,
    )

    handles = _handles(edges)
    assert len(handles) == 1
    assert handles[0].to_id == "utils.py::helper"
    assert route_nodes[0].file == "utils.py"
    assert unresolved == []


# ---------------------------------------------------------------------------
# Test 4 — class-based handler (CBV)
# ---------------------------------------------------------------------------

def test_class_based_handler_resolves_to_method_node() -> None:
    method = _func("get", "views.py", parent_class="views.py::ArticleView")

    handler_map = {
        "GET /articles": {
            "handler": "get",
            "module": "app.views",
            "qualname": "ArticleView.get",
            "name": "articles:get",
        }
    }
    dotted_to_path = {"app.views": "views.py"}

    _, edges, unresolved = _openapi_to_facts(
        _simple_openapi("/articles"), handler_map, [method], Path("."),
        dotted_to_path=dotted_to_path,
    )

    handles = _handles(edges)
    assert len(handles) == 1
    assert handles[0].to_id == "views.py::ArticleView::get"
    assert unresolved == []


# ---------------------------------------------------------------------------
# Test 5 — nested function → Unresolved, no crash
# ---------------------------------------------------------------------------

def test_nested_function_emits_unresolved_without_crashing() -> None:
    handler_map = {
        "GET /items": {
            "handler": "inner",
            "module": "routes",
            "qualname": "outer.<locals>.inner",
            "name": "",
        }
    }
    dotted_to_path = {"routes": "routes.py"}

    _, edges, unresolved = _openapi_to_facts(
        _simple_openapi(), handler_map, [], Path("."),
        dotted_to_path=dotted_to_path,
    )

    assert _handles(edges) == []
    assert len(unresolved) == 1
    assert "locals" in unresolved[0].why


# ---------------------------------------------------------------------------
# Test 6 — two classes with the same name → Unresolved, no wrong edge
# ---------------------------------------------------------------------------

def test_ambiguous_class_name_emits_unresolved_and_no_model_edge() -> None:
    nodes = [
        _class("Item", "models_a.py"),
        _class("Item", "models_b.py"),
    ]

    assert _find_class_node("Item", nodes) is None

    handler_map = {
        "GET /items": {"handler": "list_items", "module": "routes", "qualname": "list_items", "name": ""}
    }
    dotted_to_path = {"routes": "routes.py"}

    _, edges, unresolved = _openapi_to_facts(
        _simple_openapi("/items", "get", response_schema="Item"),
        handler_map, nodes, Path("."),
        dotted_to_path=dotted_to_path,
    )

    assert _edges_of(edges, EdgeType.RESPONSE_MODEL) == []
    ambiguous = [u for u in unresolved if u.what == "ambiguous_class_name:Item"]
    assert len(ambiguous) == 1
    assert "models_a.py::Item" in ambiguous[0].why
    assert "models_b.py::Item" in ambiguous[0].why


# ---------------------------------------------------------------------------
# Test 7 — introspection output contract
# ---------------------------------------------------------------------------

def test_introspection_output_includes_module_and_qualname(tmp_path: Path) -> None:
    """The real introspection script must emit module + qualname per handler.

    A minimal fake ``fastapi`` / ``starlette`` is placed next to a demo app so
    the subprocess can run the exact production script without the real
    frameworks installed.  This fails if the script stops emitting either field.
    """
    (tmp_path / "starlette").mkdir()
    (tmp_path / "starlette" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "starlette" / "routing.py").write_text(
        "class Route:\n    pass\n", encoding="utf-8"
    )
    (tmp_path / "fastapi").mkdir()
    (tmp_path / "fastapi" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "fastapi" / "routing.py").write_text(
        "class APIRoute:\n"
        "    def __init__(self, path, endpoint, name='', methods=('GET',)):\n"
        "        self.path = path\n"
        "        self.endpoint = endpoint\n"
        "        self.name = name\n"
        "        self.methods = set(methods)\n",
        encoding="utf-8",
    )

    (tmp_path / "demo_app.py").write_text(
        "from fastapi.routing import APIRoute\n"
        "\n"
        "def list_items():\n"
        "    pass\n"
        "\n"
        "class ArticleView:\n"
        "    @staticmethod\n"
        "    def get():\n"
        "        pass\n"
        "\n"
        "class _App:\n"
        "    def __init__(self):\n"
        "        self.routes = [\n"
        "            APIRoute('/items', endpoint=list_items, name='items:list'),\n"
        "            APIRoute('/articles', endpoint=ArticleView.get, name='articles:get'),\n"
        "        ]\n"
        "    def openapi(self):\n"
        "        return {'openapi': '3.0.0', 'info': {}, 'paths': {}}\n"
        "\n"
        "app = _App()\n",
        encoding="utf-8",
    )

    data = _run_app_introspection(
        app_import_path="demo_app:app",
        repo_root=tmp_path,
        source_root=".",
        timeout=30,
    )

    handlers = data["handlers"]
    assert handlers, "introspection returned no handlers"
    for info in handlers.values():
        assert "module" in info, f"handler entry missing 'module': {info}"
        assert "qualname" in info, f"handler entry missing 'qualname': {info}"

    assert handlers["GET /items"]["module"] == "demo_app"
    assert handlers["GET /items"]["qualname"] == "list_items"
    assert handlers["GET /articles"]["qualname"] == "ArticleView.get"


# ---------------------------------------------------------------------------
# Direct unit checks for the resolver helpers
# ---------------------------------------------------------------------------

def test_qualname_to_node_id_formats() -> None:
    assert _qualname_to_node_id("app/routes.py", "func") == "app/routes.py::func"
    assert (
        _qualname_to_node_id("app/views.py", "ArticleView.get")
        == "app/views.py::ArticleView::get"
    )


def test_resolve_handler_failure_reasons() -> None:
    node = _func("get", "views.py", parent_class="views.py::ArticleView")
    node_map = {node.id: node}
    dotted_to_path = {"app.views": "views.py"}

    resolved, reason = _resolve_handler(
        {"module": "app.views", "qualname": "ArticleView.get"},
        dotted_to_path, node_map,
    )
    assert resolved is node
    assert reason is None

    missing_attrs, reason_missing = _resolve_handler({}, dotted_to_path, node_map)
    assert missing_attrs is None
    assert "__module__" in reason_missing

    missing_module, reason_module = _resolve_handler(
        {"module": "nope", "qualname": "ArticleView.get"}, dotted_to_path, node_map
    )
    assert missing_module is None
    assert "not found in module index" in reason_module

    missing_node, reason_node = _resolve_handler(
        {"module": "app.views", "qualname": "ArticleView.missing"},
        dotted_to_path, node_map,
    )
    assert missing_node is None
    assert "not found in extracted graph" in reason_node
