"""CLI entry point: extract | summarize | render | check | update | eval."""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from docgen.summarize.base import Summarizer


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


def _non_negative_int(value: str) -> int:
    """argparse type for flags where a negative value is meaningless."""
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid integer: {value!r}") from None
    if number < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {number}")
    return number


def _checkpoint_writer(path: Path) -> Callable[[list], None]:
    """Return a checkpoint callback that atomically replaces *path*.

    The write goes to ``summaries.json.tmp`` and is moved with ``os.replace``, so a
    crash never leaves a half-written file. An identical payload (a cached replay)
    is skipped, so the file is not rewritten once per slice.
    """
    from docgen.summarize.store import write_summaries

    last_payload: bytes | None = None

    def write(partial: list) -> None:
        nonlocal last_payload
        tmp = path.with_suffix(".json.tmp")
        write_summaries(partial, tmp)
        payload = tmp.read_bytes()
        if payload == last_payload:
            tmp.unlink(missing_ok=True)
            return
        os.replace(tmp, path)
        last_payload = payload

    return write


def _review_state(
    graph, results: list
) -> tuple[list[str], list[str], int]:
    """(needs_human_review ids, missing ids, expected node count) for a run."""
    from docgen.summarize.hierarchy import (
        NEEDS_HUMAN_REVIEW_BACKEND,
        SYSTEM_NODE_ID,
        summarizable_node_ids,
    )

    expected_ids = summarizable_node_ids(graph) | {SYSTEM_NODE_ID}
    present_ids = {r.node_id for r in results}
    failed = [
        r.node_id for r in results if r.backend == NEEDS_HUMAN_REVIEW_BACKEND
    ]
    missing = sorted(expected_ids - present_ids)
    return failed, missing, len(expected_ids)


def _print_recovery_report(graph, results: list, existing_cache: dict) -> None:
    """Print what the run achieved, including the completeness line."""
    cached = sum(1 for r in results if existing_cache.get(r.node_id) == r)
    print(
        f"  summaries written: {len(results)} "
        f"({len(results) - cached} fresh, {cached} from cache)",
        file=sys.stderr,
    )
    failed, missing, expected = _review_state(graph, results)
    if failed:
        print(
            f"  {len(failed)} node(s) need human review: {', '.join(failed)}",
            file=sys.stderr,
        )
    else:
        print("  0 node(s) need human review", file=sys.stderr)
    print(
        f"  summary complete: {expected - len(missing)}/{expected} nodes",
        file=sys.stderr,
    )


def _enforce_strict(graph, results: list, *, command: str) -> None:
    """Exit 1 under --strict when placeholders remain or a node is missing."""
    failed, missing, _ = _review_state(graph, results)
    if not failed and not missing:
        return
    parts: list[str] = []
    if failed:
        parts.append(f"{len(failed)} placeholder(s)")
    if missing:
        parts.append(
            f"{len(missing)} missing summar{'y' if len(missing) == 1 else 'ies'}"
        )
    print(
        f"docgen {command}: --strict: {', '.join(parts)}",
        file=sys.stderr,
    )
    raise SystemExit(1)


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
        adapter_result = fastapi_extract(
            all_nodes, all_edges, config, repo_root,
            dotted_to_path=dotted_to_path,
        )
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


_BACKENDS = ("stub", "manual", "bob_shell", "claude_shell", "openai", "anthropic")


@dataclass(frozen=True)
class _BackendSettings:
    """Resolved backend settings: CLI flag > [summarize] > backend default."""

    backend: str
    model: str
    base_url: str
    api_key_env: str
    timeout: int


