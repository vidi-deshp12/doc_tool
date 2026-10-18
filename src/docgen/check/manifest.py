"""Read/write generated/manifest.json — page → fact IDs + hashes at generation time.

Why: the drift checker (check/drift.py) needs a stable record of which fact hashes
each doc page was built from.  Writing the manifest is the last step of every
``docgen render`` run.  Reading it is the first step of ``docgen check``.

All paths stored in the manifest are repo-root-relative POSIX (forward slashes),
matching the convention in facts.json.  This means manifest keys look like
``"generated/pages/index.md"`` not ``"pages/index.md"`` or an absolute path.

``hash_struct`` is the drift signal: a structural change (signature, decorator,
route path, model) makes a page stale.
``hash_source`` is the re-summarization trigger: a body/comment change means the
existing summary may be outdated, but the rendered page is only stale if the
summary actually changes (handled by the cache in hierarchy.py).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PageRecord:
    """What a single rendered page depended on at generation time.

    Attributes:
        page_path: Repo-root-relative POSIX path of the generated page
            (e.g. ``"generated/pages/index.md"``).
        fact_ids: Ordered list of node IDs whose facts were read when building
            this page.
        hashes: ``{node_id: {"hash_struct": "...", "hash_source": "..."}}``.
            Only nodes with non-empty hashes are stored.
    """

    page_path: str
    fact_ids: list[str] = field(default_factory=list)
    hashes: dict[str, dict[str, str]] = field(default_factory=dict)


def build_manifest(records: list[PageRecord]) -> dict[str, Any]:
    """Build the manifest dict from a list of PageRecords.

    Returns a dict ready for JSON serialisation.  Keys are page paths;
    values contain the ``fact_ids`` list and the ``hashes`` dict.
    """
    pages: dict[str, Any] = {}
    for rec in records:
        pages[rec.page_path] = {
            "fact_ids": sorted(set(rec.fact_ids)),
            "hashes": {
                node_id: {
                    "hash_source": h.get("hash_source", ""),
                    "hash_struct": h.get("hash_struct", ""),
                }
                for node_id, h in sorted(rec.hashes.items())
                if h.get("hash_struct") or h.get("hash_source")
            },
        }
    return {"pages": pages}


def write_manifest(manifest: dict[str, Any], path: str | Path) -> None:
    """Write the manifest dict to *path* with stable JSON formatting."""
    Path(path).write_text(
        json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_manifest(path: str | Path) -> dict[str, Any]:
    """Read and return the manifest dict from *path*."""
    return json.loads(Path(path).read_text(encoding="utf-8"))
