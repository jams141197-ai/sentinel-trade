from sentinel.fills import FillReconciler


def test_buy_crosses_to_ask_and_costs():
    fr = FillReconciler()
    r = fr.record("X", "buy", 10, paper_price=100, bid=99.5, ask=101.0)
    assert r.live_price == 101.0          # a buy crosses the spread to the ask
    assert r.slippage_bps > 0             # worse than paper
    assert round(r.cost, 2) == round((101.0 - 100) * 10, 2)


def test_sell_crosses_to_bid_and_costs():
    fr = FillReconciler()
    r = fr.record("X", "sell", 10, paper_price=100, bid=99.0, ask=100.5)
    assert r.live_price == 99.0           # a sell crosses to the bid
    assert r.slippage_bps > 0
    assert round(r.cost, 2) == round((100 - 99.0) * 10, 2)


def test_explicit_live_price_wins():
    fr = FillReconciler()
    r = fr.record("X", "buy", 5, paper_price=100, live_price=100.5, bid=1, ask=999)
    assert r.live_price == 100.5
    assert round(r.cost, 2) == round(0.5 * 5, 2)


def test_no_live_info_means_no_degradation():
    fr = FillReconciler()
    r = fr.record("X", "buy", 5, paper_price=100)
    assert r.live_price == 100 and r.cost == 0 and r.slippage_bps == 0


def test_report_aggregates_and_headline():
    fr = FillReconciler()
    fr.record("X", "buy", 10, 100, live_price=101, strategy="momentum")    # cost 10
    fr.record("X", "sell", 10, 110, live_price=109, strategy="momentum")   # cost 10
    rep = fr.report()
    assert rep["fills"] == 2
    assert rep["total_cost"] == 20.0
    assert rep["paper_notional"] == 100 * 10 + 110 * 10  # 2100
    assert round(rep["degradation_pct"], 3) == round(20 / 2100 * 100, 3)
    assert rep["avg_slippage_bps"] > 0
    assert rep["by_strategy"]["momentum"]["fills"] == 2
    assert "live execution ran" in rep["headline"]


def test_empty_report_is_safe():
    rep = FillReconciler().report()
    assert rep["fills"] == 0 and rep["headline"]
