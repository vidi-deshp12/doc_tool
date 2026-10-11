"""Tests for task 2a.8b — FastAPI AST-only route extractor."""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

from docgen.extract.adapters.fastapi_ast import (
    RouteDecl,
    extract_ast_routes,
    grade_ast_routes,
    scan_router_defs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse(src: str) -> ast.Module:
    """Parse a dedented source string into an AST module."""
    return ast.parse(textwrap.dedent(src))


# ---------------------------------------------------------------------------
# Test 1: basic two-route file
# ---------------------------------------------------------------------------

def test_scan_router_defs_basic() -> None:
    """A file with two route decorators returns two RouteDecls."""
    src = """\
        from fastapi import APIRouter
        router = APIRouter()

        @router.get("/items")
        async def list_items():
            pass

        @router.post("/items")
        async def create_item():
            pass
    """
    tree = _parse(src)
    routes = scan_router_defs(tree, "app/items.py")
    assert len(routes) == 2
    assert routes[0].method == "GET"
    assert routes[0].relative_path == "/items"
    assert routes[0].handler_name == "list_items"
    assert routes[0].file == "app/items.py"
    assert routes[1].method == "POST"
    assert routes[1].handler_name == "create_item"


# ---------------------------------------------------------------------------
# Test 2: empty-string path (common in FastAPI sub-routers)
# ---------------------------------------------------------------------------

def test_scan_router_defs_empty_path() -> None:
    """@router.get('') is a valid route with empty relative path."""
    src = """\
        from fastapi import APIRouter
        router = APIRouter()

        @router.get("")
        async def root():
            pass
    """
    routes = scan_router_defs(_parse(src), "app/root.py")
    assert len(routes) == 1
    assert routes[0].relative_path == ""
    assert routes[0].method == "GET"


# ---------------------------------------------------------------------------
# Test 3: multi-line / keyword-argument decorator
# ---------------------------------------------------------------------------

def test_scan_router_defs_multiline_decorator() -> None:
    """Multi-line decorator with keyword args is handled correctly."""
    src = """\
        from fastapi import APIRouter
        router = APIRouter()

        @router.post(
            "/things",
            status_code=201,
            response_model=str,
        )
        async def create_thing():
            pass
    """
    routes = scan_router_defs(_parse(src), "app/things.py")
    assert len(routes) == 1
    assert routes[0].method == "POST"
    assert routes[0].relative_path == "/things"


# ---------------------------------------------------------------------------
# Test 4: non-router decorators are ignored
# ---------------------------------------------------------------------------

def test_scan_router_defs_ignores_non_router_decorators() -> None:
    """Decorators from objects that are not APIRouter() are not collected."""
    src = """\
        import pytest
        from fastapi import APIRouter
        router = APIRouter()

        @pytest.fixture
        def my_fixture():
            pass

        @router.get("/real")
        async def real_route():
            pass
    """
    routes = scan_router_defs(_parse(src), "app/mix.py")
    assert len(routes) == 1
    assert routes[0].handler_name == "real_route"


# ---------------------------------------------------------------------------
# Test 5: file with no APIRouter() — returns empty list
# ---------------------------------------------------------------------------

def test_scan_router_defs_no_router() -> None:
    """A file with no APIRouter() assignment returns an empty list."""
    src = """\
        def plain_function():
            pass
    """
    routes = scan_router_defs(_parse(src), "app/plain.py")
    assert routes == []


# ---------------------------------------------------------------------------
# Test 6: extract_ast_routes on fixture files via tmp_path
# ---------------------------------------------------------------------------

def test_extract_ast_routes_fixture(tmp_path: Path) -> None:
    """extract_ast_routes correctly aggregates routes from two fixture files."""
    (tmp_path / "a.py").write_text(textwrap.dedent("""\
        from fastapi import APIRouter
        router = APIRouter()

        @router.get("/a")
        async def get_a(): pass
    """), encoding="utf-8")

    (tmp_path / "b.py").write_text(textwrap.dedent("""\
        from fastapi import APIRouter
        router = APIRouter()

        @router.delete("/b")
        async def del_b(): pass
    """), encoding="utf-8")

    routes, unresolved = extract_ast_routes(["a.py", "b.py"], tmp_path)
    assert len(routes) == 2
    assert unresolved == []
    methods = {r.method for r in routes}
    assert methods == {"GET", "DELETE"}


# ---------------------------------------------------------------------------
# Test 7: SyntaxError in a file → Unresolved entry, other files still scanned
# ---------------------------------------------------------------------------

def test_extract_ast_routes_syntax_error(tmp_path: Path) -> None:
    """A file with a SyntaxError produces an Unresolved entry and is skipped."""
    (tmp_path / "bad.py").write_text("def broken(\n", encoding="utf-8")
    (tmp_path / "good.py").write_text(textwrap.dedent("""\
        from fastapi import APIRouter
        router = APIRouter()

        @router.get("/ok")
        async def ok(): pass
    """), encoding="utf-8")

    routes, unresolved = extract_ast_routes(["bad.py", "good.py"], tmp_path)
    assert len(routes) == 1
    assert routes[0].handler_name == "ok"
    assert len(unresolved) == 1
    assert "bad.py" in unresolved[0].what


# ---------------------------------------------------------------------------
# Test 8: grade_ast_routes — partial match
# ---------------------------------------------------------------------------

def test_grade_ast_routes_partial() -> None:
    """grade_ast_routes correctly reports partial recall."""
    routes = [
        RouteDecl("GET", "/a", "get_a", "app/a.py", 1),
        RouteDecl("POST", "/a", "create_a", "app/a.py", 5),
    ]
    expected = [
        ("GET", "get_a"),
        ("POST", "create_a"),
        ("DELETE", "delete_a"),  # missing
    ]
    found, total, missing = grade_ast_routes(routes, expected)
    assert found == 2
    assert total == 3
    assert missing == [("DELETE", "delete_a")]


# ---------------------------------------------------------------------------
# Test 9: grade_ast_routes — perfect recall
# ---------------------------------------------------------------------------

def test_grade_ast_routes_perfect() -> None:
    """grade_ast_routes returns empty missing list when all expected routes found."""
    routes = [
        RouteDecl("GET", "/items", "list_items", "app/items.py", 1),
    ]
    expected = [("GET", "list_items")]
    found, total, missing = grade_ast_routes(routes, expected)
    assert found == 1
    assert total == 1
    assert missing == []


# ---------------------------------------------------------------------------
# Test 10: Integration — real target/ repo, 19 routes, 100% recall
# ---------------------------------------------------------------------------

# The known (method, handler_name) pairs from the target repo — derived by
# reading the route decorator source (confirmed via AST scan in planning).
_TARGET_EXPECTED: list[tuple[str, str]] = [
    ("GET",    "list_articles"),
    ("POST",   "create_new_article"),
    ("GET",    "retrieve_article_by_slug"),
    ("PUT",    "update_article_by_slug"),
    ("DELETE", "delete_article_by_slug"),
    ("GET",    "get_articles_for_user_feed"),
    ("POST",   "mark_article_as_favorite"),
    ("DELETE", "remove_article_from_favorites"),
    ("GET",    "list_comments_for_article"),
    ("POST",   "create_comment_for_article"),
    ("DELETE", "delete_comment_from_article"),
    ("GET",    "retrieve_profile_by_username"),
    ("POST",   "follow_for_user"),
    ("DELETE", "unsubscribe_from_user"),
    ("GET",    "get_all_tags"),
    ("GET",    "retrieve_current_user"),
    ("PUT",    "update_current_user"),
    ("POST",   "register"),
    ("POST",   "login"),
]


def test_real_repo_ast_routes_recall() -> None:
    """AST extractor finds all 19 routes in the real target/ repo (100% recall)."""
    repo_root = Path(__file__).parent.parent

    target_dir = repo_root / "target"
    if not target_dir.exists():
        pytest.skip("target/ directory not found")

    from docgen.config import load_config
    from docgen.walker import walk_repo

    config = load_config(repo_root / "docgen.toml")
    file_paths = list(walk_repo(config, repo_root=repo_root))

    routes, unresolved = extract_ast_routes(file_paths, repo_root)

    # Count must be exactly 19.
    assert len(routes) == 19, (
        f"Expected 19 routes, got {len(routes)}.\n"
        f"Found: {sorted((r.method, r.handler_name) for r in routes)}"
    )

    # Every expected (method, handler_name) must be present.
    found, total, missing = grade_ast_routes(routes, _TARGET_EXPECTED)
    assert missing == [], (
        f"Missing routes: {missing}\n"
        f"Found: {sorted((r.method, r.handler_name) for r in routes)}"
    )
    assert found == total == 19
