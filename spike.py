"""
spike.py - parse ONE Python file with `ast` and dump facts as JSON.

Usage:
    python spike.py path/to/file.py            # prints JSON
    python spike.py path/to/file.py out.json   # writes UTF-8 file
    python spike.py path/to/file.py out.json --root path/to/repo

Purpose: answer one question - could you write a useful paragraph about
this file using ONLY the JSON this script produces?
"""
import ast
import hashlib
import json
import sys
from pathlib import Path

HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}


def short_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def span_with_decorators(node, source: str):
    """Start line must include decorators, or edits to them never change the hash."""
    start = min([node.lineno] + [d.lineno for d in node.decorator_list])
    text = "\n".join(source.splitlines()[start - 1 : node.end_lineno])
    return start, text


def decorator_info(dec: ast.expr) -> dict:
    """Return the decorator as text, and route details if it looks like one."""
    info = {"text": ast.unparse(dec)}
    # Looks like @router.post("/path", response_model=X, status_code=201)
    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
        if dec.func.attr.lower() in HTTP_METHODS:
            route = {
                "router": ast.unparse(dec.func.value),
                "method": dec.func.attr.upper(),
                "path": None,
                "kwargs": {},
            }
            if dec.args and isinstance(dec.args[0], ast.Constant):
                route["path"] = dec.args[0].value
            for kw in dec.keywords:
                if kw.arg:
                    route["kwargs"][kw.arg] = ast.unparse(kw.value)
            info["route"] = route
    return info


def find_depends(fn) -> list:
    """Collect names used in Depends(...) in the function's parameters."""
    found = []
    args = fn.args
    defaults = list(args.defaults) + [d for d in args.kw_defaults if d is not None]
    for d in defaults:
        for node in ast.walk(d):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Depends"
                and node.args
            ):
                found.append(ast.unparse(node.args[0]))
    return found


def decorator_depends(fn) -> list:
    found = []
    for dec in fn.decorator_list:
        for node in ast.walk(dec):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Depends"
                and node.args
            ):
                found.append(ast.unparse(node.args[0]))
    return found


def function_node(fn, source: str, parent: str) -> dict:
    is_async = isinstance(fn, ast.AsyncFunctionDef)
    start, segment = span_with_decorators(fn, source)
    node = {
        "id": f"{parent}::{fn.name}",
        "type": "async_function" if is_async else "function",
        "name": fn.name,
        "lines": [start, fn.end_lineno],
        "def_line": fn.lineno,
        "signature": f"{fn.name}({ast.unparse(fn.args)})",
        "returns": ast.unparse(fn.returns) if fn.returns else None,
        "decorators": [decorator_info(d) for d in fn.decorator_list],
        "depends_on": find_depends(fn),
        "decorator_depends": decorator_depends(fn),
        "docstring": ast.get_docstring(fn),
        "hash": short_hash(segment),
    }
    return node


def class_node(cls: ast.ClassDef, source: str, parent: str) -> dict:
    cid = f"{parent}::{cls.name}"
    start, segment = span_with_decorators(cls, source)
    methods, fields = [], []
    for item in cls.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(function_node(item, source, cid))
        elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            fields.append(
                {
                    "name": item.target.id,
                    "annotation": ast.unparse(item.annotation),
                    "default": ast.unparse(item.value) if item.value else None,
                    "line": item.lineno,
                }
            )
    return {
        "id": cid,
        "type": "class",
        "name": cls.name,
        "lines": [start, cls.end_lineno],
        "bases": [ast.unparse(b) for b in cls.bases],
        "decorators": [decorator_info(d) for d in cls.decorator_list],
        "docstring": ast.get_docstring(cls),
        "fields": fields,
        "methods": methods,
        "hash": short_hash(segment),
    }


def import_records(tree: ast.Module) -> list:
    records = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                records.append({"module": alias.name, "names": [], "level": 0, "line": node.lineno})
        elif isinstance(node, ast.ImportFrom):
            records.append(
                {
                    "module": node.module,  # None for `from . import x`
                    "names": [a.name for a in node.names],
                    "level": node.level,  # >0 means relative import
                    "line": node.lineno,
                }
            )
    return records


def module_assignments(tree: ast.Module) -> list:
    """Top-level assignments such as `router = APIRouter()`."""
    out = []
    for item in tree.body:
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    out.append(
                        {"name": target.id, "value": ast.unparse(item.value)[:120], "line": item.lineno}
                    )
    return out


def module_id(path: Path, root: Path = None) -> str:
    """Stable ID = file path relative to the repo root, always with forward slashes."""
    if root is None:
        return path.as_posix()
    return path.resolve().relative_to(root.resolve()).as_posix()


def extract(path: Path, root: Path = None) -> dict:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    mid = module_id(path, root)
    functions, classes = [], []
    for item in tree.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(function_node(item, source, mid))
        elif isinstance(item, ast.ClassDef):
            classes.append(class_node(item, source, mid))
    return {
        "id": mid,
        "type": "module",
        "lines": [1, len(source.splitlines())],
        "docstring": ast.get_docstring(tree),
        "imports": import_records(tree),
        "assignments": module_assignments(tree),
        "classes": classes,
        "functions": functions,
        "hash": short_hash(source),
    }


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("file", help="python file to parse")
    ap.add_argument("output", nargs="?", help="optional output .json (written as UTF-8)")
    ap.add_argument("--root", help="repo root; IDs become paths relative to it")
    args = ap.parse_args()

    root = Path(args.root) if args.root else None
    result = json.dumps(extract(Path(args.file), root), indent=2)
    if args.output:
        Path(args.output).write_text(result, encoding="utf-8")
        print(f"Wrote {args.output} ({len(result)} bytes)")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(result)