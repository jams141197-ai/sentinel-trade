"""The BrokerAdapter protocol — the entire broker-agnostic contract.

Implement these three methods (or just hand Sentinel a callback that returns
``get_positions()``) and Sentinel works with any broker.
"""

from typing import Dict, List, Protocol, runtime_checkable


@runtime_checkable
class BrokerAdapter(Protocol):
    def get_positions(self) -> Dict[str, float]:
        """Return ``{symbol: signed_qty}`` (positive long, negative short)."""
        ...

    def get_balance(self) -> float:
        """Return account equity / free balance (used for max_deployed_pct)."""
        ...

    def get_open_orders(self) -> List:
        """Return the broker's currently open orders (used for orphan-order checks)."""
        ...
