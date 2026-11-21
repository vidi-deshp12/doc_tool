"""Summarizer interface: shared request/result types, the `Summarizer` protocol,
`StubSummarizer`, `MissingSummaryError`, and the error/retry types the driver uses
(`BackendError`, `FatalBackendError`, `RetryPolicy`, `RetryGate`).

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
import math
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Literal, Protocol, runtime_checkable

NodeLevel = Literal["function", "method", "class", "module", "package", "system"]


class MissingSummaryError(Exception):
    """Raised when a required summary file is missing.

    Specific so the CLI can catch it and report which node lacked a summary,
    rather than surfacing a bare `FileNotFoundError`.
    """

    def __init__(self, node_id: str) -> None:
        super().__init__(f"No summary found for node: {node_id}")
        self.node_id = node_id


class BackendError(Exception):
    """A provider failure, classified for the driver's retry policy.

    ``transient=True``   → the driver may wait and retry the same request.
    ``transient=False``  → retrying this request cannot help.
    ``fatal=True``       → configuration/auth/shape problem: stop the whole run (exit 2).
    ``fatal=False``      → this node only: write a placeholder and continue the run.
    ``retry_after``      → seconds the provider asked us to wait (HTTP Retry-After).

    Three flags, not two, because "do not retry this request" and "abort the whole
    run" are different decisions. The defaults stay permissive because an
    unclassified failure in a subprocess is far more often a hiccup than a
    misconfiguration: one wasted retry beats a hole.
    """

    def __init__(
        self,
        message: str,
        *,
        transient: bool = True,
        fatal: bool = False,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.transient = transient
        self.fatal = fatal
        self.retry_after = retry_after


class FatalBackendError(Exception):
    """A ``BackendError`` that must stop the whole run.

    Lives here rather than in ``hierarchy.py`` so ``cli.py`` can catch it without
    importing the driver's internals. ``node_id`` is the affected node, or the
    backend name when construction itself failed (missing key, missing package).
    """

    def __init__(self, node_id: str, cause: BackendError) -> None:
        super().__init__(f"{node_id}: {cause.message}")
        self.node_id = node_id
        self.cause = cause


def parse_retry_after(value: str | None, *, now: float | None = None) -> float | None:
    """Seconds to wait from an HTTP ``Retry-After`` header value.

    Accepts the delay-seconds form (``"17"``) and the HTTP-date form via
    ``email.utils.parsedate_to_datetime``, which also covers the obsolete RFC 850
    and asctime forms. Naive datetimes (the obsolete forms) are treated as UTC.

    Returns ``None`` for ``None``, an empty string, or anything unparseable, so the
    caller falls back to exponential backoff. Negative values become 0; non-finite
    values (``nan``/``inf``) are rejected rather than slept on.
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None

    try:
        seconds = float(text)
    except ValueError:
        pass
    else:
        if not math.isfinite(seconds):
            return None
        return max(0.0, seconds)

    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    current = time.time() if now is None else now
    return max(0.0, parsed.timestamp() - current)


@dataclass(frozen=True)
class RetryPolicy:
    """How many times, and how long, the driver may wait for one node.

    ``max_attempts`` counts the initial call plus retries (4 = 1 + 3).
    ``max_retry_after`` caps a provider-supplied header; ``max_delay`` caps
    computed exponential backoff. ``max_node_sleep`` bounds the *sum* of a node's
    waits, so a generous header cannot park a worker for an hour: a node that has
    already waited that long stops retrying and lands as a placeholder. Jitter is
    applied on top of both delays — waiting slightly longer is always safe, and it
    stops four workers waking in lockstep.
    """

    max_attempts: int = 4
    base_delay: float = 2.0
    max_delay: float = 60.0
    max_retry_after: float = 120.0
    max_node_sleep: float = 300.0
    jitter: float = 0.5

    def delay_for(self, attempt: int, retry_after: float | None) -> float:
        """Sleep before the next attempt, in seconds."""
        if retry_after is not None:
            delay = min(max(0.0, retry_after), self.max_retry_after)
        else:
            delay = min(self.base_delay * (2**attempt), self.max_delay)
        if delay > 0:
            delay *= 1 + random.random() * self.jitter
        return delay


class RetryGate:
    """A shared "do not call before T" so parallel workers cool down together.

    One worker's 429 with ``retry-after: 20`` otherwise leaves the other three
    hammering the same window, each burning its own four attempts. The gate only
    ever sleeps *longer*; it never shortens a backoff.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._not_before = 0.0
        self._lock = threading.Lock()

    def defer(self, seconds: float) -> None:
        """Push the shared cooldown to at least now + *seconds*."""
        with self._lock:
            self._not_before = max(self._not_before, self._clock() + seconds)

    def wait(self, sleep: Callable[[float], None]) -> float:
        """Sleep until the cooldown elapses; return the seconds slept (0 if none)."""
        with self._lock:
            delay = self._not_before - self._clock()
        if delay > 0:
            sleep(delay)
            return delay
        return 0.0


@dataclass(frozen=True)
class SummaryResult:
    """The prose a summarizer produces for one node.

    Attributes:
        node_id: Which node this summary covers (echoed from the request).
        text: Prose with inline `[[fact_id]]` citations.
        backend: Identifier of the summarizer, e.g. "stub", "manual", "bob_shell".
        hash_input: SHA-256 of the exact prompt sent; the cache in the hierarchy
            driver uses this to decide whether a summary must be regenerated. Backends
            fill in a placeholder — ``run_hierarchy`` always overwrites it.
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
    """Produces cited prose for a single node. Implementations differ only in backend.

    Every implementation makes **one** attempt per call: it must not retry, sleep,
    or swallow provider failures. It raises ``BackendError`` instead, and the
    driver (``hierarchy._call_summarizer``) owns retries, backoff, and sleeping.

    Contract: ``summarize`` must send ``build_prompt(req)`` — the prompt is the cache
    key, so a backend that rewrites, annotates, or drops part of it makes the cache
    answer "same input" for different inputs. Splitting the string across system/user
    messages is fine; the text is what is hashed.

    Optional attribute ``name``: a stable backend identifier (e.g. ``"stub"``). It
    participates in the cache key, so switching providers never reuses another
    provider's prose. When absent, the class name is used.
    """

    def summarize(self, req: SummaryRequest) -> SummaryResult: ...


class StubSummarizer:
    """Deterministic, no-LLM summarizer used by tests.

    Returns a fixed template so tests can assert on output without any network or
    Bob calls.
    """

    name = "stub"

    def summarize(self, req: SummaryRequest) -> SummaryResult:
        return SummaryResult(
            node_id=req.node_id,
            text=f"Stub summary for {req.node_id} [[{req.node_id}]]",
            backend="stub",
            hash_input=hash_input(req),
        )
