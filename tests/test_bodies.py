"""Tests for extract/bodies.py — RAISES and CALLS edge extraction."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from docgen.extract.bodies import extract_body_facts
from docgen.extract.core import extract_file
from docgen.extract.modules import build_module_index
from docgen.facts.schema import EdgeType, NodeType


# ---------------------------------------------------------------------------
# Fixture helpers (same pattern as test_classes.py)
# ---------------------------------------------------------------------------

def _write(tmp_path: Path, rel: str, src: str) -> Path:
    """Write a dedented Python source file into tmp_path."""
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(src), encoding="utf-8")
    return p


def _run(tmp_path: Path, files: list[str]) -> tuple[list, list, list, list]:
    """Extract nodes/edges from all files and run extract_body_facts.

    Returns (raises_edges, calls_edges, new_external_nodes, unresolved).
    """
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
# Test 1: Basic RAISES — external exception with args
# ---------------------------------------------------------------------------

def test_basic_raises_external_with_args(tmp_path: Path) -> None:
    """raise HTTPException(status_code=400, detail='x') → RAISES edge with args meta."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/handler.py", """
        from fastapi import HTTPException

        def my_handler():
            raise HTTPException(status_code=400, detail='bad request')
    """)

    raises, calls, ext, _ = _run(tmp_path, ["pkg/__init__.py", "pkg/handler.py"])

    assert len(raises) == 1
    r = raises[0]
    assert r.type == EdgeType.RAISES
    assert r.from_id == "pkg/handler.py::my_handler"
    assert r.to_id == "external:fastapi.HTTPException"
    assert dict(r.meta).get("args") == "status_code=400, detail='bad request'"


# ---------------------------------------------------------------------------
# Test 2: External Node created for exception type
# ---------------------------------------------------------------------------

def test_raises_creates_external_node(tmp_path: Path) -> None:
    """Each unique exception type gets exactly one external Node."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/handler.py", """
        from fastapi import HTTPException

        def f1():
            raise HTTPException(status_code=400)

        def f2():
            raise HTTPException(status_code=404)
    """)

    raises, _, ext, _ = _run(tmp_path, ["pkg/__init__.py", "pkg/handler.py"])

    assert len(raises) == 2
    # External Node should be created only once
    ext_ids = [n.id for n in ext]
    assert ext_ids.count("external:fastapi.HTTPException") == 1
    ext_node = next(n for n in ext if n.id == "external:fastapi.HTTPException")
    assert ext_node.type == NodeType.EXTERNAL
    assert ext_node.library_name == "fastapi"


# ---------------------------------------------------------------------------
# Test 3: Bare `raise` is skipped
# ---------------------------------------------------------------------------

def test_bare_raise_skipped(tmp_path: Path) -> None:
    """Bare `raise` inside except block produces no RAISES edge."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/handler.py", """
        def reraise():
            try:
                pass
            except Exception:
                raise
    """)

    raises, _, _, _ = _run(tmp_path, ["pkg/__init__.py", "pkg/handler.py"])
    assert raises == []


# ---------------------------------------------------------------------------
# Test 4: `raise variable` (non-Call) — edge with empty meta
# ---------------------------------------------------------------------------

def test_raise_variable_emits_edge_with_empty_meta(tmp_path: Path) -> None:
    """`raise err` where err is a variable → RAISES edge, empty meta."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/handler.py", """
        from fastapi import HTTPException

        def f():
            err = HTTPException(status_code=403)
            raise err
    """)

    raises, _, _, _ = _run(tmp_path, ["pkg/__init__.py", "pkg/handler.py"])

    assert len(raises) == 1
    r = raises[0]
    assert r.type == EdgeType.RAISES
    assert r.meta == ()  # no args — it's a variable, not a call


# ---------------------------------------------------------------------------
# Test 5: Chained raise — only the raised exception, not the cause
# ---------------------------------------------------------------------------

def test_chained_raise_captures_only_exc(tmp_path: Path) -> None:
    """`raise X from Y` → one RAISES edge for X only."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/handler.py", """
        from fastapi import HTTPException

        def f():
            try:
                pass
            except ValueError as e:
                raise HTTPException(status_code=500) from e
    """)

    raises, _, _, _ = _run(tmp_path, ["pkg/__init__.py", "pkg/handler.py"])

    assert len(raises) == 1
    assert raises[0].to_id == "external:fastapi.HTTPException"