def _resolve_summarize_settings(
    args: argparse.Namespace, config=None
) -> _BackendSettings:
    """Merge CLI flags over ``[summarize]`` over backend defaults.

    ``--backend`` defaults to ``None`` on the parser; if it defaulted to ``"stub"``
    the config value could never win. Empty CLI strings and ``timeout=0`` also defer
    to the config.
    """
    from docgen.config import SummarizeConfig

    configured = config.summarize if config is not None else SummarizeConfig()

    backend = getattr(args, "backend", None)
    if backend in (None, ""):
        backend = configured.backend or "stub"

    def pick(attr: str, fallback: str) -> str:
        value = getattr(args, attr, None)
        return fallback if value in (None, "") else str(value)

    timeout = getattr(args, "timeout", None)
    if timeout in (None, 0):
        timeout = configured.timeout

    return _BackendSettings(
        backend=str(backend),
        model=pick("model", configured.model),
        base_url=pick("base_url", configured.base_url),
        api_key_env=pick("api_key_env", configured.api_key_env),
        timeout=int(timeout or 0),
    )


def _make_stub(args, settings: _BackendSettings, output_dir: Path):
    from docgen.summarize.base import StubSummarizer

    return StubSummarizer()


def _make_manual(args, settings: _BackendSettings, output_dir: Path):
    from docgen.summarize.manual import ManualSummarizer

    return ManualSummarizer(output_dir / "manual_summaries")


def _make_bob_shell(args, settings: _BackendSettings, output_dir: Path):
    from docgen.summarize import bob_shell

    return bob_shell.BobShellSummarizer(
        max_cost=float(getattr(args, "max_cost", 2.0)),
        max_turns=int(getattr(args, "max_turns", 10)),
    )


def _make_claude_shell(args, settings: _BackendSettings, output_dir: Path):
    from docgen.summarize import claude_shell

    return claude_shell.ClaudeShellSummarizer(
        model=settings.model or "sonnet",
        timeout=settings.timeout or 180,
    )


def _make_openai(args, settings: _BackendSettings, output_dir: Path):
    from docgen.summarize.openai_backend import OpenAISummarizer

    return OpenAISummarizer(
        model=settings.model or "gpt-4o-mini",
        base_url=settings.base_url or None,
        api_key_env=settings.api_key_env or "OPENAI_API_KEY",
        timeout=settings.timeout or 120,
    )


def _make_anthropic(args, settings: _BackendSettings, output_dir: Path):
    from docgen.summarize.anthropic_backend import AnthropicSummarizer

    return AnthropicSummarizer(
        model=settings.model or "claude-sonnet-4-5",
        api_key_env=settings.api_key_env or "ANTHROPIC_API_KEY",
        timeout=settings.timeout or 120,
    )


_BACKEND_FACTORIES: dict[str, Callable] = {
    "stub": _make_stub,
    "manual": _make_manual,
    "bob_shell": _make_bob_shell,
    "claude_shell": _make_claude_shell,
    "openai": _make_openai,
    "anthropic": _make_anthropic,
}


def _build_summarizer(
    args: argparse.Namespace, output_dir: Path, config=None
) -> tuple[str, "Summarizer"]:
    """Construct the summarizer backend selected by the merged settings.

    Single construction point for both ``docgen summarize`` and ``docgen update``.
    Backend imports stay inside the factories so a stub run never imports a
    provider module.

    Returns:
        ``(backend_name, summarizer)``. The name is returned separately so
        ``_run_update`` can keep its "only re-summarize with a real backend" gate.
    """
    settings = _resolve_summarize_settings(args, config)

    # Documented in the README, but a warning at construction time is what the
    # user actually sees before the run burns allowance. Not an error: the driver
    # is still deterministic at any worker count.
    if settings.backend == "claude_shell" and int(
        getattr(args, "workers", 1) or 1
    ) > 1:
        print(
            "WARN: claude_shell uses a per-account Claude Pro/Max limit; "
            "--workers > 1 does not increase the allowance and makes a usage "
            "limit arrive sooner. Use --workers 1.",
            file=sys.stderr,
        )

    factory = _BACKEND_FACTORIES.get(settings.backend)
    if factory is None:
        raise SystemExit(
            f"Unknown backend {settings.backend!r} "
            f"(expected one of: {', '.join(_BACKENDS)})."
        )

    from docgen.summarize.base import BackendError, FatalBackendError

    try:
        summarizer = factory(args, settings, output_dir)
    except BackendError as exc:
        # Construction failures (missing key, missing executable, bad auth) are
        # fatal but happen outside the retry loop; classify them into the type the
        # CLI handler catches.
        if exc.fatal:
            raise FatalBackendError(settings.backend, exc) from exc
        raise

    return settings.backend, summarizer


