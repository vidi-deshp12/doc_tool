"""CLI entry point: extract | summarize | render | check | update | eval."""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path


def _print_unresolved_summary(unresolved: list) -> None:
    """Print a linter-style unresolved summary to stdout.

    Format:
        WARN [<what>] <where> — <why>
        ...
        N unresolved entries (X type_a, Y type_b, ...)
    """
    # Sort by where then what for deterministic output
    sorted_entries = sorted(unresolved, key=lambda u: (u.where, u.what))
    for u in sorted_entries:
        print(f"WARN [{u.what}] {u.where} — {u.why}")

    n = len(sorted_entries)
    if n == 0:
        print("0 unresolved entries")
        return

    counts = Counter(u.what for u in sorted_entries)
    breakdown = ", ".join(f"{v} {k}" for k, v in sorted(counts.items()))
    print(f"{n} unresolved entr{'y' if n == 1 else 'ies'} ({breakdown})")


def _run_extract(args: argparse.Namespace) -> None:
    """Run the full extraction pipeline and write facts.json.

    Pipeline:
        load_config → walk_repo → extract_file (all files)
        → build_module_index → resolve_imports
        → resolve_all_classes → extract_body_facts
        → scan_for_unresolved → FactGraph → write_facts
        → print unresolved summary
    """
    # Import here to keep CLI startup fast and avoid circular issues at module level.
    from docgen.config import load_config
    from docgen.extract.bodies import extract_body_facts
    from docgen.extract.classes import resolve_all_classes
    from docgen.extract.core import extract_file
    from docgen.extract.modules import build_module_index, resolve_imports
    from docgen.extract.unresolved import scan_for_unresolved
    from docgen.facts.schema import FactGraph, NodeType
    from docgen.facts.store import write_facts
    from docgen.walker import walk_repo

    config_path = Path(args.config)
    config = load_config(config_path)

    # Repo root is the directory containing docgen.toml
    repo_root = config_path.parent.resolve()

    print(f"docgen extract: scanning {repo_root / config.root} …", file=sys.stderr)

    # Step 1: Walk the repo
    module_paths = list(walk_repo(config, repo_root=repo_root))
    print(f"  {len(module_paths)} Python files found", file=sys.stderr)

    # Step 2: Per-file extraction
    all_nodes: list = []
    all_edges: list = []
    all_unresolved: list = []

    for rel in module_paths:
        p = repo_root / rel
        if not p.exists():
            continue
        nodes, edges, unresolved = extract_file(p, repo_root)
        all_nodes.extend(nodes)
        all_edges.extend(edges)
        all_unresolved.extend(unresolved)

    print(
        f"  {len(all_nodes)} nodes, {len(all_edges)} edges after core extraction",
        file=sys.stderr,
    )

    # Step 3: Module index + import resolution
    dotted_to_path, path_to_info = build_module_index(
        module_paths, repo_root, source_root=config.source_root
    )
    import_edges, import_unresolved, external_nodes = resolve_imports(
        dotted_to_path, path_to_info, repo_root, source_root=config.source_root
    )
    all_nodes.extend(external_nodes)
    all_edges.extend(import_edges)
    all_unresolved.extend(import_unresolved)

    # Step 4: Class resolution
    updated_nodes, inherits_edges, class_externals, class_unresolved = resolve_all_classes(
        all_nodes, all_edges, path_to_info, dotted_to_path
    )
    all_nodes = updated_nodes
    all_nodes.extend(class_externals)
    all_edges.extend(inherits_edges)
    all_unresolved.extend(class_unresolved)

    # Step 5: Body facts (raises + calls)
    raises_edges, calls_edges, body_externals, body_unresolved = extract_body_facts(
        all_nodes, all_edges, path_to_info, dotted_to_path,
        repo_root=str(repo_root),
    )
    all_nodes.extend(body_externals)
    all_edges.extend(raises_edges)
    all_edges.extend(calls_edges)
    all_unresolved.extend(body_unresolved)

    # Step 6: Dynamic pattern scan
    scan_unresolved = scan_for_unresolved(module_paths, path_to_info, repo_root)
    all_unresolved.extend(scan_unresolved)

    # Step 7: Deduplicate nodes by id (external nodes may be emitted by multiple passes)
    seen_node_ids: set[str] = set()
    deduped_nodes: list = []
    for n in all_nodes:
        if n.id not in seen_node_ids:
            seen_node_ids.add(n.id)
            deduped_nodes.append(n)

    # Step 8: Assemble FactGraph and write
    graph = FactGraph(
        nodes=tuple(deduped_nodes),
        edges=tuple(all_edges),
        unresolved=tuple(all_unresolved),
    )

    output_dir = repo_root / config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    facts_path = output_dir / "facts.json"
    write_facts(graph, facts_path)

    print(
        f"  facts.json written: {len(graph.nodes)} nodes, "
        f"{len(graph.edges)} edges, {len(graph.unresolved)} unresolved",
        file=sys.stderr,
    )

    # Step 9: Print unresolved summary to stdout
    _print_unresolved_summary(list(graph.unresolved))


def main() -> None:
    """Parse arguments and dispatch to the appropriate sub-command."""
    parser = argparse.ArgumentParser(
        prog="docgen",
        description="Cited, drift-aware documentation generator for Python repositories.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser("extract", help="Extract facts from the target repo.")
    extract_parser.add_argument(
        "--config",
        default="docgen.toml",
        help="Path to docgen.toml (default: docgen.toml in cwd).",
    )

    subparsers.add_parser("summarize", help="Generate cited summaries from facts.")
    subparsers.add_parser("render", help="Render documentation pages.")
    subparsers.add_parser("check", help="Check for doc drift (exit 1 if stale).")
    subparsers.add_parser("update", help="Regenerate stale pages.")
    subparsers.add_parser("eval", help="Run the evaluation harness.")

    args = parser.parse_args()

    if args.command == "extract":
        _run_extract(args)
    else:
        raise NotImplementedError(f"Command '{args.command}' not yet implemented.")


if __name__ == "__main__":
    main()
