"""
Subprocess helper for tests/test_seeded_bug.py.

Imports the articles router (no DB connection needed — importing the module
only loads Python objects, it never opens a socket), finds the
create_new_article route, and prints its status_code to stdout.

Exit codes:
  0  — found the route, printed status_code
  1  — route not found or import error
"""

import sys
from pathlib import Path

# Add target/ to sys.path so `app.*` imports work.
sys.path.insert(0, str(Path(__file__).parent.parent / "target"))

try:
    from app.api.routes.articles.articles_resource import router
except Exception as exc:
    print(f"Import failed: {exc}", file=sys.stderr)
    sys.exit(1)

# Find the POST "" route (create_new_article).
for route in router.routes:
    # APIRoute objects have .methods (set of str) and .status_code (int).
    if hasattr(route, "methods") and hasattr(route, "status_code"):
        if route.methods == {"POST"} and route.path == "":
            print(route.status_code)
            sys.exit(0)

print("create_new_article route not found", file=sys.stderr)
sys.exit(1)
