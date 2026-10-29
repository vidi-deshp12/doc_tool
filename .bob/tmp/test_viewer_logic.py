import re
from pathlib import Path

def _split_mermaid(content):
    pattern = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
    segments = []
    cursor = 0
    for m in pattern.finditer(content):
        before = content[cursor:m.start()]
        if before:
            segments.append(("markdown", before))
        segments.append(("mermaid", m.group(1).strip()))
        cursor = m.end()
    tail = content[cursor:]
    if tail:
        segments.append(("markdown", tail))
    return segments if segments else [("markdown", content)]

def _page_title(content, fallback):
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback

# Test 1: no mermaid
s = _split_mermaid("hello world")
assert s == [("markdown", "hello world")], s

# Test 2: mermaid only
s = _split_mermaid("```mermaid\nflowchart LR\n  A --> B\n```")
assert s == [("mermaid", "flowchart LR\n  A --> B")], s

# Test 3: text before + mermaid + text after
content = "before\n```mermaid\nflowchart LR\n  A-->B\n```\nafter"
s = _split_mermaid(content)
assert s[0] == ("markdown", "before\n"), repr(s[0])
assert s[1] == ("mermaid", "flowchart LR\n  A-->B"), repr(s[1])
assert s[2] == ("markdown", "\nafter"), repr(s[2])

# Test 4: page title
assert _page_title("# Architecture Overview\n\ntext", "x") == "Architecture Overview"
assert _page_title("no heading here", "fallback") == "fallback"

# Test 5: pages directory exists and index.md has mermaid
pages = list(Path("generated/pages").rglob("*.md"))
assert len(pages) > 0, "no pages found"
index_content = Path("generated/pages/index.md").read_text(encoding="utf-8")
segs = _split_mermaid(index_content)
mermaid_segs = [s for s in segs if s[0] == "mermaid"]
assert len(mermaid_segs) >= 1, f"expected mermaid block in index.md, got segments: {[s[0] for s in segs]}"

print(f"OK - {len(pages)} pages, {len(mermaid_segs)} mermaid block(s) in index.md, all checks pass")
