"""Citation validator: checks that every [[id]] exists in facts.json and every sentence
is grounded.

Why this exists: the summarizer is instructed to cite [[fact_id]] after every claim, but the
instruction alone cannot guarantee it. This module provides a deterministic, LLM-free pass
that verifies two rules for each SummaryResult:

1. **ID existence** — every [[id]] extracted from the text must be a node id present in
   facts.json. An unknown id means the model invented a node.

2. **Sentence coverage** — every sentence must either (a) carry at least one [[id]] citation,
   or (b) mention a raw call-target name from the node's CALLS edges. Rule (b) is the "calls
   exemption": CALLS targets are unresolved callable names (e.g. "articles_repo.create_article")
   that cannot appear as [[id]] citations because they are not node ids. Mentioning them as
   context is valid and useful (see D-008 in memory.md).

Nothing here performs I/O or calls an LLM. The caller (cli.py) reads facts.json and
summaries.json and passes the extracted data in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from docgen.summarize.base import SummaryResult
from docgen.summarize.hierarchy import NEEDS_HUMAN_REVIEW_BACKEND
from docgen.summarize.prompts import CITATION_RE, extract_citations

# Maximum characters kept in CitationError.detail for uncited-sentence entries.
_DETAIL_MAX = 120

# Splits on sentence-ending punctuation followed by whitespace.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    """Return non-empty, word-containing sentence fragments from *text*.

    Splits on ``.``, ``!``, ``?`` followed by whitespace. Each fragment is stripped;
    empty ones and fragments containing no prose word characters are dropped.

    This works correctly because the canonical citation format (enforced by CITATION_RULES
    in prompts.py) places all citations *before* the closing punctuation mark:
    ``"prose text [[id1]] [[id2]]."`` — so citations always stay with their sentence after
    a naive split on the terminating period.
    """
    parts = _SENTENCE_SPLIT_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip() and re.search(r"\w", p)]


@dataclass(frozen=True)
class CitationError:
    """A single validation failure in one summary.

    Attributes:
        node_id: The summary (node) this error belongs to.
        kind: ``"unknown_id"`` — a [[id]] not found in facts.json; or
              ``"uncited_sentence"`` — a sentence with no citation and no exempt call name.
        detail: For ``unknown_id``: the unknown id string.
                For ``uncited_sentence``: the sentence text, truncated to 120 characters.
    """

    node_id: str
    kind: str  # "unknown_id" | "uncited_sentence"
    detail: str


def validate_summaries(
    summaries: list[SummaryResult],
    known_ids: set[str],
    calls_by_node: dict[str, set[str]] | None = None,
) -> list[CitationError]:
    """Validate all summaries and return every CitationError found.

    Args:
        summaries: The list of SummaryResult to validate.
        known_ids: Set of node ids from facts.json (plus "system" added by the caller).
            Any [[id]] not in this set is an unknown-id error.
        calls_by_node: Optional mapping from node_id to the set of raw call-target names
            (the ``to_id`` values of CALLS edges). A sentence that mentions any of these
            names is exempt from the citation-coverage requirement. Pass ``None`` or ``{}``
            to skip the exemption for all nodes.

    Returns:
        A list of CitationError, one per violation, in order of (node_id, kind, detail).
        Returns an empty list when all summaries are clean.
    """
    if calls_by_node is None:
        calls_by_node = {}

    errors: list[CitationError] = []

    for result in summaries:
        # Skip nodes that failed summarization — they carry a placeholder text that
        # would trigger false citation errors, and they are already flagged by their backend.
        if result.backend == NEEDS_HUMAN_REVIEW_BACKEND:
            continue

        node_id = result.node_id
        text = result.text
        node_calls: set[str] = calls_by_node.get(node_id, set())

        # Rule 1: every [[id]] must be a known node id.
        for cited_id in extract_citations(text):
            if cited_id not in known_ids:
                errors.append(CitationError(
                    node_id=node_id,
                    kind="unknown_id",
                    detail=cited_id,
                ))

        # Rule 2: every sentence must be cited or mention a call name.
        for sentence in _split_sentences(text):
            has_citation = bool(CITATION_RE.search(sentence))
            if has_citation:
                continue
            # Calls exemption: sentence mentions at least one raw call target.
            if node_calls and any(call_name in sentence for call_name in node_calls):
                continue
            errors.append(CitationError(
                node_id=node_id,
                kind="uncited_sentence",
                detail=sentence[:_DETAIL_MAX],
            ))

    return errors


def format_report(errors: list[CitationError]) -> str:
    """Render *errors* as a human-readable linter-style string.

    Each error produces one ``ERROR [kind] <node_id>: <detail>`` line. Lines are sorted
    by (node_id, kind, detail) for deterministic output. A summary count line is appended.

    Returns ``"No citation errors.\\n"`` when the list is empty.
    """
    if not errors:
        return "No citation errors.\n"

    sorted_errors = sorted(errors, key=lambda e: (e.node_id, e.kind, e.detail))
    lines = [
        f"ERROR [{e.kind}] {e.node_id}: {e.detail}"
        for e in sorted_errors
    ]
    n = len(errors)
    lines.append(f"{n} citation error{'s' if n != 1 else ''} found.")
    return "\n".join(lines) + "\n"
