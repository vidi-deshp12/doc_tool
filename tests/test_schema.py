"""Round-trip tests for FactGraph schema and store."""

from __future__ import annotations

import tempfile
from pathlib import Path

from src.docgen.facts.schema import Edge, EdgeType, FactGraph, Node, NodeType, Unresolved
from src.docgen.facts.store import read_facts, write_facts


def make_test_graph() -> FactGraph:
    """Create a small but representative FactGraph for testing."""
    nodes = (
        Node(
            id="app/api/routes",
            type=NodeType.PACKAGE,
            file="app/api/routes/__init__.py",
            lines=(1, 1),
            hash_struct="struct_hash_pkg",
            hash_source="source_hash_pkg",
            dotted_name="app.api.routes",
        ),
        Node(
            id="app/api/routes/articles.py",
            type=NodeType.MODULE,
            file="app/api/routes/articles.py",
            lines=(1, 50),
            hash_struct="struct_hash_mod",
            hash_source="source_hash_mod",
            dotted_name="app.api.routes.articles",
            docstring="Article routes module.",
        ),
        Node(
            id="app/api/routes/articles.py::ArticleIn",
            type=NodeType.CLASS,
            file="app/api/routes/articles.py",
            lines=(5, 15),
            hash_struct="struct_hash_class",
            hash_source="source_hash_class",
            bases=("pydantic.BaseModel",),
            fields=(("title", "str", ""), ("description", "str", "''")),
            is_pydantic_model=True,
            decorators=("@dataclass",),
        ),
        Node(
            id="app/api/routes/articles.py::create_article",
            type=NodeType.FUNCTION,
            file="app/api/routes/articles.py",
            lines=(20, 35),
            hash_struct="struct_hash_func",
            hash_source="source_hash_func",
            signature="(article: ArticleIn, current_user: User = Depends(get_current_user))",
            returns="ArticleOut",
            decorators=('@router.post("", status_code=201)',),
            async_flag=True,
            parent_class="",
        ),
        Node(
            id="external:fastapi",
            type=NodeType.EXTERNAL,
            file="",
            lines=(0, 0),
            hash_struct="",
            hash_source="",
            library_name="fastapi",
        ),
        Node(
            id="unresolved:get_current_user",
            type=NodeType.UNRESOLVED,
            file="app/api/routes/articles.py",
            lines=(20, 20),
            hash_struct="",
            hash_source="",
            what="get_current_user",
            why="dynamic import",
            where="app/api/routes/articles.py:20",
        ),
        Node(
            id='route:POST /api/articles',
            type=NodeType.ROUTE,
            file="app/api/routes/articles.py",
            lines=(20, 35),
            hash_struct="struct_hash_route",
            hash_source="source_hash_route",
            method="POST",
            full_path="/api/articles",
            name="create_article",
            status_code=201,
        ),
    )

    edges = (
        Edge(
            type=EdgeType.CONTAINS,
            from_id="app/api/routes",
            to_id="app/api/routes/articles.py",
        ),
        Edge(
            type=EdgeType.CONTAINS,
            from_id="app/api/routes/articles.py",
            to_id="app/api/routes/articles.py::ArticleIn",
        ),
        Edge(
            type=EdgeType.CONTAINS,
            from_id="app/api/routes/articles.py",
            to_id="app/api/routes/articles.py::create_article",
        ),
        Edge(
            type=EdgeType.IMPORTS,
            from_id="app/api/routes/articles.py",
            to_id="external:fastapi",
        ),
        Edge(
            type=EdgeType.INHERITS,
            from_id="app/api/routes/articles.py::ArticleIn",
            to_id="external:fastapi",
            meta=(("base", "BaseModel"),),
        ),
        Edge(
            type=EdgeType.CALLS,
            from_id="app/api/routes/articles.py::create_article",
            to_id="unresolved:get_current_user",
            meta=(("call_text", "Depends(get_current_user)"),),
        ),
        Edge(
            type=EdgeType.HANDLES,
            from_id="route:POST /api/articles",
            to_id="app/api/routes/articles.py::create_article",
        ),
    )

    unresolved = (
        Unresolved(
            what="get_current_user",
            why="dynamic import",
            where="app/api/routes/articles.py:20",
        ),
    )

    return FactGraph(nodes=nodes, edges=edges, unresolved=unresolved)


