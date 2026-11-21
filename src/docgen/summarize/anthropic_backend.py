"""AnthropicSummarizer — stdlib HTTP to the Anthropic Messages API.

For users who have an API key (Claude Pro does **not** include API access). The
OpenAI-compatible endpoint works as an alternative, but native Messages is the
reliable primary for Claude.

The whole prompt is sent as one user message, exactly as ``build_prompt`` produced
it: the cache key hashes that text, so splitting it into a system message would let
part of the model's input change without invalidating cached prose.

No SDK: ``urllib.request`` keeps ``dependencies = []`` and leaves retries to the
driver. This backend makes exactly **one** attempt per call.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request

from .base import (
    BackendError,
    SummaryRequest,
    SummaryResult,
    hash_input,
    parse_retry_after,
)
from .prompts import build_prompt

_ENDPOINT = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"

_CONTEXT_MARKERS = (
    "context length",
    "context window",
    "maximum context",
    "prompt is too long",
    "too many tokens",
    "string too long",
)


class AnthropicError(BackendError):
    """An Anthropic API failure, classified for the retry policy."""


def _error_message(raw: bytes) -> str:
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


class AnthropicSummarizer:
    """Summarizes one node per Messages API request.

    Args:
        model: Anthropic model ID (default ``"claude-sonnet-4-5"``).
        api_key: Explicit key. Prefer ``api_key_env``.
        api_key_env: Environment variable holding the key.
        max_tokens: Response cap; Anthropic requires this field.
        timeout: HTTP timeout in seconds.
    """

    context_limit = 200_000

    def __init__(
        self,
        model: str = "claude-sonnet-4-5",
        api_key: str | None = None,
        api_key_env: str = "ANTHROPIC_API_KEY",
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> None:
        self.model = model
        self._api_key_env = api_key_env or "ANTHROPIC_API_KEY"
        self._max_tokens = max_tokens
        self._timeout = timeout
        self.name = f"anthropic:{model}"

        key = api_key or os.environ.get(self._api_key_env)
        if not key:
            raise AnthropicError(
                f"{self._api_key_env} is not set. Set it, or pass "
                "--api-key-env with the variable that holds your Anthropic key.",
                transient=False,
                fatal=True,
            )
        self._api_key = key

    def _redact(self, text: str) -> str:
        return text.replace(self._api_key, "[redacted]") if self._api_key else text

    def _raise_http(self, exc: urllib.error.HTTPError) -> None:
        try:
            detail = self._redact(_error_message(exc.read()))
        except OSError:
            detail = "no error body"
        code = exc.code

        if code in (401, 403):
            raise AnthropicError(
                f"authentication failed ({code}): {detail}",
                transient=False,
                fatal=True,
            ) from exc
        if code == 404:
            raise AnthropicError(
                f"model not found (404): {detail}",
                transient=False,
                fatal=True,
            ) from exc
        if code in (429, 529):
            raise AnthropicError(
                f"overloaded or rate limited ({code}): {detail}",
                transient=True,
                retry_after=parse_retry_after(exc.headers.get("Retry-After")),
            ) from exc
        if code == 400:
            lowered = detail.lower()
            if any(marker in lowered for marker in _CONTEXT_MARKERS):
                raise AnthropicError(
                    f"prompt exceeds the model context (400): {detail}",
                    transient=False,
                    fatal=False,
                ) from exc
            raise AnthropicError(
                f"bad request (400): {detail}", transient=False, fatal=True
            ) from exc
        if code >= 500:
            raise AnthropicError(
                f"provider error ({code}): {detail}",
                transient=True,
                retry_after=parse_retry_after(exc.headers.get("Retry-After")),
            ) from exc
        raise AnthropicError(
            f"HTTP {code}: {detail}", transient=False, fatal=True
        ) from exc

    def summarize(self, req: SummaryRequest) -> SummaryResult:
        """POST one Messages request and return the first text block."""
        body = {
            "model": self.model,
            "max_tokens": self._max_tokens,
            "temperature": 0,
            "messages": [{"role": "user", "content": build_prompt(req)}],
        }
        request = urllib.request.Request(
            _ENDPOINT,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": _API_VERSION,
                "content-type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            self._raise_http(exc)
        except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
            raise AnthropicError(
                f"could not reach {_ENDPOINT}: {exc}", transient=True
            ) from exc

        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AnthropicError(
                f"response is not valid JSON: {exc}", transient=True
            ) from exc

        content = data.get("content")
        if not isinstance(content, list):
            raise AnthropicError("response has no content list", transient=True)
        text = next(
            (
                block.get("text")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ),
            None,
        )
        if not isinstance(text, str) or not text.strip():
            raise AnthropicError(
                "response has no non-empty text block", transient=True
            )

        return SummaryResult(
            node_id=req.node_id,
            text=text,
            backend=f"anthropic:{self.model}",
            hash_input=hash_input(req),
        )
