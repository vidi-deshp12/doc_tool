"""
Task 1.2 — Ground truth builder.

Runs dump_ground_truth.py in a subprocess with dummy environment variables
so the target FastAPI app can be imported without a real database.

Usage:
    python eval/build_ground_truth.py [--target-python <path>]

Options:
    --target-python   Path to the Python interpreter that has the target
                      app's dependencies installed.  Defaults to the same
                      interpreter running this script (sys.executable).

Output:
    eval/ground_truth.json

The script sets the following dummy env vars before the subprocess starts
(real values are never needed; the app is imported but never started):
    APP_ENV        = dev
    SECRET_KEY     = secret
    DATABASE_URL   = postgresql://user:pass@localhost/db
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Timeout (seconds) for the subprocess that imports the app.
_IMPORT_TIMEOUT = 30


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build eval/ground_truth.json")
    parser.add_argument(
        "--target-python",
        default=sys.executable,
        help="Python interpreter with the target app's dependencies installed.",
    )
    return parser.parse_args()


def build(target_python: str) -> Path:
    """
    Run the dump helper in a subprocess and return the path to the output file.

    A subprocess is used because importing the target app executes its
    module-level code (DB pool setup, etc.).  Running it in a child process
    with a timeout prevents hangs and keeps our environment clean.
    """
    project_root = Path(__file__).parent.parent
    dump_script = project_root / "eval" / "dump_ground_truth.py"
    output_path = project_root / "eval" / "ground_truth.json"

    # Dummy environment: satisfies pydantic validation without a real DB.
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "dev",
            "SECRET_KEY": "secret",
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
        }
    )

    result = subprocess.run(
        [target_python, str(dump_script), str(output_path)],
        capture_output=True,
        text=True,
        timeout=_IMPORT_TIMEOUT,
        env=env,
    )

    if result.returncode != 0:
        print("--- stdout ---", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print("--- stderr ---", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(
            f"dump_ground_truth.py exited with code {result.returncode}"
        )

    print(result.stdout.strip())
    return output_path


def cross_check(output_path: Path) -> None:
    """
    Print a brief cross-check table so the route count can be verified by
    hand against a text search for route decorators in the target repo.
    """
    data = json.loads(output_path.read_text(encoding="utf-8"))
    routes = data["routes"]
    print(f"\nRoute count from app.openapi(): {len(routes)}")
    print("(Cross-check: grep '@router\\.' in target/app/api/routes/)")
    print()
    print(f"{'METHOD':<8} {'PATH'}")
    print("-" * 60)
    for r in routes:
        print(f"{r['method']:<8} {r['path']}")
    print()
    print(f"Schemas: {', '.join(sorted(data['schemas'].keys()))}")


def main() -> None:
    args = parse_args()
    output_path = build(args.target_python)
    cross_check(output_path)
    print(f"\nGround truth written to: {output_path}")


if __name__ == "__main__":
    main()
