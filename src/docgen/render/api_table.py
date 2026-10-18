"""Render the enriched API endpoint table.

Each row covers one ROUTE node: method, full path, HTTP status, handler function
(linked to its module page), FastAPI dependency chain, and request/response models.

"FastAPI Deps" is the column name (not "Dependencies") to avoid confusion with
Python package dependencies.  The column lists DEPENDS_ON targets of the handler
function.

Many "Request model" cells will be blank — this is a known gap in the fact graph
(E5 extraction only covers handlers where the annotation resolves to an in-repo
Pydantic model).  It is not a rendering bug.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from docgen.facts.schema import EdgeType, FactGraph, Node, NodeType


def _module_page_rel_path(node_file: str, from_page: str = "generated/pages/api.md") -> str:
    """Return a relative Markdown link from *from_page* to the module page for *node_file*.

    ``node_file`` is a POSIX repo-root-relative path like
    ``target/app/api/routes/articles/articles_resource.py``.
    The module page lives at
    ``generated/pages/target/app/api/routes/articles/articles_resource.md``.
    """
    if not node_file:
        return ""
    page_path = PurePosixPath("generated/pages") / PurePosixPath(node_file).with_suffix(".md")
    from_dir = PurePosixPath(from_page).parent
    try:
        rel = page_path.relative_to(from_dir)
    except ValueError:
        # fall back to repo-root-relative if the paths don't share a prefix
        rel = page_path
    return str(rel).replace("\\", "/")


def render_api_table(
    graph: FactGraph,
    summaries_map: dict[str, str],
    output_dir: str = "generated",
) -> tuple[str, list[str]]:
    """Render the API endpoint table as a Markdown string.

    Args:
        graph: The full fact graph.
        summaries_map: ``{node_id: summary_text}`` — used to check whether a
            summary exists (table itself does not embed summaries).
        output_dir: Repo-root-relative POSIX prefix for the generated pages
            directory (default ``"generated"``).

    Returns:
        ``(markdown_text, fact_ids_used)`` — the rendered markdown and the list
        of fact IDs (node IDs) that contributed to this page, for the manifest.
    """
    route_nodes: list[Node] = sorted(
        (n for n in graph.nodes if n.type is NodeType.ROUTE),
        key=lambda n: (n.full_path, n.method),
    )

    if not route_nodes:
        return "_No API routes found._\n", []

    # Build lookup indexes
    node_map: dict[str, Node] = {n.id: n for n in graph.nodes}
    fact_ids: list[str] = []

    # HANDLES: route_id → func_id
    handles: dict[str, str] = {}
    # DEPENDS_ON: func_id → [dep_ids]
    depends_on: dict[str, list[str]] = {}
    # REQUEST_MODEL: route_id → [class_ids]
    request_models: dict[str, list[str]] = {}
    # RESPONSE_MODEL: route_id → [class_ids]
    response_models: dict[str, list[str]] = {}

    for edge in graph.edges:
        if edge.type is EdgeType.HANDLES:
            handles[edge.from_id] = edge.to_id
        elif edge.type is EdgeType.DEPENDS_ON:
            depends_on.setdefault(edge.from_id, []).append(edge.to_id)
        elif edge.type is EdgeType.REQUEST_MODEL:
            request_models.setdefault(edge.from_id, []).append(edge.to_id)
        elif edge.type is EdgeType.RESPONSE_MODEL:
            response_models.setdefault(edge.from_id, []).append(edge.to_id)

    header = (
        "# API Endpoints\n\n"
        "<!-- Request model column is blank when the handler body-parameter annotation\n"
        "     could not be resolved to an in-repo Pydantic model (known gap). -->\n\n"
        "| Method | Path | Status | Handler | FastAPI Deps | Request model | Response models |\n"
        "|--------|------|--------|---------|--------------|---------------|-----------------|\n"
    )

    rows: list[str] = []
    for route in route_nodes:
        fact_ids.append(route.id)

        func_id = handles.get(route.id, "")
        func_node = node_map.get(func_id)

        # Handler cell: link to module page if we have a file
        if func_node and func_node.file:
            rel = _module_page_rel_path(func_node.file)
            handler_cell = f"[{func_node.name}]({rel})"
        elif func_id:
            handler_cell = func_id.rsplit("::", 1)[-1]
        else:
            handler_cell = ""

        # FastAPI deps
        deps = depends_on.get(func_id, [])
        dep_names = [_short_name(d) for d in sorted(deps) if not d.startswith("external:")]
        deps_cell = ", ".join(dep_names) if dep_names else ""

        # Request model
        req_ids = request_models.get(route.id, [])
        req_names = [_short_name(r) for r in sorted(req_ids)]
        req_cell = ", ".join(req_names) if req_names else ""

        # Response models
        resp_ids = response_models.get(route.id, [])
        resp_names = [_short_name(r) for r in sorted(resp_ids) if not r.startswith("external:")]
        resp_cell = ", ".join(resp_names) if resp_names else ""

        rows.append(
            f"| {route.method} | `{route.full_path}` | {route.status_code} "
            f"| {handler_cell} | {deps_cell} | {req_cell} | {resp_cell} |"
        )

        # Record all referenced fact IDs for the manifest
        if func_id:
            fact_ids.append(func_id)
        fact_ids.extend(req_ids)
        fact_ids.extend(resp_ids)

    return header + "\n".join(rows) + "\n", fact_ids


def _short_name(node_id: str) -> str:
    """Return the last ``::``-delimited component of a node id."""
    if "::" in node_id:
        return node_id.rsplit("::", 1)[-1]
    return PurePosixPath(node_id).stem or node_id
