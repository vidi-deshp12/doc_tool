"""A simple module with one function and one class for freshness testing."""


class Greeter:
    """Greets people by name."""

    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    def greet(self) -> str:
        """Return a greeting string."""
        return f"Hello, {self.name}!"


def farewell(name: str) -> str:
    """Return a farewell string."""
    return f"Goodbye, {name}!"
