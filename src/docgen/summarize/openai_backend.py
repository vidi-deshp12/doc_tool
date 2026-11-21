"""OpenAISummarizer — stdlib HTTP to any OpenAI-compatible Chat Completions API.

One adapter covers OpenAI, Groq, Gemini's compatibility endpoint, OpenRouter,
Together, DeepSeek, Mistral, xAI, LiteLLM/Azure gateways, Ollama, LM Studio,
llama.cpp, and vLLM. Adding a vendor class per provider would duplicate the same
request, parse, and error mapping; Anthropic's Messages shape is the one materially
different API, so it gets its own adapter.

No SDK: ``urllib.request`` keeps ``dependencies = []`` and leaves retries with the
driver in ``hierarchy.py`` instead of an SDK's hidden retry loop.

This backend makes exactly **one** attempt per call and raises ``OpenAIError`` with
a classified failure.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request

from .base import (
    BackendError,
    SummaryRequest,
    SummaryResult,
    hash_input,
    parse_retry_after,
)
from .prompts import build_prompt

_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}

# A 400 whose message points at prompt size is per-node and not retryable; any
# other 400 is a bad request (configuration) and stops the run.
_CONTEXT_MARKERS = (
    "context length",
    "context window",
    "maximum context",
    "prompt is too long",
    "too many tokens",
    "string too long",
)


class OpenAIError(BackendError):
    """An OpenAI-compatible API failure, classified for the retry policy."""


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _is_local(base_url: str) -> bool:
    host = urllib.parse.urlparse(base_url).hostname
    return host in _LOCAL_HOSTS


def _error_message(raw: bytes) -> str:
    """Extract ``error.message`` from a provider error body, or return text."""
    text = raw.decode("utf-8", "replace").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text[:300]
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])[:300]
        if data.get("message"):
            return str(data["message"])[:300]
    return text[:300] or "no error body"


class OpenAISummarizer:
    """Summarizes one node per Chat Completions request.

    Args:
        model: Provider model name (default ``"gpt-4o-mini"``).
        base_url: API root, without ``/chat/completions`` (default OpenAI).
        api_key: Explicit key. Prefer ``api_key_env`` so the key stays out of argv.
        api_key_env: Environment variable holding the key.
        timeout: HTTP timeout in seconds.
        max_tokens: Optional response cap sent as ``max_tokens``.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        api_key: str | None = None,
        api_key_env: str = "OPENAI_API_KEY",
        timeout: int = 120,
        max_tokens: int | None = None,
    ) -> None:
        self.model = model
        self.base_url = _normalize_base_url(base_url or _DEFAULT_BASE_URL)
        self._endpoint = self.base_url + "/chat/completions"
        self._api_key_env = api_key_env or "OPENAI_API_KEY"
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._local = _is_local(self.base_url)
        # Local servers usually ignore the key; hosted gateways do not.
        self.context_limit = 8_192 if self._local else 128_000
        self.name = f"openai:{self.base_url}:{model}"

        key = api_key or os.environ.get(self._api_key_env)
        if not key:
            if self._local:
                key = "local"
            elif base_url:
                raise OpenAIError(
                    f"No API key for {self.base_url}. Set {self._api_key_env} "
                    "or pass --api-key-env.",
                    transient=False,
                    fatal=True,
                )
            else:
                raise OpenAIError(
                    f"{self._api_key_env} is not set. Set it, or use --base-url "
                    "for a local server.",
                    transient=False,
                    fatal=True,
                )
        self._api_key = key

    def _redact(self, text: str) -> str:
        """Never echo the key, even if a provider reflects it in an error."""
        return text.replace(self._api_key, "[redacted]") if self._api_key else text

    def _raise_http(self, exc: urllib.error.HTTPError) -> None:
        try:
            detail = self._redact(_error_message(exc.read()))
        except OSError:
            detail = "no error body"
        code = exc.code

        if code in (401, 403):
            raise OpenAIError(
                f"authentication failed ({code}): {detail}",
                transient=False,
                fatal=True,
            ) from exc
        if code == 404:
            raise OpenAIError(
                f"endpoint or model not found (404): {detail}",
                transient=False,
                fatal=True,
            )
        if code == 429:
            raise OpenAIError(
                f"rate limited (429): {detail}",
                transient=True,
                retry_after=parse_retry_after(exc.headers.get("Retry-After")),
            ) from exc
        if code == 400:
            lowered = detail.lower()
            if any(marker in lowered for marker in _CONTEXT_MARKERS):
                raise OpenAIError(
                    f"prompt exceeds the model context (400): {detail}",
                    transient=False,
                    fatal=False,
                ) from exc
            raise OpenAIError(
                f"bad request (400): {detail}", transient=False, fatal=True
            ) from exc
        if code >= 500:
            raise OpenAIError(
                f"provider error ({code}): {detail}",
                transient=True,
                retry_after=parse_retry_after(exc.headers.get("Retry-After")),
            ) from exc
        raise OpenAIError(
            f"HTTP {code}: {detail}", transient=False, fatal=True
        ) from exc

    def summarize(self, req: SummaryRequest) -> SummaryResult:
        """POST one Chat Completions request and return the cited prose."""
        prompt = build_prompt(req)
        body: dict = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
        if self._max_tokens is not None:
            body["max_tokens"] = self._max_tokens

        request = urllib.request.Request(
            self._endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            self._raise_http(exc)
        except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
            raise OpenAIError(
                f"could not reach {self._endpoint}: {exc}", transient=True
            ) from exc

        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OpenAIError(
                f"response is not valid JSON: {exc}", transient=True
            ) from exc

        try:
            choice = data["choices"][0]
            text = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenAIError(
                "response has no choices[0].message.content", transient=True
            ) from exc

        if choice.get("finish_reason") == "length":
            raise OpenAIError(
                "response was truncated (finish_reason=length)",
                transient=False,
                fatal=False,
            )
        if not isinstance(text, str) or not text.strip():
            raise OpenAIError("model returned empty content", transient=True)

        return SummaryResult(
            node_id=req.node_id,
            text=text,
            backend=f"openai:{self.model}",
            hash_input=hash_input(req),
        )
