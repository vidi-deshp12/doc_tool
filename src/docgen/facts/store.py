"""Stable JSON read/write for FactGraph (sorted keys, no timestamps, no absolute paths)."""

from __future__ import annotations
from typing import Any

import json
from pathlib import Path

from .schema import Edge, EdgeType, FactGraph, Node, NodeType, Unresolved


def _node_to_dict(node: Node) -> dict[str, Any]:
    """Convert a Node to a dictionary for JSON serialization."""
    d: dict[str, Any] = {
        "id": node.id,
        "type": node.type.value,
        "file": node.file,
        "lines": list(node.lines),
        "hash_struct": node.hash_struct,
        "hash_source": node.hash_source,
    }

    # Add type-specific fields only if non-empty/non-default
    if node.dotted_name:
        d["dotted_name"] = node.dotted_name
    if node.docstring:
        d["docstring"] = node.docstring
    if node.bases:
        d["bases"] = list(node.bases)
    if node.fields:
        d["fields"] = [list(f) for f in node.fields]
    if node.is_pydantic_model:
        d["is_pydantic_model"] = node.is_pydantic_model
    if node.decorators:
        d["decorators"] = list(node.decorators)
    if node.signature:
        d["signature"] = node.signature
    if node.returns:
        d["returns"] = node.returns
    if node.async_flag:
        d["async_flag"] = node.async_flag
    if node.parent_class:
        d["parent_class"] = node.parent_class
    if node.library_name:
        d["library_name"] = node.library_name
    if node.what:
        d["what"] = node.what
    if node.why:
        d["why"] = node.why
    if node.where:
        d["where"] = node.where
    if node.method:
        d["method"] = node.method
    if node.full_path:
        d["full_path"] = node.full_path
    if node.name:
        d["name"] = node.name
    if node.status_code:
        d["status_code"] = node.status_code
    if node.variable:
        d["variable"] = node.variable
    if node.prefix:
        d["prefix"] = node.prefix
    if node.sql_name:
        d["sql_name"] = node.sql_name
    if node.sql_file:
        d["sql_file"] = node.sql_file

    return d


def _dict_to_node(d: dict[str, Any]) -> Node:
    """Convert a dictionary to a Node."""
    # Required fields
    node_id = d["id"]
    node_type = NodeType(d["type"])
    file = d["file"]
    lines = tuple(d["lines"])
    hash_struct = d["hash_struct"]
    hash_source = d["hash_source"]

    # Optional fields with defaults
    return Node(
        id=node_id,
        type=node_type,
        file=file,
        lines=lines,
        hash_struct=hash_struct,
        hash_source=hash_source,
        dotted_name=d.get("dotted_name", ""),
        docstring=d.get("docstring", ""),
        bases=tuple(d.get("bases", [])),
        fields=tuple(tuple(f) for f in d.get("fields", [])),
        is_pydantic_model=d.get("is_pydantic_model", False),
        decorators=tuple(d.get("decorators", [])),
        signature=d.get("signature", ""),
        returns=d.get("returns", ""),
        async_flag=d.get("async_flag", False),
        parent_class=d.get("parent_class", ""),
        library_name=d.get("library_name", ""),
        what=d.get("what", ""),
        why=d.get("why", ""),
        where=d.get("where", ""),
        method=d.get("method", ""),
        full_path=d.get("full_path", ""),
        name=d.get("name", ""),
        status_code=d.get("status_code", 0),
        variable=d.get("variable", ""),
        prefix=d.get("prefix", ""),
        sql_name=d.get("sql_name", ""),
        sql_file=d.get("sql_file", ""),
    )


def _edge_to_dict(edge: Edge) -> dict[str, Any]:
    """Convert an Edge to a dictionary for JSON serialization."""
    d: dict[str, Any] = {
        "type": edge.type.value,
        "from": edge.from_id,
        "to": edge.to_id,
    }
    if edge.meta:
        d["meta"] = dict(edge.meta)
    return d


def _dict_to_edge(d: dict[str, Any]) -> Edge:
    """Convert a dictionary to an Edge."""
    return Edge(
        type=EdgeType(d["type"]),
        from_id=d["from"],
        to_id=d["to"],
        meta=tuple(sorted(d.get("meta", {}).items())),
    )


def _unresolved_to_dict(u: Unresolved) -> dict[str, str]:
    """Convert an Unresolved to a dictionary for JSON serialization."""
    return {"what": u.what, "why": u.why, "where": u.where}


def _dict_to_unresolved(d: dict[str, str]) -> Unresolved:
    """Convert a dictionary to an Unresolved."""
    return Unresolved(what=d["what"], why=d["why"], where=d["where"])


def write_facts(graph: FactGraph, path: str | Path) -> None:
    """Write a FactGraph to a JSON file with stable, deterministic output.

    Args:
        graph: The FactGraph to write.
        path: Output file path.
    """
    data = {
        "nodes": [_node_to_dict(n) for n in graph.nodes],
        "edges": [_edge_to_dict(e) for e in graph.edges],
        "unresolved": [_unresolved_to_dict(u) for u in graph.unresolved],
    }

    # Write with sorted keys, indent=2, UTF-8, no trailing whitespace
    Path(path).write_text(
        json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_facts(path: str | Path) -> FactGraph:
    """Read a FactGraph from a JSON file.

    Args:
        path: Input file path.

    Returns:
        The deserialized FactGraph.
    """
    text = Path(path).read_text(encoding="utf-8")
    data = json.loads(text)

    nodes = tuple(_dict_to_node(n) for n in data.get("nodes", []))
    edges = tuple(_dict_to_edge(e) for e in data.get("edges", []))
    unresolved = tuple(_dict_to_unresolved(u) for u in data.get("unresolved", []))

    return FactGraph(nodes=nodes, edges=edges, unresolved=unresolved)