"""Contract tests for OpenAISummarizer. urlopen is mocked; no network is used."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request

import pytest

from docgen.summarize.base import SummaryRequest
from docgen.summarize.openai_backend import OpenAIError, OpenAISummarizer


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


def _success(text: str = "A function [[mod.py::f]]."):
    return lambda request: _Response(
        {
            "choices": [
                {"message": {"content": text}, "finish_reason": "stop"}
            ]
        }
    )


def test_missing_default_key_is_fatal_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(OpenAIError, match="OPENAI_API_KEY") as excinfo:
        OpenAISummarizer()

    assert excinfo.value.fatal
    assert not excinfo.value.transient


def test_local_base_url_uses_dummy_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    calls = _patch_urlopen(monkeypatch, _success())

    summarizer = OpenAISummarizer(
        base_url="http://localhost:11434/v1", model="qwen2.5-coder:7b"
    )
    summarizer.summarize(_request())

    assert calls[0].headers["Authorization"] == "Bearer local"


def test_request_body_url_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_urlopen(monkeypatch, _success())

    summarizer = OpenAISummarizer(
        model="gpt-4o-mini",
        base_url="https://example.test/v1/",
        api_key="sk-test",
        timeout=33,
    )
    summarizer.summarize(_request())

    request = calls[0]
    body = json.loads(request.data)
    assert request.full_url == "https://example.test/v1/chat/completions"
    assert body["model"] == "gpt-4o-mini"
    assert body["temperature"] == 0
    assert body["messages"][0]["role"] == "user"
    assert "PROMPT_VERSION" in body["messages"][0]["content"]
    assert "max_tokens" not in body


def test_success_returns_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_urlopen(monkeypatch, _success("Cited prose [[mod.py::f]]."))

    result = OpenAISummarizer(api_key="sk-test").summarize(_request())

    assert result.node_id == "mod.py::f"
    assert result.text == "Cited prose [[mod.py::f]]."
    assert result.backend == "openai:gpt-4o-mini"


def test_429_honours_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_urlopen(
        monkeypatch,
        _http_error(
            429,
            {"error": {"message": "rate limited"}},
            headers={"Retry-After": "17"},
        ),
    )

    with pytest.raises(OpenAIError) as excinfo:
        OpenAISummarizer(api_key="sk-test").summarize(_request())

    assert excinfo.value.transient
    assert excinfo.value.retry_after == 17
    assert not excinfo.value.fatal


def test_401_is_fatal_and_redacts_the_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_urlopen(
        monkeypatch,
        _http_error(
            401,
            {"error": {"message": "Incorrect API key provided: sk-secret-value"}},
        ),
    )

    with pytest.raises(OpenAIError) as excinfo:
        OpenAISummarizer(api_key="sk-secret-value").summarize(_request())

    assert excinfo.value.fatal
    assert not excinfo.value.transient
    assert "sk-secret-value" not in excinfo.value.message


def test_400_context_overflow_is_node_local(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_urlopen(
        monkeypatch,
        _http_error(
            400,
            {
                "error": {
                    "message": "This model's maximum context length is 8192 tokens"
                }
            },
        ),
    )

    with pytest.raises(OpenAIError) as excinfo:
        OpenAISummarizer(api_key="sk-test").summarize(_request())

    assert not excinfo.value.transient
    assert not excinfo.value.fatal


def test_other_400_is_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_urlopen(
        monkeypatch,
        _http_error(400, {"error": {"message": "unsupported parameter"}}),
    )

    with pytest.raises(OpenAIError) as excinfo:
        OpenAISummarizer(api_key="sk-test").summarize(_request())

    assert excinfo.value.fatal
    assert not excinfo.value.transient


def test_length_finish_reason_is_node_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_urlopen(
        monkeypatch,
        lambda request: _Response(
            {
                "choices": [
                    {
                        "message": {"content": "half a sentence"},
                        "finish_reason": "length",
                    }
                ]
            }
        ),
    )

    with pytest.raises(OpenAIError) as excinfo:
        OpenAISummarizer(api_key="sk-test").summarize(_request())

    assert not excinfo.value.transient
    assert not excinfo.value.fatal


def test_network_error_is_transient(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request):
        raise urllib.error.URLError("connection reset")

    _patch_urlopen(monkeypatch, handler)

    with pytest.raises(OpenAIError) as excinfo:
        OpenAISummarizer(api_key="sk-test").summarize(_request())

    assert excinfo.value.transient
    assert not excinfo.value.fatal


def test_name_changes_with_model_and_base_url() -> None:
    first = OpenAISummarizer(
        model="gpt-4o-mini", base_url="http://localhost:1234/v1"
    )
    same = OpenAISummarizer(
        model="gpt-4o-mini", base_url="http://localhost:1234/v1"
    )
    other_model = OpenAISummarizer(
        model="other", base_url="http://localhost:1234/v1"
    )
    other_url = OpenAISummarizer(
        model="gpt-4o-mini", base_url="http://localhost:5678/v1"
    )

    assert first.name == same.name
    assert first.name != other_model.name
    assert first.name != other_url.name
