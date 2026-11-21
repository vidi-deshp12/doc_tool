"""BobShellSummarizer — calls `bob run --format json` non-interactively.

Why: the trust story of this tool requires that summaries are written by an LLM grounded in
the extracted facts. BobShellSummarizer is the real backend: it pipes the deterministic prompt
built by ``build_prompt(req)`` into Bob Shell and parses the ``last_message`` from the JSON
response.

Delivery mechanism (D-018 + Windows fix): the prompt is written to a temp file and piped via
PowerShell ``Get-Content ... | bob run``.  This matches the confirmed-working
``echo "..." | bob run --format json`` pattern but avoids two Windows-specific traps:

- stdout captured via ``subprocess.PIPE`` deadlocks on .CMD-wrapped Node processes
  (redirected to a second temp file instead).
- ``stdin=file`` is not forwarded through the .CMD wrapper to Node
  (PowerShell handles the pipe natively).

Response shape:
    {
        "type": "result",
        "status": "success",   # or "error"
        "stats": {"session_costs": 0.009, "max_cost": 0.1, ...},
        "last_message": "<model response text>"
    }

This backend makes exactly **one** attempt per call and raises ``BobShellError``
(a ``BackendError``) with a classified failure; the driver owns retries.

Nothing in this module reads files or writes summaries.json — that is the caller's job.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .base import BackendError, SummaryRequest, SummaryResult, hash_input
from .prompts import build_prompt

# Lowercase stderr substrings that mean "your configuration is wrong", not "the
# provider is busy". Heuristic: it only ever decides to stop the run, never to
# succeed. "not found" is deliberately absent on its own — a proxy can return a
# 404 HTML page for a URL that exists, and that is transient — so it only counts
# when "model" is present too.
_FATAL_STDERR: tuple[str, ...] = (
    "auth",
    "api key",
    "api_key",
    "unauthorized",
    "401",
    "403",
    "login",
)


class BobShellError(BackendError):
    """A `bob run` failure, classified for the driver's retry policy.

    A ``BackendError`` subclass so existing ``except BobShellError`` sites keep
    working. Caught by ``hierarchy._call_summarizer``, which retries transient
    failures and writes a ``needs_human_review`` placeholder for the rest.
    """


def _find_bob() -> str:
    """Return the absolute path to the `bob` executable, or raise BobShellError."""
    path = shutil.which("bob")
    if path:
        return path
    # Explicit fallback for Windows where npm installs bob.cmd
    path = shutil.which("bob.cmd")
    if path:
        return path
    raise BobShellError(
        "bob executable not found on PATH. "
        "Install Bob Shell (https://ibm.biz/bob-shell) and ensure it is on PATH.",
        transient=False,
        fatal=True,
    )


def _call_bob(
    prompt: str,
    bob_exe: str,
    max_cost: float,
    max_turns: int,
    timeout: int,
) -> str:
    """Invoke ``bob run --format json`` via a PowerShell pipe.

    On Windows, ``bob`` is a ``.CMD`` wrapper around Node.js. Two problems
    arise when calling it from Python subprocess:

    1. **stdout deadlock**: capturing stdout via ``subprocess.PIPE`` deadlocks
       because the CMD wrapper buffers differently.  Fix: redirect stdout to a
       temp file and read it after the process exits.

    2. **stdin not forwarded**: passing the prompt via ``stdin=file`` does not
       work because the CMD wrapper does not forward file-based stdin to the
       Node.js process.  Fix: invoke PowerShell and use ``Get-Content | bob``
       — PowerShell handles the pipe natively, exactly as the confirmed-working
       interactive ``echo "..." | bob run`` does (D-018).

    The prompt is written to a temp file so the PowerShell command line stays
    short regardless of prompt size.  Both temp files are deleted in a
    ``finally`` block.

    Returns:
        The ``last_message`` string from the JSON response.

    Raises:
        BobShellError: on timeout, non-zero exit code, JSON parse failure, or
            ``status != "success"`` in the response. The error is classified:
            auth-shaped stderr (and ``model ... not found``) is fatal, every
            other failure is transient.
    """
    # Write prompt to a temp file — keeps the PowerShell command line short.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as prompt_f:
        prompt_f.write(prompt)
        prompt_path = prompt_f.name

    # Write stdout to a temp file to avoid the pipe deadlock (see above).
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as out_f:
        out_path = out_f.name

    # PowerShell pipes the prompt file into bob run; bob's stdout goes to
    # out_path.  Single-quotes around paths are safe for Windows temp paths
    # (no single-quotes in %TEMP%).  & invokes the bob .CMD as a command.
    ps_cmd = (
        f"Get-Content -Encoding UTF8 -Raw '{prompt_path}' | "
        f"& '{bob_exe}' run --format json "
        f"--max-cost {max_cost} --max-turns {max_turns}"
    )
    cmd = ["powershell", "-NoProfile", "-Command", ps_cmd]

    try:
        with open(out_path, "w", encoding="utf-8") as out_f:
            try:
                proc = subprocess.run(
                    cmd,
                    stdout=out_f,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired as exc:
                raise BobShellError(
                    f"bob run timed out after {timeout}s", transient=True
                ) from exc
        with open(out_path, encoding="utf-8") as f:
            stdout_text = f.read()
    finally:
        os.unlink(out_path)
        if os.path.exists(prompt_path):
            os.unlink(prompt_path)

    if proc.returncode != 0:
        stderr_snippet = proc.stderr.strip()[:300]
        lowered = stderr_snippet.lower()
        fatal = any(marker in lowered for marker in _FATAL_STDERR) or (
            "model" in lowered and "not found" in lowered
        )
        raise BobShellError(
            f"bob run exited with code {proc.returncode}: {stderr_snippet}",
            transient=not fatal,
            fatal=fatal,
        )

    try:
        data = json.loads(stdout_text)
    except json.JSONDecodeError as exc:
        raise BobShellError(
            f"bob run output is not valid JSON: {exc}. "
            f"First 200 chars: {stdout_text[:200]!r}"
        ) from exc

    if data.get("status") != "success":
        raise BobShellError(
            f"bob run returned status={data.get('status')!r}. "
            f"Response: {stdout_text[:300]}"
        )

    if "last_message" not in data:
        raise BobShellError(
            f"bob run response missing 'last_message' field. "
            f"Keys present: {list(data.keys())}"
        )

    return data["last_message"]

class BobShellSummarizer:
    """Calls Bob Shell non-interactively to produce cited prose summaries.

    Args:
        max_cost: Maximum Bobcoins to spend per call (default 2.0; ~222 calls on a
            50-coin budget at the confirmed ~0.009 coins/call rate).
        max_turns: Maximum conversation turns per call (default 10; keeps prompts
            single-shot since no tools are needed for prose generation).
        timeout: Subprocess timeout in seconds (default 120).
    """

    context_limit = None  # Bob's model window is provider-side and unpublished.

    def __init__(
        self,
        max_cost: float = 2.0,
        max_turns: int = 10,
        timeout: int = 120,
    ) -> None:
        if not os.environ.get("BOB_API_KEY"):
            raise BobShellError(
                "BOB_API_KEY environment variable is not set. "
                "Set it before running docgen with --backend bob_shell.",
                transient=False,
                fatal=True,
            )
        self._bob_exe = _find_bob()
        self._max_cost = max_cost
        self._max_turns = max_turns
        self._timeout = timeout

    def summarize(self, req: SummaryRequest) -> SummaryResult:
        """Build the prompt and call Bob Shell exactly once.

        Raises ``BobShellError`` (a ``BackendError``) on failure; the driver in
        ``hierarchy.py`` decides whether to wait and retry.
        """
        prompt = build_prompt(req)
        text = _call_bob(
            prompt,
            self._bob_exe,
            self._max_cost,
            self._max_turns,
            self._timeout,
        )
        return SummaryResult(
            node_id=req.node_id,
            text=text,
            backend="bob_shell",
            hash_input=hash_input(req),
        )
