"""
Tests for task 1.4 — Seeded bug.

Bug: the `create_new_article` route decorator uses HTTP_200_OK instead of
HTTP_201_CREATED as its status_code.  This is a hash_struct change (the
decorator argument changes), not merely a comment/docstring change, so
docgen's drift detector must flag the page.

The test imports `app.api.routes.articles.articles_resource` in a
subprocess (same pattern as task 1.2) so the workspace venv does not need
the target's dependencies installed.

Pass/fail logic:
  - With the bug:    the route's status_code is 200  → test FAILS
  - Without the bug: the route's status_code is 201  → test PASSES
"""

import json
import os
import subprocess
import sys
from pathlib import Path

_TARGET_PYTHON = (
    Path(__file__).parent.parent / "target" / ".venv" / "Scripts" / "python.exe"
)
_HELPER = Path(__file__).parent / "_check_create_article_status.py"

# The correct status code per the RealWorld spec.
EXPECTED_STATUS_CODE = 201


def _run_helper() -> int:
    """Run the helper subprocess and return the status code it found."""
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "dev",
            "SECRET_KEY": "secret",
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
        }
    )
    result = subprocess.run(
        [str(_TARGET_PYTHON), str(_HELPER)],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Helper exited {result.returncode}:\n{result.stderr}"
        )
    return int(result.stdout.strip())


def test_create_article_returns_201() -> None:
    """
    The POST /articles route must declare status_code=201 (HTTP_201_CREATED).

    This test FAILS with the seeded bug (status_code=200) and PASSES once
    the bug is reverted to HTTP_201_CREATED.

    Why this catches hash_struct drift:
      status_code is a decorator argument — it lives inside `hash_struct`
      (structural fields, not just body text).  Changing 201 → 200 alters
      `hash_struct` for `create_new_article`, so docgen flags every doc
      page that cites that node.
    """
    actual = _run_helper()
    assert actual == EXPECTED_STATUS_CODE, (
        f"create_new_article status_code is {actual}, expected {EXPECTED_STATUS_CODE}. "
        f"The seeded bug (HTTP_200_OK) has not been fixed."
    )
