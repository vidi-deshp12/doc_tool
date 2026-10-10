"""Tests for extract/classes.py — class resolution, field flattening, Pydantic tagging."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from docgen.extract.classes import resolve_all_classes, resolve_classes
from docgen.extract.core import extract_file
from docgen.extract.modules import build_full_index, build_module_index
from docgen.facts.schema import EdgeType, NodeType


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _write(tmp_path: Path, rel: str, src: str) -> Path:
    """Write a Python source file into tmp_path, creating parent dirs."""
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(src), encoding="utf-8")
    return p


def _extract_all(tmp_path: Path, files: list[str]) -> tuple[list, list]:
    """Run extract_file on each file in files (root-relative POSIX paths).

    Returns (all_nodes, all_edges) merged from every file.
    """
    all_nodes: list = []
    all_edges: list = []
    for rel in files:
        p = tmp_path / rel
        nodes, edges, _ = extract_file(p, tmp_path)
        all_nodes.extend(nodes)
        all_edges.extend(edges)
    return all_nodes, all_edges


# ---------------------------------------------------------------------------
# Test 1: Single-level in-repo inheritance resolves to in-repo node ID
# ---------------------------------------------------------------------------

def test_single_level_in_repo_inherits(tmp_path: Path) -> None:
    """Class B(A) where A is in another file → INHERITS edge points to that file's node."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/base.py", """
        class Base:
            x: int
    """)
    _write(tmp_path, "pkg/child.py", """
        from pkg.base import Base

        class Child(Base):
            y: str
    """)

    files = ["pkg/__init__.py", "pkg/base.py", "pkg/child.py"]
    all_nodes, all_edges = _extract_all(tmp_path, files)
    dotted_to_path, path_to_info = build_module_index(files, tmp_path, source_root="")

    updated_nodes, new_edges, _ext, _unres = resolve_all_classes(
        all_nodes, all_edges, path_to_info, dotted_to_path
    )

    inherits = [e for e in new_edges if e.type == EdgeType.INHERITS]
    assert len(inherits) == 1
    assert inherits[0].from_id == "pkg/child.py::Child"
    assert inherits[0].to_id == "pkg/base.py::Base"


# ---------------------------------------------------------------------------
# Test 2: Transitive (2-level) chain — fields flattened
# ---------------------------------------------------------------------------

def test_transitive_field_flattening(tmp_path: Path) -> None:
    """C(B), B(A) — C.fields contains own fields + A's fields (B has none)."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/a.py", """
        class A:
            inherited_field: int
    """)
    _write(tmp_path, "pkg/b.py", """
        from pkg.a import A

        class B(A):
            pass
    """)
    _write(tmp_path, "pkg/c.py", """
        from pkg.b import B

        class C(B):
            own_field: str
    """)

    files = ["pkg/__init__.py", "pkg/a.py", "pkg/b.py", "pkg/c.py"]
    all_nodes, all_edges = _extract_all(tmp_path, files)
    dotted_to_path, path_to_info = build_module_index(files, tmp_path, source_root="")

    updated_nodes, new_edges, _ext, _unres = resolve_all_classes(
        all_nodes, all_edges, path_to_info, dotted_to_path
    )

    node_map = {n.id: n for n in updated_nodes}
    c_node = node_map["pkg/c.py::C"]
    field_names = {f[0] for f in c_node.fields}
    assert "own_field" in field_names
    assert "inherited_field" in field_names


# ---------------------------------------------------------------------------
# Test 3: External base → external:pydantic.BaseModel edge + external Node
# ---------------------------------------------------------------------------

def test_external_base_emits_external_node(tmp_path: Path) -> None:
    """class Foo(BaseModel) → INHERITS to external:pydantic.BaseModel; external Node created."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/model.py", """
        from pydantic import BaseModel

        class Foo(BaseModel):
            name: str
    """)

    files = ["pkg/__init__.py", "pkg/model.py"]
    all_nodes, all_edges = _extract_all(tmp_path, files)
    dotted_to_path, path_to_info = build_module_index(files, tmp_path, source_root="")

    updated_nodes, new_edges, new_ext, _unres = resolve_all_classes(
        all_nodes, all_edges, path_to_info, dotted_to_path
    )

    inherits = [e for e in new_edges if e.type == EdgeType.INHERITS]
    assert any(e.to_id == "external:pydantic.BaseModel" for e in inherits)
    ext_ids = {n.id for n in new_ext}
    assert "external:pydantic.BaseModel" in ext_ids


# ---------------------------------------------------------------------------
# Test 4: is_pydantic_model propagates transitively
# ---------------------------------------------------------------------------