def test_round_trip() -> None:
    """Test that writing and reading a FactGraph produces an equal graph."""
    original = make_test_graph()

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "facts.json"
        write_facts(original, path)
        read_back = read_facts(path)

    assert read_back == original, "Round-trip failed: graphs are not equal"


def test_byte_identical_on_repeat() -> None:
    """Test that writing the same graph twice produces byte-identical files."""
    graph = make_test_graph()

    with tempfile.TemporaryDirectory() as tmpdir:
        path1 = Path(tmpdir) / "facts1.json"
        path2 = Path(tmpdir) / "facts2.json"

        write_facts(graph, path1)
        write_facts(graph, path2)

        content1 = path1.read_bytes()
        content2 = path2.read_bytes()

        assert content1 == content2, "Files are not byte-identical on repeat write"


def test_node_equality_and_ordering() -> None:
    """Test that Node equality and ordering work as expected."""
    n1 = Node(
        id="a",
        type=NodeType.MODULE,
        file="a.py",
        lines=(1, 10),
        hash_struct="h1",
        hash_source="s1",
    )
    n2 = Node(
        id="a",
        type=NodeType.MODULE,
        file="a.py",
        lines=(1, 10),
        hash_struct="h1",
        hash_source="s1",
    )
    n3 = Node(
        id="b",
        type=NodeType.MODULE,
        file="b.py",
        lines=(1, 10),
        hash_struct="h1",
        hash_source="s1",
    )

    assert n1 == n2
    assert n1 < n3  # ordering by id


def test_edge_equality_and_ordering() -> None:
    """Test that Edge equality and ordering work as expected."""
    e1 = Edge(
        type=EdgeType.IMPORTS,
        from_id="a",
        to_id="b",
        meta=(("key", "val"),),
    )
    e2 = Edge(
        type=EdgeType.IMPORTS,
        from_id="a",
        to_id="b",
        meta=(("key", "val"),),
    )
    e3 = Edge(
        type=EdgeType.IMPORTS,
        from_id="a",
        to_id="c",
    )

    assert e1 == e2
    assert e1 < e3  # ordering by from_id, then to_id


def test_unresolved_equality_and_ordering() -> None:
    """Test that Unresolved equality and ordering work as expected."""
    u1 = Unresolved(what="foo", why="bar", where="baz.py:1")
    u2 = Unresolved(what="foo", why="bar", where="baz.py:1")
    u3 = Unresolved(what="foo", why="bar", where="baz.py:2")

    assert u1 == u2
    assert u1 < u3


def test_fact_graph_sorting() -> None:
    """Test that FactGraph sorts nodes, edges, and unresolved on creation."""
    nodes = (
        Node(id="b", type=NodeType.MODULE, file="b.py", lines=(1, 1), hash_struct="", hash_source=""),
        Node(id="a", type=NodeType.MODULE, file="a.py", lines=(1, 1), hash_struct="", hash_source=""),
    )
    edges = (
        Edge(type=EdgeType.IMPORTS, from_id="b", to_id="a"),
        Edge(type=EdgeType.IMPORTS, from_id="a", to_id="b"),
    )
    unresolved = (
        Unresolved(what="z", why="", where=""),
        Unresolved(what="a", why="", where=""),
    )

    graph = FactGraph(nodes=nodes, edges=edges, unresolved=unresolved)

    assert [n.id for n in graph.nodes] == ["a", "b"]
    assert [(e.from_id, e.to_id) for e in graph.edges] == [("a", "b"), ("b", "a")]
    assert [u.what for u in graph.unresolved] == ["a", "z"]