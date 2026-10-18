"""Simple data models for freshness testing."""


class Item:
    """An item with an id and a label."""

    id: int
    label: str

    def __init__(self, id: int, label: str) -> None:
        self.id = id
        self.label = label