def _run_summarize(args: argparse.Namespace) -> None:
    """Run the bottom-up hierarchy summarization pass and write summaries.json.

    Pipeline:
        load_config → read facts.json → load existing summaries.json (cache) →
        run_hierarchy (bottom-up, retries, sliced checkpoints, repair pass) →
        write summaries.json

    Re-runs with no fact changes produce zero summarizer calls because the cache
    keys match. A fatal backend error exits 2; the completed slices are already on
    disk. ``--strict`` exits 1 when a node is missing or needs human review.
    """
    from docgen.config import load_config
    from docgen.facts.store import read_facts
    from docgen.summarize.base import FatalBackendError, RetryPolicy
    from docgen.summarize.hierarchy import run_hierarchy
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

    # Load existing summaries as the cache; skip if this is the first run.
    summaries_path = output_dir / "summaries.json"
    existing_cache: dict = {}
    if summaries_path.exists():
        for result in read_summaries(summaries_path):
            existing_cache[result.node_id] = result

    retry = RetryPolicy(max_attempts=getattr(args, "retries", 3) + 1)

    try:
        # Inside the handler: backend construction can fail fatally too (missing
        # key/package), and that must not print a traceback and exit 1.
        backend, summarizer = _build_summarizer(args, output_dir, config)
        print(
            f"docgen summarize: {len(graph.nodes)} nodes from {facts_path} "
            f"(backend={backend}) …",
            file=sys.stderr,
        )
        results = run_hierarchy(
            graph=graph,
            summarizer=summarizer,
            repo_root=repo_root,
            existing_cache=existing_cache,
            max_workers=getattr(args, "workers", 1),
            retry=retry,
            checkpoint=_checkpoint_writer(summaries_path),
            repair_passes=getattr(args, "repair_passes", 1),
        )
    except FatalBackendError as exc:
        print(
            f"docgen summarize: fatal backend error at {exc.node_id}: "
            f"{exc.cause.message}",
            file=sys.stderr,
        )
        raise SystemExit(2)

    write_summaries(results, summaries_path)

    _print_recovery_report(graph, results, existing_cache)
    print(f"{len(results)} summaries written")

    if getattr(args, "strict", False):
        _enforce_strict(graph, results, command="summarize")


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


def _run_render(args: argparse.Namespace) -> None:
    """Render all doc pages from facts.json + summaries.json and write manifest.json.

    Pipeline:
        load_config → read facts.json → read summaries.json →
        render_all (index + module pages + api table) →
        write_pages → build_manifest → write_manifest
    """
    from docgen.check.manifest import build_manifest, write_manifest
    from docgen.config import load_config
    from docgen.facts.store import read_facts
    from docgen.render.markdown import render_all, write_pages
    from docgen.summarize.store import read_summaries

    config_path = Path(args.config)
    config = load_config(config_path)
    repo_root = config_path.parent.resolve()
    output_dir = repo_root / config.output_dir

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
    summaries_map: dict[str, str] = {
        r.node_id: r.text for r in read_summaries(summaries_path)
    }

    print(
        f"docgen render: {len(graph.nodes)} nodes, {len(summaries_map)} summaries …",
        file=sys.stderr,
    )

    records, pages_to_write = render_all(graph, summaries_map, config.output_dir)
    write_pages(pages_to_write, repo_root)

    manifest = build_manifest(records)
    manifest_path = output_dir / "manifest.json"
    write_manifest(manifest, manifest_path)

    print(
        f"  {len(pages_to_write)} pages written, manifest.json updated",
        file=sys.stderr,
    )


