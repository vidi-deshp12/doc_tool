"""Load and validate docgen.toml configuration."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SummarizeConfig:
    """Default model backend settings from ``[summarize]``.

    Empty strings and ``timeout = 0`` mean "use the backend's own default"; the CLI
    resolves them. The backend name is validated by the CLI, not here, so its error
    can list the registry.
    """

    backend: str = "stub"
    model: str = ""
    base_url: str = ""
    api_key_env: str = ""
    timeout: int = 0


@dataclass(frozen=True)
class Config:
    """Configuration for a docgen run."""

    root: str
    source_root: str
    exclude: tuple[str, ...]
    adapter_name: str
    app: str
    output_dir: str
    summarize: SummarizeConfig = SummarizeConfig()


def _summarize_config(data: Any) -> SummarizeConfig:
    """Parse and validate the ``[summarize]`` table."""
    if not isinstance(data, dict):
        raise ValueError("[summarize] must be a table")

    def get_string(key: str, default: str) -> str:
        value = data.get(key, default)
        if not isinstance(value, str):
            raise ValueError(f"summarize.{key} must be a string")
        return value

    timeout = data.get("timeout", 0)
    if isinstance(timeout, bool) or not isinstance(timeout, int):
        raise ValueError("summarize.timeout must be an integer")
    if timeout < 0:
        raise ValueError(f"summarize.timeout must be >= 0, got {timeout}")

    return SummarizeConfig(
        backend=get_string("backend", "stub"),
        model=get_string("model", ""),
        base_url=get_string("base_url", ""),
        api_key_env=get_string("api_key_env", ""),
        timeout=timeout,
    )


def load_config(path: str | Path = "docgen.toml") -> Config:
    """Load and validate configuration from a TOML file.

    Args:
        path: Path to the docgen.toml file.

    Returns:
        A validated Config object.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
        ValueError: If required fields are missing or invalid.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("rb") as f:
        data: dict[str, Any] = tomllib.load(f)

    repo = data.get("repo", {})
    adapter = data.get("adapter", {})
    output = data.get("output", {})

    # Required fields with defaults
    root = repo.get("root", "target")
    source_root = repo.get("source_root", root)
    exclude = tuple(repo.get("exclude", []))
    adapter_name = adapter.get("name", "none")
    app = adapter.get("app", "")
    output_dir = output.get("dir", "generated")

    # Validation
    if not root:
        raise ValueError("repo.root must be a non-empty string")
    if not source_root:
        raise ValueError("repo.source_root must be a non-empty string")
    if adapter_name not in ("fastapi", "none", "flask"):
        raise ValueError(f"Unknown adapter: {adapter_name}")

    return Config(
        root=root,
        source_root=source_root,
        exclude=exclude,
        adapter_name=adapter_name,
        app=app,
        output_dir=output_dir,
        summarize=_summarize_config(data.get("summarize", {})),
    )
