"""Re-link DEPENDS_ON edges from external: placeholders to real in-repo node IDs.

``core.py`` emits every ``Depends(...)`` call it finds as:
    Edge(type=DEPENDS_ON, from_id=<function_node_id>, to_id="external:<dep_name>", ...)

where ``dep_name`` is the ``ast.unparse`` of the Depends argument.  This module
resolves those placeholders to real FUNCTION node IDs where possible, using the
module index and import records built by ``modules.py``.

Three dep_name shapes are handled (all observed in the real target repo):
  1. Simple name:          ``get_articles_filters``
  2. Factory call:         ``get_repository(ArticlesRepository)``
  3. Module-qualified:     ``authentication.get_current_user_authorizer()``
                           ``database.get_repository(CommentsRepository)``

Resolution is **conservative (Option B)**: when disambiguation fails, the edge
keeps ``to_id = "external:..."`` and an Unresolved entry is emitted.  Never guess.

The recursive dependency tree emerges naturally: every dependency function's own
DEPENDS_ON edges were already emitted by core.py during per-file extraction.
No further traversal is needed here.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import replace
from typing import Any

from ...facts.schema import Edge, EdgeType, Node, NodeType, Unresolved

# ---------------------------------------------------------------------------
# Parsing dep_name strings
# ---------------------------------------------------------------------------

# Regex splits e.g. "authentication.get_repo(Arg)" into:
#   group 1: "authentication."  (optional alias prefix, including the dot)
#   group 2: "get_repo"         (base function name)
#   group 3: "(Arg)"            (optional call args, including parens)
_DEP_NAME_RE = re.compile(
    r"^(?:([A-Za-z_][A-Za-z0-9_]*)\.)?([A-Za-z_][A-Za-z0-9_]*)(\(.*\))?$",
    re.DOTALL,
)


def _parse_dep_name(dep_name: str) -> tuple[str | None, str, str | None]:
    """Parse a dep_name string into (alias, base_name, args_str).

    Args:
        dep_name: The raw dep name from the DEPENDS_ON edge to_id, with the
            ``external:`` prefix already stripped.

    Returns:
        (alias, base_name, args_str) where alias and args_str may be None.
        alias is the module qualifier (e.g. "authentication").
        args_str is the interior of the call parens (e.g. "ArticlesRepository"),
        or "" for an empty call like "get_current_user_authorizer()", or None
        if there are no parens at all.

    Examples:
        "get_articles_filters"                          → (None, "get_articles_filters", None)
        "get_repository(ArticlesRepository)"            → (None, "get_repository", "ArticlesRepository")
        "get_current_user_authorizer()"                 → (None, "get_current_user_authorizer", "")
        "authentication.get_current_user_authorizer()"  → ("authentication", "get_current_user_authorizer", "")
        "database.get_repository(CommentsRepository)"   → ("database", "get_repository", "CommentsRepository")
    """
    m = _DEP_NAME_RE.match(dep_name.strip())
    if not m:
        return None, dep_name, None
    alias = m.group(1)  # None when no dot-prefix
    base = m.group(2)
    call_group = m.group(3)  # None, "()", or "(Args...)"
    if call_group is None:
        args_str = None
    else:
        # strip surrounding parens
        args_str = call_group[1:-1]
    return alias, base, args_str


# ---------------------------------------------------------------------------
# Name index
# ---------------------------------------------------------------------------


def _build_name_index(nodes: list[Node]) -> dict[str, list[Node]]:
    """Build a mapping from function name to list of FUNCTION nodes with that name.

    Only FUNCTION nodes are indexed.  CLASS, MODULE, etc. are excluded because
    Depends() takes callables, which map to FUNCTION nodes.
    """
    index: dict[str, list[Node]] = defaultdict(list)
    for node in nodes:
        if node.type == NodeType.FUNCTION and node.name:
            index[node.name].append(node)
    return dict(index)


# ---------------------------------------------------------------------------
# Import-record helpers
# ---------------------------------------------------------------------------


def _file_of_node_id(node_id: str) -> str:
    """Extract the file path from a node ID (everything before the first '::')."""
    return node_id.split("::")[0]


def _resolve_alias_to_file(
    alias: str,
    from_file: str,
    path_to_info: dict[str, Any],
    dotted_to_path: dict[str, str],
) -> str | None:
    """Resolve a module alias used in *from_file* to its POSIX file path.

    Looks at the import records of *from_file* for an entry whose alias matches
    *alias*, then maps the resulting dotted name through dotted_to_path.

    Returns the POSIX file path, or None if the alias cannot be resolved.
    """
    info = path_to_info.get(from_file)
    if info is None:
        return None
    for rec in info.imports:
        # Match an alias: `import foo as alias` or `from pkg import foo as alias`
        if rec.alias and rec.alias == alias:
            # rec.module is the dotted name of the imported module
            dotted = rec.module if rec.module else ""
            return dotted_to_path.get(dotted)
        # Match `from pkg import alias` (name imported without renaming)
        if alias in rec.names and not rec.alias:
            # The imported name IS the module (e.g. `from app.api.deps import authentication`)
            parent = rec.module or ""
            dotted = f"{parent}.{alias}" if parent else alias
            return dotted_to_path.get(dotted)
    return None


def _resolve_plain_name_to_file(
    base_name: str,
    from_file: str,
    path_to_info: dict[str, Any],
    dotted_to_path: dict[str, str],
) -> str | None:
    """Resolve a plain function name to the file that defines it via import records.

    Looks at the import records of *from_file* for an entry that imports *base_name*,
    then follows the module dotted name to a file path.

    Returns the POSIX file path, or None if not found.
    """
    info = path_to_info.get(from_file)
    if info is None:
        return None
    for rec in info.imports:
        if base_name in rec.names and not rec.alias:
            dotted = rec.module or ""
            return dotted_to_path.get(dotted)
        if rec.alias and rec.alias == base_name and rec.module:
            return dotted_to_path.get(rec.module)
    return None


# ---------------------------------------------------------------------------
# Single-edge resolution
# ---------------------------------------------------------------------------


def _resolve_single(
    dep_name: str,
    from_id: str,
    name_index: dict[str, list[Node]],
    path_to_info: dict[str, Any],
    dotted_to_path: dict[str, str],
) -> str | None:
    """Try to resolve a single dep_name to a FUNCTION node ID.

    Returns the resolved node ID, or None if resolution fails.
    """
    alias, base, _args = _parse_dep_name(dep_name)
    from_file = _file_of_node_id(from_id)

    candidates = name_index.get(base, [])

    if alias:
        # Module-qualified: resolve alias to file, then filter to that file's nodes.
        target_file = _resolve_alias_to_file(alias, from_file, path_to_info, dotted_to_path)
        if target_file is None:
            return None
        file_candidates = [n for n in candidates if n.file == target_file]
        if len(file_candidates) == 1:
            return file_candidates[0].id
        # 0 or 2+ in that specific file → cannot resolve
        return None

    if len(candidates) == 0:
        return None

    if len(candidates) == 1:
        return candidates[0].id

    # 2+ candidates: try to disambiguate via import records of from_file.
    target_file = _resolve_plain_name_to_file(base, from_file, path_to_info, dotted_to_path)
    if target_file is not None:
        file_candidates = [n for n in candidates if n.file == target_file]
        if len(file_candidates) == 1:
            return file_candidates[0].id

    # Disambiguation failed — conservative: return None (caller will keep external:).
    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def resolve_dep_edges(
    nodes: list[Node],
    edges: list[Edge],
    path_to_info: dict[str, Any],
    dotted_to_path: dict[str, str],
) -> tuple[list[Edge], list[Unresolved]]:
    """Replace external: placeholders in DEPENDS_ON edges with real node IDs.

    Non-DEPENDS_ON edges are passed through unchanged.  DEPENDS_ON edges whose
    to_id starts with "external:" are resolved; those that cannot be resolved
    keep their original to_id (conservative Option B).

    Args:
        nodes: All currently extracted nodes.
        edges: All currently extracted edges.
        path_to_info: Module info dict from build_module_index.
        dotted_to_path: Dotted-name → POSIX path dict from build_module_index.

    Returns:
        (resolved_edges, unresolved) where resolved_edges replaces all edges
        and unresolved contains one entry per dep that could not be resolved.
    """
    name_index = _build_name_index(nodes)
    resolved_edges: list[Edge] = []
    unresolved: list[Unresolved] = []

    for edge in edges:
        if edge.type != EdgeType.DEPENDS_ON or not edge.to_id.startswith("external:"):
            resolved_edges.append(edge)
            continue

        dep_name = edge.to_id[len("external:"):]
        _, base, args_str = _parse_dep_name(dep_name)

        resolved_id = _resolve_single(
            dep_name, edge.from_id, name_index, path_to_info, dotted_to_path
        )

        if resolved_id is None:
            # Cannot resolve — keep original edge, emit Unresolved.
            resolved_edges.append(edge)
            unresolved.append(Unresolved(
                what=f"unresolved_dep:{base}",
                why=f"Depends({dep_name!r}) could not be resolved to an in-repo function",
                where=edge.from_id,
            ))
            continue

        # Build updated meta: preserve existing entries, add factory_args if present.
        meta_dict = dict(edge.meta)
        if args_str is not None and args_str != "":
            meta_dict["factory_args"] = args_str
        new_meta = tuple(sorted(meta_dict.items()))

        resolved_edges.append(replace(edge, to_id=resolved_id, meta=new_meta))

    return resolved_edges, unresolved


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


def detect_dep_cycles(nodes: list[Node], edges: list[Edge]) -> list[str]:
    """Detect cycles in the DEPENDS_ON sub-graph using iterative DFS.

    Args:
        nodes: All nodes (used to build the ID set; not all are in the graph).
        edges: All edges.

    Returns:
        List of human-readable cycle descriptions, e.g.
        ["a::f -> b::g -> a::f"].  Empty list means no cycles.
    """
    # Build adjacency list for DEPENDS_ON edges only.
    adj: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        if edge.type == EdgeType.DEPENDS_ON:
            adj[edge.from_id].append(edge.to_id)

    visited: set[str] = set()
    cycles: list[str] = []

    def _dfs(start: str) -> None:
        # Iterative DFS with an explicit path stack.
        stack: list[tuple[str, list[str]]] = [(start, [start])]
        while stack:
            node_id, path = stack.pop()
            for neighbour in adj.get(node_id, []):
                if neighbour in path:
                    # Found a cycle — record it.
                    cycle_start = path.index(neighbour)
                    cycle_path = path[cycle_start:] + [neighbour]
                    cycles.append(" -> ".join(cycle_path))
                elif neighbour not in visited:
                    stack.append((neighbour, path + [neighbour]))
        visited.add(start)

    all_froms = set(adj.keys())
    for node_id in all_froms:
        if node_id not in visited:
            _dfs(node_id)

    return cycles
