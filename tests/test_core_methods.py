"""Tests for class method extraction in core.py (task 2a.3b)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from docgen.extract.core import extract_file
from docgen.facts.schema import EdgeType, NodeType


def _src(tmp_path: Path, src: str) -> Path:
    """Write dedented Python source to a temp file and return its path."""
    p = tmp_path / "test_module.py"
    p.write_text(textwrap.dedent(src), encoding="utf-8")
    return p


def _extract(tmp_path: Path, src: str):
    """Write src, extract, return (nodes, edges, unresolved)."""
    p = _src(tmp_path, src)
    return extract_file(p, tmp_path)


# ---------------------------------------------------------------------------
# Test 1: Class with one method → FUNCTION node with parent_class set
# ---------------------------------------------------------------------------

def test_method_node_has_parent_class(tmp_path: Path) -> None:
    """A class with one method produces a FUNCTION node with parent_class set."""
    nodes, edges, _ = _extract(tmp_path, """
        class Greeter:
            def hello(self) -> str:
                return 'hi'
    """)

    method_node = next(
        (n for n in nodes if n.type == NodeType.FUNCTION and n.name == "hello"),
        None,
    )
    assert method_node is not None
    assert method_node.id == "test_module.py::Greeter::hello"
    assert method_node.parent_class == "test_module.py::Greeter"


# ---------------------------------------------------------------------------
# Test 2: CONTAINS edge from class to method
# ---------------------------------------------------------------------------

def test_contains_edge_class_to_method(tmp_path: Path) -> None:
    """A CONTAINS edge is emitted from the class node to each method node."""
    nodes, edges, _ = _extract(tmp_path, """
        class Greeter:
            def hello(self) -> str:
                return 'hi'
    """)

    contains = [
        e for e in edges
        if e.type == EdgeType.CONTAINS
        and e.from_id == "test_module.py::Greeter"
        and e.to_id == "test_module.py::Greeter::hello"
    ]
    assert len(contains) == 1


# ---------------------------------------------------------------------------
# Test 3: Method id has three :: components
# ---------------------------------------------------------------------------

def test_method_id_has_three_parts(tmp_path: Path) -> None:
    """Method node id is <file>::<Class>::<method>."""
    nodes, _, _ = _extract(tmp_path, """
        class MyClass:
            def my_method(self) -> None:
                pass
    """)

    method = next(
        (n for n in nodes if n.type == NodeType.FUNCTION and n.name == "my_method"),
        None,
    )
    assert method is not None
    parts = method.id.split("::")
    assert len(parts) == 3
    assert parts[1] == "MyClass"
    assert parts[2] == "my_method"


# ---------------------------------------------------------------------------
# Test 4: Editing method SIGNATURE changes class hash_struct
# ---------------------------------------------------------------------------

def test_method_signature_change_changes_class_hash_struct(tmp_path: Path) -> None:
    """Changing a method's parameter type changes the class node's hash_struct."""
    nodes_a, _, _ = _extract(tmp_path, """
        class Calc:
            def add(self, x: int) -> int:
                return x
    """)
    nodes_b, _, _ = _extract(tmp_path, """
        class Calc:
            def add(self, x: float) -> float:
                return x
    """)

    cls_a = next(n for n in nodes_a if n.type == NodeType.CLASS and n.name == "Calc")
    cls_b = next(n for n in nodes_b if n.type == NodeType.CLASS and n.name == "Calc")
    assert cls_a.hash_struct != cls_b.hash_struct


# ---------------------------------------------------------------------------
# Test 5: Editing method BODY COMMENT does not change class hash_struct
# ---------------------------------------------------------------------------

def test_method_body_comment_does_not_change_class_hash_struct(tmp_path: Path) -> None:
    """Changing only a comment inside a method leaves class hash_struct unchanged."""
    nodes_a, _, _ = _extract(tmp_path, """
        class Calc:
            def add(self, x: int) -> int:
                # version 1
                return x
    """)
    nodes_b, _, _ = _extract(tmp_path, """
        class Calc:
            def add(self, x: int) -> int:
                # version 2
                return x
    """)

    cls_a = next(n for n in nodes_a if n.type == NodeType.CLASS and n.name == "Calc")
    cls_b = next(n for n in nodes_b if n.type == NodeType.CLASS and n.name == "Calc")
    assert cls_a.hash_struct == cls_b.hash_struct


# ---------------------------------------------------------------------------
# Test 6: Editing class-level FIELD changes class hash_struct
# ---------------------------------------------------------------------------

def test_class_field_change_changes_class_hash_struct(tmp_path: Path) -> None:
    """Changing a class-level annotated field changes the class hash_struct.

    Fields are part of the structural identity (hash_struct), not hash_source.
    hash_source covers only the header text (decorators + class def + docstring).
    """
    nodes_a, _, _ = _extract(tmp_path, """
        class Model:
            x: int
            def process(self) -> None:
                pass
    """)
    nodes_b, _, _ = _extract(tmp_path, """
        class Model:
            x: str
            def process(self) -> None:
                pass
    """)

    cls_a = next(n for n in nodes_a if n.type == NodeType.CLASS and n.name == "Model")
    cls_b = next(n for n in nodes_b if n.type == NodeType.CLASS and n.name == "Model")
    assert cls_a.hash_struct != cls_b.hash_struct


# ---------------------------------------------------------------------------
# Test 6b: Editing class DOCSTRING changes class hash_source
# ---------------------------------------------------------------------------

def test_class_docstring_change_changes_class_hash_source(tmp_path: Path) -> None:
    """Changing the class docstring changes hash_source (docstring is part of the header)."""
    nodes_a, _, _ = _extract(tmp_path, """
        class Model:
            '''Version one.'''
            x: int

            def process(self) -> int:
                return self.x
    """)
    nodes_b, _, _ = _extract(tmp_path, """
        class Model:
            '''Version two.'''
            x: int

            def process(self) -> int:
                return self.x
    """)

    cls_a = next(n for n in nodes_a if n.type == NodeType.CLASS and n.name == "Model")
    cls_b = next(n for n in nodes_b if n.type == NodeType.CLASS and n.name == "Model")
    assert cls_a.hash_source != cls_b.hash_source



# ---------------------------------------------------------------------------
# Test 7: Editing method BODY does not change class hash_source
# ---------------------------------------------------------------------------

def test_method_body_change_does_not_change_class_hash_source(tmp_path: Path) -> None:
    """Changing only a method body leaves class hash_source unchanged."""
    nodes_a, _, _ = _extract(tmp_path, """
        class Model:
            x: int

            def process(self) -> int:
                return self.x + 1
    """)
    nodes_b, _, _ = _extract(tmp_path, """
        class Model:
            x: int

            def process(self) -> int:
                return self.x * 2
    """)

    cls_a = next(n for n in nodes_a if n.type == NodeType.CLASS and n.name == "Model")
    cls_b = next(n for n in nodes_b if n.type == NodeType.CLASS and n.name == "Model")
    assert cls_a.hash_source == cls_b.hash_source


# ---------------------------------------------------------------------------
# Test 8: Method with Depends() → DEPENDS_ON edge from method node
# ---------------------------------------------------------------------------

def test_method_depends_on_edge(tmp_path: Path) -> None:
    """A method with Depends(...) in a parameter emits a DEPENDS_ON edge."""
    nodes, edges, _ = _extract(tmp_path, """
        class MyRouter:
            async def get_item(
                self,
                db = Depends(get_db),
            ):
                pass
    """)

    method = next(
        (n for n in nodes if n.type == NodeType.FUNCTION and n.name == "get_item"),
        None,
    )
    assert method is not None

    dep_edges = [
        e for e in edges
        if e.type == EdgeType.DEPENDS_ON and e.from_id == method.id
    ]
    assert len(dep_edges) == 1
    assert dep_edges[0].to_id == "external:get_db"
