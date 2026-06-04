"""Sentinel exception types."""


class SentinelError(Exception):
    """Base class for all Sentinel errors."""


class CapBreached(SentinelError):
    """Raised synchronously inside the order gate to BLOCK an order.

    A CapBreached must propagate out of your wrapped order function so the order
    is never submitted. ``cap`` names which rule fired; ``detail`` is human-readable.
    """

    def __init__(self, cap: str, detail: str = ""):
        self.cap = cap
        self.detail = detail
        super().__init__(f"cap breach [{cap}]: {detail}" if detail else f"cap breach [{cap}]")
