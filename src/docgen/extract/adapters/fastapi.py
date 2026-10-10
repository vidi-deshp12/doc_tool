"""FastAPI adapter: extract routes via app introspection (subprocess + app.openapi()).

The subprocess imports the target FastAPI app using the configured Python venv,
calls app.openapi() to get the full OpenAPI schema, and also reads
route.endpoint.__name__ for each route so handler names are exact.

If import fails (bad env vars, missing deps, timeout), the adapter returns an
empty AdapterResult with one Unresolved entry describing the failure.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

from ...facts.schema import Edge, EdgeType, Node, NodeType, Unresolved
from .base import AdapterResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Dummy env vars injected into the subprocess so the app can be imported
# without a real database or secret.  These are never real credentials.
_DUMMY_ENV: dict[str, str] = {
    "SECRET_KEY": "dummy-secret-for-docgen",
    # pydantic v1 PostgresDsn requires userinfo (user:pass) in the URL
    "DATABASE_URL": "postgresql://docgen:docgen@localhost/dummy",
    "MAX_CONNECTIONS_COUNT": "1",
    "MIN_CONNECTIONS_COUNT": "1",
}

_TIMEOUT_SECONDS = 30


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class IntrospectionError(RuntimeError):
    """Raised when the subprocess fails to import or introspect the app."""


# ---------------------------------------------------------------------------
# Sub-task B — Subprocess runner
# ---------------------------------------------------------------------------

# The script run inside the target venv.  It outputs a JSON object with two
# keys:
#   "openapi"  — the full OpenAPI dict from app.openapi()
#   "handlers" — dict mapping "METHOD path" → {"handler": endpoint.__name__}
_INTROSPECTION_SCRIPT = textwrap.dedent("""\
    import sys, json, importlib
    sys.path.insert(0, {source_root_path!r})

    module_path, attr = {app_import_path!r}.rsplit(":", 1)
    mod = importlib.import_module(module_path)
    app = getattr(mod, attr)

    openapi = app.openapi()

    from starlette.routing import Route
    try:
        from fastapi.routing import APIRoute
        routes = [r for r in app.routes if isinstance(r, APIRoute)]
    except ImportError:
        routes = [r for r in app.routes if isinstance(r, Route)]

    handlers = {{}}
    for route in routes:
        for method in (route.methods or []):
            key = f"{{method}} {{route.path}}"
            handlers[key] = {{
                "handler": route.endpoint.__name__,
                "name": getattr(route, "name", "") or "",
            }}

    print(json.dumps({{"openapi": openapi, "handlers": handlers}}))
