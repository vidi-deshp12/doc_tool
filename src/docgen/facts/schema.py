"""Dataclasses for the fact graph: Node, Edge, Unresolved, FactGraph."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeType(str, Enum):
    """Types of nodes in the fact graph."""

    PACKAGE = "package"
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    EXTERNAL = "external"
    UNRESOLVED = "unresolved"
    ROUTE = "route"
    ROUTER = "router"
    SQL_QUERY = "sql_query"


class EdgeType(str, Enum):
    """Types of edges in the fact graph."""

    CONTAINS = "contains"
    IMPORTS = "imports"
    INHERITS = "inherits"
    CALLS = "calls"
    RAISES = "raises"
    HANDLES = "handles"
    INCLUDES = "includes"
    DEPENDS_ON = "depends_on"
    REQUEST_MODEL = "request_model"
    RESPONSE_MODEL = "response_model"
    RUNS_QUERY = "runs_query"


@dataclass(frozen=True, order=True)
class Node:
    """A node in the fact graph.

    All nodes have id, type, file, lines, hash_struct, hash_source.
    Additional fields vary by node type (see architecture.md §5).
    """

    id: str
    type: NodeType
    file: str
    lines: tuple[int, int]  # (start_line, end_line), 1-indexed, inclusive
    hash_struct: str
    hash_source: str

    # Type-specific fields (use empty string / empty tuple / False for absent)
    dotted_name: str = ""
    docstring: str = ""
    bases: tuple[str, ...] = field(default_factory=tuple)
    fields: tuple[tuple[str, str, str], ...] = field(default_factory=tuple)  # (name, annotation, default)
    is_pydantic_model: bool = False
    decorators: tuple[str, ...] = field(default_factory=tuple)
    signature: str = ""
    returns: str = ""
    async_flag: bool = False
    parent_class: str = ""
    library_name: str = ""
    what: str = ""
    why: str = ""
    where: str = ""
    method: str = ""
    full_path: str = ""
    name: str = ""
    status_code: int = 0
    variable: str = ""
    prefix: str = ""
    sql_name: str = ""
    sql_file: str = ""

    def __post_init__(self) -> None:
        # Ensure tuples are actually tuples (dataclass default_factory can produce list)
        object.__setattr__(self, "bases", tuple(self.bases))
        object.__setattr__(self, "fields", tuple(self.fields))
        object.__setattr__(self, "decorators", tuple(self.decorators))


@dataclass(frozen=True, order=True)
class Edge:
    """An edge in the fact graph."""

    type: EdgeType
    from_id: str
    to_id: str
    meta: tuple[tuple[str, str], ...] = field(default_factory=tuple)  # sorted key-value pairs

    def __post_init__(self) -> None:
        object.__setattr__(self, "meta", tuple(sorted(self.meta)))


@dataclass(frozen=True, order=True)
class Unresolved:
    """An unresolved reference that could not be statically resolved."""

    what: str
    why: str
    where: str  # file:line or node id


@dataclass(frozen=True, order=True)
class FactGraph:
    """The complete fact graph for a repository."""

    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    unresolved: tuple[Unresolved, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "nodes", tuple(sorted(self.nodes)))
        object.__setattr__(self, "edges", tuple(sorted(self.edges)))
        object.__setattr__(self, "unresolved", tuple(sorted(self.unresolved)))