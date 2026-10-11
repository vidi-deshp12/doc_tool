"""FastAPI adapter: extract routes via AST only (Tier A — relative paths).

Scans each Python file for:
  1. ``x = APIRouter()`` assignments — identifies which names are router objects.
  2. ``@x.<http_method>(path, ...)`` decorators on async/sync def statements.

Emits one RouteDecl per (method, relative_path, handler_name, file, line) found.

No subprocess, no import, no runtime introspection.
Full-path resolution (Tier B) is deferred to v0.2 — see docs/memory.md D-030.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from ...facts.schema import Unresolved

# HTTP method names recognised as route decorators.
_HTTP_METHODS: frozenset[str] = frozenset(
    {"get", "post", "put", "delete", "patch", "head", "options"}
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class RouteDecl:
    """A single route decorator found in a file."""

    method: str          # upper-case HTTP method, e.g. "GET"
    relative_path: str   # literal path from the decorator, e.g. "" or "/{slug}"
    handler_name: str    # name of the decorated function
    file: str            # POSIX path relative to repo root
    line: int            # line of the decorator (1-based)


# ---------------------------------------------------------------------------
# Per-file scanner
# ---------------------------------------------------------------------------


def _get_string_value(node: ast.expr) -> str | None:
    """Return the string value of an AST Constant node, or None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_api_router_call(node: ast.expr) -> bool:
    """Return True if the expression looks like ``APIRouter(...)``."""
    if isinstance(node, ast.Call):
        func = node.func
        # APIRouter() or fastapi.APIRouter()
        if isinstance(func, ast.Name) and func.id == "APIRouter":
            return True
        if isinstance(func, ast.Attribute) and func.attr == "APIRouter":
            return True
    return False


def _extract_path_from_decorator(decorator: ast.expr) -> str | None:
    """Extract the path string from a ``router.get(path, ...)`` call expression.

    Returns the path string if the first positional arg is a literal, otherwise None.
    The path may also be passed as the keyword argument ``path=``.
    """
    if not isinstance(decorator, ast.Call):
        return None
    func = decorator.func
    if not (isinstance(func, ast.Attribute) and func.attr.lower() in _HTTP_METHODS):
        return None

    # First positional argument
    if decorator.args:
        return _get_string_value(decorator.args[0])

    # Keyword argument named "path"
    for kw in decorator.keywords:
        if kw.arg == "path":
            return _get_string_value(kw.value)

    return None


def scan_router_defs(file_ast: ast.Module, file_posix: str) -> list[RouteDecl]:
    """Scan a parsed module AST and return all route decorators found.

    Identifies router variable names by looking for ``x = APIRouter()``
    assignments at module level, then collects ``@x.<method>(...)`` decorators.

    Args:
        file_ast: The parsed ``ast.Module`` for the file.
        file_posix: The POSIX path of the file relative to the repo root (for RouteDecl).

    Returns:
        A list of RouteDecl for every route decorator found.
    """
    # Step 1: collect router variable names from module-level assignments.
    router_names: set[str] = set()
    for stmt in file_ast.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and _is_api_router_call(stmt.value):
                    router_names.add(target.id)
        elif isinstance(stmt, ast.AnnAssign):
            if isinstance(stmt.target, ast.Name) and stmt.value is not None:
                if _is_api_router_call(stmt.value):
                    router_names.add(stmt.target.id)

    if not router_names:
        return []

    # Step 2: walk all function definitions and inspect their decorators.
    routes: list[RouteDecl] = []

    for node in ast.walk(file_ast):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            if not isinstance(func, ast.Attribute):
                continue
            # The receiver must be one of the known router variable names.
            if not (isinstance(func.value, ast.Name) and func.value.id in router_names):
                continue
            method = func.attr.lower()
            if method not in _HTTP_METHODS:
                continue

            path = _extract_path_from_decorator(decorator)
            if path is None:
                # Non-literal path — skip; caller should emit Unresolved separately.
                continue

            routes.append(RouteDecl(
                method=method.upper(),
                relative_path=path,
                handler_name=node.name,
                file=file_posix,
                line=decorator.lineno,
            ))

    return routes


# ---------------------------------------------------------------------------
# Multi-file entry point
# ---------------------------------------------------------------------------


def extract_ast_routes(
    file_posix_paths: list[str],
    repo_root: Path,
) -> tuple[list[RouteDecl], list[Unresolved]]:
    """Scan all given files and return all route declarations found via AST.

    Args:
        file_posix_paths: Root-relative POSIX paths of Python files to scan.
        repo_root: Absolute path to the project root.

    Returns:
        (routes, unresolved) where unresolved contains entries for files that
        could not be parsed.
    """
    routes: list[RouteDecl] = []
    unresolved: list[Unresolved] = []

    for posix in file_posix_paths:
        abs_path = repo_root / posix
        try:
            source = abs_path.read_text(encoding="utf-8")
        except OSError:
            continue  # file disappeared between walk and scan — skip silently

        try:
            tree = ast.parse(source, filename=str(abs_path))
        except SyntaxError as exc:
            unresolved.append(Unresolved(
                what=posix,
                why=f"SyntaxError: {exc.msg} at line {exc.lineno}",
                where=posix,
            ))
            continue

        found = scan_router_defs(tree, posix)
        routes.extend(found)

    return routes, unresolved


# ---------------------------------------------------------------------------
# Grading helper
# ---------------------------------------------------------------------------


def grade_ast_routes(
    routes: list[RouteDecl],
    expected: list[tuple[str, str]],
) -> tuple[int, int, list[tuple[str, str]]]:
    """Grade extracted routes against an expected (method, handler_name) set.

    Tier A grades on method + handler_name since relative paths cannot be
    matched to full paths without prefix chain resolution (Tier B, v0.2).

    Args:
        routes: Extracted RouteDecl list from extract_ast_routes.
        expected: List of (method, handler_name) pairs that must be found.
            Build this from the route files or from a known fixture.

    Returns:
        (found, total, missing) where ``missing`` lists (method, handler_name)
        pairs that were expected but not extracted.
    """
    extracted: set[tuple[str, str]] = {
        (r.method, r.handler_name) for r in routes
    }
    missing = [pair for pair in expected if pair not in extracted]
    found = len(expected) - len(missing)
    return found, len(expected), missing
