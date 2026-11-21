"""Tests for the driver's retry policy, error types, and single-attempt backends.

Every delay is asserted through an injected ``sleep``: nothing here waits.
"""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime

import pytest

from docgen.facts.schema import FactGraph, Node, NodeType
from docgen.summarize.base import (
    BackendError,
    FatalBackendError,
    RetryPolicy,
    StubSummarizer,
    SummaryRequest,
    SummaryResult,
    parse_retry_after,
)
from docgen.summarize.hierarchy import (
    NEEDS_HUMAN_REVIEW_BACKEND,
    _call_summarizer,
    hash_prompt,
    run_hierarchy,
)
from docgen.summarize.prompts import build_prompt


def _request(node_id: str = "mod.py::f") -> SummaryRequest:
    return SummaryRequest(
        node_id=node_id,
        level="function",
        facts={"id": node_id, "file": "mod.py"},
        source_text="def f():\n    return 1\n",
    )


def _key(req: SummaryRequest) -> str:
    return hash_prompt("stub\n" + build_prompt(req))


class _Scripted:
    """Raises queued exceptions, then behaves like the stub."""

    name = "stub"

    def __init__(self, *errors: BaseException) -> None:
        self._errors = list(errors)
        self.calls = 0

    def summarize(self, req: SummaryRequest) -> SummaryResult:
        self.calls += 1
        if self._errors:
            raise self._errors.pop(0)
        return StubSummarizer().summarize(req)


# ---------------------------------------------------------------------------
# Test 1-3: Retry-After parsing
# ---------------------------------------------------------------------------

def test_parse_retry_after_seconds() -> None:
    assert parse_retry_after("17") == 17.0
    assert parse_retry_after("0") == 0.0
    assert parse_retry_after("-5") == 0.0


def test_parse_retry_after_http_date() -> None:
    now = 1_700_000_000.0

    ahead = datetime.fromtimestamp(now + 30, tz=timezone.utc)
    assert parse_retry_after(format_datetime(ahead, usegmt=True), now=now) == 30.0

    past = datetime.fromtimestamp(now - 30, tz=timezone.utc)
    assert parse_retry_after(format_datetime(past, usegmt=True), now=now) == 0.0


def test_parse_retry_after_garbage() -> None:
    assert parse_retry_after(None) is None
    assert parse_retry_after("") is None
    assert parse_retry_after("soon") is None
    assert parse_retry_after("nan") is None


# ---------------------------------------------------------------------------
# Test 4-9: the retry loop
# ---------------------------------------------------------------------------

def test_plain_exception_is_transient() -> None:
    req = _request()
    summarizer = _Scripted(RuntimeError("hiccup"))
    sleeps: list[float] = []

    result, retryable = _call_summarizer(
        summarizer, req, _key(req), RetryPolicy(jitter=0), sleeps.append
    )

    assert summarizer.calls == 2
    assert sleeps == [2.0]
    assert result.hash_input == _key(req)
    assert retryable is True


def test_retry_honours_retry_after() -> None:
    req = _request()
    summarizer = _Scripted(BackendError("busy", retry_after=12.0))
    sleeps: list[float] = []

    result, _ = _call_summarizer(
        summarizer, req, _key(req), RetryPolicy(jitter=0), sleeps.append
    )

    assert summarizer.calls == 2
    assert sleeps == [12.0]
    assert result.backend == "stub"


def test_backoff_without_header() -> None:
    req = _request()
    summarizer = _Scripted(*(BackendError("busy") for _ in range(4)))
    sleeps: list[float] = []

    _call_summarizer(
        summarizer,
        req,
        _key(req),
        RetryPolicy(max_attempts=4, base_delay=2.0, jitter=0),
        sleeps.append,
    )

    assert sleeps == [2.0, 4.0, 8.0]


def test_backoff_is_capped() -> None:
    req = _request()
    summarizer = _Scripted(*(BackendError("busy") for _ in range(4)))
    sleeps: list[float] = []

    _call_summarizer(
        summarizer,
        req,
        _key(req),
        RetryPolicy(max_attempts=4, base_delay=100.0, max_delay=60.0, jitter=0),
        sleeps.append,
    )

    assert sleeps == [60.0, 60.0, 60.0]


def test_retry_after_is_capped() -> None:
    req = _request()
    summarizer = _Scripted(BackendError("busy", retry_after=999.0))
    sleeps: list[float] = []

    _call_summarizer(
        summarizer,
        req,
        _key(req),
        RetryPolicy(max_retry_after=120.0, max_node_sleep=300.0, jitter=0),
        sleeps.append,
    )

    assert sleeps == [120.0]


def test_exhausted_retries_produce_placeholder() -> None:
    req = _request()
    summarizer = _Scripted(*(BackendError("busy") for _ in range(4)))
    sleeps: list[float] = []

    result, retryable = _call_summarizer(
        summarizer,
        req,
        _key(req),
        RetryPolicy(max_attempts=4, jitter=0),
        sleeps.append,
    )

    assert summarizer.calls == 4
    assert result.backend == NEEDS_HUMAN_REVIEW_BACKEND
    assert result.text == "[needs_human_review]"
    assert result.hash_input == ""
    assert retryable is True


# ---------------------------------------------------------------------------
# Test 10-11: fatal errors abort the run
# ---------------------------------------------------------------------------

def test_fatal_error_aborts() -> None:
    req = _request()
    summarizer = _Scripted(BackendError("bad key", transient=False, fatal=True))

    with pytest.raises(FatalBackendError) as excinfo:
        _call_summarizer(
            summarizer, req, _key(req), RetryPolicy(jitter=0), lambda _: None
        )

    assert excinfo.value.node_id == "mod.py::f"
    assert summarizer.calls == 1


def test_fatal_error_in_parallel_batch_aborts(tmp_path) -> None:
    class FatalOnOne:
        name = "stub"

        def summarize(self, req: SummaryRequest) -> SummaryResult:
            if req.node_id == "mod.py::f1":
                raise BackendError("bad key", transient=False, fatal=True)
            return StubSummarizer().summarize(req)

    nodes = tuple(
        Node(
            id=f"mod.py::f{i}",
            type=NodeType.FUNCTION,
            file="mod.py",
            lines=(1, 2),
            hash_struct="hs",
            hash_source="hsrc",
        )
        for i in range(4)
    )
    graph = FactGraph(nodes=nodes, edges=(), unresolved=())

    with pytest.raises(FatalBackendError):
        run_hierarchy(
            graph, FatalOnOne(), tmp_path, existing_cache={}, max_workers=4
        )


# ---------------------------------------------------------------------------
# Test 12: the backend itself never retries
# ---------------------------------------------------------------------------

def test_backend_does_not_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    from docgen.summarize import bob_shell

    monkeypatch.setenv("BOB_API_KEY", "test-key")

    calls: list[str] = []

    def fake_call(*args, **kwargs):
        calls.append("call")
        raise bob_shell.BobShellError("provider is busy")

    monkeypatch.setattr(bob_shell, "_find_bob", lambda: "bob")
    monkeypatch.setattr(bob_shell, "_call_bob", fake_call)

    summarizer = bob_shell.BobShellSummarizer()
    with pytest.raises(BackendError):
        summarizer.summarize(_request())

    assert len(calls) == 1
