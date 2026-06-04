from sentinel.alerts import AlertRouter, Console


class Boom:
    def send(self, *a, **k):
        raise RuntimeError("channel down")


class Capture:
    def __init__(self):
        self.got = []

    def send(self, title, message, level="warning"):
        self.got.append((level, title, message))


def test_router_fans_out_and_swallows_channel_errors():
    cap = Capture()
    router = AlertRouter([Boom(), cap])
    router.send("T", "M", "critical")  # Boom must not break delivery to cap
    assert cap.got == [("critical", "T", "M")]


def test_console_respects_min_level(capsys):
    c = Console(min_level="critical")
    c.send("T", "low", "info")
    c.send("T", "high", "critical")
    out = capsys.readouterr().out
    assert "low" not in out
    assert "high" in out
