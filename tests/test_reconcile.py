import pytest

from sentinel.reconcile import GHOST, MISMATCH, ORPHAN, Reconciler, diff_positions


def test_clean_no_divergence():
    assert diff_positions({"A": 1.0}, {"A": 1.0}) == []


def test_ghost_position():
    d = diff_positions({"A": 2.0}, {})
    assert len(d) == 1 and d[0].kind == GHOST and d[0].symbol == "A"
    assert "ghost" in d[0].describe()


def test_orphan_position():
    d = diff_positions({}, {"B": 3.0})
    assert d[0].kind == ORPHAN and d[0].broker_qty == 3.0


def test_quantity_mismatch():
    d = diff_positions({"A": 5.0}, {"A": 3.0})
    assert d[0].kind == MISMATCH and d[0].internal_qty == 5.0 and d[0].broker_qty == 3.0


def test_tolerance_ignores_tiny_diffs():
    assert diff_positions({"A": 1.0}, {"A": 1.0 + 1e-9}) == []


def test_near_zero_treated_as_flat():
    assert diff_positions({"A": 1e-9}, {}) == []


def test_multiple_divergences_sorted():
    d = diff_positions({"Z": 1.0, "A": 2.0}, {"A": 5.0})
    assert [x.symbol for x in d] == ["A", "Z"]


def test_reconciler_run_once_with_broker_state():
    fired = []
    r = Reconciler(internal_fn=lambda: {"A": 5.0}, on_divergence=fired.append)
    divs = r.run_once(broker_state={"A": 3.0})
    assert divs[0].kind == MISMATCH
    assert fired and fired[0] == divs


def test_reconciler_uses_broker_fn():
    r = Reconciler(internal_fn=lambda: {"A": 1.0}, broker_fn=lambda: {"A": 1.0})
    assert r.run_once() == []


def test_reconciler_requires_a_source():
    r = Reconciler(internal_fn=lambda: {})
    with pytest.raises(ValueError):
        r.run_once()