def _run_check(args: argparse.Namespace) -> None:
    """Check for doc drift by comparing manifest.json against facts.json.

    Exit 0 when all pages are fresh; exit 1 when any page is stale (list printed
    to stdout).  With ``--fresh``, re-extracts facts first.
    """
    from docgen.check.drift import find_stale_pages, warn_if_facts_stale
    from docgen.check.manifest import read_manifest
    from docgen.config import load_config
    from docgen.facts.store import read_facts

    config_path = Path(args.config)
    config = load_config(config_path)
    repo_root = config_path.parent.resolve()
    output_dir = repo_root / config.output_dir

    manifest_path = output_dir / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(
            f"manifest.json not found at {manifest_path}; run `docgen render` first."
        )

    if getattr(args, "fresh", False):
        # Re-extract before checking
        import argparse as _ap
        extract_args = _ap.Namespace(config=str(config_path))
        _run_extract(extract_args)

    facts_path = output_dir / "facts.json"
    if not facts_path.exists():
        raise SystemExit(
            f"facts.json not found at {facts_path}; run `docgen extract` first."
        )

    warn_if_facts_stale(facts_path, manifest_path)

    graph = read_facts(facts_path)
    manifest = read_manifest(manifest_path)

    stale = find_stale_pages(manifest, graph)

    if stale:
        for page in stale:
            print(page)
        raise SystemExit(1)


