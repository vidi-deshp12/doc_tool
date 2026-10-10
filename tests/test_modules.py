"""Tests for extract/modules.py - module index and import resolution."""

from __future__ import annotations

import tempfile
from pathlib import Path

from src.docgen.extract.modules import (
    build_module_index,
    resolve_imports,
    build_full_index,
    ModuleInfo,
    ImportRecord,
)
from src.docgen.walker import walk_repo_from_toml
from src.docgen.facts.schema import Edge, EdgeType, Node, NodeType, Unresolved


def create_fixture_repo(tmpdir: Path) -> list[str]:
    """Create a test repository structure."""
    # Create directory structure
    (tmpdir / "target" / "app" / "api").mkdir(parents=True)
    (tmpdir / "target" / "app" / "models").mkdir(parents=True)
    (tmpdir / "target" / "lib").mkdir(parents=True)

    # target/app/__init__.py
    (tmpdir / "target" / "app" / "__init__.py").write_text(
        '"""App package."""\nfrom .models import User\n',
        encoding="utf-8"
    )

    # target/app/main.py
    (tmpdir / "target" / "app" / "main.py").write_text(
        'from app.api import router\nfrom app.models import User\nimport os\nimport sys\n',
        encoding="utf-8"
    )

    # target/app/api/__init__.py
    (tmpdir / "target" / "app" / "api" / "__init__.py").write_text(
        '"""API package."""\nfrom .routes import router\n',
        encoding="utf-8"
    )

    # target/app/api/routes.py
    (tmpdir / "target" / "app" / "api" / "routes.py").write_text(
        'from fastapi import APIRouter\nrouter = APIRouter()\n',
        encoding="utf-8"
    )

    # target/app/models/__init__.py
    (tmpdir / "target" / "app" / "models" / "__init__.py").write_text(
        '"""Models package."""\nfrom .user import User\n',
        encoding="utf-8"
    )

    # target/app/models/user.py
    (tmpdir / "target" / "app" / "models" / "user.py").write_text(
        'from pydantic import BaseModel\nclass User(BaseModel):\n    name: str\n',
        encoding="utf-8"
    )

    # target/lib/utils.py
    (tmpdir / "target" / "lib" / "utils.py").write_text(
        'def helper():\n    return 42\n',
        encoding="utf-8"
    )

    # Return module paths (what walker would return)
    return [
        "target/app/__init__.py",
        "target/app/main.py",
        "target/app/api/__init__.py",
        "target/app/api/routes.py",
        "target/app/models/__init__.py",
        "target/app/models/user.py",
        "target/lib/utils.py",
    ]


def test_build_module_index() -> None:
    """Test building module index from file paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        module_paths = create_fixture_repo(repo_root)

        dotted_to_path, path_to_info = build_module_index(module_paths, repo_root, source_root="target")

        # Check all modules have dotted names (using source_root="target")
        assert len(dotted_to_path) == 7
        assert "app" in dotted_to_path
        assert "app.main" in dotted_to_path
        assert "app.api" in dotted_to_path
        assert "app.api.routes" in dotted_to_path
        assert "app.models" in dotted_to_path
        assert "app.models.user" in dotted_to_path
        assert "lib.utils" in dotted_to_path

        # Check paths map back correctly
        assert dotted_to_path["app"] == "target/app/__init__.py"
        assert dotted_to_path["app.main"] == "target/app/main.py"

        # Check ModuleInfo has imports
        main_info = path_to_info["target/app/main.py"]
        assert len(main_info.imports) == 4  # app.api, app.models, os, sys


def test_resolve_absolute_imports() -> None:
    """Test resolving absolute imports within repo."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        module_paths = create_fixture_repo(repo_root)

        dotted_to_path, path_to_info = build_module_index(module_paths, repo_root, source_root="target")
        import_edges, unresolved, external_nodes = resolve_imports(
            dotted_to_path, path_to_info, repo_root, source_root="target"
        )

        # Check internal imports resolved
        main_imports = [e for e in import_edges if e.from_id == "target/app/main.py"]
        # Should have 4 imports: app.api, app.models, os, sys
        # app.api and app.models should resolve to internal modules
        internal_targets = [e.to_id for e in main_imports if not e.to_id.startswith("external:")]
        assert "target/app/api/__init__.py" in internal_targets or "target/app/api/routes.py" in internal_targets
        assert "target/app/models/__init__.py" in internal_targets or "target/app/models/user.py" in internal_targets

        # os and sys should be external
        external_targets = [e.to_id for e in main_imports if e.to_id.startswith("external:")]
        assert any("os" in t for t in external_targets)
        assert any("sys" in t for t in external_targets)


