from sentinel.events import Event, EventStore


def test_append_and_count():
    s = EventStore(":memory:")
    s.append(Event(type="fill", bot="t", data={"x": 1}))
    s.append(Event(type="halt", bot="t", data={}))
    assert s.count() == 2
    assert s.count(type="fill") == 1
    s.close()


def test_recent_newest_first_and_roundtrips_data():
    s = EventStore(":memory:")
    s.append(Event(type="fill", bot="t", data={"n": 1}))
    s.append(Event(type="fill", bot="t", data={"n": 2}))
    recent = s.recent(10)
    assert recent[0].data["n"] == 2
    assert recent[0].type == "fill" and recent[0].bot == "t"
    s.close()


def test_recent_filtered_by_type():
    s = EventStore(":memory:")
    s.append(Event(type="fill", bot="t"))
    s.append(Event(type="drift", bot="t"))
    assert len(s.recent(type="drift")) == 1
    s.close()
