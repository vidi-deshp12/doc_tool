"""Tests for task 2b.6: BobShellSummarizer and needs_human_review handling.

All tests are offline: subprocess.run is monkeypatched; no real Bob calls are made.
The BOB_API_KEY environment variable is set via monkeypatch.setenv.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from docgen.summarize.base import SummaryRequest, SummaryResult
from docgen.summarize.bob_shell import BobShellError, BobShellSummarizer, _call_bob
from docgen.summarize.hierarchy import (
    NEEDS_HUMAN_REVIEW_BACKEND,
    run_hierarchy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GOOD_RESPONSE = json.dumps({
    "type": "result",
    "status": "success",
    "stats": {"session_costs": 0.009, "max_cost": 2.0},
    "last_message": "This function does a thing [[mod.py::f]].",
})

_ERROR_RESPONSE = json.dumps({
    "type": "result",
    "status": "error",
    "last_message": "",
})


def _make_proc(stdout: str = _GOOD_RESPONSE, returncode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)


def _make_request(node_id: str = "mod.py::f") -> SummaryRequest:
    return SummaryRequest(
        node_id=node_id,
        level="function",
        facts={"hash_struct": "hs", "hash_source": "hsrc", "file": "mod.py"},
        source_text="def f():\n    return 1\n",
    )


# ---------------------------------------------------------------------------
# Test 1: happy path — valid JSON, status=success, last_message returned
# ---------------------------------------------------------------------------

def test_bob_shell_success(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess
    monkeypatch.setenv("BOB_API_KEY", "test-key")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _make_proc())

    s = BobShellSummarizer(max_cost=0.1, max_turns=5)
    result = s.summarize(_make_request())

    assert result.backend == "bob_shell"
    assert "This function does a thing" in result.text
    assert result.node_id == "mod.py::f"


# ---------------------------------------------------------------------------
# Test 2: status=error in JSON → BobShellError
# ---------------------------------------------------------------------------

def test_bob_shell_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess
    monkeypatch.setenv("BOB_API_KEY", "test-key")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _make_proc(_ERROR_RESPONSE))

    s = BobShellSummarizer()
    with pytest.raises(BobShellError, match="status="):
        s.summarize(_make_request())


# ---------------------------------------------------------------------------
# Test 3: non-zero exit code → BobShellError
# ---------------------------------------------------------------------------

def test_bob_shell_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess
    monkeypatch.setenv("BOB_API_KEY", "test-key")
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **kw: _make_proc(stdout="", returncode=1),
    )

    s = BobShellSummarizer()
    with pytest.raises(BobShellError, match="exited with code 1"):
        s.summarize(_make_request())


# ---------------------------------------------------------------------------
# Test 4: valid JSON but missing last_message → BobShellError
# ---------------------------------------------------------------------------

def test_bob_shell_missing_last_message(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess
    bad = json.dumps({"type": "result", "status": "success", "stats": {}})
    monkeypatch.setenv("BOB_API_KEY", "test-key")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _make_proc(bad))

    s = BobShellSummarizer()
    with pytest.raises(BobShellError, match="last_message"):
        s.summarize(_make_request())


# ---------------------------------------------------------------------------
# Test 5: retry — first call raises, second succeeds → result returned, count=2
# ---------------------------------------------------------------------------

def test_bob_shell_retry_succeeds_on_second_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    call_count = [0]

    def fake_run(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return _make_proc(stdout="not json", returncode=0)
        return _make_proc()

    monkeypatch.setenv("BOB_API_KEY", "test-key")
    monkeypatch.setattr(subprocess, "run", fake_run)
    # Skip the real sleep
    monkeypatch.setattr("docgen.summarize.bob_shell.time.sleep", lambda s: None)

    s = BobShellSummarizer()
    result = s.summarize(_make_request())

    assert call_count[0] == 2
    assert result.backend == "bob_shell"


# ---------------------------------------------------------------------------
# Test 6: both attempts fail → BobShellError raised
# ---------------------------------------------------------------------------

def test_bob_shell_retry_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    monkeypatch.setenv("BOB_API_KEY", "test-key")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _make_proc(_ERROR_RESPONSE))
    monkeypatch.setattr("docgen.summarize.bob_shell.time.sleep", lambda s: None)

    s = BobShellSummarizer()
    with pytest.raises(BobShellError):
        s.summarize(_make_request())


# ---------------------------------------------------------------------------
# Test 7: BOB_API_KEY missing → BobShellError at construction time
# ---------------------------------------------------------------------------

def test_bob_shell_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOB_API_KEY", raising=False)
    with pytest.raises(BobShellError, match="BOB_API_KEY"):
        BobShellSummarizer()


# ---------------------------------------------------------------------------
# Test 8: run_hierarchy continues when summarizer raises
# ---------------------------------------------------------------------------

def test_run_hierarchy_continues_on_summarizer_failure(tmp_path: Path) -> None:
    """A summarizer that always raises must not abort run_hierarchy."""
    from docgen.facts.schema import Edge, EdgeType, FactGraph, Node, NodeType

    class AlwaysFails:
        def summarize(self, req: SummaryRequest) -> SummaryResult:
            raise RuntimeError("intentional failure")

    mod = Node(
        id="mod.py", type=NodeType.MODULE, file="mod.py",
        lines=(1, 5), hash_struct="hs", hash_source="hsrc",
    )
    func = Node(
        id="mod.py::f", type=NodeType.FUNCTION, file="mod.py",
        lines=(1, 2), hash_struct="fhs", hash_source="fhsrc",
    )
    graph = FactGraph(
        nodes=(mod, func),
        edges=(Edge(type=EdgeType.CONTAINS, from_id="mod.py", to_id="mod.py::f"),),
        unresolved=(),
    )

    results = run_hierarchy(
        graph=graph,
        summarizer=AlwaysFails(),
        repo_root=tmp_path,
        existing_cache={},
        prompt_version="test",
    )

    backends = {r.backend for r in results}
    assert NEEDS_HUMAN_REVIEW_BACKEND in backends


# ---------------------------------------------------------------------------
# Test 9: needs_human_review placeholder has hash_input="" → always retried
# ---------------------------------------------------------------------------

def test_needs_human_review_hash_input_empty(tmp_path: Path) -> None:
    """The placeholder must have hash_input="" so it is re-attempted next run."""
    from docgen.facts.schema import FactGraph, Node, NodeType

    class AlwaysFails:
        def summarize(self, req: SummaryRequest) -> SummaryResult:
            raise RuntimeError("fail")

    mod = Node(
        id="mod.py", type=NodeType.MODULE, file="mod.py",
        lines=(1, 2), hash_struct="hs", hash_source="hsrc",
    )
    graph = FactGraph(nodes=(mod,), edges=(), unresolved=())

    results = run_hierarchy(
        graph=graph,
        summarizer=AlwaysFails(),
        repo_root=tmp_path,
        existing_cache={},
        prompt_version="test",
    )

    failed = [r for r in results if r.backend == NEEDS_HUMAN_REVIEW_BACKEND]
    assert failed, "expected at least one needs_human_review result"
    assert all(r.hash_input == "" for r in failed)


# ---------------------------------------------------------------------------
# Test 10: validator skips needs_human_review summaries
# ---------------------------------------------------------------------------

def test_validator_skips_needs_human_review() -> None:
    """validate_summaries must not flag a needs_human_review placeholder."""
    from docgen.summarize.citations import validate_summaries

    summaries = [
        SummaryResult(
            node_id="mod.py::f",
            text="[needs_human_review]",
            backend=NEEDS_HUMAN_REVIEW_BACKEND,
            hash_input="",
        )
    ]
    errors = validate_summaries(summaries, known_ids={"mod.py::f"})
    assert errors == []
