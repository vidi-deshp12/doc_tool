"""Adapter protocol: every framework adapter implements this interface.

An adapter enriches the fact graph with framework-specific facts (routes,
dependency trees, request/response models) that cannot be extracted by the
generic core extractor alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...facts.schema import Edge, Node, Unresolved


@dataclass
class AdapterResult:
    """Facts produced by a framework adapter.

    Callers merge these into the main fact graph:
        all_nodes.extend(result.nodes)
        all_edges.extend(result.edges)
        all_unresolved.extend(result.unresolved)
    """
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    unresolved: list[Unresolved] = field(default_factory=list)
