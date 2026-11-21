"""ClaudeShellSummarizer — runs Claude Code non-interactively on a Pro/Max plan.

Why: an individual with Claude Pro has no API key and no Bob subscription. Claude
Code's print mode is the only path that can run the full hierarchy on that access.
It is a first-class backend here, not a convenience extra.

Invocation (see docs/plan-pluggable-llm-backends.md):

    claude -p --output-format json --safe-mode --no-session-persistence
           --tools "" --disallowedTools "mcp__*"
           --system-prompt "<short writer instruction>" --model sonnet

``--safe-mode``, ``--tools ""``, and ``--system-prompt`` are not optional. Without
them each call carries Claude Code's coding-agent prompt and tool schemas, roughly
10k extra tokens; over 234 calls that is the difference between ~0.4M and 2.7M
tokens, and the latter hits a Pro usage limit.

The prompt is sent on stdin (or through a temp file for a ``.cmd`` wrapper), never
on the command line: the largest measured prompt is 69,374 chars, above the 32 KB
Windows argv limit.

This backend makes exactly **one** attempt per call and raises ``ClaudeShellError``
with a classified failure; ``hierarchy._call_summarizer`` owns retries.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .base import BackendError, SummaryRequest, SummaryResult, hash_input
from .prompts import build_prompt

# Replaces Claude Code's coding-agent system prompt, which is pure overhead for
# prose generation and is the main token-cost lever. It is hashed into ``name``
# below: the cache key covers ``build_prompt(req)`` but not this separate system
# message, so without the hash an edit here would silently reuse stale prose.
_SYSTEM_PROMPT = (
    "You are a careful technical writer. Follow the instructions in the user "
    "message exactly. Do not use tools."
)

# Plan-limit text is fatal; a generic rate limit is not. "rate limit reached"
# is excluded below because the API's 429 wording must stay retryable.
_LIMIT_MARKERS: tuple[str, ...] = (
    "usage limit",
    "session limit",
    "5-hour limit",
    "weekly limit",
    "out of extra usage",
)

_FATAL_STDERR: tuple[str, ...] = (
    "not logged in",
    "login required",
    "please log in",
    "unauthorized",
    "invalid api key",
    "authentication",
    "401",
    "403",
    "model not found",
    "unsupported model",
)


class ClaudeShellError(BackendError):
    """A Claude Code failure, classified for the driver's retry policy."""


def _is_cmd_wrapper(exe: str) -> bool:
    """True for the npm ``claude.cmd`` shim, which Python cannot pipe to directly."""
    return Path(exe).suffix.lower() in {".cmd", ".bat"}


def _ps_quote(value: str) -> str:
    """Quote one PowerShell single-quoted string (doubling embedded quotes)."""
    return "'" + value.replace("'", "''") + "'"


def _powershell_command(exe: str, args: list[str], prompt_path: str | None) -> str:
    """Build the PowerShell pipeline used for a ``.cmd`` wrapper.

    Kept as a pure function so the Windows path can be tested on any platform,
    without launching PowerShell.

    The prompt is read from *prompt_path*, never interpolated, so its size and
    contents cannot reach the command line.
    """
    invocation = "& " + _ps_quote(exe)
    if args:
        invocation += " " + " ".join(_ps_quote(a) for a in args)
    if prompt_path is None:
        return invocation
    return (
        f"Get-Content -Encoding UTF8 -Raw {_ps_quote(prompt_path)} | {invocation}"
    )


def _parse_json_object(text: str) -> dict | None:
    """Parse a JSON object, tolerating a warning line before it."""
    stripped = text.strip()
    if not stripped:
        return None
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        return data
    for line in reversed(stripped.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            return candidate
    return None


def _looks_like_plan_limit(text: str) -> bool:
    """True only for a subscription-window limit, not a generic rate limit."""
    lowered = text.lower()
    if any(marker in lowered for marker in _LIMIT_MARKERS):
        return True
    return "limit reached" in lowered and "rate limit" not in lowered


def _find_claude() -> str:
    """Resolve the Claude Code executable, preferring a native binary.

    On Windows the npm install is a ``.cmd`` shim; the native installer puts a real
    ``claude.exe`` under ``%USERPROFILE%\\.local\\bin``, which pipes cleanly.
    """
    home = Path.home()
    candidates = [
        home / ".local" / "bin" / "claude.exe",
        home / ".local" / "bin" / "claude",
    ]
    for name in ("claude", "claude.cmd"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise ClaudeShellError(
        "claude executable not found on PATH or in ~/.local/bin. "
        "Install Claude Code (https://claude.com/claude-code) and run "
        "`claude auth login` with a Pro/Max account.",
        transient=False,
        fatal=True,
    )


def _run_claude(
    exe: str,
    args: list[str],
    *,
    prompt: str | None,
    timeout: int,
    env: dict[str, str],
) -> tuple[int, str, str]:
    """Run Claude once; return ``(returncode, stdout, stderr)``.

    A native ``.exe`` gets the prompt on stdin. A ``.cmd`` shim uses the same
    PowerShell temp-file pattern as ``bob_shell``: stdout goes to a file because
    capturing a wrapped Node process through a pipe deadlocks on Windows, and
    ``stdin`` is not forwarded through the wrapper.
    """
    if not _is_cmd_wrapper(exe):
        kwargs: dict = {
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "timeout": timeout,
            "env": env,
        }
        if prompt is None:
            kwargs["stdin"] = subprocess.DEVNULL
        else:
            kwargs["input"] = prompt
        proc = subprocess.run([exe, *args], **kwargs)
        return proc.returncode, proc.stdout, proc.stderr

    prompt_path: str | None = None
    out_path: str | None = None
    try:
        if prompt is not None:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            ) as prompt_f:
                prompt_f.write(prompt)
                prompt_path = prompt_f.name
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as out_f:
            out_path = out_f.name

        ps_cmd = _powershell_command(exe, args, prompt_path)
        with open(out_path, "w", encoding="utf-8") as out_f:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                stdout=out_f,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                timeout=timeout,
                env=env,
            )
        stdout_text = Path(out_path).read_text(encoding="utf-8-sig")
        return proc.returncode, stdout_text, proc.stderr
    finally:
        if out_path is not None:
            Path(out_path).unlink(missing_ok=True)
        if prompt_path is not None:
            Path(prompt_path).unlink(missing_ok=True)


