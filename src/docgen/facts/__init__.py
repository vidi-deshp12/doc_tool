"""facts sub-package: schema dataclasses and stable JSON store."""

from .schema import Edge, EdgeType, FactGraph, Node, NodeType, Unresolved
from .store import read_facts, write_facts

__all__ = [
    "Node",
    "NodeType",
    "Edge",
    "EdgeType",
    "Unresolved",
    "FactGraph",
    "read_facts",
    "write_facts",
]