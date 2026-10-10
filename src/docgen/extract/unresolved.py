"""Scan all files for statically-unresolvable patterns and emit Unresolved entries.

Detects three entry types not covered by other extraction passes:

- star_import    : `from x import *`  (names unknown until runtime)
- dynamic_import : `__import__(...)` or `importlib.import_module(...)` calls
- getattr_dynamic: `getattr(obj, name)` where `name` is not a string literal

All other unresolved entry types (syntax_error, relative import issues, unresolvable
base classes) are emitted by core.py, modules.py, and classes.py respectively.
"""

from __future__ import annotations

import ast
from pathlib import Path

from ..facts.schema import Unresolved
from .modules import ModuleInfo


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _scan_star_imports(path_to_info: dict[str, ModuleInfo]) -> list[Unresolved]:
    """Emit one Unresolved entry per star import across all files."""
    entries: list[Unresolved] = []
    for file_path, info in path_to_info.items():
        for imp in info.imports:
            if not imp.is_star:
                continue
            module_str = imp.module or "."
            level_dots = "." * imp.level
            what_text = f"from {level_dots}{module_str} import *"
            entries.append(Unresolved(
                what="star_import",
                why=what_text,
                where=f"{file_path}:{imp.line}",
            ))
    return entries


def _scan_dynamic_imports(file_path: str, tree: ast.Module) -> list[Unresolved]:
    """Detect `__import__(...)` and `importlib.*` calls in a parsed AST."""
    entries: list[Unresolved] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        try:
            func_text = ast.unparse(node.func)
        except Exception:
            continue

        is_dynamic = (
            func_text == "__import__"
            or func_text.startswith("importlib.")
        )
        if not is_dynamic:
            continue

        try:
            call_text = ast.unparse(node)
        except Exception:
            call_text = func_text + "(...)"

        line = getattr(node, "lineno", 0)
        entries.append(Unresolved(
            what="dynamic_import",
            why=call_text,
            where=f"{file_path}:{line}",
        ))
    return entries


def _scan_getattr(file_path: str, tree: ast.Module) -> list[Unresolved]:
    """Detect `getattr(obj, name)` where `name` is not a string literal."""
    entries: list[Unresolved] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        try:
            func_text = ast.unparse(node.func)
        except Exception:
            continue

        if func_text != "getattr":
            continue

        # getattr needs at least 2 args; the second is the attribute name.
        args = node.args
        if len(args) < 2:
            continue

        name_arg = args[1]
        # Only flag if the name argument is NOT a plain string constant.
        if isinstance(name_arg, ast.Constant) and isinstance(name_arg.value, str):
            continue  # static string — resolvable

        try:
            call_text = ast.unparse(node)
        except Exception:
            call_text = "getattr(...)"

        line = getattr(node, "lineno", 0)
        entries.append(Unresolved(
            what="getattr_dynamic",
            why=call_text,
            where=f"{file_path}:{line}",
        ))
    return entries


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def scan_for_unresolved(
    module_paths: list[str],
    path_to_info: dict[str, ModuleInfo],
    repo_root: str | Path,
) -> list[Unresolved]:
    """Scan all files for dynamically-unresolvable patterns.

    Detects star imports, dynamic imports (__import__ / importlib), and
    dynamic getattr calls.  Re-parses each file once; silently skips files
    that cannot be read or parsed (those are already in the unresolved list
    from core.py as syntax_error entries).

    Args:
        module_paths: Root-relative POSIX paths from walker.
        path_to_info: Per-file module info from modules.build_module_index().
        repo_root: Absolute path to the repository root.

    Returns:
        List of Unresolved entries, sorted by (where, what).
    """
    repo_root = Path(repo_root)
    entries: list[Unresolved] = []

    # Star imports — detected from ModuleInfo, no re-parsing needed
    entries.extend(_scan_star_imports(path_to_info))

    # Dynamic imports and getattr — need to re-parse each file
    for file_path in module_paths:
        src_path = repo_root / file_path
        try:
            source = src_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(src_path))
        except (OSError, SyntaxError):
            # Already reported as syntax_error / unparsed_file by core.py
            continue

        entries.extend(_scan_dynamic_imports(file_path, tree))
        entries.extend(_scan_getattr(file_path, tree))

    entries.sort(key=lambda u: (u.where, u.what))
    return entries
