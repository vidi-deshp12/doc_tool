"""Plan an incremental update: find which pages and nodes need regeneration.

Why: ``docgen update`` should only re-render pages whose structure changed, and
only re-summarize nodes whose body changed (``hash_source`` differs).  This keeps
update runs cheap when few files change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from docgen.facts.schema import FactGraph


@dataclass
class UpdatePlan:
    """Which pages to re-render and which nodes to re-summarize.

    Attributes:
        stale_pages: Repo-root-relative POSIX paths of pages to regenerate
            (same values as returned by :func:`~docgen.check.drift.find_stale_pages`).
        stale_node_ids: Node IDs whose ``hash_struct`` changed — a subset of the
            nodes that contributed to the stale pages.
        nodes_to_resummarize: Node IDs whose ``hash_source`` also changed, meaning
            the summary prose may be outdated.  Re-summarization is optional and
            only triggered when the caller passes a non-stub backend.
    """

    stale_pages: list[str] = field(default_factory=list)
    stale_node_ids: set[str] = field(default_factory=set)
    nodes_to_resummarize: set[str] = field(default_factory=set)


def plan_update(
    stale_pages: list[str],
    manifest: dict[str, Any],
    graph: FactGraph,
    summaries_map: dict[str, str],
) -> UpdatePlan:
    """Build an :class:`UpdatePlan` from the list of stale page paths.

    For each stale page, inspect every node in its manifest ``hashes`` dict:

    - If ``hash_struct`` changed → add to ``stale_node_ids``.
    - If ``hash_source`` also changed AND the node has an existing summary →
      add to ``nodes_to_resummarize``.

    Args:
        stale_pages: Paths returned by :func:`~docgen.check.drift.find_stale_pages`.
        manifest: Full manifest dict (``{"pages": {...}}``).
        graph: Current fact graph.
        summaries_map: ``{node_id: summary_text}`` from ``summaries.json``.

    Returns:
        An :class:`UpdatePlan` ready for the caller to act on.
    """
    node_map = {n.id: n for n in graph.nodes}
    pages_data: dict[str, Any] = manifest.get("pages", {})

    stale_node_ids: set[str] = set()
    nodes_to_resummarize: set[str] = set()

    for page_path in stale_pages:
        page_data = pages_data.get(page_path, {})
        hashes: dict[str, dict[str, str]] = page_data.get("hashes", {})

        for node_id, recorded in hashes.items():
            node = node_map.get(node_id)
            if node is None:
                # Deleted node — mark stale but nothing to resummarize
                stale_node_ids.add(node_id)
                continue

            recorded_struct = recorded.get("hash_struct", "")
            recorded_source = recorded.get("hash_source", "")

            if node.hash_struct != recorded_struct:
                stale_node_ids.add(node_id)

            if node.hash_source != recorded_source and node_id in summaries_map:
                nodes_to_resummarize.add(node_id)

    return UpdatePlan(
        stale_pages=list(stale_pages),
        stale_node_ids=stale_node_ids,
        nodes_to_resummarize=nodes_to_resummarize,
    )
