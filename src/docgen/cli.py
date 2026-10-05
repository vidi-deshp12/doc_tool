"""CLI entry point: extract | summarize | render | check | update | eval."""
import argparse


def main() -> None:
    """Parse arguments and dispatch to the appropriate sub-command."""
    parser = argparse.ArgumentParser(
        prog="docgen",
        description="Cited, drift-aware documentation generator for Python repositories.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("extract", help="Extract facts from the target repo.")
    subparsers.add_parser("summarize", help="Generate cited summaries from facts.")
    subparsers.add_parser("render", help="Render documentation pages.")
    subparsers.add_parser("check", help="Check for doc drift (exit 1 if stale).")
    subparsers.add_parser("update", help="Regenerate stale pages.")
    subparsers.add_parser("eval", help="Run the evaluation harness.")

    args = parser.parse_args()
    raise NotImplementedError(f"Command '{args.command}' not yet implemented.")


if __name__ == "__main__":
    main()
