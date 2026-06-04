"""Example: Sentinel wrapped around a real ccxt bot.

Illustrative — needs `pip install "sentinel-trade[ccxt]"` and your own API keys/strategy.
The point is the broker callback: ~10 lines turns any ccxt exchange into a Sentinel source.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sentinel
from sentinel.brokers.ccxt_adapter import CcxtAdapter


def build_exchange():
    import ccxt

    return ccxt.binanceusdm(
        {"apiKey": os.environ["BINANCE_KEY"], "secret": os.environ["BINANCE_SECRET"]}
    )


def main():
    exchange = build_exchange()
    adapter = CcxtAdapter(exchange)

    sentinel.init(
        bot="binance-funding-arb",
        caps=sentinel.Caps(daily_loss_usd=300, max_position_usd=2000, max_open_positions=10),
        equity=adapter.get_balance(),
        heartbeat_minutes=20,
        alerts=[sentinel.Telegram(chat_id=os.environ["TG_CHAT"], token=os.environ["TG_TOKEN"])],
        db_path="sentinel.db",
    )

    # The broker truth — Sentinel diffs your internal state against this.
    @sentinel.broker_positions
    def broker():
        return adapter.get_positions()

    @sentinel.order
    def submit(symbol, side, qty, price):
        return exchange.create_order(symbol, "limit", side, qty, price)

    @sentinel.fill
    def on_fill(symbol, side, qty, fill_price, expected_price):
        pass  # Sentinel records position/PnL/slippage; your logic goes here

    sentinel.watch_reconciliation(interval_seconds=30)

    # ... your strategy loop calls submit(...) and on_fill(...) as usual.
    # A breached cap raises sentinel.CapBreached out of submit() before the order is sent.


if __name__ == "__main__":
    main()
