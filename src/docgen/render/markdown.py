"""Render the architecture index page and per-module markdown pages.

Why: facts + summaries are machine-readable; these renderers produce the
human-readable docs that developers actually read.  Everything here is a
pure function of facts.json + summaries.json — no I/O, no extraction, no LLM.

Page layout decisions:
- Module pages mirror the source directory structure under generated/pages/
  so relative links work and filenames stay human-readable.
- <details> blocks are NOT used for body facts: they don't render in all
  Markdown renderers (notably many static-site generators).
- The .py extension is stripped from the page heading.
- "_(no summary yet)_" is shown when a summary is absent.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from docgen.check.manifest import PageRecord
from docgen.facts.schema import EdgeType, FactGraph, Node, NodeType
from docgen.render.mermaid import render_mermaid_diagram


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _summary(node_id: str, summaries_map: dict[str, str]) -> str:
    """Return the summary text for *node_id*, or the missing-summary placeholder."""
    return summaries_map.get(node_id, "_(no summary yet)_")


def _short_name(node_id: str) -> str:
    """Last ``::``-delimited component, or the file stem."""
    if "::" in node_id:
        return node_id.rsplit("::", 1)[-1]
    return PurePosixPath(node_id).stem or node_id


def _module_page_path(module_id: str, output_dir: str = "generated") -> str:
    """Repo-root-relative POSIX path for the page file of a module.

    ``target/app/api/dependencies/articles.py``
    → ``generated/pages/target/app/api/dependencies/articles.md``
    """
    md_path = PurePosixPath(module_id).with_suffix(".md")
    return str(PurePosixPath(output_dir) / "pages" / md_path).replace("\\", "/")


# ---------------------------------------------------------------------------
# Index page
# ---------------------------------------------------------------------------

def render_index(
    graph: FactGraph,
    summaries_map: dict[str, str],
    output_dir: str = "generated",
) -> tuple[str, PageRecord]:
    """Render the architecture overview index page.

    Content:
    - System-level summary
    - Mermaid package diagram
    - One paragraph per package (package summary)

    Returns ``(markdown_text, PageRecord)`` for the manifest.
    """
    fact_ids: list[str] = []
    hashes: dict[str, dict[str, str]] = {}

    node_map: dict[str, Node] = {n.id: n for n in graph.nodes}

    lines: list[str] = ["# Architecture Overview\n"]

    # System summary
    system_text = _summary("system", summaries_map)
    lines.append(system_text)
    lines.append("")
    fact_ids.append("system")

    # Mermaid diagram
    lines.append(render_mermaid_diagram(graph))
    lines.append("")

    # Package summaries
    pkg_nodes = sorted(
        (n for n in graph.nodes if n.type is NodeType.PACKAGE),
        key=lambda n: n.id,
    )
    if pkg_nodes:
        lines.append("## Packages\n")
        for pkg in pkg_nodes:
            label = PurePosixPath(pkg.id).name or pkg.id
            lines.append(f"### {label}\n")
            lines.append(_summary(pkg.id, summaries_map))
            lines.append("")
            fact_ids.append(pkg.id)
            if pkg.hash_struct or pkg.hash_source:
                hashes[pkg.id] = {
                    "hash_struct": pkg.hash_struct,
                    "hash_source": pkg.hash_source,
                }

    page_path = str(PurePosixPath(output_dir) / "pages" / "index.md").replace("\\", "/")
    record = PageRecord(page_path=page_path, fact_ids=fact_ids, hashes=hashes)
    return "\n".join(lines) + "\n", record


# ---------------------------------------------------------------------------
# Per-module pages
# ---------------------------------------------------------------------------

def render_module_page(
    module_node: Node,
    graph: FactGraph,
    summaries_map: dict[str, str],
    output_dir: str = "generated",
) -> tuple[str, PageRecord]:
    """Render one module page, mirroring the source directory structure.

    Content: module summary, then one section per class (with fields + method
    summaries), then one section per module-level function (with inline raises
    and depends_on facts).

    Returns ``(markdown_text, PageRecord)`` for the manifest.
    """
    fact_ids: list[str] = [module_node.id]
    hashes: dict[str, dict[str, str]] = {}

    node_map: dict[str, Node] = {n.id: n for n in graph.nodes}

    def _record(node: Node) -> None:
        fact_ids.append(node.id)
        if node.hash_struct or node.hash_source:
            hashes[node.id] = {
                "hash_struct": node.hash_struct,
                "hash_source": node.hash_source,
            }

    _record(module_node)

    # Heading: strip .py, use last path component
    heading = PurePosixPath(module_node.id).stem
    lines: list[str] = [f"# {heading}\n"]
    lines.append(_summary(module_node.id, summaries_map))
    lines.append("")

    # Build relational-edge indexes
    raises_by: dict[str, list[str]] = {}
    deps_by: dict[str, list[str]] = {}
    contains: dict[str, list[str]] = {}  # parent_id → [child_id]

    for edge in graph.edges:
        if edge.type is EdgeType.RAISES:
            raises_by.setdefault(edge.from_id, []).append(edge.to_id)
        elif edge.type is EdgeType.DEPENDS_ON:
            deps_by.setdefault(edge.from_id, []).append(edge.to_id)
        elif edge.type is EdgeType.CONTAINS:
            contains.setdefault(edge.from_id, []).append(edge.to_id)

    def _render_function(func_node: Node, level: int) -> None:
        prefix = "#" * level
        name = func_node.name or _short_name(func_node.id)
        lines.append(f"{prefix} {name}\n")
        lines.append(_summary(func_node.id, summaries_map))

        raises = raises_by.get(func_node.id, [])
        deps = deps_by.get(func_node.id, [])

        if raises:
            exc_names = ", ".join(
                e.split("external:")[-1] if e.startswith("external:") else _short_name(e)
                for e in sorted(set(raises))
            )
            lines.append(f"\n> **Raises:** {exc_names}")
        if deps:
            dep_names = ", ".join(
                _short_name(d) for d in sorted(set(deps))
                if not d.startswith("external:")
            )
            if dep_names:
                lines.append(f"\n> **FastAPI deps:** {dep_names}")
        lines.append("")
        _record(func_node)

    # Classes
    class_ids = [
        cid for cid in contains.get(module_node.id, [])
        if node_map.get(cid) and node_map[cid].type is NodeType.CLASS
    ]
    for class_id in sorted(class_ids):
        cls_node = node_map[class_id]
        lines.append(f"## {cls_node.name}\n")
        lines.append(_summary(class_id, summaries_map))
        lines.append("")
        _record(cls_node)

        # Field table
        if cls_node.fields:
            lines.append("| Field | Type | Default |")
            lines.append("|-------|------|---------|")
            for fname, ftype, fdefault in cls_node.fields:
                default_cell = f"`{fdefault}`" if fdefault else ""
                lines.append(f"| `{fname}` | `{ftype}` | {default_cell} |")
            lines.append("")

        # Methods
        method_ids = [
            mid for mid in contains.get(class_id, [])
            if node_map.get(mid) and node_map[mid].type is NodeType.FUNCTION
        ]
        for method_id in sorted(method_ids):
            _render_function(node_map[method_id], level=3)

    # Module-level functions
    func_ids = [
        fid for fid in contains.get(module_node.id, [])
        if node_map.get(fid) and node_map[fid].type is NodeType.FUNCTION
    ]
    for func_id in sorted(func_ids):
        _render_function(node_map[func_id], level=2)

    page_path = _module_page_path(module_node.id, output_dir)
    record = PageRecord(page_path=page_path, fact_ids=fact_ids, hashes=hashes)
    return "\n".join(lines) + "\n", record


# ---------------------------------------------------------------------------
# Render all pages
# ---------------------------------------------------------------------------

def render_all(
    graph: FactGraph,
    summaries_map: dict[str, str],
    output_dir: str = "generated",
) -> tuple[list[PageRecord], list[tuple[str, str]]]:
    """Render index, all module pages, the API table, and return all PageRecords.

    Does NOT write files — returns ``(records, pages_to_write)`` so the CLI can
    write them and build the manifest.  Callers: ``cli._run_render``.

    Returns:
        A tuple of:
        - ``records``: one :class:`PageRecord` per page (for the manifest).
        - ``pages_to_write``: ``(repo_root_relative_posix_path, markdown_text)``
          pairs ready to be passed to :func:`write_pages`.
    """
    from docgen.render.api_table import render_api_table  # local import avoids circular

    records: list[PageRecord] = []
    pages_to_write: list[tuple[str, str]] = []

    # Index
    index_text, index_record = render_index(graph, summaries_map, output_dir)
    records.append(index_record)
    pages_to_write.append((index_record.page_path, index_text))

    # Module pages
    module_nodes = sorted(
        (n for n in graph.nodes if n.type is NodeType.MODULE),
        key=lambda n: n.id,
    )
    for mod in module_nodes:
        text, record = render_module_page(mod, graph, summaries_map, output_dir)
        records.append(record)
        pages_to_write.append((record.page_path, text))

    # API table page
    api_text, api_fact_ids = render_api_table(graph, summaries_map, output_dir)
    api_page_path = str(PurePosixPath(output_dir) / "pages" / "api.md").replace("\\", "/")
    # Build hashes for route nodes referenced in the API table
    node_map: dict[str, Node] = {n.id: n for n in graph.nodes}
    api_hashes: dict[str, dict[str, str]] = {}
    for nid in api_fact_ids:
        node = node_map.get(nid)
        if node and (node.hash_struct or node.hash_source):
            api_hashes[nid] = {
                "hash_struct": node.hash_struct,
                "hash_source": node.hash_source,
            }
    api_record = PageRecord(
        page_path=api_page_path,
        fact_ids=api_fact_ids,
        hashes=api_hashes,
    )
    records.append(api_record)
    pages_to_write.append((api_page_path, api_text))

    return records, pages_to_write


def write_pages(
    pages: list[tuple[str, str]],
    repo_root: Path,
) -> None:
    """Write rendered page files to disk.

    Args:
        pages: List of ``(repo_root_relative_posix_path, markdown_text)`` pairs.
        repo_root: Absolute path to the project root.
    """
    for page_path, text in pages:
        abs_path = repo_root / page_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(text, encoding="utf-8")