def test_is_pydantic_propagates(tmp_path: Path) -> None:
    """Foo(BaseModel) → is_pydantic_model=True; Bar(Foo) → also True."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/base.py", """
        from pydantic import BaseModel

        class Foo(BaseModel):
            x: int
    """)
    _write(tmp_path, "pkg/child.py", """
        from pkg.base import Foo

        class Bar(Foo):
            y: str
    """)

    files = ["pkg/__init__.py", "pkg/base.py", "pkg/child.py"]
    all_nodes, all_edges = _extract_all(tmp_path, files)
    dotted_to_path, path_to_info = build_module_index(files, tmp_path, source_root="")

    updated_nodes, _edges, _ext, _unres = resolve_all_classes(
        all_nodes, all_edges, path_to_info, dotted_to_path
    )

    node_map = {n.id: n for n in updated_nodes}
    assert node_map["pkg/base.py::Foo"].is_pydantic_model is True
    assert node_map["pkg/child.py::Bar"].is_pydantic_model is True


# ---------------------------------------------------------------------------
# Test 5: Cycle guard — A(B), B(A) does not hang
# ---------------------------------------------------------------------------

def test_cycle_guard(tmp_path: Path) -> None:
    """Mutual inheritance A(B), B(A) must not cause infinite recursion."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/a.py", """
        from pkg.b import B

        class A(B):
            a_field: int
    """)
    _write(tmp_path, "pkg/b.py", """
        from pkg.a import A

        class B(A):
            b_field: str
    """)

    files = ["pkg/__init__.py", "pkg/a.py", "pkg/b.py"]
    all_nodes, all_edges = _extract_all(tmp_path, files)
    dotted_to_path, path_to_info = build_module_index(files, tmp_path, source_root="")

    # Must complete without RecursionError
    updated_nodes, new_edges, _ext, _unres = resolve_all_classes(
        all_nodes, all_edges, path_to_info, dotted_to_path
    )
    assert updated_nodes is not None  # just confirm it finished


# ---------------------------------------------------------------------------
# Test 6: Unresolvable base → Unresolved entry emitted, no crash
# ---------------------------------------------------------------------------

def test_unresolvable_base_emits_unresolved(tmp_path: Path) -> None:
    """class Foo(MysteryBase) where MysteryBase is not imported → Unresolved entry."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/model.py", """
        class Foo(MysteryBase):
            x: int
    """)

    files = ["pkg/__init__.py", "pkg/model.py"]
    all_nodes, all_edges = _extract_all(tmp_path, files)
    dotted_to_path, path_to_info = build_module_index(files, tmp_path, source_root="")

    _updated, _edges, _ext, unresolved = resolve_all_classes(
        all_nodes, all_edges, path_to_info, dotted_to_path
    )

    assert any("MysteryBase" in u.what for u in unresolved)


# ---------------------------------------------------------------------------
# Test 7: Multiple inheritance — fields from both parents, child wins on clash
# ---------------------------------------------------------------------------

def test_multiple_inheritance_field_merge(tmp_path: Path) -> None:
    """class C(A, B): fields from A and B merged; C's own field overrides on clash."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/a.py", """
        class A:
            shared: int
            a_only: str
    """)
    _write(tmp_path, "pkg/b.py", """
        class B:
            shared: float   # same name as A.shared — child/first-parent wins
            b_only: bytes
    """)
    _write(tmp_path, "pkg/c.py", """
        from pkg.a import A
        from pkg.b import B

        class C(A, B):
            own: bool
    """)

    files = ["pkg/__init__.py", "pkg/a.py", "pkg/b.py", "pkg/c.py"]
    all_nodes, all_edges = _extract_all(tmp_path, files)
    dotted_to_path, path_to_info = build_module_index(files, tmp_path, source_root="")

    updated_nodes, _edges, _ext, _unres = resolve_all_classes(
        all_nodes, all_edges, path_to_info, dotted_to_path
    )

    node_map = {n.id: n for n in updated_nodes}
    c_node = node_map["pkg/c.py::C"]
    field_names = [f[0] for f in c_node.fields]
    assert "own" in field_names
    assert "a_only" in field_names
    assert "b_only" in field_names
    # "shared" appears exactly once (not duplicated from B)
    assert field_names.count("shared") == 1


# ---------------------------------------------------------------------------
# Test 8: Integration smoke test against real target/ repo
# ---------------------------------------------------------------------------

def test_real_repo_list_of_articles_is_pydantic(tmp_path: Path) -> None:
    """ListOfArticlesInResponse in the real target/ repo must have is_pydantic_model=True."""
    repo_root = Path(__file__).parent.parent / "target"
    if not repo_root.exists():
        pytest.skip("target/ repo not present")

    from docgen.config import load_config
    from docgen.walker import walk_repo

    config = load_config(Path(__file__).parent.parent / "docgen.toml")
    module_paths = list(walk_repo(config, repo_root=Path(__file__).parent.parent))

    all_nodes: list = []
    all_edges: list = []
    for rel in module_paths:
        p = Path(__file__).parent.parent / rel
        if p.exists():
            nodes, edges, _ = extract_file(p, Path(__file__).parent.parent)
            all_nodes.extend(nodes)
            all_edges.extend(edges)

    dotted_to_path, path_to_info = build_module_index(
        module_paths,
        Path(__file__).parent.parent,
        source_root=config.source_root,
    )

    updated_nodes, _edges, _ext, _unres = resolve_all_classes(
        all_nodes, all_edges, path_to_info, dotted_to_path
    )

    node_map = {n.id: n for n in updated_nodes}
    target = next(
        (n for n in updated_nodes
         if n.type == NodeType.CLASS and n.name == "ListOfArticlesInResponse"),
        None,
    )
    assert target is not None, "ListOfArticlesInResponse class node not found"
    assert target.is_pydantic_model is True, (
        f"Expected is_pydantic_model=True on ListOfArticlesInResponse, got False"
    )
