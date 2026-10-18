"""Streamlit documentation viewer for docgen-generated pages.

Reads generated/pages/ at runtime — no LLM, no database, no API calls.

Run with:
    streamlit run viewer/app.py
"""

from __future__ import annotations

import re
from pathlib import Path

import streamlit as st
from streamlit_mermaid import st_mermaid

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PAGES_DIR = Path(__file__).parent.parent / "generated" / "pages"
DEFAULT_PAGE = "generated/pages/index.md"

st.set_page_config(
    page_title="docgen viewer",
    page_icon="📄",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_pages() -> list[Path]:
    """Return all .md files under PAGES_DIR, sorted by POSIX path."""
    return sorted(PAGES_DIR.rglob("*.md"), key=lambda p: p.as_posix())


def _repo_rel(path: Path) -> str:
    """Convert a page path to a repo-root-relative POSIX string.

    If *path* is already relative (e.g. ``Path("generated/pages/index.md")``
    passed in from session state), return its POSIX form directly.
    Only call ``relative_to`` when the path is absolute (e.g. from rglob).
    """
    if not path.is_absolute():
        return path.as_posix()
    root = Path(__file__).parent.parent
    return path.relative_to(root).as_posix()


def _page_title(content: str, fallback: str) -> tuple[str, str]:
    """Extract the first # heading and return (title, remaining_content).

    Strips the heading line (and any immediately following blank line) from the
    content so it is not rendered twice — once via st.title() and once inside
    st.markdown().  Returns (fallback, content) unchanged when no heading found.
    """
    lines = content.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            # Drop the heading line; also drop the blank line that follows it
            rest_start = i + 1
            if rest_start < len(lines) and lines[rest_start].strip() == "":
                rest_start += 1
            remaining = "".join(lines[rest_start:])
            return title, remaining
    return fallback, content


def _split_mermaid(content: str) -> list[tuple[str, str]]:
    """Split *content* into alternating (kind, text) segments.

    kind is either ``"markdown"`` or ``"mermaid"``.
    Mermaid fenced blocks (```mermaid … ```) are extracted as their own
    segments so they can be rendered by st_mermaid(); everything else goes
    through st.markdown().
    """
    pattern = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
    segments: list[tuple[str, str]] = []
    cursor = 0
    for m in pattern.finditer(content):
        before = content[cursor : m.start()]
        if before:
            segments.append(("markdown", before))
        segments.append(("mermaid", m.group(1).strip()))
        cursor = m.end()
    tail = content[cursor:]
    if tail:
        segments.append(("markdown", tail))
    return segments if segments else [("markdown", content)]


def _render_page(page_path_str: str) -> None:
    """Render the selected page in the main panel."""
    repo_root = Path(__file__).parent.parent
    path = Path(page_path_str)
    # Resolve relative paths against the repo root so the app works regardless
    # of which directory `streamlit run` is called from.
    if not path.is_absolute():
        path = repo_root / path
    if not path.exists():
        st.error(f"Page not found: `{page_path_str}`")
        return

    content = path.read_text(encoding="utf-8")
    rel_path = _repo_rel(path)
    # _page_title strips the heading line from content so it isn't rendered twice
    title, body = _page_title(content, path.stem)

    # Top bar
    st.title(title)
    st.caption(f"`{rel_path}`")
    st.divider()

    # Body: split on mermaid blocks and render each segment appropriately
    for kind, text in _split_mermaid(body):
        if kind == "mermaid":
            # Cap diagram height to avoid excessive scrolling
            st_mermaid(text, height=400)
        else:
            st.markdown(text)


# ---------------------------------------------------------------------------
# Sidebar — nested file tree
# ---------------------------------------------------------------------------

# Tree node type: leaf is a Path; branch is a dict keyed by folder name.
_TreeNode = "dict[str, '_TreeNode | Path']"


def _build_tree(pages: list[Path]) -> tuple[list[Path], dict]:
    """Split pages into top-level files and a nested dict for everything else.

    Returns:
        top_level: pages directly in PAGES_DIR (index.md, api.md, …)
        tree: nested dict ``{folder_name: {subfolder_name: {…, stem: Path}}}``
            Leaves are Path objects; branches are dicts.
    """
    top_level: list[Path] = []
    tree: dict = {}

    for p in pages:
        parts = p.relative_to(PAGES_DIR).parts  # e.g. ("target", "app", "db", "events.md")
        if len(parts) == 1:
            top_level.append(p)
        else:
            node = tree
            for part in parts[:-1]:          # walk/create folder nodes
                node = node.setdefault(part, {})
            node[parts[-1]] = p              # leaf: filename → Path

    return top_level, tree


def _render_tree(node: dict, selected: str, container: object) -> None:
    """Recursively render a tree node inside *container* (sidebar or expander).

    Folders become expanders (auto-expanded when they contain the active page).
    Files become buttons (primary style when active).
    """
    for key in sorted(node):
        value = node[key]
        if isinstance(value, Path):
            # Leaf — render as a button
            repo_rel = _repo_rel(value)
            is_active = repo_rel == selected
            if container.button(
                value.stem,
                key=f"btn_{repo_rel}",
                type="primary" if is_active else "secondary",
                use_container_width=True,
            ):
                st.session_state["selected"] = repo_rel
                st.rerun()
        else:
            # Branch — render as an expander containing recursive children
            folder_name = key
            # Auto-expand if this subtree contains the active page
            expanded = _subtree_contains(value, selected)
            with container.expander(f"📁 {folder_name}", expanded=expanded):
                _render_tree(value, selected, st)  # st inside expander = sidebar context


def _subtree_contains(node: dict, selected: str) -> bool:
    """Return True if any leaf under *node* is the currently selected page."""
    for value in node.values():
        if isinstance(value, Path):
            if _repo_rel(value) == selected:
                return True
        elif _subtree_contains(value, selected):
            return True
    return False


def _build_sidebar() -> None:
    """Populate the sidebar with a fully nested file tree of all .md pages."""
    pages = _all_pages()
    if not pages:
        st.sidebar.warning("No pages found in generated/pages/")
        return

    st.sidebar.title("📄 Pages")

    selected = st.session_state.get("selected", DEFAULT_PAGE)
    top_level, tree = _build_tree(pages)

    # Top-level files first (index, api) — no expander
    for p in top_level:
        repo_rel = _repo_rel(p)
        is_active = repo_rel == selected
        if st.sidebar.button(
            p.stem,
            key=f"btn_{repo_rel}",
            type="primary" if is_active else "secondary",
            use_container_width=True,
        ):
            st.session_state["selected"] = repo_rel
            st.rerun()

    # Nested tree — folders as recursive expanders
    _render_tree(tree, selected, st.sidebar)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point called by Streamlit on every rerun."""
    # Initialise session state with the default page on first load
    if "selected" not in st.session_state:
        st.session_state["selected"] = DEFAULT_PAGE

    _build_sidebar()
    _render_page(st.session_state["selected"])


main()
