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
    from docgen.facts.schema import FactGraph, Unresolved
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

    # Step 5b: Synthesize PACKAGE nodes from directory structure.
    # Runs after body facts so all MODULE nodes exist; runs before the FastAPI
    # adapter so route extraction can see the package hierarchy.
    from docgen.extract.packages import synthesize_packages
    pkg_nodes, pkg_edges = synthesize_packages(all_nodes, source_root=config.source_root)
    all_nodes.extend(pkg_nodes)
    all_edges.extend(pkg_edges)
    print(f"  packages: {len(pkg_nodes)} synthesized from directory structure", file=sys.stderr)

    # Step 6: Dynamic pattern scan
    scan_unresolved = scan_for_unresolved(module_paths, path_to_info, repo_root)
    all_unresolved.extend(scan_unresolved)

    # Step 7: Framework adapter (FastAPI introspection)
    if config.adapter_name == "fastapi":
        from docgen.extract.adapters.fastapi import extract as fastapi_extract
        adapter_result = fastapi_extract(all_nodes, all_edges, config, repo_root)
        all_nodes.extend(adapter_result.nodes)
        all_edges.extend(adapter_result.edges)
        all_unresolved.extend(adapter_result.unresolved)
        print(
            f"  adapter: {len(adapter_result.nodes)} route nodes, "
            f"{len(adapter_result.edges)} route edges",
            file=sys.stderr,
        )

    # Step 7b: AST-only route extraction (Tier A — method + relative path + handler)
    # Runs unconditionally for any fastapi adapter; results printed to stdout as a
    # graded recall line.  Full-path resolution (Tier B) is deferred to v0.2.
    if config.adapter_name == "fastapi":
        from docgen.extract.adapters.fastapi_ast import extract_ast_routes, grade_ast_routes
        ast_routes, ast_unresolved = extract_ast_routes(module_paths, repo_root)
        all_unresolved.extend(ast_unresolved)
        print(
            f"AST routes: {len(ast_routes)} route decorators found "
            f"(method + relative path + handler; full paths deferred to v0.2)"
        )

    # Step 7c: Resolve DEPENDS_ON edges from external: to real in-repo node IDs.
    # Runs after core extraction and import resolution so all FUNCTION nodes exist.
    # Cycle detection emits Unresolved entries but does not abort the run.
    from docgen.extract.adapters.resolve_deps import detect_dep_cycles, resolve_dep_edges
    all_edges, dep_unresolved = resolve_dep_edges(
        all_nodes, all_edges, path_to_info, dotted_to_path
    )
    all_unresolved.extend(dep_unresolved)
    dep_cycles = detect_dep_cycles(all_nodes, all_edges)
    for cycle in dep_cycles:
        all_unresolved.append(Unresolved(
            what="dep_cycle",
            why=f"Dependency cycle detected: {cycle}",
            where="dep_graph",
        ))
    resolved_count = sum(
        1 for e in all_edges
        if e.type.value == "depends_on" and not e.to_id.startswith("external:")
    )
    total_dep = sum(1 for e in all_edges if e.type.value == "depends_on")
    print(
        f"DEP edges: {resolved_count}/{total_dep} resolved"
        + (f", {len(dep_cycles)} cycle(s)" if dep_cycles else "")
    )

    # Step 8: Deduplicate nodes by id (external nodes may be emitted by multiple passes)
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


def _run_summarize(args: argparse.Namespace) -> None:
    """Run the bottom-up hierarchy summarization pass and write summaries.json.

    Pipeline:
        load_config → read facts.json → load existing summaries.json (cache) →
        run_hierarchy (bottom-up, child summaries passed to parents) →
        write summaries.json

    Re-runs with no fact changes produce zero summarizer calls because the cache
    keys match.
    """
    from docgen.config import load_config
    from docgen.facts.store import read_facts
    from docgen.summarize.base import StubSummarizer
    from docgen.summarize.bob_shell import BobShellSummarizer
    from docgen.summarize.hierarchy import run_hierarchy
    from docgen.summarize.manual import ManualSummarizer
    from docgen.summarize.prompts import PROMPT_VERSION
    from docgen.summarize.store import read_summaries, write_summaries

    config_path = Path(args.config)
    config = load_config(config_path)
    repo_root = config_path.parent.resolve()
    output_dir = repo_root / config.output_dir

    facts_path = output_dir / "facts.json"
    if not facts_path.exists():
        raise SystemExit(
            f"facts.json not found at {facts_path}; run `docgen extract` first."
        )
    graph = read_facts(facts_path)

    backend = getattr(args, "backend", "stub")
    max_cost = float(getattr(args, "max_cost", 2.0))
    max_turns = int(getattr(args, "max_turns", 10))

    if backend == "stub":
        summarizer = StubSummarizer()
    elif backend == "manual":
        summarizer = ManualSummarizer(output_dir / "manual_summaries")
    elif backend == "bob_shell":
        summarizer = BobShellSummarizer(max_cost=max_cost, max_turns=max_turns)
    else:
        raise SystemExit(
            f"Unknown backend: {backend!r} (expected 'stub', 'manual', or 'bob_shell')."
        )

    print(
        f"docgen summarize: {len(graph.nodes)} nodes from {facts_path} (backend={backend}) …",
        file=sys.stderr,
    )

    # Load existing summaries as the cache; skip if this is the first run.
    summaries_path = output_dir / "summaries.json"
    existing_cache: dict = {}
    if summaries_path.exists():
        for result in read_summaries(summaries_path):
            existing_cache[result.node_id] = result

    results = run_hierarchy(
        graph=graph,
        summarizer=summarizer,
        repo_root=repo_root,
        existing_cache=existing_cache,
        prompt_version=PROMPT_VERSION,
    )

    write_summaries(results, summaries_path)

    print(f"  summaries.json written: {len(results)} summaries", file=sys.stderr)
    print(f"{len(results)} summaries written")


