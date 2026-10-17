"""Per-level prompt templates and the canonical `[[fact_id]]` citation format.

Why: the trust story of this tool is that the LLM only *explains* structure the
extractor already found, and every sentence can be traced back to a fact in
`facts.json`. This module builds the instruction that makes that possible
(``build_prompt``) and defines the citation syntax the prompt demands and the
validator (2b.4) will enforce. Keeping the format and the per-level guidance in
one place means the prompt and the validation can never drift apart.

Nothing here performs I/O or calls a model: ``build_prompt`` is a pure function of
a :class:`~docgen.summarize.base.SummaryRequest`, so its output is deterministic
and cheap to test.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .base import NodeLevel, SummaryRequest

# Bump when the wording of the prompt changes. The cache key in base.hash_input()
# does not include this yet (see plan-2b2-prompts.md, decision D-E); 2b.3 should
# fold it in so a prompt edit invalidates cached summaries.
PROMPT_VERSION = "2b4.1"

# The one true citation matcher, reused by the prompt tests and (in 2b.4) the validator.
CITATION_RE = re.compile(r"\[\[([^\[\]]+)\]\]")

SYSTEM_PREAMBLE = (
    "You are documenting a Python codebase for developers who are new to it. "
    "Your job is to explain, in plain English, what already exists. You never invent "
    "structure, behavior, or components: everything you write must be supported by the "
    "facts, relational facts, source, and child summaries provided below."
)

CITATION_RULES = (
    "- Place all citations for a sentence immediately before the closing punctuation mark "
    "(., !, or ?), not after it.\n"
    "  Format: \"prose text [[id1]] [[id2]].\" — citations grouped before the period.\n"
    "  Example: \"This function raises HTTPException when the slug already exists "
    "[[external:fastapi.HTTPException]].\"\n"
    "  Example (multiple): \"It validates the token and fetches the user "
    "[[pkg/auth.py::verify_token]] [[pkg/auth.py::get_user]].\"\n"
    "- Cite ONLY IDs from the \"Allowed fact IDs\" list below. Never invent an ID.\n"
    "- Do not restate anything you cannot ground in the inputs.\n"
    "- A name shown only under \"Relational facts\" (for example a bare call name) is context, "
    "not a citable ID, unless it also appears in \"Allowed fact IDs\"."
)

OUTPUT_INSTRUCTION = (
    "Write markdown prose: no headings, no bullet lists, no code fences. "
    "Every sentence carries at least one [[id]] citation placed before its closing punctuation."
)

_GROUNDING_RULE = (
    "Base every statement only on the inputs shown; if something is unclear from them, "
    "omit it rather than guess."
)

# Level-specific focus; the shared grounding rule is appended to each entry below.
_LEVEL_FOCUS: dict[str, str] = {
    "function": (
        "Describe what this function does: its purpose, its inputs (from the signature), "
        "what it returns, any notable decorators (for example route registration or "
        "authorization), the exceptions it raises, what it depends on, and any notable calls."
    ),
    "method": (
        "Describe what this method does and its role within its class: its purpose, inputs, "
        "return value, notable decorators, exceptions raised, dependencies, and notable calls."
    ),
    "class": (
        "Describe this class's responsibility, its base classes, its fields (including "
        "inherited ones), and whether it is a Pydantic model. Use the child method summaries "
        "where provided."
    ),
    "module": (
        "Describe this module's purpose and the main things it defines (functions and classes), "
        "composing the description from the child summaries. Explain how the pieces relate to "
        "one another."
    ),
    "package": (
        "Describe this package's purpose and how its submodules fit together, composing the "
        "description from the child summaries."
    ),
    "system": (
        "Write an architecture overview of the whole project: the main packages, their "
        "responsibilities, and how they relate, composing the description from the child "
        "summaries."
    ),
}

LEVEL_INSTRUCTIONS: dict[NodeLevel, str] = {
    level: f"{focus}\n\n{_GROUNDING_RULE}" for level, focus in _LEVEL_FOCUS.items()
}

# Edge types whose `to` value is a node id and may therefore be cited.
# "handles" is included so a handler function can cite its own route node
# (e.g. [[route:POST /api/articles]]) — route nodes are in facts.json and
# therefore already in the validator's known_ids set.
_CITEABLE_EDGE_TYPES = frozenset({"raises", "depends_on", "inherits", "handles"})

# Order in which relational facts are rendered.
_RENDERED_EDGE_TYPES = ("handles", "raises", "depends_on", "calls", "inherits")


def format_citation(fact_id: str) -> str:
    """Render a fact id as an inline citation."""
    return f"[[{fact_id}]]"


def extract_citations(text: str) -> list[str]:
    """Return the citation ids in `text`, in order of first appearance, de-duplicated.

    Ignores malformed spans such as `[]` or an unclosed `[[`. Reused by the 2b.4
    validator so prompt-side and validation-side parsing always agree.
    """
    seen: list[str] = []
    for match in CITATION_RE.findall(text):
        if match not in seen:
            seen.append(match)
    return seen


def allowed_fact_ids(req: SummaryRequest) -> list[str]:
    """The only ids a summary of `req` may cite, sorted and de-duplicated.

    Includes the node's own id, its module and enclosing class (when present), its
    child summaries' ids, and the in-repo targets of its `raises` / `depends_on` /
    `inherits` edges. `external:...` targets and `calls` targets are excluded: they
    are not node ids in `facts.json`.
    """
    ids: set[str] = {req.node_id}

    for key in ("file", "parent_class"):
        value = req.facts.get(key)
        if value:
            ids.add(value)

    for child in req.child_summaries:
        if child.node_id:
            ids.add(child.node_id)

    for edge in req.edges:
        edge_type = edge.get("type")
        if edge_type not in _CITEABLE_EDGE_TYPES:
            continue
        if edge_type == "handles":
            # The HANDLES edge is stored as {from: route_id, to: function_id}.
            # The function already owns its own id; the route id (in "from") is the
            # citeable target we want to add.
            route_id = edge.get("from", "")
            if route_id and not route_id.startswith("external:"):
                ids.add(route_id)
        else:
            target = edge.get("to", "")
            if target and not target.startswith("external:"):
                ids.add(target)

    return sorted(i for i in ids if i)


def render_edges(edges: list[dict[str, Any]]) -> str:
    """Render relational edges as context lines, grouped by type and ordered by target.

    `calls` targets (bare call names) appear here so the model can mention them, but
    they are not offered as citable ids. Returns "" when there are no edges.
    """
    if not edges:
        return ""

    by_type: dict[str, list[str]] = {}
    for edge in edges:
        by_type.setdefault(str(edge.get("type", "")), []).append(str(edge.get("to", "")))

    lines: list[str] = []
    for edge_type in _RENDERED_EDGE_TYPES:
        for target in sorted(by_type.get(edge_type, [])):
            lines.append(f"- {edge_type}: {target}")
    # Defensive: render any unexpected type last so nothing is silently dropped.
    for edge_type in sorted(t for t in by_type if t not in _RENDERED_EDGE_TYPES):
        for target in sorted(by_type[edge_type]):
            lines.append(f"- {edge_type}: {target}")
    return "\n".join(lines)


def build_prompt(req: SummaryRequest) -> str:
    """Assemble the citation-instructed prompt for one node.

    Pure and deterministic: same `req` -> byte-identical prompt. Empty optional
    sections (relational facts, source, child summaries) are omitted entirely.
    """
    instruction = LEVEL_INSTRUCTIONS.get(req.level, LEVEL_INSTRUCTIONS["function"])

    parts: list[str] = [
        f"PROMPT_VERSION: {PROMPT_VERSION}",
        SYSTEM_PREAMBLE,
        "## Your task\n" + instruction,
        "## Citation rules\n" + CITATION_RULES,
        "## Allowed fact IDs\n"
        + "\n".join(f"- {fact_id}" for fact_id in allowed_fact_ids(req)),
        "## Node facts\n```json\n"
        + json.dumps(req.facts, sort_keys=True, indent=2, ensure_ascii=False)
        + "\n```",
    ]

    edges_block = render_edges(req.edges)
    if edges_block:
        parts.append("## Relational facts\n" + edges_block)

    if req.source_text:
        parts.append("## Source\n```python\n" + req.source_text + "\n```")

    if req.child_summaries:
        child_blocks = [
            f"### {child.node_id}\n{child.text}"
            for child in sorted(req.child_summaries, key=lambda c: c.node_id)
        ]
        parts.append("## Child summaries\n" + "\n\n".join(child_blocks))

    parts.append("## Output\n" + OUTPUT_INSTRUCTION)

    return "\n\n".join(parts) + "\n"