""")


def _find_venv_python(repo_root: Path) -> str:
    """Return the Python executable path from the target venv.

    Falls back to sys.executable if the venv is not found.
    """
    if platform.system() == "Windows":
        candidates = [
            repo_root / "target" / ".venv" / "Scripts" / "python.exe",
        ]
    else:
        candidates = [
            repo_root / "target" / ".venv" / "bin" / "python",
            repo_root / "target" / ".venv" / "bin" / "python3",
        ]
    for p in candidates:
        if p.exists():
            return str(p)
    return sys.executable


def _run_app_introspection(
    app_import_path: str,
    repo_root: Path,
    source_root: str,
    timeout: int = _TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Import the FastAPI app in a subprocess and return the introspection dict.

    Args:
        app_import_path: e.g. "app.main:app"
        repo_root: Absolute path to the project root (contains docgen.toml).
        source_root: Subdirectory containing the Python packages (e.g. "target").
        timeout: Seconds before the subprocess is killed.

    Returns:
        Dict with keys "openapi" and "handlers".

    Raises:
        IntrospectionError: If the subprocess fails for any reason.
    """
    source_root_abs = str((repo_root / source_root).resolve())
    script = _INTROSPECTION_SCRIPT.format(
        source_root_path=source_root_abs,
        app_import_path=app_import_path,
    )

    python = _find_venv_python(repo_root)

    env = {**os.environ, **_DUMMY_ENV}

    try:
        result = subprocess.run(
            [python, "-c", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise IntrospectionError(
            f"App import timed out after {timeout}s: {exc}"
        ) from exc
    except OSError as exc:
        raise IntrospectionError(f"Failed to start subprocess: {exc}") from exc

    if result.returncode != 0:
        stderr_snippet = result.stderr[-500:] if result.stderr else "(no stderr)"
        raise IntrospectionError(
            f"Subprocess exited with code {result.returncode}. "
            f"stderr (last 500 chars): {stderr_snippet}"
        )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise IntrospectionError(
            f"Subprocess output is not valid JSON: {exc}"
        ) from exc

    return data


# ---------------------------------------------------------------------------
# Sub-task C — OpenAPI dict → fact graph
# ---------------------------------------------------------------------------

def _extract_status_code(responses: dict[str, Any]) -> int:
    """Return the first 2xx HTTP status code from an OpenAPI responses dict."""
    for key in responses:
        try:
            code = int(key)
            if 200 <= code < 300:
                return code
        except (ValueError, TypeError):
            continue
    return 200  # default


def _extract_schema_name(ref_or_schema: Any) -> str | None:
    """Extract a schema name from a $ref string or inline schema.

    Returns None if the reference cannot be parsed.
    """
    if isinstance(ref_or_schema, dict):
        ref = ref_or_schema.get("$ref", "")
        if ref.startswith("#/components/schemas/"):
            return ref[len("#/components/schemas/"):]
    return None


def _extract_body_schema_name(request_body: dict[str, Any]) -> str | None:
    """Extract the request body schema name from an OpenAPI requestBody entry."""
    content = request_body.get("content", {})
    for media_type in content.values():
        schema = media_type.get("schema", {})
        # May be direct $ref or allOf/anyOf wrapper
        name = _extract_schema_name(schema)
        if name:
            return name
        # Try allOf[0]
        for key in ("allOf", "anyOf", "oneOf"):
            items = schema.get(key, [])
            for item in items:
                name = _extract_schema_name(item)
                if name:
                    return name
    return None


def _find_function_node(func_name: str, all_nodes: list[Node]) -> Node | None:
    """Find a FUNCTION node by exact name match."""
    for node in all_nodes:
        if node.type == NodeType.FUNCTION and node.name == func_name:
            return node
    return None


def _find_class_node(class_name: str, all_nodes: list[Node]) -> Node | None:
    """Find a CLASS node by exact name match."""
    for node in all_nodes:
        if node.type == NodeType.CLASS and node.name == class_name:
            return node
    return None


def _openapi_to_facts(
    openapi_dict: dict[str, Any],
    handler_map: dict[str, dict[str, str]],
    all_nodes: list[Node],
) -> tuple[list[Node], list[Edge], list[Unresolved]]:
    """Convert an OpenAPI dict + handler map into ROUTE nodes and edges.

    Args:
        openapi_dict: The full OpenAPI spec from app.openapi().
        handler_map: {"METHOD path": {"handler": func_name, "name": route_name}}
        all_nodes: All currently extracted nodes (for handler/model matching).

    Returns:
        (route_nodes, edges, unresolved)
    """
    route_nodes: list[Node] = []
    edges: list[Edge] = []
    unresolved: list[Unresolved] = []

    paths = openapi_dict.get("paths", {})

    for path, path_item in paths.items():
        for method_lower, operation in path_item.items():
            if method_lower in ("parameters", "summary", "description"):
                continue  # not a method entry

            method = method_lower.upper()
            route_id = f"route:{method} {path}"
            handler_key = f"{method} {path}"

            handler_info = handler_map.get(handler_key, {})
            func_name = handler_info.get("handler", "")
            route_name = handler_info.get("name", "")

            # Status code
            responses = operation.get("responses", {})
            status_code = _extract_status_code(responses)

            # Locate handler's file and line range from FUNCTION nodes
            func_node = _find_function_node(func_name, all_nodes) if func_name else None
            handler_file = func_node.file if func_node else ""
            handler_lines = func_node.lines if func_node else (0, 0)

            # Build ROUTE node
            route_node = Node(
                id=route_id,
                type=NodeType.ROUTE,
                file=handler_file,
                lines=handler_lines,
                hash_struct="",
                hash_source="",
                method=method,
                full_path=path,
                name=route_name,
                status_code=status_code,
            )
            route_nodes.append(route_node)

            # HANDLES edge: route → handler function
            if func_node:
                edges.append(Edge(
                    type=EdgeType.HANDLES,
                    from_id=route_id,
                    to_id=func_node.id,
                    meta=(),
                ))
            elif func_name:
                unresolved.append(Unresolved(
                    what=f"handler function '{func_name}'",
                    why="function node not found in extracted fact graph",
                    where=route_id,
                ))

            # RESPONSE_MODEL edges
            for status_key, response in responses.items():
                resp_schema = response.get("content", {})
                for media in resp_schema.values():
                    schema = media.get("schema", {})
                    schema_name = _extract_schema_name(schema)
                    if not schema_name:
                        # Try allOf
                        for item in schema.get("allOf", []):
                            schema_name = _extract_schema_name(item)
                            if schema_name:
                                break
                    if schema_name:
                        cls_node = _find_class_node(schema_name, all_nodes)
                        to_id = cls_node.id if cls_node else f"external:{schema_name}"
                        edges.append(Edge(
                            type=EdgeType.RESPONSE_MODEL,
                            from_id=route_id,
                            to_id=to_id,
                            meta=(),
                        ))

            # REQUEST_MODEL edges
            request_body = operation.get("requestBody", {})
            if request_body:
                req_schema_name = _extract_body_schema_name(request_body)
                if req_schema_name:
                    cls_node = _find_class_node(req_schema_name, all_nodes)
                    to_id = cls_node.id if cls_node else f"external:{req_schema_name}"
                    edges.append(Edge(
                        type=EdgeType.REQUEST_MODEL,
                        from_id=route_id,
                        to_id=to_id,
                        meta=(),
                    ))

    return route_nodes, edges, unresolved


# ---------------------------------------------------------------------------
# Sub-task D — Public extract() entry point
# ---------------------------------------------------------------------------

def extract(
    nodes: list[Node],
    edges: list[Edge],
    config: Any,
    repo_root: Path,
) -> AdapterResult:
    """Extract route facts by importing the FastAPI app in a subprocess.

    Args:
        nodes: All currently extracted nodes.
        edges: All currently extracted edges.
        config: Config object with .app (import path) and .source_root.
        repo_root: Absolute path to the project root.

    Returns:
        AdapterResult with route nodes, edges, and any unresolved entries.
        On import failure: empty nodes/edges + one Unresolved entry.
    """
    try:
        data = _run_app_introspection(
            app_import_path=config.app,
            repo_root=repo_root,
            source_root=config.source_root,
        )
    except IntrospectionError as exc:
        print(
            f"WARNING: FastAPI adapter import failed — route facts omitted. "
            f"Reason: {exc}",
            file=sys.stderr,
        )
        return AdapterResult(
            unresolved=[Unresolved(
                what="adapter_import_failed",
                why=str(exc),
                where=f"adapter:fastapi:{config.app}",
            )]
        )

    openapi_dict = data.get("openapi", {})
    handler_map = data.get("handlers", {})

    route_nodes, new_edges, route_unresolved = _openapi_to_facts(
        openapi_dict, handler_map, nodes
    )

    return AdapterResult(
        nodes=route_nodes,
        edges=new_edges,
        unresolved=route_unresolved,
    )
