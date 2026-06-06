"""The Monitor — wires state, caps, reconciliation, slippage, events, and alerts together."""

import threading
import time
from typing import Callable, List, Optional

from .alerts import AlertRouter, Console
from .caps import CapGate
from .config import Caps
from .events import Event, EventStore
from .fills import FillReconciler
from .reconcile import Divergence, Reconciler
from .slippage import SlippageTracker
from .state import AccountState


class Monitor:
    def __init__(
        self,
        bot: str,
        caps: Optional[Caps] = None,
        equity: Optional[float] = None,
        alerts: Optional[List] = None,
        db_path: str = ":memory:",
        heartbeat_minutes: Optional[float] = None,
        market_hours: Optional[Callable[[float], bool]] = None,
        ping_url: Optional[str] = None,
        reconcile_tol: float = 1e-6,
        halt_on_drift: bool = True,
        slippage: Optional[SlippageTracker] = None,
        clock=None,
    ):
        self.bot = bot
        self.state = AccountState(equity=equity, clock=clock)
        self.cap_gate = CapGate(caps, self.state)
        self.events = EventStore(db_path)
        self.alerts = AlertRouter(alerts if alerts is not None else [Console()])
        self.slippage = slippage or SlippageTracker()
        self.fills = FillReconciler()
        self.halt_on_drift = halt_on_drift
        self.broker_positions_fn: Optional[Callable[[], dict]] = None
        self.reconciler = Reconciler(
            internal_fn=self.state.net_positions, on_divergence=self._on_divergence, tol=reconcile_tol
        )

        self.heartbeat = None
        if heartbeat_minutes:
            from .heartbeat import Heartbeat

            self.heartbeat = Heartbeat(
                idle_seconds=heartbeat_minutes * 60,
                on_silent=self._on_silent,
                market_hours=market_hours,
                ping_url=ping_url,
                name=bot,
            )

        self._warned: set = set()
        self._warn_lock = threading.Lock()
        self._recon_stop = threading.Event()
        self._recon_thread: Optional[threading.Thread] = None

    # --- emit / alert helpers ---
    def emit(self, type_: str, **data) -> None:
        self.events.append(Event(type=type_, bot=self.bot, ts=time.time(), data=data))

    def alert(self, title: str, message: str, level: str = "warning") -> None:
        self.alerts.send(f"[{self.bot}] {title}", message, level)

    def warn_once(self, key: str, message: str) -> None:
        with self._warn_lock:
            if key in self._warned:
                return
            self._warned.add(key)
        self.emit("warning", message=message)
        self.alert("Config warning", message, "warning")

    # --- recording / gating ---
    def record_fill(self, symbol, side, qty, fill_price, expected_price=None) -> float:
        realized = self.state.apply_fill(symbol, side, float(qty), float(fill_price))
        bps = self.slippage.record(side, float(expected_price), float(fill_price)) if expected_price else None
        self.emit(
            "fill", symbol=symbol, side=side, qty=qty, price=fill_price,
            expected=expected_price, slippage_bps=bps, realized=realized,
        )
        if self.heartbeat:
            self.heartbeat.beat()
        if expected_price and self.slippage.degraded():
            avg = self.slippage.recent_avg()
            self.emit("slippage", symbol=symbol, recent_bps=round(avg, 1))
            self.alert("Slippage degrading", f"{symbol}: recent avg {avg:.0f} bps", "warning")
        return realized

    def record_paper_fill(self, symbol, side, qty, paper_price, live_price=None, bid=None, ask=None, strategy=""):
        """Record a paper-vs-live fill for execution-degradation reconciliation. Returns the FillRecord."""
        rec = self.fills.record(symbol, side, qty, paper_price, live_price=live_price, bid=bid, ask=ask, strategy=strategy)
        self.emit("paper_fill", symbol=symbol, side=side, qty=rec.qty, paper=rec.paper_price,
                  live=rec.live_price, slippage_bps=rec.slippage_bps, cost=rec.cost)
        return rec

    def fill_report(self) -> dict:
        """Paper-vs-live execution-degradation report — the headline number for how much fills slip live."""
        return self.fills.report()

    def check_order(self, symbol, side, qty, price) -> None:
        """Raises CapBreached to block. Call BEFORE submitting an order."""
        self.cap_gate.check(symbol, side, float(qty), float(price))

    # --- reconciliation ---
    def sync_positions(self, broker_state) -> List[Divergence]:
        return self.reconciler.run_once(broker_state=broker_state)

    def watch_reconciliation(self, interval_seconds: float = 30.0) -> None:
        if self.broker_positions_fn is None:
            raise ValueError("register a @sentinel.broker_positions callback before watch_reconciliation()")
        self.reconciler.broker_fn = self.broker_positions_fn
        if self._recon_thread is not None:
            return

        def loop():
            while not self._recon_stop.wait(interval_seconds):
                try:
                    self.reconciler.run_once()
                except Exception as exc:
                    self.emit("error", where="reconcile", error=str(exc))

        self._recon_thread = threading.Thread(
            target=loop, daemon=True, name=f"sentinel-reconcile-{self.bot}"
        )
        self._recon_thread.start()

    def _on_divergence(self, divs: List[Divergence]) -> None:
        msg = "; ".join(d.describe() for d in divs)
        for d in divs:
            self.emit("drift", symbol=d.symbol, kind=d.kind, internal=d.internal_qty, broker=d.broker_qty)
        if self.halt_on_drift:
            self.cap_gate.halt(f"position drift: {msg}")
            self.alert("Position drift — trading paused", msg, "critical")
        else:
            self.alert("Position drift", msg, "critical")

    def _on_silent(self, idle: float) -> None:
        self.emit("silent_death", idle_seconds=round(idle, 1))
        self.alert(
            "Silent death",
            f"no fills in {idle / 60:.1f} min during market hours — process alive, zero economic activity",
            "critical",
        )

    # --- control ---
    def halt(self, reason: str = "manual") -> None:
        self.cap_gate.halt(reason)
        self.emit("halt", reason=reason)
        self.alert("HALTED", reason, "critical")

    def resume(self) -> None:
        self.cap_gate.resume()
        self.emit("resume")
        self.alert("Resumed", "trading re-enabled", "info")

    def status(self) -> dict:
        fills = self.fills.report()
        return {
            "bot": self.bot,
            "halted": self.cap_gate.halted,
            "halt_reason": self.cap_gate.halt_reason,
            "realized_pnl_today": self.state.realized_pnl_today,
            "open_positions": self.state.open_count(),
            "positions": self.state.net_positions(),
            "recent_slippage_bps": round(self.slippage.recent_avg(), 1),
            "fill_degradation_pct": fills["degradation_pct"],
            "fill_headline": fills["headline"],
        }

    def stop(self) -> None:
        self._recon_stop.set()
        if self.heartbeat:
            self.heartbeat.stop()
        self.events.close()
