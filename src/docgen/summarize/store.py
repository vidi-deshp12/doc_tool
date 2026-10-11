"""Stable JSON read/write for summaries (sorted keys, no timestamps, UTF-8).

Parallel to `facts/store.py`: same determinism rules so the same inputs always
produce the byte-identical file.
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import SummaryResult


def _result_to_dict(result: SummaryResult) -> dict[str, str]:
    """Convert a SummaryResult to a dictionary for JSON serialization."""
    return {
        "node_id": result.node_id,
        "text": result.text,
        "backend": result.backend,
        "hash_input": result.hash_input,
    }


def _dict_to_result(d: dict[str, str]) -> SummaryResult:
    """Convert a dictionary back into a SummaryResult."""
    return SummaryResult(
        node_id=d["node_id"],
        text=d["text"],
        backend=d["backend"],
        hash_input=d["hash_input"],
    )


def write_summaries(results: list[SummaryResult], path: str | Path) -> None:
    """Write summaries to a JSON file with stable, deterministic output.

    Args:
        results: The summaries to write (order is preserved as given).
        path: Output file path.
    """
    data = {"summaries": [_result_to_dict(r) for r in results]}

    Path(path).write_text(
        json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_summaries(path: str | Path) -> list[SummaryResult]:
    """Read summaries from a JSON file.

    Args:
        path: Input file path.

    Returns:
        The deserialized list of SummaryResult, in file order.
    """
    text = Path(path).read_text(encoding="utf-8")
    data = json.loads(text)
    return [_dict_to_result(d) for d in data.get("summaries", [])]
