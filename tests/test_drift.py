"""Tests for check/drift.py: find_stale_pages and warn_if_facts_stale."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from docgen.check.drift import find_stale_pages, warn_if_facts_stale
from docgen.facts.schema import Edge, EdgeType, FactGraph, Node, NodeType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node(node_id: str, hash_struct: str = "hs", hash_source: str = "src") -> Node:
    return Node(
        id=node_id,
        type=NodeType.FUNCTION,
        file="myapp/utils.py",
        lines=(1, 5),
        hash_struct=hash_struct,
        hash_source=hash_source,
        name=node_id.rsplit("::", 1)[-1],
    )


def _graph(*nodes: Node) -> FactGraph:
    return FactGraph(nodes=nodes, edges=(), unresolved=())


def _manifest(pages: dict) -> dict:
    return {"pages": pages}


def _page(fact_ids: list[str], hashes: dict) -> dict:
    return {"fact_ids": fact_ids, "hashes": hashes}


# ---------------------------------------------------------------------------
# Test 1: clean manifest returns empty list
# ---------------------------------------------------------------------------

def test_check_clean_returns_empty() -> None:
    """When all hash_struct values match, find_stale_pages returns []."""
    node = _node("myapp/utils.py::greet", hash_struct="abc")
    graph = _graph(node)
    manifest = _manifest({
        "generated/pages/myapp/utils.md": _page(
            fact_ids=["myapp/utils.py::greet"],
            hashes={"myapp/utils.py::greet": {"hash_struct": "abc", "hash_source": "xyz"}},
        )
    })
    assert find_stale_pages(manifest, graph) == []


# ---------------------------------------------------------------------------
# Test 2: changed hash_struct makes the page stale
# ---------------------------------------------------------------------------

def test_check_detects_hash_struct_change() -> None:
    """A node whose hash_struct changed causes its page to appear in the stale list."""
    node = _node("myapp/utils.py::greet", hash_struct="NEW")
    graph = _graph(node)
    manifest = _manifest({
        "generated/pages/myapp/utils.md": _page(
            fact_ids=["myapp/utils.py::greet"],
            hashes={"myapp/utils.py::greet": {"hash_struct": "OLD", "hash_source": "xyz"}},
        )
    })
    stale = find_stale_pages(manifest, graph)
    assert stale == ["generated/pages/myapp/utils.md"]


# ---------------------------------------------------------------------------
# Test 3: hash_source-only change does NOT make the page stale
# ---------------------------------------------------------------------------

def test_check_ignores_hash_source_only_change() -> None:
    """When only hash_source changes (hash_struct identical), page is not stale."""
    node = _node("myapp/utils.py::greet", hash_struct="SAME", hash_source="CHANGED")
    graph = _graph(node)
    manifest = _manifest({
        "generated/pages/myapp/utils.md": _page(
            fact_ids=["myapp/utils.py::greet"],
            hashes={"myapp/utils.py::greet": {"hash_struct": "SAME", "hash_source": "ORIGINAL"}},
        )
    })
    assert find_stale_pages(manifest, graph) == []


# ---------------------------------------------------------------------------
# Test 4: deleted node makes the page stale
# ---------------------------------------------------------------------------

def test_check_detects_deleted_node() -> None:
    """A node ID that exists in the manifest but not in the graph marks its page stale."""
    # Graph has no nodes at all — node was deleted
    graph = _graph()
    manifest = _manifest({
        "generated/pages/myapp/utils.md": _page(
            fact_ids=["myapp/utils.py::greet"],
            hashes={"myapp/utils.py::greet": {"hash_struct": "abc", "hash_source": "xyz"}},
        )
    })
    stale = find_stale_pages(manifest, graph)
    assert stale == ["generated/pages/myapp/utils.md"]


# ---------------------------------------------------------------------------
# Test 5: new node (not in any page's hashes) does not trigger staleness
# ---------------------------------------------------------------------------

def test_check_new_node_not_stale() -> None:
    """A brand-new node that no manifest page depends on does not cause any page to go stale."""
    existing_node = _node("myapp/utils.py::greet", hash_struct="abc")
    new_node = _node("myapp/utils.py::new_func", hash_struct="xyz")
    graph = _graph(existing_node, new_node)
    manifest = _manifest({
        "generated/pages/myapp/utils.md": _page(
            fact_ids=["myapp/utils.py::greet"],
            hashes={"myapp/utils.py::greet": {"hash_struct": "abc", "hash_source": "src"}},
        )
    })
    assert find_stale_pages(manifest, graph) == []


# ---------------------------------------------------------------------------
# Test 6: warn_if_facts_stale emits to stderr when facts predate manifest
# ---------------------------------------------------------------------------

def test_warn_if_facts_stale(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """warn_if_facts_stale prints a warning when facts.json is older than manifest.json."""
    facts_path = tmp_path / "facts.json"
    manifest_path = tmp_path / "manifest.json"

    facts_path.write_text("{}", encoding="utf-8")
    # Sleep briefly so the mtime is different, then write manifest
    time.sleep(0.05)
    manifest_path.write_text("{}", encoding="utf-8")

    warn_if_facts_stale(facts_path, manifest_path)
    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert "facts.json predates manifest.json" in captured.err
