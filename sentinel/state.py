"""Internal account state: signed positions, average cost, and realized daily PnL.

This is the bot's *own* view of the world. Sentinel diffs it against the broker
(see :mod:`sentinel.reconcile`) to catch divergence.
"""

import threading
from dataclasses import dataclass
from datetime import datetime, date
from typing import Callable, Dict, Optional

_EPS = 1e-12


def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


@dataclass
class Position:
    """A single signed position with average entry price.

    ``qty`` is signed: positive = long, negative = short.
    """

    qty: float = 0.0
    avg_price: float = 0.0

    def apply(self, side: str, qty: float, price: float) -> float:
        """Apply a fill (``side`` is ``"buy"`` or ``"sell"``). Returns realized PnL.

        Average-cost accounting: increasing the position updates the average price;
        reducing it realizes PnL; over-reducing flips the position and re-bases the
        average at ``price``.
        """
        signed = qty if side == "buy" else -qty
        realized = 0.0
        if abs(self.qty) <= _EPS or _sign(self.qty) == _sign(signed):
            # opening or increasing in the same direction
            total = abs(self.qty) + abs(signed)
            if total > _EPS:
                self.avg_price = (self.avg_price * abs(self.qty) + price * abs(signed)) / total
            self.qty += signed
        else:
            # reducing, closing, or flipping
            closing = min(abs(self.qty), abs(signed))
            realized = (price - self.avg_price) * closing * _sign(self.qty)
            new_qty = self.qty + signed
            if abs(new_qty) <= _EPS:
                self.qty = 0.0
                self.avg_price = 0.0
            elif _sign(new_qty) != _sign(self.qty):
                # flipped to the other side: new leg opened at `price`
                self.qty = new_qty
                self.avg_price = price
            else:
                # partially reduced, same side: average unchanged
                self.qty = new_qty
        return realized


class AccountState:
    """Thread-safe account state. Tracks positions, last prices, and realized daily PnL."""

    def __init__(self, equity: Optional[float] = None, clock: Optional[Callable[[], datetime]] = None):
        self._lock = threading.RLock()
        self.positions: Dict[str, Position] = {}
        self.last_price: Dict[str, float] = {}
        self.realized_pnl_today: float = 0.0
        self.equity = equity
        self._clock = clock or datetime.now
        self._day: date = self._clock().date()

    def _roll_day(self) -> None:
        today = self._clock().date()
        if today != self._day:
            self._day = today
            self.realized_pnl_today = 0.0

    def apply_fill(self, symbol: str, side: str, qty: float, price: float) -> float:
        """Record a fill; returns realized PnL booked by it."""
        with self._lock:
            self._roll_day()
            pos = self.positions.setdefault(symbol, Position())
            realized = pos.apply(side, qty, price)
            self.realized_pnl_today += realized
            self.last_price[symbol] = price
            return realized

    def set_equity(self, equity: float) -> None:
        with self._lock:
            self.equity = equity

    def position_qty(self, symbol: str) -> float:
        with self._lock:
            p = self.positions.get(symbol)
            return p.qty if p else 0.0

    def net_positions(self) -> Dict[str, float]:
        """Symbols with a non-zero net position -> signed qty."""
        with self._lock:
            return {s: p.qty for s, p in self.positions.items() if abs(p.qty) > _EPS}

    def open_count(self) -> int:
        with self._lock:
            return sum(1 for p in self.positions.values() if abs(p.qty) > _EPS)

    def deployed_notional(self) -> float:
        """Sum of |qty| * last_price across open positions."""
        with self._lock:
            total = 0.0
            for s, p in self.positions.items():
                px = self.last_price.get(s, p.avg_price)
                total += abs(p.qty) * px
            return total
