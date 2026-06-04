from sentinel.slippage import SlippageTracker, slippage_bps


def test_buy_worse_fill_is_positive():
    # paid 1% more than expected -> +100 bps
    assert round(slippage_bps("buy", 100, 101), 4) == 100.0


def test_sell_worse_fill_is_positive():
    # received 1% less than expected -> +100 bps
    assert round(slippage_bps("sell", 100, 99), 4) == 100.0


def test_buy_better_fill_is_negative():
    assert slippage_bps("buy", 100, 99) < 0


def test_zero_expected_is_safe():
    assert slippage_bps("buy", 0, 100) == 0.0


def test_tracker_detects_degradation():
    t = SlippageTracker(window=10, baseline_bps=10, alert_factor=3, min_samples=5)
    for _ in range(5):
        t.record("buy", 100, 100.5)  # 50 bps each
    assert round(t.recent_avg(), 2) == 50.0
    assert t.degraded()  # 50 > 10*3


def test_tracker_quiet_under_baseline():
    t = SlippageTracker(window=10, baseline_bps=10, alert_factor=3, min_samples=5)
    for _ in range(5):
        t.record("buy", 100, 100.1)  # 10 bps each
    assert not t.degraded()


def test_tracker_needs_min_samples():
    t = SlippageTracker(min_samples=5)
    t.record("buy", 100, 200)  # huge slippage but only 1 sample
    assert not t.degraded()
