"""Render a Mermaid dependency diagram showing package structure.

Why only packages (not modules): the target repo has 70 modules + 16 packages.
A full import graph at module level would be unreadable (~86 nodes before edges).
The package→package diagram gives the structural overview the architecture page
needs (app → db, api, core, services, …) and stays well under Mermaid's practical
rendering limit.  Module-level detail belongs on the per-module pages.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from docgen.facts.schema import EdgeType, FactGraph, NodeType


def render_mermaid_diagram(graph: FactGraph) -> str:
    """Return a Mermaid ``flowchart LR`` string showing package→package structure.

    Only PACKAGE nodes and CONTAINS edges between two PACKAGE nodes are included.
    Node labels use the last path component of the package id (e.g. ``db`` for
    ``target/app/db``).  The full id is emitted as a Mermaid node alias so that
    labels stay short without losing identity.

    Returns the full Mermaid fenced code block (including the ` ```mermaid ` fence).
    """
    pkg_ids: set[str] = {
        n.id for n in graph.nodes if n.type is NodeType.PACKAGE
    }

    if not pkg_ids:
        return "```mermaid\nflowchart LR\n    empty[\"No packages found\"]\n```"

    # Collect package→package edges only
    edges: list[tuple[str, str]] = []
    for edge in graph.edges:
        if (
            edge.type is EdgeType.CONTAINS
            and edge.from_id in pkg_ids
            and edge.to_id in pkg_ids
        ):
            edges.append((edge.from_id, edge.to_id))

    # Build a safe Mermaid node id from a package path: replace / with _
    def _mermaid_id(pkg_id: str) -> str:
        return pkg_id.replace("/", "_").replace(".", "_")

    def _label(pkg_id: str) -> str:
        return PurePosixPath(pkg_id).name or pkg_id

    lines: list[str] = ["```mermaid", "flowchart LR"]

    # Declare nodes (sorted for determinism)
    for pkg_id in sorted(pkg_ids):
        mid = _mermaid_id(pkg_id)
        label = _label(pkg_id)
        lines.append(f'    {mid}["{label}"]')

    # Emit edges (sorted for determinism)
    for from_id, to_id in sorted(edges):
        lines.append(f"    {_mermaid_id(from_id)} --> {_mermaid_id(to_id)}")

    lines.append("```")
    return "\n".join(lines)
