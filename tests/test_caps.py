import pytest

from sentinel.caps import CapGate
from sentinel.config import Caps
from sentinel.exceptions import CapBreached
from sentinel.state import AccountState


def gate(caps, equity=None):
    return CapGate(caps, AccountState(equity=equity))


def test_allows_when_under_caps():
    g = gate(Caps(max_order_usd=1000))
    g.check("X", "buy", 5, 100)  # 500, no raise


def test_max_order_usd_blocks_single_order():
    g = gate(Caps(max_order_usd=1000))
    g.check("X", "buy", 10, 100)  # exactly 1000 allowed
    with pytest.raises(CapBreached) as e:
        g.check("X", "buy", 20, 100)  # 2000
    assert e.value.cap == "max_order_usd"


def test_daily_loss_latches_and_requires_resume():
    s = AccountState()
    g = CapGate(Caps(daily_loss_usd=200), s)
    g.check("X", "buy", 1, 100)  # fine
    s.realized_pnl_today = -250
    with pytest.raises(CapBreached) as e:
        g.check("X", "buy", 1, 100)
    assert e.value.cap == "daily_loss"
    assert g.halted
    # Latched: even a tiny order is blocked while halted
    s.realized_pnl_today = 0.0
    with pytest.raises(CapBreached) as e2:
        g.check("X", "buy", 1, 100)
    assert e2.value.cap == "halted"
    g.resume()
    g.check("X", "buy", 1, 100)  # allowed again


def test_max_position_usd_blocks_projected_breach():
    s = AccountState()
    g = CapGate(Caps(max_position_usd=1000), s)
    s.apply_fill("X", "buy", 8, 100)  # position notional 800
    g.check("X", "buy", 2, 100)  # -> 1000 exactly, allowed
    with pytest.raises(CapBreached) as e:
        g.check("X", "buy", 5, 100)  # -> 1300
    assert e.value.cap == "max_position_usd"


def test_max_open_positions_blocks_new_symbol_only():
    s = AccountState()
    g = CapGate(Caps(max_open_positions=2), s)
    s.apply_fill("A", "buy", 1, 100)
    s.apply_fill("B", "buy", 1, 100)
    with pytest.raises(CapBreached) as e:
        g.check("C", "buy", 1, 100)  # opening a 3rd symbol
    assert e.value.cap == "max_open_positions"
    g.check("A", "buy", 1, 100)  # adding to an existing symbol is fine


def test_max_deployed_pct():
    s = AccountState(equity=1000)
    g = CapGate(Caps(max_deployed_pct=0.5), s)
    g.check("X", "buy", 4, 100)  # 400 <= 500
    with pytest.raises(CapBreached) as e:
        g.check("X", "buy", 6, 100)  # 600 > 500
    assert e.value.cap == "max_deployed_pct"


def test_fail_closed_on_state_error():
    class BadState(AccountState):
        def position_qty(self, symbol):
            raise RuntimeError("broker state unavailable")

    g = CapGate(Caps(max_position_usd=100), BadState())
    with pytest.raises(CapBreached) as e:
        g.check("X", "buy", 1, 100)
    assert e.value.cap == "fail_closed"


def test_no_caps_allows_everything():
    g = gate(None)
    g.check("X", "buy", 1_000_000, 100)  # no raise
