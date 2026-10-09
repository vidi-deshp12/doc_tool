"""
Subprocess helper for task 1.2 — Ground truth.

Run this script *inside* the target repo's Python environment.
It imports the FastAPI app object, calls app.openapi(), and writes
the result as JSON to the path given as the first argument.

Usage (called by build_ground_truth.py):
    python eval/dump_ground_truth.py <output_path>

Environment variables required before calling:
    SECRET_KEY, DATABASE_URL  (dummy values are fine; DB is never opened)
"""

import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: dump_ground_truth.py <output_path>", file=sys.stderr)
        sys.exit(2)

    output_path = Path(sys.argv[1])

    # Add target/ to sys.path so `app.*` imports resolve.
    target_dir = Path(__file__).parent.parent / "target"
    sys.path.insert(0, str(target_dir))

    # Import the app object.  The app is never *started* (no ASGI lifespan);
    # we only call openapi() which is a pure in-memory operation.
    from app.main import app  # noqa: E402  (import not at top — intentional)

    spec = app.openapi()

    # Build a compact, stable summary:
    # - routes: list of {method, path, operation_id, name, summary}
    # - schemas: dict of component schema names (values are the full schema objects)
    routes = []
    for path_str, path_item in sorted(spec.get("paths", {}).items()):
        for method, operation in sorted(path_item.items()):
            if method in {"get", "post", "put", "delete", "patch", "head", "options"}:
                routes.append(
                    {
                        "method": method.upper(),
                        "path": path_str,
                        "operation_id": operation.get("operationId", ""),
                        "summary": operation.get("summary", ""),
                        "tags": operation.get("tags", []),
                    }
                )

    schemas = spec.get("components", {}).get("schemas", {})

    ground_truth = {
        "openapi_version": spec.get("openapi", ""),
        "route_count": len(routes),
        "routes": routes,
        "schemas": schemas,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(ground_truth, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"Wrote {len(routes)} routes and {len(schemas)} schemas to {output_path}")


if __name__ == "__main__":
    main()
