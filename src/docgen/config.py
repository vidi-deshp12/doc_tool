"""Load and validate docgen.toml configuration."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Config:
    """Configuration for a docgen run."""

    root: str
    source_root: str
    exclude: tuple[str, ...]
    adapter_name: str
    app: str
    output_dir: str


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
    )