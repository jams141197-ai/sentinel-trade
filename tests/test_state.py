from datetime import datetime

from sentinel.state import AccountState, Position


def test_long_open_and_average():
    p = Position()
    assert p.apply("buy", 10, 100) == 0.0
    assert p.qty == 10 and p.avg_price == 100
    assert p.apply("buy", 10, 120) == 0.0
    assert p.qty == 20 and p.avg_price == 110


def test_long_close_realizes_pnl():
    p = Position()
    p.apply("buy", 10, 100)
    realized = p.apply("sell", 4, 130)
    assert realized == (130 - 100) * 4
    assert p.qty == 6 and p.avg_price == 100  # average unchanged on partial reduce


def test_short_profit():
    p = Position()
    p.apply("sell", 10, 100)  # short 10 @ 100
    assert p.qty == -10 and p.avg_price == 100
    realized = p.apply("buy", 10, 90)  # cover @ 90 -> profit 100
    assert realized == 100
    assert p.qty == 0 and p.avg_price == 0


def test_flip_long_to_short():
    p = Position()
    p.apply("buy", 5, 100)
    realized = p.apply("sell", 8, 110)  # close 5 (+50), open short 3 @ 110
    assert realized == (110 - 100) * 5
    assert p.qty == -3 and p.avg_price == 110


def test_full_close_resets_average():
    p = Position()
    p.apply("buy", 5, 100)
    p.apply("sell", 5, 90)
    assert p.qty == 0 and p.avg_price == 0


def test_account_realized_pnl_accumulates():
    s = AccountState()
    s.apply_fill("X", "buy", 10, 100)
    s.apply_fill("X", "sell", 5, 110)  # +50
    assert round(s.realized_pnl_today, 6) == 50.0


def test_daily_reset_on_new_day():
    now = {"t": datetime(2026, 6, 3, 10, 0, 0)}
    s = AccountState(clock=lambda: now["t"])
    s.apply_fill("X", "buy", 10, 100)
    s.apply_fill("X", "sell", 10, 90)  # realized -100
    assert round(s.realized_pnl_today, 6) == -100.0
    now["t"] = datetime(2026, 6, 4, 9, 0, 0)
    s.apply_fill("Y", "buy", 1, 100)  # new day -> reset before applying (open books nothing)
    assert s.realized_pnl_today == 0.0


def test_open_count_and_net_positions():
    s = AccountState()
    s.apply_fill("A", "buy", 1, 100)
    s.apply_fill("B", "sell", 2, 50)
    assert s.open_count() == 2
    assert s.net_positions() == {"A": 1.0, "B": -2.0}
    s.apply_fill("A", "sell", 1, 100)  # close A
    assert s.open_count() == 1
    assert "A" not in s.net_positions()


def test_deployed_notional_uses_last_price():
    s = AccountState()
    s.apply_fill("A", "buy", 2, 100)  # last price 100 -> 200
    s.apply_fill("B", "buy", 1, 50)   # -> 50
    assert s.deployed_notional() == 250.0
