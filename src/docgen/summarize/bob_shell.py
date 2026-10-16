"""BobShellSummarizer — calls `bob run --format json` non-interactively.

Why: the trust story of this tool requires that summaries are written by an LLM grounded in
the extracted facts. BobShellSummarizer is the real backend: it pipes the deterministic prompt
built by ``build_prompt(req)`` into Bob Shell and parses the ``last_message`` from the JSON
response.

Confirmed working (D-018): `echo "prompt" | bob run --format json --max-cost 0.1`
Response shape:
    {
        "type": "result",
        "status": "success",   # or "error"
        "stats": {"session_costs": 0.009, "max_cost": 0.1, ...},
        "last_message": "<model response text>"
    }

Nothing in this module reads files or writes summaries.json — that is the caller's job.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .base import SummaryRequest, SummaryResult, hash_input
from .prompts import build_prompt

_RETRY_ATTEMPTS = 2
_RETRY_SLEEP_S = 5


class BobShellError(Exception):
    """Raised when `bob run` fails or returns an unexpected response.

    Caught by ``run_hierarchy`` in hierarchy.py, which writes a
    ``needs_human_review`` placeholder and continues the run.
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
        "Install Bob Shell (https://ibm.biz/bob-shell) and ensure it is on PATH."
    )


def _call_bob(
    prompt: str,
    bob_exe: str,
    max_cost: float,
    max_turns: int,
    timeout: int,
) -> str:
    """Invoke ``bob run --format json`` with *prompt* on stdin.

    Writes the prompt to a temporary file and passes it as stdin to avoid
    any shell-quoting issues with long, multi-line prompts containing JSON
    and code fences.  The temp file is deleted in a ``finally`` block.

    Returns:
        The ``last_message`` string from the JSON response.

    Raises:
        BobShellError: on non-zero exit code, JSON parse failure, or
            ``status != "success"`` in the response.
    """
    cmd = [
        bob_exe, "run",
        "--format", "json",
        "--max-cost", str(max_cost),
        "--max-turns", str(max_turns),
    ]

    # Write prompt to a temp file.  `delete=False` is required on Windows:
    # a NamedTemporaryFile cannot be opened twice while still open.
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", encoding="utf-8", delete=False
    )
    try:
        tmp.write(prompt)
        tmp.flush()
        tmp.close()

        with open(tmp.name, encoding="utf-8") as stdin_fh:
            proc = subprocess.run(
                cmd,
                stdin=stdin_fh,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                timeout=timeout,
            )
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    if proc.returncode != 0:
        stderr_snippet = proc.stderr.strip()[:300]
        raise BobShellError(
            f"bob run exited with code {proc.returncode}: {stderr_snippet}"
        )

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise BobShellError(
            f"bob run output is not valid JSON: {exc}. "
            f"First 200 chars: {proc.stdout[:200]!r}"
        ) from exc

    if data.get("status") != "success":
        raise BobShellError(
            f"bob run returned status={data.get('status')!r}. "
            f"Response: {proc.stdout[:300]}"
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

    def __init__(
        self,
        max_cost: float = 2.0,
        max_turns: int = 10,
        timeout: int = 120,
    ) -> None:
        if not os.environ.get("BOB_API_KEY"):
            raise BobShellError(
                "BOB_API_KEY environment variable is not set. "
                "Set it before running docgen with --backend bob_shell."
            )
        self._bob_exe = _find_bob()
        self._max_cost = max_cost
        self._max_turns = max_turns
        self._timeout = timeout

    def summarize(self, req: SummaryRequest) -> SummaryResult:
        """Build the prompt, call Bob Shell, and return the cited prose.

        Retries once after a 5-second pause on failure.  Raises ``BobShellError``
        if both attempts fail (caught by ``run_hierarchy``).
        """
        prompt = build_prompt(req)
        last_exc: Exception | None = None

        for attempt in range(_RETRY_ATTEMPTS):
            try:
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
            except BobShellError as exc:
                last_exc = exc
                if attempt < _RETRY_ATTEMPTS - 1:
                    time.sleep(_RETRY_SLEEP_S)

        raise BobShellError(
            f"bob run failed after {_RETRY_ATTEMPTS} attempts for {req.node_id!r}: "
            f"{last_exc}"
        ) from last_exc
