"""FastAPI adapter: extract routes via app introspection (subprocess + app.openapi()).

The subprocess imports the target FastAPI app using the configured Python venv,
calls app.openapi() to get the full OpenAPI schema, and also reads
route.endpoint.__module__ + __qualname__ for each route so the handler function is
resolved to an exact node ID (file path + qualname) rather than by name alone.

If import fails (bad env vars, missing deps, timeout), the adapter returns an
empty AdapterResult with one Unresolved entry describing the failure.
"""

from __future__ import annotations

import ast
import hashlib
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
        endpoint = route.endpoint
        for method in (route.methods or []):
            key = f"{{method}} {{route.path}}"
            handlers[key] = {{
                "handler": getattr(endpoint, "__name__", None),
                "module": getattr(endpoint, "__module__", None),
                "qualname": getattr(endpoint, "__qualname__", None),
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


def _extract_body_schema_name(
    request_body: dict[str, Any],
    components: dict[str, Any],
) -> str | None:
    """Extract the request body schema name from an OpenAPI requestBody entry.

    FastAPI wraps parameters declared with ``Body(embed=True)`` or
    ``Body(alias=...)`` in a generated ``Body_<operation>`` schema whose
    ``properties`` hold the real model as a ``$ref``.  Unwrap one level so the
    real model name is returned instead of the generated wrapper.
    """
    content = request_body.get("content", {})
    for media_type in content.values():
        schema = media_type.get("schema", {})
        # May be direct $ref or allOf/anyOf wrapper
        name = _extract_schema_name(schema)
        if not name:
            for key in ("allOf", "anyOf", "oneOf"):
                for item in schema.get(key, []):
                    name = _extract_schema_name(item)
                    if name:
                        break
        if not name:
            continue
        if name.startswith("Body_"):
            # Unwrap: look in components/schemas/<name>/properties for nested $ref
            body_schema = components.get(name, {})
            for prop in body_schema.get("properties", {}).values():
                nested = _extract_schema_name(prop)
                if nested:
                    return nested
        else:
            return name
    return None


def _qualname_to_node_id(file_path: str, qualname: str) -> str:
    """Convert file path + __qualname__ to a node ID.

    "func"           → "path/to/file.py::func"
    "Class.method"   → "path/to/file.py::Class::method"
    """
    return file_path + "::" + qualname.replace(".", "::")


def _resolve_handler(
    handler_info: dict,
    dotted_to_path: dict[str, str],
    node_map: dict[str, Node],
) -> tuple[Node | None, str | None]:
    """Resolve a handler info dict to its Node using __module__ + __qualname__.

    Returns (node, failure_reason).  failure_reason is None on success.
    Never guesses — returns (None, reason) on any lookup failure.
    """
    module = handler_info.get("module")
    qualname = handler_info.get("qualname")

    if not module or not qualname:
        return None, "missing __module__ or __qualname__ (unusual endpoint)"

    if "<locals>" in qualname:
        return None, f"nested function '{qualname}' is not a graph node"

    file_path = dotted_to_path.get(module)
    if not file_path:
        return None, f"module '{module}' not found in module index"

    node_id = _qualname_to_node_id(file_path, qualname)
    node = node_map.get(node_id)
    if node is None:
        return None, f"node '{node_id}' not found in extracted graph"

    return node, None


def _find_class_node(class_name: str, all_nodes: list[Node]) -> Node | None:
    """Return the unique CLASS node with this name, or None.

    Returns None for both zero matches (not found) and two-or-more matches
    (ambiguous — caller must emit Unresolved rather than guessing).
    """
    matches = [n for n in all_nodes if n.type is NodeType.CLASS and n.name == class_name]
    return matches[0] if len(matches) == 1 else None


def _resolve_model_id(
    schema_name: str,
    all_nodes: list[Node],
    unresolved: list[Unresolved],
    where: str,
) -> str | None:
    """Resolve an OpenAPI schema name to a node ID.

    Returns the in-repo CLASS node ID, ``external:<name>`` when no in-repo class
    matches, or None when the name is ambiguous — in which case an Unresolved
    entry is appended instead of guessing.
    """
    matches = [n for n in all_nodes if n.type is NodeType.CLASS and n.name == schema_name]
    if len(matches) > 1:
        unresolved.append(Unresolved(
            what=f"ambiguous_class_name:{schema_name}",
            why=f"{len(matches)} CLASS nodes named '{schema_name}': "
                + ", ".join(n.id for n in matches),
            where=where,
        ))
        return None

    cls_node = _find_class_node(schema_name, all_nodes)
    return cls_node.id if cls_node else f"external:{schema_name}"


# ---------------------------------------------------------------------------
# Sub-task C2 — Request model extraction from handler AST (E5)
# ---------------------------------------------------------------------------

# Parameter names that are never request bodies regardless of their annotation.
_NON_BODY_PARAM_NAMES: frozenset[str] = frozenset(
    {"self", "cls", "request", "response", "db", "background_tasks", "current_user"}
)

# FastAPI dependency/query default call names — parameters with these defaults are
# not request bodies even if their annotation is a Pydantic model.
_NON_BODY_DEFAULT_CALLS: frozenset[str] = frozenset(
    {"Depends", "Query", "Path", "Header", "Cookie", "Form", "File", "Security"}
)


def _is_body_default(default_node: ast.expr | None) -> bool | None:
    """Return True if the default is Body(...), False if it is a known non-body
    call (Depends/Query/Path/…), None if no default (let annotation decide)."""
    if default_node is None:
        return None  # no default — check annotation
    if isinstance(default_node, ast.Call):
        func_name = ""
        if isinstance(default_node.func, ast.Name):
            func_name = default_node.func.id
        elif isinstance(default_node.func, ast.Attribute):
            func_name = default_node.func.attr
        if func_name == "Body":
            return True
        if func_name in _NON_BODY_DEFAULT_CALLS:
            return False
    return None  # unknown default — let annotation decide


def _resolve_annotation_to_class_id(
    annotation: ast.expr | None,
    file_path: str,
    all_nodes: list[Node],
) -> str | None:
    """Resolve a parameter annotation to a CLASS node id if it is an in-repo
    Pydantic model.  Returns None if the annotation cannot be resolved or is not
    a Pydantic model.
    """
    if annotation is None:
        return None
    try:
        name = ast.unparse(annotation)
    except Exception:
        return None
    # Only handle simple names (no subscripts like list[Item])
    if "[" in name or "." in name:
        return None
    # Look for a CLASS node with this name
    for node in all_nodes:
        if node.type is NodeType.CLASS and node.name == name and node.is_pydantic_model:
            return node.id
    return None


def _extract_request_models_from_handler(
    func_node: Node,
    repo_root: Path,
    all_nodes: list[Node],
) -> list[str]:
    """Return a list of resolved class node IDs for request-body parameters in
    the handler function.

    Detects two patterns:
    - Explicit: ``item: ItemModel = Body(...)``
    - Implicit: ``item: ItemModel`` with no default, when ItemModel is an
      in-repo Pydantic model and the parameter name is not in _NON_BODY_PARAM_NAMES.

    Returns an empty list when nothing is found (caller falls back to OpenAPI).
    """
    try:
        src_path = repo_root / func_node.file
        source = src_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(src_path))
    except (OSError, SyntaxError):
        return []

    # Find the function AST node by name (top-level only; methods handled by parent_class).
    # NOTE: follow-up — this name-only lookup cannot disambiguate two functions with
    # the same name in the same file; matching on parent_class would be needed there.
    # It is safe today because the caller always passes the exact handler file.
    func_ast: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    for item in ast.walk(tree):
        if (
            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name == func_node.name
        ):
            func_ast = item
            break
    if func_ast is None:
        return []

    body_model_ids: list[str] = []
    args = func_ast.args
    # Pair each arg with its default (defaults are right-aligned in CPython AST)
    n_args = len(args.args)
    n_defaults = len(args.defaults)
    defaults: list[ast.expr | None] = [None] * (n_args - n_defaults) + list(args.defaults)

    for arg, default in zip(args.args, defaults):
        param_name = arg.arg
        if param_name in _NON_BODY_PARAM_NAMES:
            continue

        body_flag = _is_body_default(default)
        if body_flag is False:
            # Explicitly a Depends/Query/etc — skip
            continue

        # body_flag is True (explicit Body) or None (no default / unknown default)
        class_id = _resolve_annotation_to_class_id(arg.annotation, func_node.file, all_nodes)
        if class_id:
            body_model_ids.append(class_id)

    return body_model_ids


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _openapi_to_facts(
    openapi_dict: dict[str, Any],
    handler_map: dict[str, dict[str, str]],
    all_nodes: list[Node],
    repo_root: Path,
    dotted_to_path: dict[str, str],
) -> tuple[list[Node], list[Edge], list[Unresolved]]:
    """Convert an OpenAPI dict + handler map into ROUTE nodes and edges.

    Order of operations per route (plan §sub-task 2):
      1. Resolve the handler function node by exact ID (__module__ → file path,
         __qualname__ → Class::method).  Emit Unresolved on any failure.
      2. Resolve REQUEST_MODEL via handler AST (E5); fall back to OpenAPI names,
         unwrapping auto-generated Body_... wrappers.
      3. Resolve RESPONSE_MODEL from OpenAPI.
      4. Compute hash_struct / hash_source from fully-resolved data (E4).
      5. Construct the ROUTE Node.
      6. Emit HANDLES, REQUEST_MODEL, RESPONSE_MODEL edges.

    Args:
        openapi_dict: The full OpenAPI spec from app.openapi().
        handler_map: {"METHOD path": {"handler": name, "module": dotted,
            "qualname": qualname, "name": route_name}}
        all_nodes: All currently extracted nodes (for handler/model matching).
        repo_root: Absolute path to the project root (for AST re-parsing).
        dotted_to_path: Dotted module name → repo-relative path.

    Returns:
        (route_nodes, edges, unresolved)
    """
    route_nodes: list[Node] = []
    edges: list[Edge] = []
    unresolved: list[Unresolved] = []

    node_map = {n.id: n for n in all_nodes}
    components = openapi_dict.get("components", {}).get("schemas", {})
    paths = openapi_dict.get("paths", {})

    for path, path_item in paths.items():
        for method_lower, operation in path_item.items():
            if method_lower in ("parameters", "summary", "description"):
                continue  # not a method entry

            method = method_lower.upper()
            route_id = f"route:{method} {path}"
            handler_key = f"{method} {path}"

            handler_info = handler_map.get(handler_key, {})
            func_name = handler_info.get("handler") or ""
            route_name = handler_info.get("name") or ""

            # Status code
            responses = operation.get("responses", {})
            status_code = _extract_status_code(responses)

            # Step 1: resolve handler function node by exact ID
            func_node, handler_failure = _resolve_handler(
                handler_info, dotted_to_path, node_map
            )
            if func_node is None:
                unresolved.append(Unresolved(
                    what=f"handler function '{func_name or '(unknown)'}'",
                    why=handler_failure or "handler could not be resolved",
                    where=route_id,
                ))
            handler_file = func_node.file if func_node else ""
            handler_lines = func_node.lines if func_node else (0, 0)

            # Step 2: REQUEST_MODEL — AST-derived first (E5), fall back to OpenAPI
            req_model_ids: list[str] = []
            if func_node:
                req_model_ids = _extract_request_models_from_handler(
                    func_node, repo_root, all_nodes
                )
            if not req_model_ids:
                # Fall back: OpenAPI-derived name (Body_... wrappers are unwrapped
                # inside _extract_body_schema_name)
                request_body = operation.get("requestBody", {})
                if request_body:
                    req_schema_name = _extract_body_schema_name(request_body, components)
                    if req_schema_name:
                        req_to_id = _resolve_model_id(
                            req_schema_name, all_nodes, unresolved, route_id
                        )
                        if req_to_id:
                            req_model_ids = [req_to_id]

            # Step 3: RESPONSE_MODEL — from OpenAPI
            resp_model_ids: list[str] = []
            for _status_key, response in responses.items():
                resp_schema = response.get("content", {})
                for media in resp_schema.values():
                    schema = media.get("schema", {})
                    schema_name = _extract_schema_name(schema)
                    if not schema_name:
                        for item in schema.get("allOf", []):
                            schema_name = _extract_schema_name(item)
                            if schema_name:
                                break
                    if schema_name:
                        resp_to_id = _resolve_model_id(
                            schema_name, all_nodes, unresolved, route_id
                        )
                        if resp_to_id:
                            resp_model_ids.append(resp_to_id)

            # Step 4: compute hash_struct / hash_source from fully-resolved data (E4)
            # hash_struct = structural fields: method, path, status, handler, models
            handler_id = func_node.id if func_node else ""
            struct_payload = (
                method
                + path
                + str(status_code)
                + handler_id
                + "|".join(sorted(req_model_ids))
                + "|".join(sorted(resp_model_ids))
            )
            route_hash = _sha256(struct_payload)
            # hash_source == hash_struct: routes have no separate body to hash
            route_hash_source = route_hash

            # Step 5: construct the ROUTE Node
            route_node = Node(
                id=route_id,
                type=NodeType.ROUTE,
                file=handler_file,
                lines=handler_lines,
                hash_struct=route_hash,
                hash_source=route_hash_source,
                method=method,
                full_path=path,
                name=route_name,
                status_code=status_code,
            )
            route_nodes.append(route_node)

            # Step 6: emit edges
            # HANDLES edge: route → handler function
            if func_node:
                edges.append(Edge(
                    type=EdgeType.HANDLES,
                    from_id=route_id,
                    to_id=func_node.id,
                    meta=(),
                ))

            # REQUEST_MODEL edges
            for rm_id in req_model_ids:
                edges.append(Edge(
                    type=EdgeType.REQUEST_MODEL,
                    from_id=route_id,
                    to_id=rm_id,
                    meta=(),
                ))

            # RESPONSE_MODEL edges
            for rm_id in resp_model_ids:
                edges.append(Edge(
                    type=EdgeType.RESPONSE_MODEL,
                    from_id=route_id,
                    to_id=rm_id,
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
    dotted_to_path: dict[str, str],
) -> AdapterResult:
    """Extract route facts by importing the FastAPI app in a subprocess.

    Args:
        nodes: All currently extracted nodes.
        edges: All currently extracted edges.
        config: Config object with .app (import path) and .source_root.
        repo_root: Absolute path to the project root.
        dotted_to_path: Dotted module name → repo-relative path (from
            build_module_index), used to resolve handler __module__ exactly.

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
        openapi_dict, handler_map, nodes, repo_root, dotted_to_path
    )

    return AdapterResult(
        nodes=route_nodes,
        edges=new_edges,
        unresolved=route_unresolved,
    )