# ---------------------------------------------------------------------------
# Test 6: Basic CALLS — correct to_id and meta
# ---------------------------------------------------------------------------

def test_basic_calls_correct_ids(tmp_path: Path) -> None:
    """Function with two calls → two CALLS edges with correct to_id and call_text."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/service.py", """
        def process(items):
            result = sorted(items)
            return len(result)
    """)

    _, calls, _, _ = _run(tmp_path, ["pkg/__init__.py", "pkg/service.py"])

    to_ids = {e.to_id for e in calls}
    assert "sorted" in to_ids
    assert "len" in to_ids

    # Check meta carries call_text
    sorted_edge = next(e for e in calls if e.to_id == "sorted")
    assert dict(sorted_edge.meta).get("call_text") == "sorted(items)"


# ---------------------------------------------------------------------------
# Test 7: Calls deduplicated by to_id
# ---------------------------------------------------------------------------

def test_calls_deduplicated_by_to_id(tmp_path: Path) -> None:
    """Same callable called twice → one CALLS edge per unique to_id."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/service.py", """
        def process(a, b):
            x = len(a)
            y = len(b)
            return x + y
    """)

    _, calls, _, _ = _run(tmp_path, ["pkg/__init__.py", "pkg/service.py"])

    len_edges = [e for e in calls if e.to_id == "len"]
    assert len(len_edges) == 1


# ---------------------------------------------------------------------------
# Test 8: ast.walk depth — call nested in list comprehension is captured
# ---------------------------------------------------------------------------

def test_calls_captured_in_nested_expression(tmp_path: Path) -> None:
    """Call inside a list comprehension is still captured by ast.walk."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/service.py", """
        def process(items):
            return [str(x) for x in items]
    """)

    _, calls, _, _ = _run(tmp_path, ["pkg/__init__.py", "pkg/service.py"])

    to_ids = {e.to_id for e in calls}
    assert "str" in to_ids


# ---------------------------------------------------------------------------
# Test 9: Non-function nodes produce no RAISES/CALLS edges
# ---------------------------------------------------------------------------

def test_non_function_nodes_produce_no_edges(tmp_path: Path) -> None:
    """Module and class nodes must not produce RAISES or CALLS edges."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/model.py", """
        class MyModel:
            x: int = 0
    """)

    raises, calls, _, _ = _run(tmp_path, ["pkg/__init__.py", "pkg/model.py"])

    assert raises == []
    assert calls == []


# ---------------------------------------------------------------------------
# Test 10: Integration smoke — create_new_article has one RAISES edge to HTTPException
# ---------------------------------------------------------------------------

def test_real_repo_create_new_article_raises_http_exception() -> None:
    """create_new_article in the real target/ repo has exactly one RAISES edge → external:fastapi.HTTPException."""
    repo_root = Path(__file__).parent.parent
    articles_file = repo_root / "target/app/api/routes/articles/articles_resource.py"
    if not articles_file.exists():
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

    raises, calls, ext, _ = extract_body_facts(
        all_nodes, all_edges, path_to_info, dotted_to_path,
        repo_root=str(repo_root),
    )

    # create_new_article lives in target/app/api/routes/articles/articles_resource.py
    handler_id = "target/app/api/routes/articles/articles_resource.py::create_new_article"
    handler_raises = [e for e in raises if e.from_id == handler_id]

    assert len(handler_raises) == 1, (
        f"Expected 1 RAISES edge from create_new_article, got {len(handler_raises)}"
    )
    assert handler_raises[0].to_id == "external:fastapi.HTTPException", (
        f"Expected to_id=external:fastapi.HTTPException, got {handler_raises[0].to_id!r}"
    )
    args = dict(handler_raises[0].meta).get("args", "")
    assert "HTTP_400_BAD_REQUEST" in args, f"Expected status_code in args, got {args!r}"
