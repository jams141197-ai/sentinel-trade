"""The synchronous, fail-closed cap gate — the differentiating piece of Sentinel.

``CapGate.check`` runs *inside* your order function, before the order is sent.
It is a handful of in-memory comparisons (microseconds, no network) and it fails
CLOSED: if it cannot verify state, it raises rather than waving an order through.
"""

import threading
from typing import Optional

from .config import Caps
from .exceptions import CapBreached
from .state import AccountState

_EPS = 1e-9


class CapGate:
    def __init__(self, caps: Optional[Caps], state: AccountState):
        self.caps = caps or Caps()
        self.state = state
        self._lock = threading.RLock()
        self.halted = False
        self.halt_reason = ""

    def halt(self, reason: str = "") -> None:
        with self._lock:
            self.halted = True
            self.halt_reason = reason

    def resume(self) -> None:
        with self._lock:
            self.halted = False
            self.halt_reason = ""

    def check(self, symbol: str, side: str, qty: float, price: float) -> None:
        """Raise :class:`CapBreached` to block the order. Returns ``None`` if allowed.

        Fail-closed: any unexpected error verifying state becomes a CapBreached.
        """
        try:
            with self._lock:
                if self.halted:
                    raise CapBreached("halted", self.halt_reason or "trading halted")

                c = self.caps

                # 1) daily-loss LATCH — once breached, halt and stay halted.
                if c.daily_loss_usd is not None and self.state.realized_pnl_today <= -abs(c.daily_loss_usd):
                    self.halt(f"daily loss {self.state.realized_pnl_today:.2f} <= -{abs(c.daily_loss_usd):.2f}")
                    raise CapBreached("daily_loss", self.halt_reason)

                order_notional = abs(qty) * price

                # 2) per-order size
                if c.max_order_usd is not None and order_notional > abs(c.max_order_usd) + _EPS:
                    raise CapBreached("max_order_usd", f"order {order_notional:.2f} > {abs(c.max_order_usd):.2f}")

                signed = qty if side == "buy" else -qty
                cur = self.state.position_qty(symbol)
                proj = cur + signed

                # 3) projected position notional
                if c.max_position_usd is not None and abs(proj) * price > abs(c.max_position_usd) + _EPS:
                    raise CapBreached(
                        "max_position_usd", f"projected position {abs(proj) * price:.2f} > {abs(c.max_position_usd):.2f}"
                    )

                # 4) opening a NEW symbol when already at the cap
                opening_new = abs(cur) <= _EPS < abs(proj)
                if c.max_open_positions is not None and opening_new and self.state.open_count() >= c.max_open_positions:
                    raise CapBreached("max_open_positions", f"already {self.state.open_count()} positions open")

                # 5) deployed-capital fraction of equity
                if c.max_deployed_pct is not None and self.state.equity:
                    cur_notional = abs(cur) * price
                    proj_notional = abs(proj) * price
                    proj_deployed = self.state.deployed_notional() - cur_notional + proj_notional
                    limit = abs(c.max_deployed_pct) * self.state.equity
                    if proj_deployed > limit + _EPS:
                        raise CapBreached("max_deployed_pct", f"deployed {proj_deployed:.2f} > {limit:.2f}")
        except CapBreached:
            raise
        except Exception as exc:  # fail-closed
            raise CapBreached("fail_closed", f"could not verify caps: {exc}")
