"""Per-file AST extraction: modules, classes, functions, decorators, docstrings, imports.

Ported from spike.py but outputs Node/Edge/Unresolved dataclasses from schema.py.
"""

from __future__ import annotations

import ast
import hashlib
import token
import tokenize
import io
from pathlib import Path
from typing import Any

from ..facts.schema import Edge, EdgeType, Node, NodeType, Unresolved

HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}


def _sha256(text: str) -> str:
    """Return SHA-256 hex digest of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _make_synthetic_ast_for_hash(node: ast.AST) -> ast.AST:
    """Create a synthetic AST node containing only structural fields for hash_struct.

    hash_struct includes: function signature, decorator texts (including route args),
    bases, class field names+annotations, import module names.
    Excludes: line numbers, docstrings, function body, comments, default values.
    """
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        # Create a new function with same signature, decorators, returns
        # but no body, no default values, no docstring
        new_args = ast.arguments(
            posonlyargs=node.args.posonlyargs,
            args=[ast.arg(arg=a.arg, annotation=a.annotation) for a in node.args.args],
            kwonlyargs=[ast.arg(arg=a.arg, annotation=a.annotation) for a in node.args.kwonlyargs],
            kw_defaults=[None] * len(node.args.kwonlyargs),
            defaults=[],
            vararg=ast.arg(arg=node.args.vararg.arg, annotation=node.args.vararg.annotation) if node.args.vararg else None,
            kwarg=ast.arg(arg=node.args.kwarg.arg, annotation=node.args.kwarg.annotation) if node.args.kwarg else None,
        )
        # Keep decorators with their full text
        decorators = node.decorator_list
        returns = node.returns
        new_node = type(node)(
            name=node.name,
            args=new_args,
            body=[],  # empty body
            decorator_list=decorators,
            returns=returns,
            type_params=[],
        )
        return new_node

    elif isinstance(node, ast.ClassDef):
        # Create a class with same bases, decorators, but only field annotations.
        # method_hash_structs are injected as Constant nodes so a method signature
        # change propagates into the class hash_struct.
        new_bases = node.bases
        new_decorators = node.decorator_list
        new_body = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                # Keep only annotated field (name + annotation), no default
                new_body.append(ast.AnnAssign(
                    target=ast.Name(id=item.target.id, ctx=ast.Store()),
                    annotation=item.annotation,
                    value=None,
                    simple=1,
                ))
        new_node = ast.ClassDef(
            name=node.name,
            bases=new_bases,
            keywords=node.keywords,
            body=new_body,
            decorator_list=new_decorators,
            type_params=[],
        )
        return new_node

    elif isinstance(node, ast.Import):
        return node
    elif isinstance(node, ast.ImportFrom):
        return node
    elif isinstance(node, ast.Module):
        # Keep only imports and simple assignments
        new_body = []
        for item in node.body:
            if isinstance(item, (ast.Import, ast.ImportFrom)):
                new_body.append(item)
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        new_body.append(ast.Assign(
                            targets=[ast.Name(id=target.id, ctx=ast.Store())],
                            value=ast.Constant(value=0),
                        ))
                        break
        return ast.Module(body=new_body, type_ignores=[])

    return node


def _hash_struct_node(node: ast.AST) -> str:
    """Compute hash_struct for a node using ast.dump of synthetic AST.

    hash_struct includes structural fields only, excludes line numbers, comments, body.
    """
    synthetic = _make_synthetic_ast_for_hash(node)
    # Use ast.dump with indent=None for compact representation
    dumped = ast.dump(synthetic, annotate_fields=True, include_attributes=False)
    return _sha256(dumped)


def _hash_struct_class(class_node: ast.ClassDef, method_hash_structs: list[str]) -> str:
    """Compute hash_struct for a class, including method signature hashes.

    The synthetic class body contains:
    - Annotated field assignments (name + annotation, no default)
    - Each method's hash_struct as a Constant string node

    This means: editing a method signature changes the class hash_struct.
    Editing only a method body comment does not.
    """
    synthetic = _make_synthetic_ast_for_hash(class_node)
    # Append method hash_structs as Constant nodes after field annotations
    for mhs in method_hash_structs:
        synthetic.body.append(ast.Expr(value=ast.Constant(value=mhs)))  # type: ignore[attr-defined]
    dumped = ast.dump(synthetic, annotate_fields=True, include_attributes=False)
    return _sha256(dumped)


def _hash_source_span(source: str, start_line: int, end_line: int) -> str:
    """Compute hash_source using Python tokenize module.

    Tokenizes the source span (first decorator to end of body), filters out
    NEWLINE/NL/INDENT/DEDENT/ENCODING tokens and whitespace-only tokens,
    joins remaining token strings, sha256 the result.
    """
    # Get the source span
    lines = source.splitlines()
    span_text = "\n".join(lines[start_line - 1:end_line])

    # Tokenize
    tokens = list(tokenize.generate_tokens(io.StringIO(span_text).readline))

    # Filter tokens
    kept_strings = []
    for tok_type, tok_string, _, _, _ in tokens:
        # Skip NEWLINE, NL, INDENT, DEDENT, ENCODING, ENDMARKER
        if tok_type in (token.NEWLINE, token.NL, token.INDENT, token.DEDENT,
                        token.ENCODING, token.ENDMARKER):
            continue
        # Skip whitespace-only strings
        if tok_string.strip() == "":
            continue
        kept_strings.append(tok_string)

    result = "".join(kept_strings)
    return _sha256(result)


def _get_decorator_start_line(node: ast.AST) -> int:
    """Get the first line of decorators, or the node's own line if no decorators."""
    if hasattr(node, 'decorator_list') and node.decorator_list:
        return min(d.lineno for d in node.decorator_list)
    return node.lineno


