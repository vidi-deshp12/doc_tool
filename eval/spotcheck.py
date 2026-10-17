"""Entailment spot-check: sample cited claims from summaries.json and build a
hand-grading CSV sheet.

Why this exists: the citation validator (2b.4) checks that [[id]] references
exist in facts.json and that every sentence carries a citation. It cannot check
*semantic* grounding — whether the cited fact actually supports the claim.

This module extracts (sentence, cited_id) pairs, looks up a human-readable
snippet for each cited fact, and writes a CSV that a human (or Bob in the IDE)
can grade (verdict: 1 = supported, 0 = not, ? = unclear). The sheet is the
artefact for task 2b.5 / PRD §8 claim-precision measurement.

Nothing here calls an LLM. All I/O is delegated to the CLI wrapper.
"""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path
from typing import Any

from docgen.facts.schema import FactGraph
from docgen.summarize.base import SummaryResult
from docgen.summarize.citations import _split_sentences
from docgen.summarize.hierarchy import NEEDS_HUMAN_REVIEW_BACKEND, read_source_text
from docgen.summarize.prompts import extract_citations


# ---------------------------------------------------------------------------
# Sub-task 1: claim extraction
# ---------------------------------------------------------------------------

def extract_claims(summaries: list[SummaryResult]) -> list[dict[str, str]]:
    """Return one dict per (sentence, cited_id) pair across all summaries.

    Skips summaries whose backend is NEEDS_HUMAN_REVIEW_BACKEND. Sentences
    with no citations produce no rows (nothing to grade). A sentence with two
    citations produces two rows (same sentence, different cited_id).

    Keys: ``node_id``, ``sentence``, ``cited_id``.
    """
    claims: list[dict[str, str]] = []
    for result in summaries:
        if result.backend == NEEDS_HUMAN_REVIEW_BACKEND:
            continue
        for sentence in _split_sentences(result.text):
            for cited_id in extract_citations(sentence):
                claims.append({
                    "node_id": result.node_id,
                    "sentence": sentence,
                    "cited_id": cited_id,
                })
    return claims


# ---------------------------------------------------------------------------
# Sub-task 2: fact snippet lookup
# ---------------------------------------------------------------------------

def get_fact_snippet(
    node_id: str,
    graph: FactGraph,
    repo_root: Path,
) -> tuple[str, str]:
    """Return ``(fact_type, fact_snippet)`` for *node_id*.

    Priority for the snippet:
    1. ``node.docstring`` (most human-readable)
    2. ``node.signature`` (for functions / methods)
    3. First 200 characters of raw source text (re-read from disk)
    4. Just the id and type as a fallback

    Unknown ids (external:…, system, or anything not in the graph) return
    ``("external", "(external — no source)")``.
    """
    if node_id.startswith("external:") or node_id == "system":
        return ("external", "(external — no source)")

    node_map = {n.id: n for n in graph.nodes}
    node = node_map.get(node_id)
    if node is None:
        return ("external", "(external — no source)")

    fact_type = node.type.value

    if node.docstring:
        return (fact_type, node.docstring[:300])

    if node.signature:
        return (fact_type, node.signature)

    source = read_source_text(repo_root, node)
    if source:
        return (fact_type, source[:200])

    return (fact_type, f"(no snippet — {node_id})")


# ---------------------------------------------------------------------------
# Sub-task 3: sample + write CSV
# ---------------------------------------------------------------------------

def sample_claims(
    claims: list[dict[str, str]],
    n: int,
    seed: int = 42,
) -> list[dict[str, str]]:
    """Return a deterministic random sample of *claims* of size ``min(n, len(claims))``.

    Uses ``random.Random(seed).sample`` for reproducibility — same seed always
    gives the same subset.
    """
    k = min(n, len(claims))
    if k == 0:
        return []
    return random.Random(seed).sample(claims, k)


def write_spotcheck_csv(rows: list[dict[str, Any]], path: Path) -> None:
    """Write a hand-grading sheet to *path* as UTF-8 CSV.

    Columns: ``row, node_id, sentence, cited_id, fact_type, fact_snippet, verdict``.
    Rows are sorted by ``(node_id, sentence)`` for determinism. The ``verdict``
    column is blank — the human (or Bob) fills it in.
    """
    sorted_rows = sorted(rows, key=lambda r: (r["node_id"], r["sentence"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["row", "node_id", "sentence", "cited_id", "fact_type", "fact_snippet", "verdict"])
        for i, row in enumerate(sorted_rows, start=1):
            writer.writerow([
                i,
                row["node_id"],
                row["sentence"],
                row["cited_id"],
                row.get("fact_type", ""),
                row.get("fact_snippet", ""),
                "",  # verdict — blank for grader
            ])


def run_spotcheck(
    summaries: list[SummaryResult],
    graph: FactGraph,
    repo_root: Path,
    n: int,
    seed: int,
    output_path: Path,
) -> int:
    """Orchestrate the full spotcheck pipeline.

    Extracts all claims → samples *n* → looks up snippets → writes CSV.
    Returns the number of rows written.
    """
    claims = extract_claims(summaries)
    sampled = sample_claims(claims, n, seed)

    enriched: list[dict[str, Any]] = []
    for claim in sampled:
        fact_type, fact_snippet = get_fact_snippet(claim["cited_id"], graph, repo_root)
        enriched.append({
            "node_id": claim["node_id"],
            "sentence": claim["sentence"],
            "cited_id": claim["cited_id"],
            "fact_type": fact_type,
            "fact_snippet": fact_snippet,
        })

    write_spotcheck_csv(enriched, output_path)
    return len(enriched)
