"""Contract tests for ClaudeShellSummarizer. No real Claude call is made."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from docgen.summarize import claude_shell
from docgen.summarize.base import SummaryRequest
from docgen.summarize.claude_shell import (
    ClaudeShellError,
    ClaudeShellSummarizer,
    _powershell_command,
)

_EXE = "C:/fake/claude.exe"


def _request(node_id: str = "mod.py::f") -> SummaryRequest:
    return SummaryRequest(
        node_id=node_id,
        level="function",
        facts={"hash_struct": "hs", "hash_source": "hsrc", "file": "mod.py"},
        source_text="def f():\n    return 1\n",
    )


def _fake_run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    auth_method: str = "claude.ai",
    payload: dict | None = None,
    stdout: str | None = None,
    returncode: int = 0,
    stderr: str = "",
) -> list[tuple[list[str], dict]]:
    calls: list[tuple[list[str], dict]] = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        if argv[1:3] == ["auth", "status"]:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"authMethod": auth_method}),
                stderr="",
            )
        body = payload if payload is not None else {
            "is_error": False,
            "result": "A function that returns one. [[mod.py::f]]",
        }
        return SimpleNamespace(
            returncode=returncode,
            stdout=stdout if stdout is not None else json.dumps(body),
            stderr=stderr,
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def _summarizer(**kwargs) -> ClaudeShellSummarizer:
    return ClaudeShellSummarizer(model="sonnet", claude_exe=_EXE, **kwargs)


def test_missing_executable_is_fatal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(claude_shell.shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        claude_shell.Path, "home", classmethod(lambda cls: tmp_path)
    )

    with pytest.raises(ClaudeShellError, match="not found") as excinfo:
        ClaudeShellSummarizer()

    assert excinfo.value.fatal
    assert not excinfo.value.transient


def test_auth_none_is_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_run(monkeypatch, auth_method="none")

    with pytest.raises(ClaudeShellError, match="claude auth login") as excinfo:
        _summarizer()

    assert excinfo.value.fatal


def test_auth_api_key_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_run(monkeypatch, auth_method="api_key")

    with pytest.raises(ClaudeShellError, match="subscription") as excinfo:
        _summarizer()

    assert excinfo.value.fatal
    assert not excinfo.value.transient


@pytest.mark.parametrize("method", ["claude.ai", "oauth_token"])
def test_subscription_auth_methods_construct(
    monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    _fake_run(monkeypatch, auth_method=method)

    summarizer = _summarizer()

    assert summarizer.name.startswith("claude_shell:sonnet:")


def test_child_env_strips_api_key_but_keeps_oauth_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-not-be-used")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-token")
    calls = _fake_run(monkeypatch)

    _summarizer().summarize(_request())

    summary_argv, summary_kwargs = next(
        (argv, kwargs) for argv, kwargs in calls if argv[1] == "-p"
    )
    assert summary_argv
    assert "ANTHROPIC_API_KEY" not in summary_kwargs["env"]
    assert summary_kwargs["env"]["CLAUDE_CODE_OAUTH_TOKEN"] == "oauth-token"


def test_argv_uses_lean_flags_and_prompt_is_not_in_argv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _fake_run(monkeypatch)

    _summarizer().summarize(_request())

    argv, kwargs = next((argv, kwargs) for argv, kwargs in calls if argv[1] == "-p")
    for flag in (
        "--output-format",
        "--safe-mode",
        "--no-session-persistence",
        "--tools",
        "--disallowedTools",
        "--system-prompt",
        "--model",
    ):
        assert flag in argv
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--disallowedTools") + 1] == "mcp__*"
    assert argv[argv.index("--model") + 1] == "sonnet"
    assert "--bare" not in argv
    assert "PROMPT_VERSION" not in " ".join(argv)
    assert "PROMPT_VERSION" in kwargs["input"]


def test_success_returns_summary_and_makes_one_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _fake_run(monkeypatch)

    result = _summarizer().summarize(_request())

    assert result.node_id == "mod.py::f"
    assert result.text.startswith("A function")
    assert result.backend == "claude_shell:sonnet"
    assert sum(1 for argv, _ in calls if argv[1] == "-p") == 1


def test_error_is_one_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _fake_run(monkeypatch, stdout="not json")

    with pytest.raises(ClaudeShellError):
        _summarizer().summarize(_request())

    assert sum(1 for argv, _ in calls if argv[1] == "-p") == 1


def test_usage_limit_is_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_run(
        monkeypatch,
        payload={
            "is_error": True,
            "result": "Claude usage limit reached. Resets at 5pm.",
        },
        returncode=1,
    )

    with pytest.raises(ClaudeShellError) as excinfo:
        _summarizer().summarize(_request())

    assert excinfo.value.fatal
    assert not excinfo.value.transient


@pytest.mark.parametrize(
    "stdout",
    ["not json", json.dumps({"is_error": False, "result": ""})],
)
def test_transient_failures_are_retryable(
    monkeypatch: pytest.MonkeyPatch, stdout: str
) -> None:
    _fake_run(monkeypatch, stdout=stdout)

    with pytest.raises(ClaudeShellError) as excinfo:
        _summarizer().summarize(_request())

    assert excinfo.value.transient
    assert not excinfo.value.fatal


def test_name_hashes_the_system_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_run(monkeypatch)

    first = _summarizer()
    original = claude_shell._SYSTEM_PROMPT
    monkeypatch.setattr(claude_shell, "_SYSTEM_PROMPT", original + " Be terse.")
    second = _summarizer()

    assert first.name != second.name
    assert first.name.startswith("claude_shell:sonnet:")
    assert len(first.name.rsplit(":", 1)[1]) == 8


def test_powershell_command_uses_a_prompt_file_not_prompt_text() -> None:
    command = _powershell_command(
        "C:/Program Files/claude.cmd", ["-p", "--tools", ""], "C:/tmp/prompt.txt"
    )

    assert "Get-Content -Encoding UTF8 -Raw 'C:/tmp/prompt.txt'" in command
    assert "& 'C:/Program Files/claude.cmd'" in command
    assert command.count("''") >= 1  # the empty --tools value