def _extract_decorator_texts(node: ast.AST) -> tuple[str, ...]:
    """Extract decorator texts as strings."""
    if not hasattr(node, 'decorator_list'):
        return ()
    return tuple(
        ast.unparse(d) if isinstance(d, ast.expr) else str(d)
        for d in node.decorator_list
    )


def _class_header_end_line(class_node: ast.ClassDef) -> int:
    """Return the last line of the class header (decorators + class def + docstring).

    The header ends at:
    - The last line of the docstring, if the first body statement is a string Expr.
    - Otherwise the class def line itself (node.lineno).

    This determines how far hash_source covers for the class node — method bodies
    are excluded so they don't trigger class-level re-summarisation.
    """
    if class_node.body:
        first = class_node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            # Docstring present — header ends at its last line
            return first.end_lineno  # type: ignore[attr-defined]
    # No docstring: header is just the class def line
    return class_node.lineno


def _make_function_node(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    source: str,
    mid: str,
    is_async: bool,
    hash_source: str,
) -> Node:
    """Create a Node from a function AST node with decorator-inclusive span."""
    start = _get_decorator_start_line(node)
    end = node.end_lineno
    lines = (start, end)

    hash_struct = _hash_struct_node(node)

    decorators = _extract_decorator_texts(node)

    return Node(
        id=f"{mid}::{node.name}",
        type=NodeType.FUNCTION,
        file=mid,
        lines=lines,
        hash_struct=hash_struct,
        hash_source=hash_source,
        dotted_name="",
        docstring=ast.get_docstring(node) or "",
        bases=(),
        fields=(),
        is_pydantic_model=False,
        decorators=decorators,
        signature=ast.unparse(node.args) if node.args else "",
        returns=ast.unparse(node.returns) if node.returns else "",
        async_flag=is_async,
        parent_class="",
        library_name="",
        what="",
        why="",
        where="",
        method="",
        full_path="",
        name=node.name,
        status_code=0,
        variable="",
        prefix="",
        sql_name="",
        sql_file="",
    )


