"""
Tests for task 1.2 — Ground truth.

These tests validate that eval/ground_truth.json was generated correctly
and that it matches our hand-count of route decorators in the target repo.

The tests do NOT import the target app or call any LLM.  They only read
the committed JSON file produced by `python eval/build_ground_truth.py`.
"""

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

GROUND_TRUTH_PATH = Path(__file__).parent.parent / "eval" / "ground_truth.json"

# Hand-counted by grepping '@router.<method>' in target/app/api/routes/
# (see task 1.2 cross-check in docs/memory.md)
HAND_COUNTED_ROUTES = 19


@pytest.fixture(scope="module")
def ground_truth() -> dict:
    """Load and return the parsed ground_truth.json."""
    assert GROUND_TRUTH_PATH.exists(), (
        f"{GROUND_TRUTH_PATH} not found. "
        "Run: python eval/build_ground_truth.py --target-python target/.venv/Scripts/python.exe"
    )
    return json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Structure tests
# ---------------------------------------------------------------------------


def test_ground_truth_has_required_keys(ground_truth: dict) -> None:
    """Top-level keys must all be present."""
    for key in ("openapi_version", "route_count", "routes", "schemas"):
        assert key in ground_truth, f"Missing key: {key}"


def test_openapi_version_is_set(ground_truth: dict) -> None:
    assert ground_truth["openapi_version"].startswith("3."), (
        "Expected OpenAPI 3.x"
    )


def test_routes_is_a_list(ground_truth: dict) -> None:
    assert isinstance(ground_truth["routes"], list)


def test_schemas_is_a_dict(ground_truth: dict) -> None:
    assert isinstance(ground_truth["schemas"], dict)


# ---------------------------------------------------------------------------
# Route count tests
# ---------------------------------------------------------------------------


def test_route_count_matches_list_length(ground_truth: dict) -> None:
    """The stored route_count must equal len(routes)."""
    assert ground_truth["route_count"] == len(ground_truth["routes"])


def test_route_count_matches_hand_count(ground_truth: dict) -> None:
    """
    The route count from app.openapi() must equal the number of @router.<method>
    decorators found by hand in the target source.

    19 decorators were counted by grep in target/app/api/routes/ — see
    docs/memory.md decision D-015.
    """
    assert ground_truth["route_count"] == HAND_COUNTED_ROUTES, (
        f"Expected {HAND_COUNTED_ROUTES} routes (hand-counted), "
        f"got {ground_truth['route_count']}"
    )


# ---------------------------------------------------------------------------
# Per-route field tests
# ---------------------------------------------------------------------------


def test_every_route_has_required_fields(ground_truth: dict) -> None:
    """Every route entry must have method, path, and operation_id."""
    required = {"method", "path", "operation_id"}
    for i, route in enumerate(ground_truth["routes"]):
        missing = required - route.keys()
        assert not missing, f"Route[{i}] is missing fields: {missing}"


def test_every_route_method_is_uppercase(ground_truth: dict) -> None:
    valid_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
    for route in ground_truth["routes"]:
        assert route["method"] in valid_methods, (
            f"Unexpected HTTP method: {route['method']!r}"
        )


def test_every_route_path_starts_with_api_prefix(ground_truth: dict) -> None:
    """All routes in this app are under /api (api_prefix from AppSettings)."""
    for route in ground_truth["routes"]:
        assert route["path"].startswith("/api/"), (
            f"Route path does not start with /api/: {route['path']!r}"
        )


def test_no_duplicate_method_path_combinations(ground_truth: dict) -> None:
    """Each (method, path) pair must appear at most once."""
    seen: set[tuple[str, str]] = set()
    for route in ground_truth["routes"]:
        key = (route["method"], route["path"])
        assert key not in seen, f"Duplicate route: {key}"
        seen.add(key)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


def test_core_schemas_present(ground_truth: dict) -> None:
    """Key domain schemas must appear in components/schemas."""
    expected = {
        "UserInResponse",
        "ArticleInResponse",
        "ListOfArticlesInResponse",
        "CommentInResponse",
        "ProfileInResponse",
        "TagsInList",
    }
    missing = expected - ground_truth["schemas"].keys()
    assert not missing, f"Missing schemas: {missing}"


def test_schema_count_is_reasonable(ground_truth: dict) -> None:
    """There should be at least 10 schemas (sanity check)."""
    assert len(ground_truth["schemas"]) >= 10, (
        f"Only {len(ground_truth['schemas'])} schemas found; expected >= 10"
    )


# ---------------------------------------------------------------------------
# Spot-check specific routes
# ---------------------------------------------------------------------------


def _routes_by_key(ground_truth: dict) -> dict[tuple[str, str], dict]:
    return {(r["method"], r["path"]): r for r in ground_truth["routes"]}


def test_auth_login_route(ground_truth: dict) -> None:
    routes = _routes_by_key(ground_truth)
    assert ("POST", "/api/users/login") in routes


def test_auth_register_route(ground_truth: dict) -> None:
    routes = _routes_by_key(ground_truth)
    assert ("POST", "/api/users") in routes


def test_articles_crud_routes(ground_truth: dict) -> None:
    routes = _routes_by_key(ground_truth)
    assert ("GET", "/api/articles") in routes
    assert ("POST", "/api/articles") in routes
    assert ("GET", "/api/articles/{slug}") in routes
    assert ("PUT", "/api/articles/{slug}") in routes
    assert ("DELETE", "/api/articles/{slug}") in routes


def test_tags_route(ground_truth: dict) -> None:
    routes = _routes_by_key(ground_truth)
    assert ("GET", "/api/tags") in routes
