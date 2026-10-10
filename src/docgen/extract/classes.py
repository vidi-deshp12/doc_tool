"""Resolve class bases, flatten inherited fields (in-repo only), tag Pydantic models.

This module takes the raw class Nodes produced by extract/core.py (which store bases
as unparsed source strings like "RWSchema") and produces:

1. Resolved INHERITS edges — pointing to in-repo node IDs or external:<lib> nodes.
2. Updated class Nodes — fields flattened from in-repo ancestors; is_pydantic_model set.

core.py intentionally does NOT emit INHERITS edges; this module owns all of them.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from ..facts.schema import Edge, EdgeType, Node, NodeType, Unresolved
from .modules import ImportRecord, ModuleInfo

# Pydantic base class dotted names that trigger is_pydantic_model=True.
_PYDANTIC_BASES = frozenset({
    "pydantic.BaseModel",
    "pydantic.main.BaseModel",
})


def _strip_subscript(name: str) -> str:
    """Return the bare name from a potentially subscripted base like 'Generic[T]'."""
    bracket = name.find("[")
    if bracket != -1:
        name = name[:bracket]
    return name.strip()


def _resolve_base_name(
    raw_base: str,
    file_path: str,
    path_to_info: dict[str, ModuleInfo],
    dotted_to_path: dict[str, str],
    file_to_classes: dict[str, dict[str, Node]],
) -> str | None:
    """Resolve a raw base class name to a node ID.

    Returns the resolved node ID (e.g. "app/models/rwschema.py::RWSchema" or
    "external:pydantic.BaseModel"), or None if the name should be skipped
    (e.g. it is a generic parameter, not a real base class).
    """
    base = _strip_subscript(raw_base)

    # Skip empty names (e.g. subscript-only strings like "[T]").
    if not base:
        return None

    info = path_to_info.get(file_path)
    if info is None:
        # File not in index — treat as external
        return f"external:{base}"

    # Build a name→resolved_dotted map from the file's imports.
    # e.g. "from app.models.schemas.rwschema import RWSchema" → {"RWSchema": "app.models.schemas.rwschema.RWSchema"}
    name_to_dotted: dict[str, str] = {}
    for imp in info.imports:
        if imp.level == 0 and imp.module:
            # absolute ImportFrom: `from module import name1, name2`
            for n in imp.names:
                name_to_dotted[n] = f"{imp.module}.{n}"
        elif imp.level == 0 and not imp.names:
            # bare `import module` — resolves as module name itself
            if imp.module:
                # top-level name = first component
                top = imp.module.split(".")[0]
                name_to_dotted[top] = imp.module

    # Check imports first
    if base in name_to_dotted:
        dotted = name_to_dotted[base]
        # Is it a known in-repo module?  Try exact match then longest prefix match.
        if dotted in dotted_to_path:
            target_file = dotted_to_path[dotted]
            # dotted ends with the class name; verify class exists in target file
            class_name = dotted.split(".")[-1]
            if class_name in file_to_classes.get(target_file, {}):
                return f"{target_file}::{class_name}"
            # The dotted name itself is a module, not a class — fall through
        # Try longest prefix: the class may be in a module whose dotted name is the prefix
        parts = dotted.split(".")
        for i in range(len(parts) - 1, 0, -1):
            prefix = ".".join(parts[:i])
            class_name = ".".join(parts[i:])
            if "." not in class_name and prefix in dotted_to_path:
                target_file = dotted_to_path[prefix]
                if class_name in file_to_classes.get(target_file, {}):
                    return f"{target_file}::{class_name}"
        # Imported but not in repo — external.  Use the full dotted name.
        return f"external:{dotted}"

    # Not imported — check if defined in the same file (same-file inheritance)
    if base in file_to_classes.get(file_path, {}):
        return f"{file_path}::{base}"

    # Truly unresolvable
    return None


def resolve_classes(
    nodes: list[Node],
    edges: list[Edge],
    path_to_info: dict[str, ModuleInfo],
    dotted_to_path: dict[str, str],
) -> tuple[list[Edge], list[Node], list[Unresolved]]:
    """Resolve class bases and emit INHERITS edges.

    For each class Node whose bases are non-empty, resolve each raw base string
    to either an in-repo node ID or an external:<dotted> ID.

    Args:
        nodes: All nodes extracted so far (from core.py across all files).
        edges: All edges extracted so far (does not include INHERITS — core.py
               was modified to suppress them).
        path_to_info: Per-file module info from modules.build_module_index().
        dotted_to_path: Dotted name → file path from modules.build_module_index().

    Returns:
        (new_inherits_edges, new_external_nodes, unresolved_entries)
    """
    # Build file → {class_name → Node} lookup
    file_to_classes: dict[str, dict[str, Node]] = {}
    for node in nodes:
        if node.type == NodeType.CLASS:
            file_to_classes.setdefault(node.file, {})[node.name] = node

    new_edges: list[Edge] = []
    new_external_nodes: list[Node] = []
    external_seen: set[str] = set()
    unresolved: list[Unresolved] = []

    for node in nodes:
        if node.type != NodeType.CLASS:
            continue
        for raw_base in node.bases:
            resolved_id = _resolve_base_name(
                raw_base,
                node.file,
                path_to_info,
                dotted_to_path,
                file_to_classes,
            )

            if resolved_id is None:
                # Unresolvable (generic param, empty, truly dynamic)
                if _strip_subscript(raw_base):
                    unresolved.append(Unresolved(
                        what=f"base class '{raw_base}'",
                        why="name not found in imports or same-file definitions",
                        where=f"{node.file}:{node.lines[0]}",
                    ))
                continue

            new_edges.append(Edge(
                type=EdgeType.INHERITS,
                from_id=node.id,
                to_id=resolved_id,
                meta=(),
            ))

            # Ensure external Node exists
            if resolved_id.startswith("external:") and resolved_id not in external_seen:
                external_seen.add(resolved_id)
                lib_dotted = resolved_id[len("external:"):]
                lib_name = lib_dotted.split(".")[0]
                new_external_nodes.append(Node(
                    id=resolved_id,
                    type=NodeType.EXTERNAL,
                    file="",
                    lines=(0, 0),
                    hash_struct="",
                    hash_source="",
                    library_name=lib_name,
                ))

    return new_edges, new_external_nodes, unresolved


def _collect_ancestor_fields(
    node_id: str,
    node_map: dict[str, Node],
    resolved_inherits: dict[str, list[str]],
    visited: set[str],
) -> list[tuple[str, str, str]]:
    """Recursively collect annotated fields from in-repo ancestors.

    Returns fields in MRO order: own first, then parent, then grandparent, etc.
    External bases are skipped (they contribute no fields).
    Cycle-safe via the visited set.
    """
    if node_id in visited:
        return []
    visited.add(node_id)

    node = node_map.get(node_id)
    if node is None:
        return []

    own_fields = list(node.fields)
    parent_fields: list[tuple[str, str, str]] = []

    for base_id in resolved_inherits.get(node_id, []):
        if base_id.startswith("external:"):
            continue
        parent_fields.extend(
            _collect_ancestor_fields(base_id, node_map, resolved_inherits, visited)
        )

    # Merge: child fields win on name clash
    seen_names = {f[0] for f in own_fields}
    for pf in parent_fields:
        if pf[0] not in seen_names:
            own_fields.append(pf)
            seen_names.add(pf[0])

    return own_fields


def _is_pydantic(
    node_id: str,
    resolved_inherits: dict[str, list[str]],
    visited: set[str],
) -> bool:
    """Return True if any ancestor (transitively) is pydantic.BaseModel."""
    if node_id in visited:
        return False
    visited.add(node_id)

    for base_id in resolved_inherits.get(node_id, []):
        if base_id.startswith("external:"):
            dotted = base_id[len("external:"):]
            if dotted in _PYDANTIC_BASES or dotted.startswith("pydantic."):
                return True
        else:
            if _is_pydantic(base_id, resolved_inherits, visited):
                return True

    return False


def resolve_all_classes(
    nodes: list[Node],
    edges: list[Edge],
    path_to_info: dict[str, ModuleInfo],
    dotted_to_path: dict[str, str],
) -> tuple[list[Node], list[Edge], list[Node], list[Unresolved]]:
    """Run full class resolution: emit INHERITS edges, flatten fields, tag Pydantic.

    This is the single entry point for class resolution.  Call it after
    extract_file() has been called on all files and after build_full_index()
    has been called to produce path_to_info and dotted_to_path.

    Args:
        nodes: All extracted nodes (across all files).
        edges: All extracted edges (no INHERITS — core.py suppresses them).
        path_to_info: From modules.build_module_index().
        dotted_to_path: From modules.build_module_index().

    Returns:
        (updated_nodes, new_inherits_edges, new_external_nodes, unresolved)

        updated_nodes — same list as input but class Nodes have updated
                        fields and is_pydantic_model; all non-class nodes unchanged.
        new_inherits_edges — INHERITS edges to merge into the fact graph.
        new_external_nodes — external Nodes for bases not already in the graph.
        unresolved — entries for bases that could not be resolved.
    """
    new_edges, new_external_nodes, unresolved = resolve_classes(
        nodes, edges, path_to_info, dotted_to_path
    )

    # Build lookup tables for the update pass
    node_map: dict[str, Node] = {n.id: n for n in nodes}
    resolved_inherits: dict[str, list[str]] = {}
    for edge in new_edges:
        if edge.type == EdgeType.INHERITS:
            resolved_inherits.setdefault(edge.from_id, []).append(edge.to_id)

    # Update class Nodes with flattened fields and Pydantic flag
    updated_nodes: list[Node] = []
    for node in nodes:
        if node.type != NodeType.CLASS:
            updated_nodes.append(node)
            continue

        flat_fields = tuple(
            _collect_ancestor_fields(node.id, node_map, resolved_inherits, set())
        )
        is_pydantic = _is_pydantic(node.id, resolved_inherits, set())

        updated_nodes.append(dataclasses.replace(
            node,
            fields=flat_fields,
            is_pydantic_model=is_pydantic,
        ))

    return updated_nodes, new_edges, new_external_nodes, unresolved