def _make_method_node(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    source: str,
    mid: str,
    class_id: str,
    class_name: str,
    is_async: bool,
) -> Node:
    """Create a FUNCTION Node for a class method.

    Args:
        node: The method's AST node.
        source: Full source text of the file.
        mid: Root-relative POSIX file path (module ID).
        class_id: The class node's id (e.g. "app/models.py::MyClass").
        class_name: The class name (e.g. "MyClass").
        is_async: Whether the method is async.
    """
    start = _get_decorator_start_line(node)
    end = node.end_lineno
    lines = (start, end)

    hash_struct = _hash_struct_node(node)
    hash_source = _hash_source_span(source, start, end)
    decorators = _extract_decorator_texts(node)

    return Node(
        id=f"{mid}::{class_name}::{node.name}",
        type=NodeType.FUNCTION,
        file=mid,
        lines=lines,
        hash_struct=hash_struct,
        hash_source=hash_source,
        dotted_name="",
        docstring=ast.get_docstring(node) or "",
        bases=(),
        fields=(),
        is_pydantic_model=False,
        decorators=decorators,
        signature=ast.unparse(node.args) if node.args else "",
        returns=ast.unparse(node.returns) if node.returns else "",
        async_flag=is_async,
        parent_class=class_id,
        library_name="",
        what="",
        why="",
        where="",
        method="",
        full_path="",
        name=node.name,
        status_code=0,
        variable="",
        prefix="",
        sql_name="",
        sql_file="",
    )


def _make_class_node(
    node: ast.ClassDef,
    source: str,
    mid: str,
    method_hash_structs: list[str],
) -> Node:
    """Create a Node from a class AST node.

    hash_struct includes field annotations AND each method's hash_struct (so a
    method signature change marks the class stale).
    hash_source covers only the class header: decorators + class def + docstring.
    Method bodies are excluded from hash_source; they belong to method nodes.
    """
    decorator_start = _get_decorator_start_line(node)
    end = node.end_lineno
    lines = (decorator_start, end)

    # hash_struct: fields + injected method hashes
    hash_struct = _hash_struct_class(node, method_hash_structs)

    # hash_source: header span only (decorators → end of docstring or class def line)
    header_end = _class_header_end_line(node)
    hash_source = _hash_source_span(source, decorator_start, header_end)

    fields: list[tuple[str, str, str]] = []
    for item in node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            fields.append((
                item.target.id,
                ast.unparse(item.annotation),
                ast.unparse(item.value) if item.value else "",
            ))

    decorators = _extract_decorator_texts(node)

    return Node(
        id=f"{mid}::{node.name}",
        type=NodeType.CLASS,
        file=mid,
        lines=lines,
        hash_struct=hash_struct,
        hash_source=hash_source,
        dotted_name="",
        docstring=ast.get_docstring(node) or "",
        bases=tuple(ast.unparse(b) for b in node.bases),
        fields=tuple(fields),
        is_pydantic_model=False,
        decorators=decorators,
        signature="",
        returns="",
        async_flag=False,
        parent_class="",
        library_name="",
        what="",
        why="",
        where="",
        method="",
        full_path="",
        name=node.name,
        status_code=0,
        variable="",
        prefix="",
        sql_name="",
        sql_file="",
    )


def _make_module_node(
    tree: ast.Module,
    source: str,
    mid: str,
    hash_source: str,
) -> Node:
    """Create a Module Node from the parsed AST."""
    # hash_struct for module: imports + simple assignments
    hash_struct = _hash_struct_node(tree)

    return Node(
        id=mid,
        type=NodeType.MODULE,
        file=mid,
        lines=(1, len(source.splitlines())),
        hash_struct=hash_struct,
        hash_source=hash_source,
        dotted_name="",
        docstring=ast.get_docstring(tree) or "",
        bases=(),
        fields=(),
        is_pydantic_model=False,
        decorators=(),
        signature="",
        returns="",
        async_flag=False,
        parent_class="",
        library_name="",
        what="",
        why="",
        where="",
        method="",
        full_path="",
        name="",
        status_code=0,
        variable="",
        prefix="",
        sql_name="",
        sql_file="",
    )


