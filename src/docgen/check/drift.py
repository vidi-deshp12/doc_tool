"""Compare manifest.json hashes against the current fact graph to find stale pages.

Why: ``docgen check`` needs a pure function that takes the manifest and the current
graph and returns which pages need regenerating.  Keeping this separate from I/O
makes it straightforward to test without touching the filesystem.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from docgen.facts.schema import FactGraph


def find_stale_pages(manifest: dict[str, Any], graph: FactGraph) -> list[str]:
    """Return repo-root-relative POSIX paths of pages whose ``hash_struct`` changed.

    A page is stale when at least one of its recorded ``hash_struct`` values
    differs from the current graph, or when a recorded node ID is absent from
    the current graph entirely.

    ``hash_source``-only changes are *not* considered drift — the rendered
    Markdown for a page only changes when the structure changes (signature,
    decorator, route path, model field).  A body-only change may mean the
    existing summary is slightly outdated, but the rendered page is not stale
    until the summary is regenerated (handled by the hierarchy cache).

    Args:
        manifest: Dict as returned by :func:`~docgen.check.manifest.read_manifest`.
        graph: The current (possibly re-extracted) fact graph.

    Returns:
        Sorted list of stale page paths.
    """
    node_hash_struct: dict[str, str] = {n.id: n.hash_struct for n in graph.nodes}

    stale: list[str] = []
    pages: dict[str, Any] = manifest.get("pages", {})

    for page_path, page_data in pages.items():
        hashes: dict[str, dict[str, str]] = page_data.get("hashes", {})
        page_stale = False
        for node_id, recorded in hashes.items():
            recorded_struct = recorded.get("hash_struct", "")
            if node_id not in node_hash_struct:
                # Node was deleted — structural change
                page_stale = True
                break
            if node_hash_struct[node_id] != recorded_struct:
                page_stale = True
                break
        if page_stale:
            stale.append(page_path)

    return sorted(stale)


def warn_if_facts_stale(facts_path: Path, manifest_path: Path) -> None:
    """Print a stderr warning when ``facts.json`` is older than ``manifest.json``.

    This catches the footgun where a developer runs ``docgen check``, sees "all
    good," but ``facts.json`` is days old so the check was against stale data.
    The check still runs — this is a warning, not an error.
    """
    if facts_path.stat().st_mtime < manifest_path.stat().st_mtime:
        print(
            "WARNING: facts.json predates manifest.json — "
            "run 'docgen extract' first or use --fresh",
            file=sys.stderr,
        )
