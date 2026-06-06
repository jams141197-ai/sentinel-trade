"""Paper-vs-live fill reconciliation — the one number for how much your fills degrade live.

Paper and backtest fills are optimistic: instant, mid-price, no spread, no slippage. Live fills
cross the spread and slip. That gap is the single most common reason a bot that looked great in
paper bleeds money live — and almost nobody measures it *before* they go live.

Feed Sentinel each fill with the price your paper/backtest assumed plus either the actual live
price OR the live bid/ask (Sentinel models a realistic crossing fill). It reports the degradation:
average slippage in basis points, the dollar cost, and the percentage your paper results overstate
live execution. That's the number you want before you risk real money.

    fr = FillReconciler()
    fr.record("ETH/USDT", "buy",  qty=2, paper_price=2500, bid=2499.5, ask=2501.0)
    fr.record("ETH/USDT", "sell", qty=2, paper_price=2520, live_price=2517.8)
    print(fr.report()["headline"])
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from .slippage import slippage_bps


@dataclass
class FillRecord:
    symbol: str
    side: str
    qty: float
    paper_price: float
    live_price: float
    strategy: str = ""
    slippage_bps: float = 0.0
    cost: float = 0.0  # dollars worse than paper assumed (positive = worse live)


class FillReconciler:
    """Accumulates paper-vs-live fills and reports the execution degradation."""

    def __init__(self):
        self.records: List[FillRecord] = []

    @staticmethod
    def _resolve_live(side: str, paper_price: float, live_price, bid, ask) -> float:
        if live_price is not None:
            return float(live_price)
        if bid is not None and ask is not None:
            return float(ask) if side == "buy" else float(bid)  # a realistic crossing fill
        return float(paper_price)  # no live info -> assume no degradation (conservative)

    def record(self, symbol, side, qty, paper_price, live_price=None, bid=None, ask=None, strategy="") -> FillRecord:
        """Record one fill. Provide ``live_price`` OR ``bid``+``ask`` (Sentinel models the crossing fill)."""
        paper_price = float(paper_price)
        qty = abs(float(qty))
        live = self._resolve_live(side, paper_price, live_price, bid, ask)
        bps = slippage_bps(side, paper_price, live)  # positive = worse than paper
        cost = (live - paper_price) * qty if side == "buy" else (paper_price - live) * qty
        rec = FillRecord(symbol, side, qty, paper_price, live, strategy, round(bps, 2), round(cost, 6))
        self.records.append(rec)
        return rec

    def report(self) -> Dict:
        n = len(self.records)
        if n == 0:
            return {"fills": 0, "avg_slippage_bps": 0.0, "total_cost": 0.0, "paper_notional": 0.0,
                    "degradation_pct": 0.0, "by_strategy": {}, "headline": "No fills recorded yet."}

        total_cost = sum(r.cost for r in self.records)
        paper_notional = sum(r.paper_price * r.qty for r in self.records)
        avg_bps = sum(r.slippage_bps for r in self.records) / n
        deg_pct = (total_cost / paper_notional * 100.0) if paper_notional else 0.0

        by_strategy: Dict[str, Dict] = {}
        for r in self.records:
            s = by_strategy.setdefault(r.strategy or "(default)", {"fills": 0, "cost": 0.0, "_bps": 0.0})
            s["fills"] += 1
            s["cost"] += r.cost
            s["_bps"] += r.slippage_bps
        for s in by_strategy.values():
            s["avg_bps"] = round(s.pop("_bps") / s["fills"], 1)
            s["cost"] = round(s["cost"], 2)

        headline = (
            f"Across {n} fills, live execution ran ~{avg_bps:.0f} bps worse than paper "
            f"— {deg_pct:.2f}% of traded value (${total_cost:,.2f}) your paper results never showed."
        )
        return {"fills": n, "avg_slippage_bps": round(avg_bps, 1), "total_cost": round(total_cost, 2),
                "paper_notional": round(paper_notional, 2), "degradation_pct": round(deg_pct, 3),
                "by_strategy": by_strategy, "headline": headline}

    def headline(self) -> str:
        return self.report()["headline"]
