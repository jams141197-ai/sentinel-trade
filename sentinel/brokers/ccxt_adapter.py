"""Example BrokerAdapter for any ccxt exchange (100+ crypto venues).

``ccxt`` is imported lazily, so importing this module never requires ccxt installed —
only instantiating ``CcxtAdapter`` does. This is an EXAMPLE: the SDK just needs a
callback returning ``{symbol: signed_qty}``; this shows how to build one.
"""

from typing import Dict, List


class CcxtAdapter:
    def __init__(self, exchange):
        # `exchange` is an instantiated ccxt exchange (e.g. ccxt.binance({...})).
        self.exchange = exchange

    def get_positions(self) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for p in self.exchange.fetch_positions() or []:
            symbol = p.get("symbol")
            contracts = p.get("contracts") or p.get("contractSize") or 0.0
            side = (p.get("side") or "long").lower()
            qty = float(contracts) * (1 if side == "long" else -1)
            if symbol and abs(qty) > 0:
                out[symbol] = out.get(symbol, 0.0) + qty
        return out

    def get_balance(self) -> float:
        bal = self.exchange.fetch_balance()
        total = bal.get("total", {})
        # Best-effort: USDT/USD free+used as a proxy for equity.
        for k in ("USDT", "USD", "USDC"):
            if k in total:
                return float(total[k])
        return float(sum(v for v in total.values() if isinstance(v, (int, float))))

    def get_open_orders(self) -> List:
        return self.exchange.fetch_open_orders()
