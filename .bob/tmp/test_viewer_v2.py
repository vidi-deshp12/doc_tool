import re
from pathlib import Path

# ── _page_title ──────────────────────────────────────────────────────────────

def _page_title(content, fallback):
    lines = content.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            rest_start = i + 1
            if rest_start < len(lines) and lines[rest_start].strip() == "":
                rest_start += 1
            remaining = "".join(lines[rest_start:])
            return title, remaining
    return fallback, content

# heading stripped + blank line after heading also stripped
t, body = _page_title("# Architecture Overview\n\nSome content here.\n", "x")
assert t == "Architecture Overview", repr(t)
assert body == "Some content here.\n", repr(body)

# heading with no blank line after
t, body = _page_title("# My Page\nFirst line.\n", "x")
assert t == "My Page"
assert body == "First line.\n", repr(body)

# no heading → fallback, content unchanged
t, body = _page_title("no heading\nsome text\n", "fallback")
assert t == "fallback"
assert body == "no heading\nsome text\n"

# heading not first line → still found; content before the heading is dropped
# (all real pages start with # as the first line, so this edge case doesn't arise)
t, body = _page_title("preamble\n# Title Here\ncontent\n", "x")
assert t == "Title Here"
assert body == "content\n", repr(body)

# ── _build_tree ──────────────────────────────────────────────────────────────

PAGES_DIR = Path("generated/pages")

def _build_tree(pages, pages_dir):
    top_level = []
    tree = {}
    for p in pages:
        parts = p.relative_to(pages_dir).parts
        if len(parts) == 1:
            top_level.append(p)
        else:
            node = tree
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = p
    return top_level, tree

# Build from real pages
pages = sorted(PAGES_DIR.rglob("*.md"), key=lambda p: p.as_posix())
top, tree = _build_tree(pages, PAGES_DIR)

# index.md and api.md should be top-level
top_stems = [p.stem for p in top]
assert "index" in top_stems, top_stems
assert "api" in top_stems, top_stems

# "target" should be a folder key in tree
assert "target" in tree, list(tree.keys())

# target/app should be nested
assert "app" in tree["target"], list(tree["target"].keys())

# target/app/services/jwt.md should be a Path leaf
jwt = tree["target"]["app"]["services"]["jwt.md"]
assert isinstance(jwt, Path), type(jwt)
assert jwt.stem == "jwt"

# subtree_contains logic
def _repo_rel(p):
    if not p.is_absolute():
        return p.as_posix()
    root = Path(__file__).parent
    return p.relative_to(root).as_posix()

def _subtree_contains(node, selected):
    for value in node.values():
        if isinstance(value, Path):
            if _repo_rel(value) == selected:
                return True
        elif _subtree_contains(value, selected):
            return True
    return False

jwt_rel = _repo_rel(jwt)
assert _subtree_contains(tree["target"]["app"]["services"], jwt_rel)
assert not _subtree_contains(tree["target"]["app"]["services"], "generated/pages/index.md")

print(f"OK — {len(pages)} pages, {len(top)} top-level, tree keys: {list(tree.keys())}, all checks pass")
