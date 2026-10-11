"""ManualSummarizer: reads summary files written by a human (or Bob in the IDE).

The early demo flow is: Bob writes a summary in the IDE -> the file lands in a
folder -> the pipeline picks it up. Each node maps to one markdown file whose name
is the node id with characters that are illegal (or awkward) in filenames
replaced, so a node id such as `app/main.py::create_app` becomes a plain filename.
"""

from __future__ import annotations

from pathlib import Path

from .base import MissingSummaryError, SummaryRequest, SummaryResult, hash_input


def _safe_name(node_id: str) -> str:
    """Sanitize a node id into a filename stem.

    `/`, `::`, `:`, and spaces are replaced; `::` becomes `__` so member names
    stay visually separated from path separators.
    """
    return (
        node_id.replace("/", "_")
        .replace("::", "__")
        .replace(":", "_")
        .replace(" ", "_")
    )


class ManualSummarizer:
    """Reads pre-written `.md` files from a folder, one per node.

    Args:
        folder: Directory containing the summary files. Defaults are chosen by the
            caller (the CLI uses `<output_dir>/manual_summaries/`).
    """

    def __init__(self, folder: str | Path) -> None:
        self.folder = Path(folder)

    def summarize(self, req: SummaryRequest) -> SummaryResult:
        path = self.folder / f"{_safe_name(req.node_id)}.md"
        if not path.exists():
            raise MissingSummaryError(req.node_id)

        text = path.read_text(encoding="utf-8")
        return SummaryResult(
            node_id=req.node_id,
            text=text,
            backend="manual",
            hash_input=hash_input(req),
        )
