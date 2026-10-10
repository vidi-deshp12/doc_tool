"""Dotted-name <-> path index; resolve absolute/relative imports, aliases, __init__ re-exports."""

from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..facts.schema import Edge, EdgeType, Node, NodeType, Unresolved
from .core import extract_file


@dataclass
class ModuleInfo:
    """Information about a module from its file."""
    dotted_name: str
    file_path: str  # root-relative POSIX
    imports: list[ImportRecord]
    is_package: bool = False


@dataclass
class ImportRecord:
    """An import statement from a module."""
    module: str | None  # None for `from . import x`
    names: list[str]    # imported names (empty for `import x`)
    level: int          # 0 = absolute, >0 = relative
    line: int
    is_star: bool = False  # `from x import *`
    alias: str | None = None  # for `import x as y` or `from x import y as z`


def build_module_index(
    module_paths: list[str],
    repo_root: Path,
    source_root: str = "target",
) -> tuple[dict[str, str], dict[str, ModuleInfo]]:
    """Build module index from walker output.

    Args:
        module_paths: List of root-relative POSIX file paths from walker.
        repo_root: Repository root path.
        source_root: The directory containing top-level packages (from config).

    Returns:
        (dotted_to_path, path_to_info) mappings.
    """
    dotted_to_path: dict[str, str] = {}
    path_to_info: dict[str, ModuleInfo] = {}

    # Normalize source_root to use POSIX
    source_root = source_root.replace("\\", "/").strip("/")

    # First pass: determine dotted names and package status
    for file_path in module_paths:
        # Convert file path to dotted name relative to source_root
        # e.g., "target/app/api/routes/api.py" with source_root="target" -> "app.api.routes.api"
        # e.g., "target/app/api/__init__.py" with source_root="target" -> "app.api"
        if file_path.startswith(source_root + "/"):
            rel_path = file_path[len(source_root) + 1:]
        elif file_path == source_root:
            rel_path = ""
        else:
            # File outside source_root - use full path
            rel_path = file_path

        if rel_path.endswith(".py"):
            if rel_path.endswith("__init__.py"):
                # Package: remove __init__.py and get parent
                dotted = rel_path[:-12].replace("/", ".")
            else:
                dotted = rel_path[:-3].replace("/", ".")
        else:
            dotted = rel_path.replace("/", ".")

        # Check if it's an __init__.py (package)
        is_package = file_path.endswith("__init__.py")

        # Extract imports by parsing the file
        full_path = repo_root / file_path
        try:
            source = full_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(full_path))
        except (SyntaxError, OSError):
            imports = []
        else:
            imports = _extract_imports(tree)

        info = ModuleInfo(
            dotted_name=dotted,
            file_path=file_path,
            imports=imports,
            is_package=is_package,
        )
        dotted_to_path[dotted] = file_path
        path_to_info[file_path] = info

    return dotted_to_path, path_to_info


def _extract_imports(tree: ast.Module) -> list[ImportRecord]:
    """Extract import records from an AST."""
    imports: list[ImportRecord] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(ImportRecord(
                    module=alias.name,
                    names=[alias.name],
                    level=0,
                    line=node.lineno,
                    is_star=False,
                    alias=alias.asname if alias.asname != alias.name else None,
                ))
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            names = []
            is_star = False
            for alias in node.names:
                if alias.name == "*":
                    is_star = True
                else:
                    names.append(alias.name)
            imports.append(ImportRecord(
                module=module,
                names=names,
                level=node.level,
                line=node.lineno,
                is_star=is_star,
                alias=None,  # aliases for ImportFrom handled per-name
            ))
            # For ImportFrom with aliases, we'd need more detail
            if not is_star:
                for alias in node.names:
                    if alias.asname and alias.asname != alias.name:
                        # We'll track this in resolution
                        pass
    return imports


