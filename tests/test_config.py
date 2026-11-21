"""Tests for [summarize] parsing and CLI > config > default precedence."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from docgen.cli import _resolve_summarize_settings
from docgen.config import load_config


def _write_config(tmp_path: Path, summarize: str = "", timeout: int | None = None) -> Path:
    text = (
        "[repo]\n"
        'root = "."\n'
        'source_root = "."\n'
        "exclude = []\n"
        "\n[adapter]\n"
        'name = "none"\n'
        "\n[output]\n"
        'dir = "out"\n'
    )
    if summarize:
        text += "\n[summarize]\n" + summarize
    if timeout is not None:
        text += f"\ntimeout = {timeout}\n"
    path = tmp_path / "docgen.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_absent_summarize_section_uses_defaults(tmp_path: Path) -> None:
    config = load_config(_write_config(tmp_path))

    assert config.summarize.backend == "stub"
    assert config.summarize.model == ""
    assert config.summarize.base_url == ""
    assert config.summarize.api_key_env == ""
    assert config.summarize.timeout == 0


def test_full_summarize_section_is_parsed(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        'backend = "openai"\n'
        'model = "qwen2.5-coder:7b"\n'
        'base_url = "http://localhost:11434/v1"\n'
        'api_key_env = "GROQ_API_KEY"\n'
        "timeout = 45\n",
    )

    summarize = load_config(path).summarize

    assert summarize.backend == "openai"
    assert summarize.model == "qwen2.5-coder:7b"
    assert summarize.base_url == "http://localhost:11434/v1"
    assert summarize.api_key_env == "GROQ_API_KEY"
    assert summarize.timeout == 45


def test_cli_backend_overrides_config_and_config_overrides_default(
    tmp_path: Path,
) -> None:
    config = load_config(_write_config(tmp_path, 'backend = "openai"\n'))

    from_config = _resolve_summarize_settings(
        argparse.Namespace(backend=None), config
    )
    assert from_config.backend == "openai"

    from_cli = _resolve_summarize_settings(
        argparse.Namespace(backend="claude_shell"), config
    )
    assert from_cli.backend == "claude_shell"

    default = _resolve_summarize_settings(argparse.Namespace(backend=None), None)
    assert default.backend == "stub"


def test_cli_model_and_base_url_override_config(tmp_path: Path) -> None:
    config = load_config(
        _write_config(
            tmp_path,
            'backend = "openai"\n'
            'model = "config-model"\n'
            'base_url = "http://config.example/v1"\n'
            'api_key_env = "CONFIG_KEY"\n'
            "timeout = 30\n",
        )
    )

    merged = _resolve_summarize_settings(
        argparse.Namespace(
            backend=None,
            model="cli-model",
            base_url="http://cli.example/v1",
            api_key_env="CLI_KEY",
            timeout=5,
        ),
        config,
    )
    assert merged.model == "cli-model"
    assert merged.base_url == "http://cli.example/v1"
    assert merged.api_key_env == "CLI_KEY"
    assert merged.timeout == 5


def test_empty_cli_values_defer_to_config(tmp_path: Path) -> None:
    config = load_config(
        _write_config(
            tmp_path,
            'model = "config-model"\n'
            'base_url = "http://config.example/v1"\n'
            'api_key_env = "CONFIG_KEY"\n'
            "timeout = 30\n",
        )
    )

    merged = _resolve_summarize_settings(
        argparse.Namespace(
            backend=None,
            model="",
            base_url="",
            api_key_env="",
            timeout=0,
        ),
        config,
    )
    assert merged.model == "config-model"
    assert merged.base_url == "http://config.example/v1"
    assert merged.api_key_env == "CONFIG_KEY"
    assert merged.timeout == 30


def test_unknown_backend_exits_listing_all_names(tmp_path: Path) -> None:
    from docgen.cli import _build_summarizer

    with pytest.raises(SystemExit) as excinfo:
        _build_summarizer(argparse.Namespace(backend="nope"), tmp_path)

    message = str(excinfo.value)
    for name in ("stub", "manual", "bob_shell", "claude_shell", "openai", "anthropic"):
        assert name in message


def test_negative_timeout_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timeout"):
        load_config(_write_config(tmp_path, "timeout = -1\n"))


def test_claude_shell_warns_at_construction_when_workers_exceed_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import docgen.cli as cli

    monkeypatch.setitem(
        cli._BACKEND_FACTORIES, "claude_shell", lambda *args: object()
    )

    cli._build_summarizer(
        argparse.Namespace(backend="claude_shell", workers=2), tmp_path
    )

    err = capsys.readouterr().err
    assert "WARN" in err
    assert "claude_shell" in err
    assert "--workers 1" in err

    capsys.readouterr()
    cli._build_summarizer(
        argparse.Namespace(backend="claude_shell", workers=1), tmp_path
    )
    assert capsys.readouterr().err == ""
