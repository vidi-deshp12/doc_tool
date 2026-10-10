"""Extract body facts: raises (type + args) and raw calls per function.

For each module-level function node this module emits:
- RAISES edges: function → resolved exception type (external: or in-repo node ID),
  meta=(("args", "<unparsed constructor args>"),).
- CALLS edges: function → callable name (ast.unparse of call.func),
  meta=(("call_text", "<full unparsed call>"),). One edge per unique callee per function.

core.py does not emit RAISES or CALLS edges; this module owns all of them.
Only module-level functions are processed (class methods are not yet extracted by core.py).
"""

from __future__ import annotations

import ast

from ..facts.schema import Edge, EdgeType, Node, NodeType, Unresolved
from .modules import ModuleInfo


# ---------------------------------------------------------------------------
# Sub-task A — Exception type resolution
# ---------------------------------------------------------------------------

def _build_name_to_dotted(info: ModuleInfo) -> dict[str, str]:
    """Build a {bare_name: dotted_name} map from a file's import records.

    Handles:
    - `from pkg.mod import Name` → {"Name": "pkg.mod.Name"}
    - `import pkg.mod` → {"pkg": "pkg.mod"}
    """
    name_to_dotted: dict[str, str] = {}
    for imp in info.imports:
        if imp.level == 0 and imp.module:
            if imp.names:
                # from module import name1, name2
                for n in imp.names:
                    name_to_dotted[n] = f"{imp.module}.{n}"
            else:
                # import module  (bare import)
                top = imp.module.split(".")[0]
                name_to_dotted[top] = imp.module
    return name_to_dotted


def _resolve_exception_type(
    raw_name: str,
    file_path: str,
    path_to_info: dict[str, ModuleInfo],
    dotted_to_path: dict[str, str],
    node_map: dict[str, Node],
) -> str:
    """Resolve an exception type name to a node ID.

    raw_name may be a simple name ("HTTPException") or dotted ("errors.NotFound").
    Returns "external:<dotted>" or "<file>::<ClassName>" for in-repo types.
    Falls back to "external:<raw_name>" when nothing resolves.
    """
    info = path_to_info.get(file_path)
    name_to_dotted = _build_name_to_dotted(info) if info else {}

    # For dotted names like "errors.NotFound", resolve the leading component first.
    if "." in raw_name:
        head, tail = raw_name.split(".", 1)
        if head in name_to_dotted:
            dotted = f"{name_to_dotted[head]}.{tail}"
        else:
            return f"external:{raw_name}"
    else:
        dotted = name_to_dotted.get(raw_name)
        if dotted is None:
            # Not imported — check same-file class definitions
            same_file_id = f"{file_path}::{raw_name}"
            if same_file_id in node_map:
                return same_file_id
            return f"external:{raw_name}"

    # Try exact dotted match in the repo index
    if dotted in dotted_to_path:
        target_file = dotted_to_path[dotted]
        class_name = dotted.split(".")[-1]
        candidate_id = f"{target_file}::{class_name}"
        if candidate_id in node_map:
            return candidate_id

    # Try longest-prefix match (class in a module)
    parts = dotted.split(".")
    for i in range(len(parts) - 1, 0, -1):
        prefix = ".".join(parts[:i])
        class_name = ".".join(parts[i:])
        if "." not in class_name and prefix in dotted_to_path:
            target_file = dotted_to_path[prefix]
            candidate_id = f"{target_file}::{class_name}"
            if candidate_id in node_map:
                return candidate_id

    # Imported but not in repo → external
    return f"external:{dotted}"


# ---------------------------------------------------------------------------
# Sub-task B — RAISES edge extraction
# ---------------------------------------------------------------------------

def _unparse_args(call_node: ast.Call) -> str:
    """Unparse all positional and keyword args of a Call into a single string."""
    parts: list[str] = []
    for arg in call_node.args:
        parts.append(ast.unparse(arg))
    for kw in call_node.keywords:
        if kw.arg:
            parts.append(f"{kw.arg}={ast.unparse(kw.value)}")
        else:
            # **kwargs spread
            parts.append(f"**{ast.unparse(kw.value)}")
    return ", ".join(parts)


