"""Bottom-up hierarchy driver and summary cache.

Why this exists: the flat pass in 2b.1 called the summarizer once per FUNCTION/CLASS/MODULE
node but never passed child summaries to parents, so module- and package-level summaries could
not refer to their children. This module adds:

1. A CONTAINS-edge index so we know which nodes are children of which parent.
2. A topological sort (children before parents) so every parent's children are already
   summarized when the parent's turn arrives.
3. A cache key that is a hash of the exact prompt sent to the backend (plus the backend's
   identity). If the key is unchanged, the summarizer is not called. The prompt already renders
   the node's facts, its residual source, its relational edges, and every child summary, so the
   key is a function of the payload rather than a hand-maintained proxy for it: a change to
   anything the model would read invalidates exactly the nodes it affects.
4. A synthetic "system" root that receives all package-level summaries as children.

Nodes at the same depth of the CONTAINS tree are summarised concurrently when
``run_hierarchy`` is called with ``max_workers > 1``. The ``Summarizer`` protocol
is therefore called from worker threads: implementations must be safe to call
concurrently. The returned results are always assembled by the main thread in
batch order, so ``summaries.json`` is identical regardless of the worker count.

Nothing here performs I/O beyond reading source lines; all I/O (facts.json, summaries.json) is
done by the caller (``_run_summarize`` in cli.py).
"""

from __future__ import annotations

import hashlib
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from docgen.facts.schema import EdgeType, FactGraph, Node, NodeType
from docgen.facts.store import _node_to_dict
from docgen.summarize.base import NodeLevel, Summarizer, SummaryRequest, SummaryResult
from docgen.summarize.prompts import build_prompt

# Node types that participate in summarization. Routes, externals, etc. are skipped.
_SUMMARIZABLE: frozenset[NodeType] = frozenset(
    {NodeType.FUNCTION, NodeType.CLASS, NodeType.MODULE, NodeType.PACKAGE}
)

# Fixed node-id for the synthetic system root.
SYSTEM_NODE_ID = "system"

# Backend identifier for nodes that failed summarization.
# The citation validator skips these entries rather than flagging them as broken.
NEEDS_HUMAN_REVIEW_BACKEND = "needs_human_review"

# Fact fields that are internal to the pipeline and meaningless to a doc writer.
# They are stripped from the dict handed to the summarizer (and therefore from the
# prompt's "Node facts" block). Since the cache key hashes the prompt, this set is
# payload policy: changing it changes what is sent, and only that.
#
# "lines" is dropped on purpose. Line numbers are not citable and the renderers read
# them from facts.json, and leaving them in the prompt would make a blank line inserted
# at the top of a file regenerate every node in it (the extractor's own hashes are
# token-based and ignore such a shift).
#
# "file" must stay: ``prompts.allowed_fact_ids`` reads it to make the module id citeable
# from a function prompt. If it is ever dropped here, derive the module id from the node
# id in ``allowed_fact_ids`` instead.
_PROMPT_FACTS_DROP: frozenset[str] = frozenset({
    "type",
    "lines",
    "hash_struct",
    "hash_source",
    "what",
    "why",
    "where",
    "variable",
    "prefix",
})


def _prompt_facts(facts: dict[str, Any]) -> dict[str, Any]:
    """The fact dict actually sent to the summarizer, and therefore hashed."""
    return {k: v for k, v in facts.items() if k not in _PROMPT_FACTS_DROP}


# ---------------------------------------------------------------------------
# Source-text reader (moved here from cli.py; not CLI-specific)
# ---------------------------------------------------------------------------

def read_source_text(repo_root: Path, node: Node) -> str:
    """Return the raw source lines for *node*, or "" if the file cannot be read.

    ``node.file`` is repo-root-relative POSIX; ``node.lines`` is a 1-indexed
    inclusive (start, end) pair. Failures degrade to "" so the summarizer always
    receives a valid (possibly empty) string.
    """
    if not node.file:
        return ""
    start, end = node.lines
    if start <= 0 or end < start:
        return ""
    path = repo_root / node.file
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return ""
    return "\n".join(lines[start - 1 : end])