def _run_update(args: argparse.Namespace) -> None:
    """Regenerate only stale pages and rebuild manifest.json.

    Pipeline:
        load_config → read facts.json + summaries.json + manifest.json →
        plan_update → (optional) re-summarize stale nodes →
        re-render stale pages → write → rebuild manifest
    """
    from docgen.check.drift import find_stale_pages
    from docgen.check.manifest import build_manifest, read_manifest, write_manifest
    from docgen.check.update import plan_update
    from docgen.config import load_config
    from docgen.facts.store import read_facts
    from docgen.render.markdown import render_index, render_module_page, write_pages
    from docgen.render.api_table import render_api_table
    from docgen.summarize.store import read_summaries

    config_path = Path(args.config)
    config = load_config(config_path)
    repo_root = config_path.parent.resolve()
    output_dir = repo_root / config.output_dir

    manifest_path = output_dir / "manifest.json"
    facts_path = output_dir / "facts.json"
    summaries_path = output_dir / "summaries.json"

    for p, name in [
        (manifest_path, "manifest.json — run `docgen render` first"),
        (facts_path, "facts.json — run `docgen extract` first"),
        (summaries_path, "summaries.json — run `docgen summarize` first"),
    ]:
        if not p.exists():
            raise SystemExit(f"{name} not found at {p}")

    graph = read_facts(facts_path)
    summary_results = read_summaries(summaries_path)
    summaries_map: dict[str, str] = {
        r.node_id: r.text for r in summary_results
    }
    manifest = read_manifest(manifest_path)

    stale = find_stale_pages(manifest, graph)
    if not stale:
        print("docgen update: nothing to update", file=sys.stderr)
        if getattr(args, "strict", False):
            _enforce_strict(graph, summary_results, command="update")
        return

    update_plan = plan_update(stale, manifest, graph, summaries_map)
    print(
        f"docgen update: {len(update_plan.stale_pages)} stale pages, "
        f"{len(update_plan.stale_node_ids)} changed nodes …",
        file=sys.stderr,
    )

    # Optional re-summarization (only when a real backend is requested)
    settings = _resolve_summarize_settings(args, config)
    if update_plan.nodes_to_resummarize and settings.backend != "stub":
        from docgen.summarize.base import FatalBackendError, RetryPolicy
        from docgen.summarize.hierarchy import run_hierarchy
        from docgen.summarize.store import write_summaries

        existing_cache = {r.node_id: r for r in summary_results}
        retry = RetryPolicy(max_attempts=getattr(args, "retries", 3) + 1)

        try:
            _, summarizer = _build_summarizer(args, output_dir, config)
            results = run_hierarchy(
                graph=graph,
                summarizer=summarizer,
                repo_root=repo_root,
                existing_cache=existing_cache,
                max_workers=getattr(args, "workers", 1),
                retry=retry,
                checkpoint=_checkpoint_writer(summaries_path),
                repair_passes=getattr(args, "repair_passes", 1),
            )
        except FatalBackendError as exc:
            print(
                f"docgen update: fatal backend error at {exc.node_id}: "
                f"{exc.cause.message}",
                file=sys.stderr,
            )
            raise SystemExit(2)

        write_summaries(results, summaries_path)
        summaries_map = {r.node_id: r.text for r in results}
        summary_results = results

    # Re-render only stale pages
    from docgen.check.manifest import PageRecord
    from pathlib import PurePosixPath as _PurePosixPath

    node_map = {n.id: n for n in graph.nodes}
    pages_to_write: list[tuple[str, str]] = []
    updated_records: list = []

    api_page_path = str(_PurePosixPath(config.output_dir) / "pages" / "api.md").replace("\\", "/")

    for page_path in update_plan.stale_pages:
        if page_path == str(_PurePosixPath(config.output_dir) / "pages" / "index.md").replace("\\", "/"):
            text, record = render_index(graph, summaries_map, config.output_dir)
            pages_to_write.append((page_path, text))
            updated_records.append(record)
        elif page_path == api_page_path:
            api_text, api_fact_ids = render_api_table(graph, summaries_map, config.output_dir)
            api_hashes = {
                nid: {"hash_struct": node_map[nid].hash_struct, "hash_source": node_map[nid].hash_source}
                for nid in api_fact_ids
                if nid in node_map and (node_map[nid].hash_struct or node_map[nid].hash_source)
            }
            updated_records.append(PageRecord(
                page_path=api_page_path,
                fact_ids=api_fact_ids,
                hashes=api_hashes,
            ))
            pages_to_write.append((api_page_path, api_text))
        else:
            # Module page: recover module_id from path
            # e.g. "generated/pages/target/app/utils.md" → "target/app/utils.py"
            prefix = config.output_dir + "/pages/"
            if page_path.startswith(prefix):
                module_id = page_path[len(prefix):].replace(".md", ".py")
            else:
                module_id = page_path
            mod_node = node_map.get(module_id)
            if mod_node is None:
                print(f"  WARN: cannot find node for {page_path}; skipping", file=sys.stderr)
                continue
            text, record = render_module_page(mod_node, graph, summaries_map, config.output_dir)
            pages_to_write.append((page_path, text))
            updated_records.append(record)

    write_pages(pages_to_write, repo_root)

    # Rebuild manifest: merge updated records over the existing manifest
    existing_pages = manifest.get("pages", {})
    for rec in updated_records:
        from docgen.check.manifest import build_manifest as _bm
        single = _bm([rec])
        existing_pages[rec.page_path] = single["pages"][rec.page_path]
    new_manifest = {"pages": existing_pages}
    write_manifest(new_manifest, manifest_path)

    print(
        f"  {len(pages_to_write)} pages updated, manifest.json rebuilt",
        file=sys.stderr,
    )

    if getattr(args, "strict", False):
        _enforce_strict(graph, summary_results, command="update")


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
        default=None,
        help=(
            "Summarizer backend: stub, manual, bob_shell, claude_shell, "
            "openai, or anthropic (default: [summarize] in docgen.toml, else stub)."
        ),
    )
    summarize_parser.add_argument(
        "--model", default=None, help="Model name/alias (backend-specific)."
    )
    summarize_parser.add_argument(
        "--base-url",
        dest="base_url",
        default=None,
        help="OpenAI-compatible API root (openai backend).",
    )
    summarize_parser.add_argument(
        "--api-key-env",
        dest="api_key_env",
        default=None,
        help="Environment variable holding the API key.",
    )
    summarize_parser.add_argument(
        "--timeout",
        type=_non_negative_int,
        default=None,
        help="Per-call timeout in seconds (backend-specific default).",
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
    summarize_parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help=(
            "Number of parallel summarizer calls per batch "
            "(default: 1 = sequential). Values above 6 risk "
            "rate-limiting from hosted LLM APIs."
        ),
    )
    summarize_parser.add_argument(
        "--retries",
        type=_non_negative_int,
        default=3,
        help="Retries per node (default: 3; 0 = one attempt).",
    )
    summarize_parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Exit 1 if any node is missing or needs human review.",
    )
    summarize_parser.add_argument(
        "--repair-passes",
        type=_non_negative_int,
        dest="repair_passes",
        default=1,
        help=(
            "Extra bottom-up passes that retry failed nodes so their ancestors "
            "are rebuilt in the same run (default: 1; 0 = disable)."
        ),
    )

    validate_parser = subparsers.add_parser(
        "validate", help="Validate citations in summaries.json (exit 1 if broken)."
    )
    validate_parser.add_argument(
        "--config",
        default="docgen.toml",
        help="Path to docgen.toml (default: docgen.toml in cwd).",
    )

    render_parser = subparsers.add_parser("render", help="Render documentation pages.")
    render_parser.add_argument(
        "--config",
        default="docgen.toml",
        help="Path to docgen.toml (default: docgen.toml in cwd).",
    )

    check_parser = subparsers.add_parser(
        "check", help="Check for doc drift (exit 1 if stale)."
    )
    check_parser.add_argument(
        "--config",
        default="docgen.toml",
        help="Path to docgen.toml (default: docgen.toml in cwd).",
    )
    check_parser.add_argument(
        "--fresh",
        action="store_true",
        default=False,
        help="Re-extract facts before checking.",
    )

    update_parser = subparsers.add_parser("update", help="Regenerate stale pages.")
    update_parser.add_argument(
        "--config",
        default="docgen.toml",
        help="Path to docgen.toml (default: docgen.toml in cwd).",
    )
    update_parser.add_argument(
        "--backend",
        default=None,
        help=(
            "Summarizer backend for re-summarization: stub, manual, bob_shell, "
            "claude_shell, openai, or anthropic (default: docgen.toml, else stub)."
        ),
    )
    update_parser.add_argument(
        "--model", default=None, help="Model name/alias (backend-specific)."
    )
    update_parser.add_argument(
        "--base-url",
        dest="base_url",
        default=None,
        help="OpenAI-compatible API root (openai backend).",
    )
    update_parser.add_argument(
        "--api-key-env",
        dest="api_key_env",
        default=None,
        help="Environment variable holding the API key.",
    )
    update_parser.add_argument(
        "--timeout",
        type=_non_negative_int,
        default=None,
        help="Per-call timeout in seconds (backend-specific default).",
    )
    update_parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help=(
            "Number of parallel summarizer calls per batch "
            "(default: 1 = sequential). Values above 6 risk "
            "rate-limiting from hosted LLM APIs."
        ),
    )
    update_parser.add_argument(
        "--retries",
        type=_non_negative_int,
        default=3,
        help="Retries per node (default: 3; 0 = one attempt).",
    )
    update_parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Exit 1 if any node is missing or needs human review.",
    )
    update_parser.add_argument(
        "--repair-passes",
        type=_non_negative_int,
        dest="repair_passes",
        default=1,
        help=(
            "Extra bottom-up passes that retry failed nodes so their ancestors "
            "are rebuilt in the same run (default: 1; 0 = disable)."
        ),
    )

    subparsers.add_parser("eval", help="Run the evaluation harness.")

    args = parser.parse_args()

    if args.command == "extract":
        _run_extract(args)
    elif args.command == "summarize":
        _run_summarize(args)
    elif args.command == "validate":
        _run_validate(args)
    elif args.command == "render":
        _run_render(args)
    elif args.command == "check":
        _run_check(args)
    elif args.command == "update":
        _run_update(args)
    else:
        raise NotImplementedError(f"Command '{args.command}' not yet implemented.")


if __name__ == "__main__":
    main()