def _collect_depends_from_params(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Collect names used in Depends(...) in the function's parameters."""
    found = []
    args = node.args
    defaults = list(args.defaults) + [d for d in args.kw_defaults if d is not None]
    for d in defaults:
        for n in ast.walk(d):
            if (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id == "Depends"
                and n.args
            ):
                found.append(ast.unparse(n.args[0]))
    return found


def _collect_decorator_depends(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Collect names used in Depends(...) in decorators."""
    found = []
    for dec in node.decorator_list:
        for n in ast.walk(dec):
            if (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id == "Depends"
                and n.args
            ):
                found.append(ast.unparse(n.args[0]))
    return found


def extract_file(path: Path, root: Path) -> tuple[list[Node], list[Edge], list[Unresolved]]:
    """Extract nodes, edges, and unresolved from a single Python file.

    Args:
        path: Path to the Python file.
        root: Repository root (for relative path IDs).

    Returns:
        Tuple of (nodes, edges, unresolved).
        On SyntaxError: returns ([], [], [one Unresolved entry]).
    """
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        # Per-file SyntaxError: record as unresolved, return empty nodes/edges
        try:
            file_id = path.resolve().relative_to(root.resolve()).as_posix().replace("\\", "/")
        except ValueError:
            file_id = str(path)
        return [], [], [
            Unresolved(
                what="syntax_error",
                why=f"SyntaxError: {e}",
                where=f"{file_id}:0",
            )
        ]

    # Compute root-relative POSIX path
    try:
        mid = path.resolve().relative_to(root.resolve()).as_posix().replace("\\", "/")
    except ValueError:
        mid = str(path).replace("\\", "/")

    # Compute file-level hash_source using tokenize on full source
    # Hash the entire file content through tokenize (keeps comments, strips blanks)
    hash_source = _hash_source_span(source, 1, len(source.splitlines()))

    # Build module node
    module_node = _make_module_node(tree, source, mid, hash_source)

    nodes: list[Node] = [module_node]
    edges: list[Edge] = []
    unresolved: list[Unresolved] = []

    # Process classes and functions
    for item in tree.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            is_async = isinstance(item, ast.AsyncFunctionDef)
            fn_node = _make_function_node(item, source, mid, is_async, hash_source)
            nodes.append(fn_node)

            # Edge: module contains function
            edges.append(
                Edge(
                    type=EdgeType.CONTAINS,
                    from_id=module_node.id,
                    to_id=fn_node.id,
                    meta=(),
                )
            )

            # Edges for depends_on from parameters
            for dep_name in _collect_depends_from_params(item):
                edges.append(
                    Edge(
                        type=EdgeType.DEPENDS_ON,
                        from_id=fn_node.id,
                        to_id=f"external:{dep_name}",
                        meta=(("via", "parameter"),),
                    )
                )

            # Edges for decorator depends
            for dep_name in _collect_decorator_depends(item):
                edges.append(
                    Edge(
                        type=EdgeType.DEPENDS_ON,
                        from_id=fn_node.id,
                        to_id=f"external:{dep_name}",
                        meta=(("via", "decorator"),),
                    )
                )

        elif isinstance(item, ast.ClassDef):
            # Collect method AST nodes (direct children only; no nested classes)
            method_asts = [
                m for m in item.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]

            # Pre-compute each method's hash_struct for injection into class hash_struct
            method_hash_structs = [_hash_struct_node(m) for m in method_asts]

            cls_node = _make_class_node(item, source, mid, method_hash_structs)
            nodes.append(cls_node)

            # Edge: module contains class
            edges.append(
                Edge(
                    type=EdgeType.CONTAINS,
                    from_id=module_node.id,
                    to_id=cls_node.id,
                    meta=(),
                )
            )

            # INHERITS edges are produced by extract/classes.py after name resolution.

            # Extract method nodes and edges
            for method_ast in method_asts:
                is_async = isinstance(method_ast, ast.AsyncFunctionDef)
                method_node = _make_method_node(
                    method_ast, source, mid,
                    class_id=cls_node.id,
                    class_name=item.name,
                    is_async=is_async,
                )
                nodes.append(method_node)

                # Edge: class contains method
                edges.append(
                    Edge(
                        type=EdgeType.CONTAINS,
                        from_id=cls_node.id,
                        to_id=method_node.id,
                        meta=(),
                    )
                )

                # Depends edges from method parameters and decorators
                for dep_name in _collect_depends_from_params(method_ast):
                    edges.append(
                        Edge(
                            type=EdgeType.DEPENDS_ON,
                            from_id=method_node.id,
                            to_id=f"external:{dep_name}",
                            meta=(("via", "parameter"),),
                        )
                    )
                for dep_name in _collect_decorator_depends(method_ast):
                    edges.append(
                        Edge(
                            type=EdgeType.DEPENDS_ON,
                            from_id=method_node.id,
                            to_id=f"external:{dep_name}",
                            meta=(("via", "decorator"),),
                        )
                    )

    return nodes, edges, unresolved