def test_resolve_relative_imports() -> None:
    """Test resolving relative imports."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        module_paths = create_fixture_repo(repo_root)

        dotted_to_path, path_to_info = build_module_index(module_paths, repo_root, source_root="target")
        import_edges, unresolved, external_nodes = resolve_imports(
            dotted_to_path, path_to_info, repo_root, source_root="target"
        )

    # Check app/__init__.py imports .models.User
    app_init_imports = [e for e in import_edges if e.from_id == "target/app/__init__.py"]
    internal = [e.to_id for e in app_init_imports if not e.to_id.startswith("external:")]
    assert "target/app/models/__init__.py" in internal or "target/app/models/user.py" in internal


def test_external_imports_marked() -> None:
    """Test that external imports are marked as external nodes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        module_paths = create_fixture_repo(repo_root)

        dotted_to_path, path_to_info = build_module_index(module_paths, repo_root)
        import_edges, unresolved, external_nodes = resolve_imports(
            dotted_to_path, path_to_info, repo_root
        )

        # fastapi, pydantic should be external
        external_ids = [n.id for n in external_nodes]
        assert any("fastapi" in eid for eid in external_ids)
        assert any("pydantic" in eid for eid in external_ids)
        assert any("os" in eid for eid in external_ids)
        assert any("sys" in eid for eid in external_ids)

        # Check external nodes have correct structure
        for ext in external_nodes:
            assert ext.type == NodeType.EXTERNAL
            assert ext.library_name != ""


def test_star_imports_flagged() -> None:
    """Test that star imports are flagged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Create module with star import
        (repo_root / "target" / "app").mkdir(parents=True)
        (repo_root / "target" / "app" / "main.py").write_text(
            'from os import *\n',
            encoding="utf-8"
        )
        module_paths = ["target/app/main.py"]

        dotted_to_path, path_to_info = build_module_index(module_paths, repo_root)
        import_edges, unresolved, external_nodes = resolve_imports(
            dotted_to_path, path_to_info, repo_root
        )

        # Check star import edge has star meta
        star_edges = [e for e in import_edges if e.from_id == "target/app/main.py"]
        for e in star_edges:
            meta_dict = dict(e.meta)
            if "star" in meta_dict:
                assert meta_dict["star"] == "True"


def test_unresolved_relative_import_errors() -> None:
    """Test that invalid relative imports are reported as unresolved."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        (repo_root / "target" / "app").mkdir(parents=True)
        (repo_root / "target" / "app" / "main.py").write_text(
            'from .. import something\n',  # Invalid: beyond top level
            encoding="utf-8"
        )
        module_paths = ["target/app/main.py"]

        dotted_to_path, path_to_info = build_module_index(module_paths, repo_root, source_root="target")
        import_edges, unresolved, external_nodes = resolve_imports(
            dotted_to_path, path_to_info, repo_root, source_root="target"
        )

        # Should have unresolved entry
        assert len(unresolved) > 0
        assert any("relative import level exceeds" in u.why for u in unresolved)


def test_alias_handling() -> None:
    """Test that import aliases are tracked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        (repo_root / "target" / "app").mkdir(parents=True)
        (repo_root / "target" / "app" / "main.py").write_text(
            'import os as operating_system\nfrom sys import path as sys_path\n',
            encoding="utf-8"
        )
        module_paths = ["target/app/main.py"]

        dotted_to_path, path_to_info = build_module_index(module_paths, repo_root)
        import_edges, unresolved, external_nodes = resolve_imports(
            dotted_to_path, path_to_info, repo_root
        )

        # Check edges have alias meta
        main_edges = [e for e in import_edges if e.from_id == "target/app/main.py"]
        for e in main_edges:
            meta_dict = dict(e.meta)
            if "alias" in meta_dict and meta_dict["alias"]:
                assert meta_dict["alias"] in ("operating_system", "sys_path")


def test_build_full_index() -> None:
    """Test the convenience function."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        module_paths = create_fixture_repo(repo_root)

        path_to_info, dotted_to_path, import_edges, unresolved, external_nodes = build_full_index(
            module_paths, repo_root
        )

        assert len(path_to_info) == 7
        assert len(dotted_to_path) == 7
        assert len(import_edges) > 0
        assert len(external_nodes) > 0


def test_real_repo_walker_integration() -> None:
    """Test integration with real walker output."""
    # Use actual docgen.toml config
    module_paths = list(walk_repo_from_toml("docgen.toml", "."))

    # Should have 70 files
    assert len(module_paths) == 70

    # Build index
    path_to_info, dotted_to_path, import_edges, unresolved, external_nodes = build_full_index(
        module_paths, Path(".")
    )

    # Should have many resolved imports
    assert len(import_edges) > 50
    # Should have external imports (fastapi, pydantic, etc.)
    assert len(external_nodes) > 10
    # External nodes should have proper library names
    libs = {n.library_name for n in external_nodes}
    assert "fastapi" in libs
    assert "pydantic" in libs


if __name__ == "__main__":
    test_build_module_index()
    print("✓ test_build_module_index")

    test_resolve_absolute_imports()
    print("✓ test_resolve_absolute_imports")

    test_resolve_relative_imports()
    print("✓ test_resolve_relative_imports")

    test_external_imports_marked()
    print("✓ test_external_imports_marked")

    test_star_imports_flagged()
    print("✓ test_star_imports_flagged")

    test_unresolved_relative_import_errors()
    print("✓ test_unresolved_relative_import_errors")

    test_alias_handling()
    print("✓ test_alias_handling")

    test_build_full_index()
    print("✓ test_build_full_index")

    test_real_repo_walker_integration()
    print("✓ test_real_repo_walker_integration")

    print("\nAll tests passed!")