def read_residual_source(repo_root: Path, node: Node, children: list[Node]) -> str:
    """Source inside *node*'s span that no direct child already covers.

    A child is described by its own summary, so sending its code as well would put
    the same information in the prompt twice (once as prose, once as source). What
    a parent still needs from its own span is everything that has no child summary:
    the class header and docstring, a class-level constant between methods, a
    module's imports and constants.

    Nodes with no children, children in another file, and unreadable files fall back
    to the full span. The result is whitespace-normalised so a reformat inside a
    child cannot change this node's cache key.
    """
    full = read_source_text(repo_root, node)
    if not children or not full:
        return full

    start, end = node.lines
    if start <= 0 or end < start:
        return ""

    # Covered ranges are node-relative 1-indexed line numbers, clamped to this
    # node's own span. ``child.lines`` starts at the first decorator line, so
    # decorators are covered too.
    covered: list[tuple[int, int]] = []
    for child in children:
        if child.file != node.file:
            continue
        c_start, c_end = child.lines
        if c_start <= 0 or c_end < c_start:
            continue
        c_start, c_end = max(c_start, start), min(c_end, end)
        if c_end < c_start:
            continue
        covered.append((c_start, c_end))

    covered.sort()
    merged: list[tuple[int, int]] = []
    for c_start, c_end in covered:
        # Overlapping or adjacent ranges merge; an adjacency only yields a blank
        # line, which normalisation would drop anyway.
        if merged and c_start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], c_end))
        else:
            merged.append((c_start, c_end))

    lines = full.splitlines()
    kept: list[str] = []
    cursor = 0  # 0-indexed position in ``lines``, relative to the node span
    for c_start, c_end in merged:
        kept.extend(lines[cursor : c_start - start])
        cursor = c_end - start + 1
    kept.extend(lines[cursor:])

    # Normalise: strip trailing whitespace, collapse runs of blank lines, drop
    # leading/trailing blanks.
    out: list[str] = []
    for line in kept:
        stripped = line.rstrip()
        if not stripped:
            if not out or out[-1] == "":
                continue
            out.append("")
        else:
            out.append(stripped)
    while out and out[-1] == "":
        out.pop()

    return "\n".join(out)


# ---------------------------------------------------------------------------
# Cache key
# ---------------------------------------------------------------------------

def hash_prompt(prompt: str) -> str:
    """Cache key for one summarizer call: SHA-256 of the exact text sent.

    Deterministic: an identical prompt always produces the identical digest. Because
    the prompt is the model's entire input, the key answers "would this call produce
    the same output?" by construction instead of by agreement between the key and the
    prompt builder.
    """
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _summarizer_identity(summarizer: Summarizer) -> str:
    """Which backend would produce the prose.

    ``name`` is an optional, documented protocol attribute; the class name is the
    fallback so third-party backends (and test doubles) need no change. Including it
    in the key means ``--backend`` switches never reuse another provider's prose.
    """
    return str(getattr(summarizer, "name", type(summarizer).__name__))


# ---------------------------------------------------------------------------
# CONTAINS index + topological sort
# ---------------------------------------------------------------------------

def build_contains_index(graph: FactGraph) -> dict[str, list[Node]]:
    """Return a mapping from parent node id to the list of its direct CONTAINS children.

    Only summarizable node types (FUNCTION, CLASS, MODULE, PACKAGE) appear on either
    side. Non-summarizable nodes (ROUTE, EXTERNAL, UNRESOLVED, …) are excluded so the
    hierarchy driver never tries to summarize them.
    """
    summarizable_ids: set[str] = {n.id for n in graph.nodes if n.type in _SUMMARIZABLE}
    index: dict[str, list[Node]] = {}
    node_map: dict[str, Node] = {n.id: n for n in graph.nodes}

    for edge in graph.edges:
        if edge.type is not EdgeType.CONTAINS:
            continue
        if edge.from_id not in summarizable_ids:
            continue
        if edge.to_id not in summarizable_ids:
            continue
        child_node = node_map.get(edge.to_id)
        if child_node is None:
            continue
        index.setdefault(edge.from_id, []).append(child_node)

    # Sort children deterministically for reproducible output.
    for children in index.values():
        children.sort()

    return index


def topological_order(
    graph: FactGraph, index: dict[str, list[Node]]
) -> list[Node]:
    """Return summarizable nodes in bottom-up (children-before-parents) order.

    Uses an iterative post-order DFS. Nodes that appear as children in the index
    are visited before their parents. Nodes with no parent (package-level roots) are
    visited last before the synthetic system node (which is not returned here).
    """
    summarizable: list[Node] = [n for n in graph.nodes if n.type in _SUMMARIZABLE]

    # Determine which nodes have a summarizable CONTAINS parent.
    child_ids: set[str] = set()
    for children in index.values():
        for child in children:
            child_ids.add(child.id)

    # Roots are summarizable nodes with no summarizable CONTAINS parent.
    root_nodes = [n for n in summarizable if n.id not in child_ids]

    visited: set[str] = set()
    order: list[Node] = []

    def _visit(node: Node) -> None:
        if node.id in visited:
            return
        for child in index.get(node.id, []):
            _visit(child)
        visited.add(node.id)
        order.append(node)

    for root in sorted(root_nodes):  # sort for determinism
        _visit(root)

    # Any summarizable node not reachable from the roots (orphans) gets appended at the end.
    for node in sorted(summarizable):
        if node.id not in visited:
            _visit(node)

    return order