class ClaudeShellSummarizer:
    """Summarizes one node per ``claude -p`` call on a Claude subscription.

    Args:
        model: Claude Code model alias (default ``"sonnet"``). Use ``"haiku"`` for
            smoke tests; never hardcode a dated model ID.
        timeout: Per-call subprocess timeout in seconds (default 180).
        claude_exe: Explicit executable path, mainly for tests. When omitted the
            executable is resolved from ``~/.local/bin`` and ``PATH``.
    """

    context_limit = 200_000

    def __init__(
        self,
        model: str = "sonnet",
        timeout: int = 180,
        claude_exe: str | None = None,
    ) -> None:
        self.model = model
        self._timeout = timeout
        self._exe = claude_exe or _find_claude()
        # One snapshot for both the hash and the argv, so the cache identity can
        # never describe a different system prompt than the one actually sent.
        self._system_prompt = _SYSTEM_PROMPT
        self._system_prompt_hash = hashlib.sha256(
            self._system_prompt.encode("utf-8")
        ).hexdigest()[:8]
        self.name = f"claude_shell:{model}:{self._system_prompt_hash}"

        # Subscription auth only. Stripping the API key here (and per call) means
        # Claude Code cannot silently bill the API; API-key users choose the
        # anthropic backend instead.
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        self._check_auth(env)

    def _check_auth(self, env: dict[str, str]) -> None:
        """Verify once that Claude Code is logged in with a subscription."""
        try:
            returncode, stdout, stderr = _run_claude(
                self._exe,
                ["auth", "status"],
                prompt=None,
                timeout=min(self._timeout, 30),
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise ClaudeShellError(
                f"`claude auth status` timed out after {min(self._timeout, 30)}s",
                transient=True,
            ) from exc
        except OSError as exc:
            raise ClaudeShellError(
                f"could not run claude: {exc}", transient=False, fatal=True
            ) from exc

        if returncode != 0:
            raise ClaudeShellError(
                "Claude Code auth check failed: "
                + (stderr.strip()[:300] or f"exit code {returncode}"),
                transient=False,
                fatal=True,
            )

        data = _parse_json_object(stdout)
        method = (data or {}).get("authMethod") or (data or {}).get("auth_method")
        if method not in ("claude.ai", "oauth_token"):
            raise ClaudeShellError(
                "Claude Code is not logged in with a Claude subscription.\n"
                "Run `claude auth login` with your Pro/Max account, or set "
                "CLAUDE_CODE_OAUTH_TOKEN from `claude setup-token`. "
                "claude_shell deliberately ignores ANTHROPIC_API_KEY; use "
                "--backend anthropic for API-key billing.",
                transient=False,
                fatal=True,
            )

    def summarize(self, req: SummaryRequest) -> SummaryResult:
        """Build the prompt and call Claude Code exactly once."""
        prompt = build_prompt(req)
        argv = [
            "-p",
            "--output-format",
            "json",
            "--safe-mode",
            "--no-session-persistence",
            "--tools",
            "",
            "--disallowedTools",
            "mcp__*",
            "--system-prompt",
            self._system_prompt,
            "--model",
            self.model,
        ]
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

        try:
            returncode, stdout, stderr = _run_claude(
                self._exe,
                argv,
                prompt=prompt,  # stdin, never argv
                timeout=self._timeout,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise ClaudeShellError(
                f"claude timed out after {self._timeout}s", transient=True
            ) from exc
        except OSError as exc:
            raise ClaudeShellError(
                f"could not run claude: {exc}", transient=False, fatal=True
            ) from exc

        data = _parse_json_object(stdout)
        if data is None:
            detail = (stderr or stdout).strip()[:300]
            fatal = any(m in detail.lower() for m in _FATAL_STDERR)
            raise ClaudeShellError(
                f"claude returned no JSON (exit {returncode}): {detail}",
                transient=not fatal,
                fatal=fatal,
            )

        if data.get("is_error"):
            message = str(
                data.get("result")
                or data.get("subtype")
                or "claude returned an error"
            )
            limit = _looks_like_plan_limit(message)
            raise ClaudeShellError(
                message, transient=not limit, fatal=limit
            )

        if returncode != 0:
            detail = (stderr or stdout).strip()[:300]
            fatal = any(m in detail.lower() for m in _FATAL_STDERR)
            raise ClaudeShellError(
                f"claude exited with code {returncode}: {detail}",
                transient=not fatal,
                fatal=fatal,
            )

        text = data.get("result")
        if not isinstance(text, str) or not text.strip():
            raise ClaudeShellError(
                "claude response has no non-empty 'result' string", transient=True
            )

        return SummaryResult(
            node_id=req.node_id,
            text=text,
            backend=f"claude_shell:{self.model}",
            hash_input=hash_input(req),
        )
