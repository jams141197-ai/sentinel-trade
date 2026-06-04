from sentinel.heartbeat import Heartbeat


def make(idle=60, market=None):
    now = {"t": 1000.0}
    fired = []
    hb = Heartbeat(
        idle_seconds=idle,
        on_silent=lambda x: fired.append(x),
        market_hours=market,
        clock=lambda: now["t"],
        name="t",
    )
    return hb, now, fired


def test_fires_after_idle():
    hb, now, fired = make(idle=60)
    now["t"] = 1059
    assert hb.check() is False
    now["t"] = 1061
    assert hb.check() is True
    assert fired and fired[0] >= 60


def test_fires_only_once_until_beat():
    hb, now, fired = make(idle=60)
    now["t"] = 1100
    assert hb.check() is True
    assert hb.check() is False  # already fired, no duplicate page
    hb.beat()                    # a fill arrives -> re-arm
    now["t"] = 1161
    assert hb.check() is True


def test_respects_market_hours():
    hb, now, fired = make(idle=60, market=lambda ts: False)
    now["t"] = 5000
    assert hb.check() is False
    assert fired == []


def test_beat_resets_timer():
    hb, now, fired = make(idle=60)
    now["t"] = 1050
    hb.beat()           # last fill now 1050
    now["t"] = 1100     # only 50s since
    assert hb.check() is False
