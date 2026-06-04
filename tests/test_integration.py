import pytest

import sentinel
from sentinel.exceptions import CapBreached


class Capture:
    def __init__(self):
        self.msgs = []

    def send(self, title, message, level="warning"):
        self.msgs.append((level, title, message))


@pytest.fixture(autouse=True)
def _reset_monitor():
    yield
    try:
        sentinel.stop()
    except Exception:
        pass


def test_order_gate_blocks_oversize_order():
    sentinel.init(bot="t", caps=sentinel.Caps(max_order_usd=1000), alerts=[Capture()])
    placed = []

    @sentinel.order
    def submit(symbol, side, qty, price):
        placed.append((symbol, side, qty, price))
        return "ok"

    assert submit(symbol="X", side="buy", qty=5, price=100) == "ok"
    with pytest.raises(CapBreached):
        submit(symbol="X", side="buy", qty=50, price=100)  # 5000 > 1000
    assert placed == [("X", "buy", 5, 100)]  # blocked order body never ran


def test_fill_updates_position_and_pnl():
    sentinel.init(bot="t", caps=None, alerts=[Capture()])

    @sentinel.fill
    def on_fill(symbol, side, qty, fill_price, expected_price=None):
        return "filled"

    on_fill(symbol="X", side="buy", qty=10, fill_price=100)
    on_fill(symbol="X", side="sell", qty=4, fill_price=130, expected_price=130)
    st = sentinel.status()
    assert st["positions"]["X"] == 6
    assert round(st["realized_pnl_today"], 6) == (130 - 100) * 4


def test_daily_loss_latch_blocks_subsequent_orders():
    sentinel.init(bot="t", caps=sentinel.Caps(daily_loss_usd=50), alerts=[Capture()])

    @sentinel.fill
    def on_fill(symbol, side, qty, fill_price, expected_price=None):
        pass

    @sentinel.order
    def submit(symbol, side, qty, price):
        return "ok"

    on_fill(symbol="X", side="buy", qty=10, fill_price=100)
    on_fill(symbol="X", side="sell", qty=10, fill_price=90)  # realized -100 <= -50
    with pytest.raises(CapBreached):
        submit(symbol="X", side="buy", qty=1, price=100)
    assert sentinel.get_monitor().cap_gate.halted


def test_drift_halts_and_alerts_critical():
    cap = Capture()
    sentinel.init(bot="t", caps=None, alerts=[cap], halt_on_drift=True)

    @sentinel.broker_positions
    def broker():
        return {"GHOST": 5.0}

    divs = sentinel.sync_positions({"GHOST": 5.0})
    assert divs[0].kind == "orphan"
    assert sentinel.get_monitor().cap_gate.halted
    assert any(lvl == "critical" and "drift" in title.lower() for lvl, title, _ in cap.msgs)


def test_misconfigured_order_decorator_warns_but_does_not_block():
    cap = Capture()
    sentinel.init(bot="t", caps=sentinel.Caps(max_order_usd=10), alerts=[cap])
    ran = []

    @sentinel.order
    def weird(ticker, amount):  # wrong param names — Sentinel can't read the order
        ran.append(1)
        return "ran"

    # Must NOT block (breaking every order is worse than the disease); must warn loudly.
    assert weird("X", 999999) == "ran"
    assert ran == [1]
    assert any("Config warning" in title for _, title, _ in cap.msgs)


def test_status_and_resume_cycle():
    sentinel.init(bot="t", caps=sentinel.Caps(daily_loss_usd=10), alerts=[Capture()])
    sentinel.halt("manual test")
    assert sentinel.status()["halted"] is True
    sentinel.resume()
    assert sentinel.status()["halted"] is False
