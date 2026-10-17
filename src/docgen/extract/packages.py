"""Synthesize PACKAGE nodes from the directory structure of the extracted MODULE nodes.

Why: the hierarchy driver (summarize/hierarchy.py) needs PACKAGE nodes to build the
package summarization level, which in turn feeds the system summary.  Many Python
projects don't use __init__.py-based packages (or the walker excludes them), so we
derive packages from folder names instead.

A package is created for every unique parent directory that contains at least one
MODULE node.  Nested directories produce nested packages (child CONTAINS parent links
are emitted in bottom-up order).  The root directory is never turned into a package
node — the synthetic "system" node in hierarchy.py plays that role.
"""

from __future__ import annotations

import hashlib
from pathlib import PurePosixPath

from ..facts.schema import Edge, EdgeType, Node, NodeType


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def synthesize_packages(
    all_nodes: list[Node],
    source_root: str,
) -> tuple[list[Node], list[Edge]]:
    """Create PACKAGE nodes and CONTAINS edges from the MODULE node file paths.

    Args:
        all_nodes: All nodes extracted so far (used to find MODULE nodes and to
            avoid duplicating PACKAGE nodes that already exist).
        source_root: The ``source_root`` from docgen.toml (e.g. ``"target"``).
            Used to determine which directory component is the repo-relative root
            so that the root itself is not turned into a package.

    Returns:
        ``(new_package_nodes, new_contains_edges)`` — these must be appended to
        the running node/edge lists in cli._run_extract.
    """
    existing_ids: set[str] = {n.id for n in all_nodes}

    # Collect all MODULE nodes and their parent directories.
    # module_id is a POSIX path relative to repo root, e.g. "target/app/db/queries.py"
    # parent dir is e.g. "target/app/db"
    module_nodes = [n for n in all_nodes if n.type is NodeType.MODULE]

    # Map: package_dir (POSIX) → list of direct-child node ids (modules or sub-packages)
    pkg_children: dict[str, list[str]] = {}

    # Determine root dir from source_root (the top-level we never want to make a package)
    # source_root is e.g. "target" — its immediate children are the real top-level packages
    root_posix = PurePosixPath(source_root).as_posix()  # normalise

    for mod in module_nodes:
        parent_dir = PurePosixPath(mod.id).parent.as_posix()
        # Skip the root itself: "target" or "." should not become a package
        if parent_dir in (".", "", root_posix):
            continue
        pkg_children.setdefault(parent_dir, []).append(mod.id)

    # Expand parent chain: "target/app/db/repositories" also needs "target/app/db",
    # "target/app", etc.  Walk up until we hit the root.
    all_pkg_dirs: set[str] = set(pkg_children.keys())
    for d in list(all_pkg_dirs):
        p = PurePosixPath(d)
        while True:
            parent = p.parent.as_posix()
            if parent in (".", "", root_posix):
                break
            if parent not in all_pkg_dirs:
                all_pkg_dirs.add(parent)
                pkg_children.setdefault(parent, [])
            p = PurePosixPath(parent)

    # Wire child packages into their parents.
    for pkg_dir in sorted(all_pkg_dirs):
        parent_dir = PurePosixPath(pkg_dir).parent.as_posix()
        if parent_dir in (".", "", root_posix):
            continue
        if parent_dir in all_pkg_dirs:
            # pkg_dir is a sub-package of parent_dir
            if pkg_dir not in pkg_children[parent_dir]:
                pkg_children[parent_dir].append(pkg_dir)

    new_nodes: list[Node] = []
    new_edges: list[Edge] = []

    # Build package nodes in sorted order (shorter paths first = outer packages first,
    # but CONTAINS edges from module→package are still bottom-up because topological_order
    # in hierarchy.py handles the sort).
    for pkg_dir in sorted(all_pkg_dirs):
        pkg_id = pkg_dir  # already a POSIX repo-root-relative path

        if pkg_id in existing_ids:
            # Package already exists (rare: __init__.py was extracted as module with same id)
            continue

        children = sorted(set(pkg_children.get(pkg_dir, [])))
        if not children:
            continue  # no children → skip ghost package

        # hash_struct: sha256 of sorted child node IDs — changes when a module is added/removed
        hash_val = _sha256("\n".join(children))

        pkg_node = Node(
            id=pkg_id,
            type=NodeType.PACKAGE,
            file="",
            lines=(0, 0),
            hash_struct=hash_val,
            hash_source=hash_val,
            name=PurePosixPath(pkg_dir).name,
        )
        new_nodes.append(pkg_node)
        existing_ids.add(pkg_id)  # prevent duplicates within this call

        # CONTAINS edges: package → each direct child
        for child_id in children:
            new_edges.append(Edge(
                type=EdgeType.CONTAINS,
                from_id=pkg_id,
                to_id=child_id,
                meta=(),
            ))

    return new_nodes, new_edges