def _run_validate(args: argparse.Namespace) -> None:
    """Validate citations in summaries.json against facts.json.

    Pipeline:
        load_config → read facts.json (build known_ids + calls_by_node) →
        read summaries.json → validate_summaries → print report → exit 0/1

    Exit 0 when no errors are found; exit 1 when at least one CitationError is reported.
    """
    from docgen.config import load_config
    from docgen.facts.schema import EdgeType
    from docgen.facts.store import read_facts
    from docgen.summarize.citations import format_report, validate_summaries
    from docgen.summarize.hierarchy import SYSTEM_NODE_ID
    from docgen.summarize.store import read_summaries

    config_path = Path(args.config)
    config = load_config(config_path)
    output_dir = config_path.parent.resolve() / config.output_dir

    facts_path = output_dir / "facts.json"
    if not facts_path.exists():
        raise SystemExit(
            f"facts.json not found at {facts_path}; run `docgen extract` first."
        )
    summaries_path = output_dir / "summaries.json"
    if not summaries_path.exists():
        raise SystemExit(
            f"summaries.json not found at {summaries_path}; run `docgen summarize` first."
        )

    graph = read_facts(facts_path)
    summaries = read_summaries(summaries_path)

    # Build the set of known node ids. Add the synthetic system node explicitly so a
    # self-citation [[system]] in the system summary is treated as valid.
    known_ids: set[str] = {n.id for n in graph.nodes} | {SYSTEM_NODE_ID}

    # Build the calls-by-node index for the coverage exemption.
    calls_by_node: dict[str, set[str]] = {}
    for edge in graph.edges:
        if edge.type is EdgeType.CALLS:
            calls_by_node.setdefault(edge.from_id, set()).add(edge.to_id)

    print(
        f"docgen validate: {len(summaries)} summaries, {len(known_ids)} known ids …",
        file=sys.stderr,
    )

    errors = validate_summaries(summaries, known_ids, calls_by_node)
    report = format_report(errors)
    print(report, end="")

    if errors:
        raise SystemExit(1)


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

    summarize_parser = subparsers.add_parser(
        "summarize", help="Generate cited summaries from facts."
    )
    summarize_parser.add_argument(
        "--config",
        default="docgen.toml",
        help="Path to docgen.toml (default: docgen.toml in cwd).",
    )
    summarize_parser.add_argument(
        "--backend",
        default="stub",
        help="Summarizer backend: 'stub', 'manual', or 'bob_shell' (default: stub).",
    )
    summarize_parser.add_argument(
        "--max-cost",
        type=float,
        default=2.0,
        dest="max_cost",
        help="Maximum Bobcoins per bob_shell call (default: 2.0).",
    )
    summarize_parser.add_argument(
        "--max-turns",
        type=int,
        default=10,
        dest="max_turns",
        help="Maximum conversation turns per bob_shell call (default: 10).",
    )

    validate_parser = subparsers.add_parser(
        "validate", help="Validate citations in summaries.json (exit 1 if broken)."
    )
    validate_parser.add_argument(
        "--config",
        default="docgen.toml",
        help="Path to docgen.toml (default: docgen.toml in cwd).",
    )

    subparsers.add_parser("render", help="Render documentation pages.")
    subparsers.add_parser("check", help="Check for doc drift (exit 1 if stale).")
    subparsers.add_parser("update", help="Regenerate stale pages.")
    subparsers.add_parser("eval", help="Run the evaluation harness.")

    args = parser.parse_args()

    if args.command == "extract":
        _run_extract(args)
    elif args.command == "summarize":
        _run_summarize(args)
    elif args.command == "validate":
        _run_validate(args)
    else:
        raise NotImplementedError(f"Command '{args.command}' not yet implemented.")


if __name__ == "__main__":
    main()
