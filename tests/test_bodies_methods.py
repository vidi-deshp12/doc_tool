"""Tests for class method body facts in bodies.py (task 2a.6b)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from docgen.extract.bodies import extract_body_facts
from docgen.extract.core import extract_file
from docgen.extract.modules import build_module_index
from docgen.facts.schema import EdgeType, NodeType


def _write(tmp_path: Path, rel: str, src: str) -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(src), encoding="utf-8")
    return p


def _run(tmp_path: Path, files: list[str]) -> tuple[list, list, list, list]:
    """Extract and return (raises, calls, externals, unresolved)."""
    all_nodes: list = []
    all_edges: list = []
    for rel in files:
        p = tmp_path / rel
        nodes, edges, _ = extract_file(p, tmp_path)
        all_nodes.extend(nodes)
        all_edges.extend(edges)

    dotted_to_path, path_to_info = build_module_index(files, tmp_path, source_root="")
    return extract_body_facts(
        all_nodes, all_edges, path_to_info, dotted_to_path,
        repo_root=str(tmp_path),
    )


# ---------------------------------------------------------------------------
# Test 1: raise inside a class method → RAISES edge from method node
# ---------------------------------------------------------------------------

def test_method_raises_edge(tmp_path: Path) -> None:
    """raise HTTPException(...) inside a method → RAISES from method node id."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/handler.py", """
        from fastapi import HTTPException

        class Router:
            async def get_item(self, item_id: int):
                if item_id < 0:
                    raise HTTPException(status_code=404, detail='not found')
    """)

    raises, calls, _, _ = _run(
        tmp_path, ["pkg/__init__.py", "pkg/handler.py"]
    )

    method_raises = [
        e for e in raises
        if e.from_id == "pkg/handler.py::Router::get_item"
    ]
    assert len(method_raises) == 1
    assert method_raises[0].to_id == "external:fastapi.HTTPException"
    assert "404" in dict(method_raises[0].meta).get("args", "")


# ---------------------------------------------------------------------------
# Test 2: call inside a class method → CALLS edge from method node
# ---------------------------------------------------------------------------

def test_method_calls_edge(tmp_path: Path) -> None:
    """A function call inside a method produces a CALLS edge from the method node."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/service.py", """
        class Service:
            def process(self, items):
                return sorted(items)
    """)

    _, calls, _, _ = _run(
        tmp_path, ["pkg/__init__.py", "pkg/service.py"]
    )

    method_calls = [
        e for e in calls
        if e.from_id == "pkg/service.py::Service::process"
    ]
    to_ids = {e.to_id for e in method_calls}
    assert "sorted" in to_ids


# ---------------------------------------------------------------------------
# Test 3: Module-level functions still produce edges (regression)
# ---------------------------------------------------------------------------

def test_module_level_functions_still_processed(tmp_path: Path) -> None:
    """Module-level function edges are still produced after the method extension."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/utils.py", """
        from fastapi import HTTPException

        def validate(x):
            if x < 0:
                raise HTTPException(status_code=400)
    """)

    raises, _, _, _ = _run(
        tmp_path, ["pkg/__init__.py", "pkg/utils.py"]
    )

    func_raises = [e for e in raises if e.from_id == "pkg/utils.py::validate"]
    assert len(func_raises) == 1


# ---------------------------------------------------------------------------
# Test 4: Integration — real target repo, a repository method raises something
# ---------------------------------------------------------------------------

def test_real_repo_method_body_facts() -> None:
    """At least one method in the real target/ repo produces RAISES or CALLS edges."""
    repo_root = Path(__file__).parent.parent
    if not (repo_root / "target").exists():
        pytest.skip("target/ repo not present")

    from docgen.config import load_config
    from docgen.walker import walk_repo

    config = load_config(repo_root / "docgen.toml")
    module_paths = list(walk_repo(config, repo_root=repo_root))

    all_nodes: list = []
    all_edges: list = []
    for rel in module_paths:
        p = repo_root / rel
        if p.exists():
            nodes, edges, _ = extract_file(p, repo_root)
            all_nodes.extend(nodes)
            all_edges.extend(edges)

    dotted_to_path, path_to_info = build_module_index(
        module_paths, repo_root, source_root=config.source_root
    )

    raises, calls, _, _ = extract_body_facts(
        all_nodes, all_edges, path_to_info, dotted_to_path,
        repo_root=str(repo_root),
    )

    # At least some method nodes should produce CALLS edges
    method_calls = [
        e for e in calls
        if "::" in e.from_id and e.from_id.count("::") == 2
    ]
    assert len(method_calls) > 0, "Expected method CALLS edges but got none"
