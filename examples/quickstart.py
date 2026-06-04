"""Runnable demo — wraps a (fake) bot with Sentinel and trips every guard.

    python examples/quickstart.py

No broker, no keys, no network. Just shows the gate, the daily-loss latch, and
drift detection firing on a simulated exchange.
"""

import os
import sys

# Make `import sentinel` work when run straight from the repo.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sentinel

# A pretend exchange holding the broker's TRUE positions.
exchange_positions = {}


def place(symbol, side, qty, price):
    signed = qty if side == "buy" else -qty
    exchange_positions[symbol] = exchange_positions.get(symbol, 0.0) + signed
    if abs(exchange_positions[symbol]) < 1e-9:
        exchange_positions.pop(symbol, None)


def main():
    sentinel.init(
        bot="demo-bot",
        caps=sentinel.Caps(daily_loss_usd=50, max_order_usd=1000, max_open_positions=3),
        alerts=[sentinel.Console()],
        db_path="sentinel.db",
    )

    @sentinel.broker_positions
    def broker():
        return dict(exchange_positions)

    @sentinel.order
    def submit(symbol, side, qty, price):
        place(symbol, side, qty, price)
        print(f"   -> ORDER SENT: {side} {qty} {symbol} @ {price}")
        return "ok"

    @sentinel.fill
    def on_fill(symbol, side, qty, fill_price, expected_price=None):
        print(f"   -> FILL: {side} {qty} {symbol} @ {fill_price}")

    print("\n1) A normal order passes the gate:")
    submit(symbol="ETH", side="buy", qty=2, price=100)
    on_fill(symbol="ETH", side="buy", qty=2, fill_price=100, expected_price=100)

    print("\n2) An oversize order is BLOCKED before it's sent:")
    try:
        submit(symbol="ETH", side="buy", qty=50, price=100)  # 5000 > 1000 cap
    except sentinel.CapBreached as e:
        print(f"   -> BLOCKED: {e}")

    print("\n3) A losing trade trips the daily-loss latch:")
    submit(symbol="ETH", side="sell", qty=2, price=70)
    on_fill(symbol="ETH", side="sell", qty=2, fill_price=70, expected_price=70)  # realized -60
    try:
        submit(symbol="ETH", side="buy", qty=1, price=100)
    except sentinel.CapBreached as e:
        print(f"   -> BLOCKED (halted for the day): {e}")

    print("\n4) Resume, then a position the bot doesn't know about trips drift detection:")
    sentinel.resume()
    exchange_positions["DOGE"] = 1000.0  # appeared at the broker; bot never placed it
    for d in sentinel.sync_positions(broker()):
        print(f"   -> DRIFT: {d.describe()}")
    print(f"   -> halted now? {sentinel.get_monitor().cap_gate.halted}")

    print("\n5) Final status:")
    for k, v in sentinel.status().items():
        print(f"   {k}: {v}")

    sentinel.stop()
    print("\nDone. Event log written to sentinel.db — `streamlit run dashboard/app.py` to explore it.\n")


if __name__ == "__main__":
    main()
