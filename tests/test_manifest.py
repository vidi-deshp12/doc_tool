"""Tests for check/manifest.py: PageRecord, build_manifest, write_manifest, read_manifest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from docgen.check.manifest import PageRecord, build_manifest, read_manifest, write_manifest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_records() -> list[PageRecord]:
    return [
        PageRecord(
            page_path="generated/pages/index.md",
            fact_ids=["system", "myapp"],
            hashes={
                "myapp": {"hash_struct": "abc123", "hash_source": "def456"},
            },
        ),
        PageRecord(
            page_path="generated/pages/myapp/utils.md",
            fact_ids=["myapp/utils.py", "myapp/utils.py::greet"],
            hashes={
                "myapp/utils.py": {"hash_struct": "aaa", "hash_source": "bbb"},
                "myapp/utils.py::greet": {"hash_struct": "ccc", "hash_source": "ddd"},
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Test 1: write + read round-trip produces identical content
# ---------------------------------------------------------------------------

def test_manifest_roundtrip(tmp_path: Path) -> None:
    """write_manifest followed by read_manifest returns the same dict."""
    records = _sample_records()
    manifest = build_manifest(records)

    path = tmp_path / "manifest.json"
    write_manifest(manifest, path)
    loaded = read_manifest(path)

    assert loaded == manifest


# ---------------------------------------------------------------------------
# Test 2: same inputs → byte-identical output
# ---------------------------------------------------------------------------

def test_manifest_stable_json(tmp_path: Path) -> None:
    """build_manifest + write_manifest is deterministic (byte-identical on two calls)."""
    records = _sample_records()

    path1 = tmp_path / "manifest1.json"
    path2 = tmp_path / "manifest2.json"
    write_manifest(build_manifest(records), path1)
    write_manifest(build_manifest(records), path2)

    assert path1.read_text(encoding="utf-8") == path2.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 3: every page file has a manifest entry
# ---------------------------------------------------------------------------

def test_manifest_covers_all_pages() -> None:
    """build_manifest produces one entry per PageRecord."""
    records = _sample_records()
    manifest = build_manifest(records)
    pages = manifest["pages"]

    for rec in records:
        assert rec.page_path in pages, f"{rec.page_path!r} missing from manifest"


# ---------------------------------------------------------------------------
# Test 4: a known node's hash_struct is stored correctly
# ---------------------------------------------------------------------------

def test_manifest_records_hash_struct() -> None:
    """The recorded hash_struct for a known node matches the PageRecord hashes."""
    records = [
        PageRecord(
            page_path="generated/pages/myapp/models.md",
            fact_ids=["myapp/models.py"],
            hashes={
                "myapp/models.py": {"hash_struct": "deadbeef", "hash_source": "cafebabe"},
            },
        )
    ]
    manifest = build_manifest(records)
    stored = manifest["pages"]["generated/pages/myapp/models.md"]["hashes"]["myapp/models.py"]
    assert stored["hash_struct"] == "deadbeef"
    assert stored["hash_source"] == "cafebabe"