def batched_topological_order(
    graph: FactGraph, index: dict[str, list[Node]]
) -> list[list[Node]]:
    """Return summarizable nodes grouped into bottom-up batches by CONTAINS depth.

    Every node in a batch has all of its summarizable children in an earlier
    batch, so a batch can be summarised concurrently. Leaf nodes form batch 0;
    packages (and the synthetic system node, handled separately) come last.

    The depth of a node is ``max(depth(child) for child in children) + 1``, or 0
    for a node with no summarizable children. Depth, not ``NodeType``, is the
    correct signal: a module containing only functions is shallower than a module
    containing classes, whose methods are themselves a level down.

    Batches are deterministic: nodes within a batch are sorted by their natural
    (id) ordering, and empty depths are dropped.
    """
    memo: dict[str, int] = {}

    def _depth(node_id: str) -> int:
        if node_id in memo:
            return memo[node_id]
        children = index.get(node_id, [])
        depth = max((_depth(child.id) for child in children), default=-1) + 1
        memo[node_id] = depth
        return depth

    summarizable = [n for n in graph.nodes if n.type in _SUMMARIZABLE]
    depth_map = {n.id: _depth(n.id) for n in summarizable}
    max_depth = max(depth_map.values(), default=0)

    batches: list[list[Node]] = [[] for _ in range(max_depth + 1)]
    for node in sorted(summarizable):
        batches[depth_map[node.id]].append(node)
    return [batch for batch in batches if batch]


# ---------------------------------------------------------------------------
# Relational-edge index (mirrors the logic in cli._run_summarize)
# ---------------------------------------------------------------------------

def _build_edges_by_from(graph: FactGraph) -> dict[str, list[dict[str, Any]]]:
    """Index relational edges by the node that should see them in its SummaryRequest.

    For raises/depends_on/calls/inherits: indexed by ``from_id`` (the function).
    For request_model/response_model: indexed by ``from_id`` (the route) *and* by the
    handler function of that route. Route nodes are never summarized, so without the
    second copy the models would never reach the prompt that needs them.
    For handles: indexed by ``to_id`` (the handler function) so the handler sees
    which route it serves.  This lets the function's prompt mention the full path,
    method, and status code, and lets the handler cite its own route ID.
    """
    from docgen.facts.schema import EdgeType as ET  # local import to avoid cycle confusion

    by_from_types = {
        ET.RAISES,
        ET.DEPENDS_ON,
        ET.CALLS,
        ET.INHERITS,
        ET.REQUEST_MODEL,
        ET.RESPONSE_MODEL,
    }
    # route_id -> handler function ids, used to hand model edges to the handler.
    handlers_by_route: dict[str, list[str]] = {}
    for edge in graph.edges:
        if edge.type is ET.HANDLES:
            handlers_by_route.setdefault(edge.from_id, []).append(edge.to_id)

    result: dict[str, list[dict[str, Any]]] = {}
    for edge in graph.edges:
        edge_dict = {
            "type": edge.type.value,
            "from": edge.from_id,
            "to": edge.to_id,
            "meta": dict(edge.meta),
        }
        if edge.type in by_from_types:
            result.setdefault(edge.from_id, []).append(edge_dict)
        elif edge.type is ET.HANDLES:
            # Index by the handler function (to_id) so the function sees it
            result.setdefault(edge.to_id, []).append(edge_dict)

        if edge.type in (ET.REQUEST_MODEL, ET.RESPONSE_MODEL):
            # The route is the edge's source; the handler is who needs the model.
            for handler_id in handlers_by_route.get(edge.from_id, []):
                result.setdefault(handler_id, []).append(edge_dict)
    return result


def _node_level(node: Node) -> NodeLevel:
    """Map a Node to its NodeLevel for the summarizer."""
    if node.type is NodeType.FUNCTION:
        return "method" if node.parent_class else "function"
    if node.type is NodeType.CLASS:
        return "class"
    if node.type is NodeType.PACKAGE:
        return "package"
    return "module"


