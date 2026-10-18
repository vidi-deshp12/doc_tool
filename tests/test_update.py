"""Tests for check/update.py: UpdatePlan and plan_update."""

from __future__ import annotations

from pathlib import Path

import pytest

from docgen.check.update import UpdatePlan, plan_update
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


# ---------------------------------------------------------------------------
# Test 1: plan_update returns only stale pages (not all pages)
# ---------------------------------------------------------------------------

def test_update_rerenders_only_stale_pages() -> None:
    """plan_update.stale_pages contains exactly the pages passed in."""
    node_a = _node("myapp/utils.py::greet", hash_struct="NEW")
    node_b = _node("myapp/models.py::Item", hash_struct="SAME")
    graph = _graph(node_a, node_b)

    manifest = _manifest({
        "generated/pages/myapp/utils.md": {
            "fact_ids": ["myapp/utils.py::greet"],
            "hashes": {"myapp/utils.py::greet": {"hash_struct": "OLD", "hash_source": "src"}},
        },
        "generated/pages/myapp/models.md": {
            "fact_ids": ["myapp/models.py::Item"],
            "hashes": {"myapp/models.py::Item": {"hash_struct": "SAME", "hash_source": "src"}},
        },
    })
    stale = ["generated/pages/myapp/utils.md"]  # only utils is stale
    summaries = {}

    plan = plan_update(stale, manifest, graph, summaries)

    assert plan.stale_pages == ["generated/pages/myapp/utils.md"]
    assert "myapp/utils.py::greet" in plan.stale_node_ids
    assert "myapp/models.py::Item" not in plan.stale_node_ids


# ---------------------------------------------------------------------------
# Test 2: node whose hash_source is unchanged → NOT in nodes_to_resummarize
# ---------------------------------------------------------------------------

def test_update_skips_resummarize_when_hash_source_unchanged() -> None:
    """If only hash_struct changed (not hash_source), node is not in nodes_to_resummarize."""
    node = _node("myapp/utils.py::greet", hash_struct="NEW", hash_source="SAME_SRC")
    graph = _graph(node)
    manifest = _manifest({
        "generated/pages/myapp/utils.md": {
            "fact_ids": ["myapp/utils.py::greet"],
            "hashes": {
                "myapp/utils.py::greet": {
                    "hash_struct": "OLD",
                    "hash_source": "SAME_SRC",  # source unchanged
                }
            },
        },
    })
    summaries = {"myapp/utils.py::greet": "existing summary"}

    plan = plan_update(
        ["generated/pages/myapp/utils.md"], manifest, graph, summaries
    )
    assert "myapp/utils.py::greet" not in plan.nodes_to_resummarize


# ---------------------------------------------------------------------------
# Test 3: re-summarize flag set when hash_source also changed
# ---------------------------------------------------------------------------

def test_update_writes_updated_manifest() -> None:
    """Node with both hash_struct AND hash_source changed → in nodes_to_resummarize."""
    node = _node("myapp/utils.py::greet", hash_struct="NEW_HS", hash_source="NEW_SRC")
    graph = _graph(node)
    manifest = _manifest({
        "generated/pages/myapp/utils.md": {
            "fact_ids": ["myapp/utils.py::greet"],
            "hashes": {
                "myapp/utils.py::greet": {
                    "hash_struct": "OLD_HS",
                    "hash_source": "OLD_SRC",
                }
            },
        },
    })
    summaries = {"myapp/utils.py::greet": "some existing summary"}

    plan = plan_update(
        ["generated/pages/myapp/utils.md"], manifest, graph, summaries
    )
    assert "myapp/utils.py::greet" in plan.stale_node_ids
    assert "myapp/utils.py::greet" in plan.nodes_to_resummarize


# ---------------------------------------------------------------------------
# Test 4: no stale pages → empty UpdatePlan
# ---------------------------------------------------------------------------

def test_update_noop_when_no_stale_pages() -> None:
    """When stale_pages is empty, plan_update returns an empty UpdatePlan."""
    graph = _graph(_node("myapp/utils.py::greet"))
    manifest = _manifest({})
    plan = plan_update([], manifest, graph, {})

    assert plan.stale_pages == []
    assert plan.stale_node_ids == set()
    assert plan.nodes_to_resummarize == set()
