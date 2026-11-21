"""Contract tests for AnthropicSummarizer. urlopen is mocked; no network is used."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request

import pytest

from docgen.summarize.anthropic_backend import (
    AnthropicError,
    AnthropicSummarizer,
)
from docgen.summarize.base import SummaryRequest


class _Response:
    def __init__(self, payload: dict) -> None:
        self._data = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _request() -> SummaryRequest:
    return SummaryRequest(
        node_id="mod.py::f",
        level="function",
        facts={"hash_struct": "hs", "hash_source": "hsrc", "file": "mod.py"},
        source_text="def f():\n    return 1\n",
    )


def _patch_urlopen(monkeypatch: pytest.MonkeyPatch, handler):
    calls: list[urllib.request.Request] = []

    def fake_urlopen(request, timeout=None):
        calls.append(request)
        return handler(request)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return calls


def _http_error(code: int, body: dict, headers: dict | None = None):
    def handler(request):
        raise urllib.error.HTTPError(
            request.full_url,
            code,
            "error",
            headers or {},
            io.BytesIO(json.dumps(body).encode("utf-8")),
        )

    return handler


def _success(text: str = "Cited prose [[mod.py::f]]."):
    return lambda request: _Response(
        {"content": [{"type": "text", "text": text}]}
    )


def test_missing_key_is_fatal_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(AnthropicError, match="ANTHROPIC_API_KEY") as excinfo:
        AnthropicSummarizer()

    assert excinfo.value.fatal
    assert not excinfo.value.transient


def test_request_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_urlopen(monkeypatch, _success())

    summarizer = AnthropicSummarizer(
        model="claude-sonnet-4-5", api_key="sk-ant-test", timeout=44
    )
    summarizer.summarize(_request())

    request = calls[0]
    body = json.loads(request.data)
    assert request.full_url == "https://api.anthropic.com/v1/messages"
    headers = {key.lower(): value for key, value in request.headers.items()}
    assert headers["x-api-key"] == "sk-ant-test"
    assert headers["anthropic-version"] == "2023-06-01"
    assert body["model"] == "claude-sonnet-4-5"
    assert body["max_tokens"] == 4096
    assert body["temperature"] == 0
    assert len(body["messages"]) == 1
    assert "PROMPT_VERSION" in body["messages"][0]["content"]


def test_success_returns_first_text_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_urlopen(
        monkeypatch,
        lambda request: _Response(
            {
                "content": [
                    {"type": "thinking", "thinking": "..."},
                    {"type": "text", "text": "A function [[mod.py::f]]."},
                ]
            }
        ),
    )

    result = AnthropicSummarizer(api_key="sk-ant-test").summarize(_request())

    assert result.text == "A function [[mod.py::f]]."
    assert result.backend == "anthropic:claude-sonnet-4-5"


@pytest.mark.parametrize("code", [429, 529])
def test_429_and_529_are_transient(
    monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    _patch_urlopen(
        monkeypatch,
        _http_error(
            code,
            {"error": {"message": "overloaded"}},
            headers={"Retry-After": "9"},
        ),
    )

    with pytest.raises(AnthropicError) as excinfo:
        AnthropicSummarizer(api_key="sk-ant-test").summarize(_request())

    assert excinfo.value.transient
    assert excinfo.value.retry_after == 9


def test_401_is_fatal_and_redacts_the_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_urlopen(
        monkeypatch,
        _http_error(
            401,
            {"error": {"message": "invalid x-api-key sk-ant-secret"}},
        ),
    )

    with pytest.raises(AnthropicError) as excinfo:
        AnthropicSummarizer(api_key="sk-ant-secret").summarize(_request())

    assert excinfo.value.fatal
    assert "sk-ant-secret" not in excinfo.value.message


def test_400_context_overflow_is_node_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_urlopen(
        monkeypatch,
        _http_error(
            400,
            {"error": {"message": "prompt is too long: context window exceeded"}},
        ),
    )

    with pytest.raises(AnthropicError) as excinfo:
        AnthropicSummarizer(api_key="sk-ant-test").summarize(_request())

    assert not excinfo.value.transient
    assert not excinfo.value.fatal


def test_name_is_model_only() -> None:
    summarizer = AnthropicSummarizer(model="claude-opus-4-1", api_key="k")

    assert summarizer.name == "anthropic:claude-opus-4-1"
    assert summarizer.context_limit == 200_000