def _extract_raises(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    func_id: str,
    file_path: str,
    path_to_info: dict[str, ModuleInfo],
    dotted_to_path: dict[str, str],
    node_map: dict[str, Node],
    external_seen: set[str],
) -> tuple[list[Edge], list[Node]]:
    """Extract RAISES edges from a function body.

    Returns (raises_edges, new_external_nodes).
    """
    edges: list[Edge] = []
    new_externals: list[Node] = []

    for node in ast.walk(func_node):
        # Only visit the body, not the function signature itself.
        # ast.walk on func_node includes the function node; skip non-Raise nodes.
        if not isinstance(node, ast.Raise):
            continue
        if node.exc is None:
            # Bare `raise` — re-raise inside except, no type to capture.
            continue

        exc = node.exc  # may be ast.Call or ast.Name/ast.Attribute

        if isinstance(exc, ast.Call):
            raw_name = ast.unparse(exc.func)
            args_text = _unparse_args(exc)
            meta: tuple[tuple[str, str], ...] = (("args", args_text),) if args_text else ()
        else:
            # raise SomeVariable or raise module.ExcClass (not called)
            raw_name = ast.unparse(exc)
            meta = ()

        resolved_id = _resolve_exception_type(
            raw_name, file_path, path_to_info, dotted_to_path, node_map
        )

        edges.append(Edge(
            type=EdgeType.RAISES,
            from_id=func_id,
            to_id=resolved_id,
            meta=meta,
        ))

        # Emit external Node once per unique external ID
        if resolved_id.startswith("external:") and resolved_id not in external_seen:
            external_seen.add(resolved_id)
            lib_dotted = resolved_id[len("external:"):]
            lib_name = lib_dotted.split(".")[0]
            new_externals.append(Node(
                id=resolved_id,
                type=NodeType.EXTERNAL,
                file="",
                lines=(0, 0),
                hash_struct="",
                hash_source="",
                library_name=lib_name,
            ))

    return edges, new_externals


# ---------------------------------------------------------------------------
# Sub-task C — CALLS edge extraction
# ---------------------------------------------------------------------------

def _extract_calls(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    func_id: str,
) -> list[Edge]:
    """Extract CALLS edges from a function body.

    One edge per unique callable (to_id = ast.unparse(call.func)).
    meta carries the full call text for the summarizer.
    When the same callable is called multiple times, the last call_text is kept.
    """
    # Use a dict keyed by to_id so duplicates are naturally deduplicated.
    seen: dict[str, Edge] = {}

    for node in ast.walk(func_node):
        if not isinstance(node, ast.Call):
            continue
        try:
            to_id = ast.unparse(node.func)
            call_text = ast.unparse(node)
        except Exception:
            # ast.unparse can fail on malformed nodes in rare edge cases
            continue

        seen[to_id] = Edge(
            type=EdgeType.CALLS,
            from_id=func_id,
            to_id=to_id,
            meta=(("call_text", call_text),),
        )

    return list(seen.values())


# ---------------------------------------------------------------------------
# Sub-task D — Public entry point
# ---------------------------------------------------------------------------

def extract_body_facts(
    nodes: list[Node],
    edges: list[Edge],
    path_to_info: dict[str, ModuleInfo],
    dotted_to_path: dict[str, str],
    repo_root: str | None = None,
) -> tuple[list[Edge], list[Edge], list[Node], list[Unresolved]]:
    """Extract RAISES and CALLS edges for all module-level function nodes.

    Call this after extract_file() has been called on all files and after
    build_module_index() has produced path_to_info and dotted_to_path.

    Args:
        nodes: All extracted nodes (across all files).
        edges: All extracted edges (from core.py / classes.py).
        path_to_info: From modules.build_module_index().
        dotted_to_path: From modules.build_module_index().
        repo_root: Absolute path to the repository root. Required to re-parse
                   source files for AST walking. If None, files are looked up
                   via path_to_info's own source reading.

    Returns:
        (raises_edges, calls_edges, new_external_nodes, unresolved)
    """
    from pathlib import Path

    node_map: dict[str, Node] = {n.id: n for n in nodes}
    # Pre-seed external_seen from nodes already in the graph
    external_seen: set[str] = {n.id for n in nodes if n.type == NodeType.EXTERNAL}

    all_raises: list[Edge] = []
    all_calls: list[Edge] = []
    all_externals: list[Node] = []

    # Build per-file AST cache: file_path → {func_name → ast.FunctionDef}
    # We re-parse each file once, lazily.
    ast_cache: dict[str, dict[str, ast.FunctionDef | ast.AsyncFunctionDef]] = {}

    def _get_func_ast(
        file_path: str,
    ) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
        if file_path in ast_cache:
            return ast_cache[file_path]

        func_map: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        try:
            if repo_root:
                src_path = Path(repo_root) / file_path
            else:
                # Fall back: try relative to cwd
                src_path = Path(file_path)
            source = src_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(src_path))
            for item in tree.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_map[item.name] = item
        except (OSError, SyntaxError):
            pass

        ast_cache[file_path] = func_map
        return func_map

    for node in nodes:
        if node.type != NodeType.FUNCTION:
            continue

        func_map = _get_func_ast(node.file)
        func_ast = func_map.get(node.name)
        if func_ast is None:
            continue

        raises_edges, new_ext = _extract_raises(
            func_ast, node.id, node.file,
            path_to_info, dotted_to_path, node_map, external_seen,
        )
        calls_edges = _extract_calls(func_ast, node.id)

        all_raises.extend(raises_edges)
        all_calls.extend(calls_edges)
        all_externals.extend(new_ext)

    return all_raises, all_calls, all_externals, []
