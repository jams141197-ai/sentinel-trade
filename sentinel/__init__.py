"""Sentinel — a broker-agnostic safety + observability layer you wrap around a bot you already wrote.

    import sentinel

    sentinel.init(
        bot="eth-meanrev-01",
        caps=sentinel.Caps(daily_loss_usd=200, max_position_usd=500, max_open_positions=8),
        heartbeat_minutes=15,
        alerts=[sentinel.Console()],
    )

    @sentinel.broker_positions
    def live_positions():
        return {p["symbol"]: p["qty"] for p in exchange.fetch_positions()}

    @sentinel.order
    def submit(symbol, side, qty, price):
        return exchange.create_order(symbol, "limit", side, qty, price)

    @sentinel.fill
    def on_fill(symbol, side, qty, fill_price, expected_price):
        ...

    sentinel.watch_reconciliation(interval_seconds=30)
"""

from typing import Callable, List, Optional

from .alerts import AlertRouter, Console, Discord, Email, Telegram
from .config import Caps
from .core import Monitor
from .exceptions import CapBreached, SentinelError
from .fills import FillReconciler
from .reconcile import Divergence, diff_positions
from .slippage import slippage_bps

__version__ = "0.1.0"

__all__ = [
    "init", "get_monitor", "Caps", "Console", "Telegram", "Discord", "Email",
    "CapBreached", "SentinelError", "Divergence", "diff_positions", "slippage_bps", "FillReconciler",
    "order", "fill", "position", "broker_positions",
    "watch_reconciliation", "record_fill", "record_paper_fill", "fill_report", "sync_positions", "check_order",
    "halt", "resume", "status", "stop",
]

_monitor: Optional[Monitor] = None


def init(
    bot: str,
    caps: Optional[Caps] = None,
    equity: Optional[float] = None,
    alerts: Optional[List] = None,
    db_path: str = ":memory:",
    heartbeat_minutes: Optional[float] = None,
    market_hours: Optional[Callable[[float], bool]] = None,
    ping_url: Optional[str] = None,
    halt_on_drift: bool = True,
    **kwargs,
) -> Monitor:
    """Create the active monitor. Call this once, before decorating your functions."""
    global _monitor
    _monitor = Monitor(
        bot=bot, caps=caps, equity=equity, alerts=alerts, db_path=db_path,
        heartbeat_minutes=heartbeat_minutes, market_hours=market_hours,
        ping_url=ping_url, halt_on_drift=halt_on_drift, **kwargs,
    )
    if _monitor.heartbeat is not None:
        interval = max(5.0, min(30.0, (heartbeat_minutes * 60) / 2)) if heartbeat_minutes else 30.0
        _monitor.heartbeat.start(interval=interval)
    return _monitor


def get_monitor() -> Monitor:
    if _monitor is None:
        raise SentinelError("sentinel.init(...) has not been called yet")
    return _monitor


# Decorators (imported after get_monitor is defined to avoid circular import).
from .decorators import broker_positions, fill, order, position  # noqa: E402


def watch_reconciliation(interval_seconds: float = 30.0) -> None:
    return get_monitor().watch_reconciliation(interval_seconds)


def record_fill(symbol, side, qty, fill_price, expected_price=None) -> float:
    return get_monitor().record_fill(symbol, side, qty, fill_price, expected_price)


def record_paper_fill(symbol, side, qty, paper_price, live_price=None, bid=None, ask=None, strategy=""):
    """Record a paper-vs-live fill so Sentinel can report how much your fills degrade live."""
    return get_monitor().record_paper_fill(
        symbol, side, qty, paper_price, live_price=live_price, bid=bid, ask=ask, strategy=strategy
    )


def fill_report() -> dict:
    """The paper-vs-live execution-degradation report (the headline number)."""
    return get_monitor().fill_report()


def sync_positions(broker_state) -> List[Divergence]:
    return get_monitor().sync_positions(broker_state)


def check_order(symbol, side, qty, price) -> None:
    return get_monitor().check_order(symbol, side, qty, price)


def halt(reason: str = "manual") -> None:
    return get_monitor().halt(reason)


def resume() -> None:
    return get_monitor().resume()


def status() -> dict:
    return get_monitor().status()


def stop() -> None:
    global _monitor
    if _monitor is not None:
        _monitor.stop()
        _monitor = None