def resolve_imports(
    dotted_to_path: dict[str, str],
    path_to_info: dict[str, ModuleInfo],
    repo_root: Path,
    source_root: str = "target",
) -> tuple[list[Edge], list[Unresolved], list[Node]]:
    """Resolve all imports across the module index.

    Args:
        dotted_to_path: Mapping from dotted name to file path.
        path_to_info: Module info by file path.
        repo_root: Repository root.
        source_root: The directory containing top-level packages.

    Returns:
        (edges, unresolved, external_nodes)
    """
    edges: list[Edge] = []
    unresolved: list[Unresolved] = []
    external_nodes: list[Node] = []
    external_cache: set[str] = set()

    for file_path, info in path_to_info.items():
        current_dotted = info.dotted_name
        current_parts = current_dotted.split(".")
        # Package depth: if current module is a package, depth = len(parts)
        # If it's a module, depth = len(parts) - 1 (last part is module name)
        pkg_depth = len(current_parts) if info.is_package else len(current_parts) - 1

        for imp in info.imports:
            if imp.module is None:
                # `from . import x` - relative import without module
                if imp.level == 0:
                    unresolved.append(Unresolved(
                        what=f"from . import {', '.join(imp.names)}",
                        why="relative import without module at top level",
                        where=f"{file_path}:{imp.line}",
                    ))
                    continue
                # Build base module from level
                # level=1 means current package, level=2 means parent, etc.
                # Check against package depth, not module depth
                if imp.level > pkg_depth:
                    unresolved.append(Unresolved(
                        what=f"from {'..'*imp.level} import {', '.join(imp.names)}",
                        why="relative import level exceeds package depth",
                        where=f"{file_path}:{imp.line}",
                    ))
                    continue
                # level=1: current package (base_parts = first pkg_depth parts)
                # level=2: parent package (base_parts = first pkg_depth - 1 parts)
                # etc.
                base_parts = current_parts[:pkg_depth - imp.level + 1]
                base_module = ".".join(base_parts) if base_parts else ""
            else:
                # Has a module name
                if imp.level == 0:
                    # Absolute import: `import x` or `from x import y`
                    base_module = imp.module
                else:
                    # Relative import with module: `from .x import y`
                    # level=1: current package, so base = current_dotted
                    # level=2: parent package
                    if imp.level > pkg_depth:
                        unresolved.append(Unresolved(
                            what=f"from {'..'*imp.level}.{imp.module} import ...",
                            why="relative import level exceeds package depth",
                            where=f"{file_path}:{imp.line}",
                        ))
                        continue
                    # For relative imports with module, level=1 means current package
                    base_parts = current_parts[:pkg_depth - imp.level + 1]
                    if imp.module:
                        base_module = ".".join(base_parts + [imp.module])
                    else:
                        base_module = ".".join(base_parts)

            # Now resolve the base_module + names
            if imp.names:
                # `from ... import name1, name2`
                for name in imp.names:
                    full_dotted = f"{base_module}.{name}" if base_module else name
                    _resolve_single_import(
                        full_dotted=full_dotted,
                        from_dotted=current_dotted,
                        from_path=file_path,
                        dotted_to_path=dotted_to_path,
                        path_to_info=path_to_info,
                        edges=edges,
                        unresolved=unresolved,
                        external_nodes=external_nodes,
                        external_cache=external_cache,
                        line=imp.line,
                        is_star=imp.is_star,
                        alias=None,
                    )
            else:
                # `import module` or `import module as alias`
                _resolve_single_import(
                    full_dotted=base_module,
                    from_dotted=current_dotted,
                    from_path=file_path,
                    dotted_to_path=dotted_to_path,
                    path_to_info=path_to_info,
                    edges=edges,
                    unresolved=unresolved,
                    external_nodes=external_nodes,
                    external_cache=external_cache,
                    line=imp.line,
                    is_star=False,
                    alias=imp.alias,
                )

    return edges, unresolved, external_nodes


def _resolve_single_import(
    full_dotted: str,
    from_dotted: str,
    from_path: str,
    dotted_to_path: dict[str, str],
    path_to_info: dict[str, ModuleInfo],
    edges: list[Edge],
    unresolved: list[Unresolved],
    external_nodes: list[Node],
    external_cache: set[str],
    line: int,
    is_star: bool,
    alias: str | None,
) -> None:
    """Resolve a single imported name."""
    # Check if it's a known in-repo module
    if full_dotted in dotted_to_path:
        to_path = dotted_to_path[full_dotted]
        edges.append(Edge(
            type=EdgeType.IMPORTS,
            from_id=from_path,
            to_id=to_path,
            meta=(("alias", alias), ("star", str(is_star))) if (alias or is_star) else (),
        ))
        return

    # Check if it's a submodule of a known package (e.g., importing from __init__.py re-exports)
    # Try to find the longest prefix that matches
    parts = full_dotted.split(".")
    for i in range(len(parts), 0, -1):
        prefix = ".".join(parts[:i])
        if prefix in dotted_to_path:
            # Found a parent package - this might be a re-export or submodule
            to_path = dotted_to_path[prefix]
            edges.append(Edge(
                type=EdgeType.IMPORTS,
                from_id=from_path,
                to_id=to_path,
                meta=(("alias", alias), ("star", str(is_star)), ("submodule", ".".join(parts[i:]))) if (alias or is_star or i < len(parts)) else (),
            ))
            return

    # Not found in repo - mark as external
    if full_dotted not in external_cache:
        external_cache.add(full_dotted)
        # Determine library name (first component)
        lib_name = full_dotted.split(".")[0]
        external_nodes.append(Node(
            id=f"external:{full_dotted}",
            type=NodeType.EXTERNAL,
            file="",
            lines=(0, 0),
            hash_struct="",
            hash_source="",
            library_name=lib_name,
        ))
    edges.append(Edge(
        type=EdgeType.IMPORTS,
        from_id=from_path,
        to_id=f"external:{full_dotted}",
        meta=(("alias", alias), ("star", str(is_star))) if (alias or is_star) else (),
    ))


def build_full_index(
    module_paths: list[str],
    repo_root: Path,
    source_root: str = "target",
) -> tuple[dict[str, ModuleInfo], dict[str, str], list[Edge], list[Unresolved], list[Node]]:
    """Build complete module index with resolved imports.

    Args:
        module_paths: List of root-relative POSIX file paths from walker.
        repo_root: Repository root path.
        source_root: The directory containing top-level packages (from config).

    Returns:
        (path_to_info, dotted_to_path, import_edges, unresolved, external_nodes)
    """
    dotted_to_path, path_to_info = build_module_index(module_paths, repo_root, source_root)
    import_edges, unresolved, external_nodes = resolve_imports(
        dotted_to_path, path_to_info, repo_root, source_root
    )
    return path_to_info, dotted_to_path, import_edges, unresolved, external_nodes