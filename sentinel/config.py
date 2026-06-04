"""Configuration dataclasses for Sentinel."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Caps:
    """Hard risk limits enforced synchronously *before* each order.

    Any limit left as ``None`` is not enforced. ``daily_loss_usd`` is a latch:
    once breached, the gate HALTS and blocks every subsequent order until you
    call :func:`sentinel.resume`. All other caps block only the offending order.

    Args:
        daily_loss_usd: Halt for the day once realized PnL <= -this value.
        max_order_usd: Block any single order whose notional exceeds this.
        max_position_usd: Block any order that would push a position's notional past this.
        max_open_positions: Block opening a *new* symbol once this many are open.
        max_deployed_pct: Block any order that would push deployed capital past this
            fraction (0..1) of ``equity`` (requires equity to be set).
    """

    daily_loss_usd: Optional[float] = None
    max_order_usd: Optional[float] = None
    max_position_usd: Optional[float] = None
    max_open_positions: Optional[int] = None
    max_deployed_pct: Optional[float] = None
