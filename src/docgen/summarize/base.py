"""Summarizer interface: shared request/result types, the `Summarizer` protocol,
`StubSummarizer`, and the `MissingSummaryError`.

Why this exists: the rest of the pipeline (CLI, later the hierarchy driver,
citation validator, and checker) must never care *which* backend produced the
prose. They speak only `SummaryRequest` -> `SummaryResult`. That single boundary
is what lets us swap a deterministic stub (tests), a folder of hand-written
files (early demos), or Bob Shell (later) without touching downstream code.

Nothing in this module performs I/O: the caller reads `source_text` and passes it
in, so every backend stays pure and easy to test.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

NodeLevel = Literal["function", "method", "class", "module", "package", "system"]


class MissingSummaryError(Exception):
    """Raised when a required summary file is missing.

    Specific so the CLI can catch it and report which node lacked a summary,
    rather than surfacing a bare `FileNotFoundError`.
    """

    def __init__(self, node_id: str) -> None:
        super().__init__(f"No summary found for node: {node_id}")
        self.node_id = node_id


@dataclass(frozen=True)
class SummaryResult:
    """The prose a summarizer produces for one node.

    Attributes:
        node_id: Which node this summary covers (echoed from the request).
        text: Prose with inline `[[fact_id]]` citations.
        backend: Identifier of the summarizer, e.g. "stub", "manual", "bob_shell".
        hash_input: SHA-256 of the inputs; the cache in 2b.3 uses this to decide
            whether a summary must be regenerated.
    """

    node_id: str
    text: str
    backend: str
    hash_input: str


@dataclass(frozen=True)
class SummaryRequest:
    """Everything a summarizer is allowed to see for one node.

    Attributes:
        node_id: The node's ID string.
        level: One of function/method/class/module/package/system.
        facts: The node's own fact dict (all fields from its `facts.json` entry).
        source_text: Raw source for this node, already read by the caller. No I/O
            happens inside a summarizer.
        child_summaries: Summaries of already-summarized children. Empty for the
            flat pass in 2b.1; populated by the hierarchy driver in 2b.3.
        edges: Relational facts emitted by this node, as edge dicts in the same shape
            as `facts.json` (`{"type", "from", "to", "meta"?}`). The CLI retains the
            `raises`, `depends_on`, `calls`, and `inherits` edges so a summary can
            cite them. Empty when the node has no such edges.
    """

    node_id: str
    level: NodeLevel
    facts: dict[str, Any]
    source_text: str
    child_summaries: list[SummaryResult] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)


def hash_input(req: SummaryRequest) -> str:
    """Compute the cache key for a request.

    SHA-256 over the node id plus its structural and source hashes. Deterministic:
    identical inputs always produce the identical digest.
    """
    payload = (
        req.node_id
        + str(req.facts.get("hash_struct", ""))
        + str(req.facts.get("hash_source", ""))
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@runtime_checkable
class Summarizer(Protocol):
    """Produces cited prose for a single node. Implementations differ only in backend."""

    def summarize(self, req: SummaryRequest) -> SummaryResult: ...


class StubSummarizer:
    """Deterministic, no-LLM summarizer used by tests.

    Returns a fixed template so tests can assert on output without any network or
    Bob calls.
    """

    def summarize(self, req: SummaryRequest) -> SummaryResult:
        return SummaryResult(
            node_id=req.node_id,
            text=f"Stub summary for {req.node_id} [[{req.node_id}]]",
            backend="stub",
            hash_input=hash_input(req),
        )