def _call_summarizer(
    summarizer: Summarizer,
    req: SummaryRequest,
    cache_key: str,
) -> SummaryResult:
    """Call *summarizer* and return a SummaryResult with *cache_key* as hash_input.

    On any exception: prints a WARN line to stderr, returns a ``needs_human_review``
    placeholder with ``hash_input=""`` so the node is re-attempted on the next run.
    The run continues — one failing node never aborts the whole pipeline.
    """
    try:
        result = summarizer.summarize(req)
        return SummaryResult(
            node_id=result.node_id,
            text=result.text,
            backend=result.backend,
            hash_input=cache_key,
        )
    except Exception as exc:  # noqa: BLE001
        print(
            f"  WARN: summarizer failed for {req.node_id!r}: {exc}",
            file=sys.stderr,
        )
        return SummaryResult(
            node_id=req.node_id,
            text="[needs_human_review]",
            backend=NEEDS_HUMAN_REVIEW_BACKEND,
            hash_input="",  # empty → always retried on next run
        )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_hierarchy(
    graph: FactGraph,
    summarizer: Summarizer,
    repo_root: Path,
    existing_cache: dict[str, SummaryResult],
    max_workers: int = 1,
) -> list[SummaryResult]:
    """Summarize all nodes bottom-up and return the complete list of SummaryResults.

    Args:
        graph: The fully-extracted fact graph.
        summarizer: The backend to call when a node is not in the cache. It may be
            called concurrently from worker threads; implementations must be
            thread-safe (the shipped backends are stateless per call).
        repo_root: Absolute path to the repository root, used to read source text.
        existing_cache: Node-id → SummaryResult from a previous run. Nodes whose
            cached ``hash_input`` matches the hash of the prompt this run would send
            are skipped.
        max_workers: Node-level concurrency within a depth batch (default 1 =
            sequential). Values below 1 are clamped to 1.

    Returns:
        One SummaryResult per summarizable node plus a synthetic system-level result.
        Results are ordered: bottom-up batch order for real nodes, system last.
        That order — and therefore ``summaries.json`` — is identical for every
        ``max_workers`` value.
    """
    max_workers = max(1, int(max_workers))

    index = build_contains_index(graph)
    batches = batched_topological_order(graph, index)
    edges_by_from = _build_edges_by_from(graph)

    # Accumulated results, keyed by node_id for child-summary lookup. Written by
    # the main thread only; workers return results and never touch this dict.
    results: dict[str, SummaryResult] = {}

    # Constant for the whole run: which backend would answer. Part of every key.
    summarizer_identity = _summarizer_identity(summarizer)

    def _cache_key(prompt: str) -> str:
        return hash_prompt(summarizer_identity + "\n" + prompt)

    def _process_node(node: Node) -> SummaryResult:
        children = index.get(node.id, [])
        req = SummaryRequest(
            node_id=node.id,
            level=_node_level(node),
            facts=_prompt_facts(_node_to_dict(node)),
            source_text=read_residual_source(repo_root, node, children),
            child_summaries=[results[c.id] for c in children if c.id in results],
            edges=edges_by_from.get(node.id, []),
        )

        cache_key = _cache_key(build_prompt(req))
        cached = existing_cache.get(node.id)
        if cached is not None and cached.hash_input == cache_key:
            return cached

        return _call_summarizer(summarizer, req, cache_key)

    for batch in batches:
        if max_workers <= 1 or len(batch) == 1:
            pairs = [(node, _process_node(node)) for node in batch]
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = [
                    (node, pool.submit(_process_node, node)) for node in batch
                ]
                # Collect in submission order, not completion order: this keeps
                # summaries.json byte-identical to the sequential run.
                pairs = [(node, future.result()) for node, future in futures]

        for node, result in pairs:
            results[node.id] = result

    # Synthetic system-level summary: child_summaries = all package summaries.
    package_results = sorted(
        (r for n, r in results.items() if _node_type_for_id(n, graph) is NodeType.PACKAGE),
        key=lambda r: r.node_id,
    )
    system_req = SummaryRequest(
        node_id=SYSTEM_NODE_ID,
        level="system",
        facts={},
        source_text="",
        child_summaries=package_results,
        edges=[],
    )
    system_key = _cache_key(build_prompt(system_req))
    cached_system = existing_cache.get(SYSTEM_NODE_ID)
    if cached_system is not None and cached_system.hash_input == system_key:
        system_result = cached_system
    else:
        system_result = _call_summarizer(summarizer, system_req, system_key)

    return list(results.values()) + [system_result]


def _node_type_for_id(node_id: str, graph: FactGraph) -> NodeType | None:
    """Look up the NodeType for a node_id in the graph. Returns None if not found."""
    for node in graph.nodes:
        if node.id == node_id:
            return node.type
    return None
