"""Example BrokerAdapter for Interactive Brokers via ib_async (or ib_insync).

Lazy-imported: importing this module never requires ib_async. EXAMPLE only — the SDK
just needs a callback returning ``{symbol: signed_qty}``.
"""

from typing import Dict, List


class IBKRAdapter:
    def __init__(self, ib):
        # `ib` is a connected ib_async.IB() / ib_insync.IB() instance.
        self.ib = ib

    def get_positions(self) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for pos in self.ib.positions():
            symbol = getattr(pos.contract, "localSymbol", None) or getattr(pos.contract, "symbol", None)
            if symbol:
                out[symbol] = out.get(symbol, 0.0) + float(pos.position)
        return {s: q for s, q in out.items() if abs(q) > 0}

    def get_balance(self) -> float:
        for row in self.ib.accountValues():
            if row.tag == "NetLiquidation":
                try:
                    return float(row.value)
                except (TypeError, ValueError):
                    return 0.0
        return 0.0

    def get_open_orders(self) -> List:
        return list(self.ib.openOrders())
