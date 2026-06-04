"""Silent-economic-death watchdog.

The bot is *running* — cron green, logs writing, no exceptions — but it has placed
no trades in N minutes during market hours because something quietly broke. Generic
infra monitoring cannot see this. The heartbeat can. It also optionally pings an
external URL each loop so an outside system notices if the *process* dies entirely.

``check`` is pure and testable (inject ``clock``); ``start``/``stop`` run it on a
background thread.
"""

import threading
import time
import urllib.request
from typing import Callable, Optional


class Heartbeat:
    def __init__(
        self,
        idle_seconds: float,
        on_silent: Optional[Callable[[float], None]] = None,
        market_hours: Optional[Callable[[float], bool]] = None,
        ping_url: Optional[str] = None,
        clock: Optional[Callable[[], float]] = None,
        name: str = "bot",
    ):
        self.idle_seconds = idle_seconds
        self.on_silent = on_silent
        self.market_hours = market_hours  # callable(now_ts) -> bool; None = always active
        self.ping_url = ping_url
        self._clock = clock or time.time
        self.name = name
        self.last_fill_ts = self._clock()
        self._active = True
        self._fired = False
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def beat(self) -> None:
        """Call on every fill. Resets the idle timer and re-arms the alert."""
        self.last_fill_ts = self._clock()
        self._fired = False

    def pause(self) -> None:
        self._active = False

    def resume(self) -> None:
        self._active = True
        self.beat()

    def _in_market(self, now: float) -> bool:
        return True if self.market_hours is None else bool(self.market_hours(now))

    def check(self) -> bool:
        """Return True (and fire ``on_silent`` once) if the bot has gone silent."""
        now = self._clock()
        if not self._active or not self._in_market(now):
            return False
        if (now - self.last_fill_ts) >= self.idle_seconds and not self._fired:
            self._fired = True
            if self.on_silent:
                self.on_silent(now - self.last_fill_ts)
            return True
        return False

    def _ping(self) -> None:
        if self.ping_url:
            try:
                urllib.request.urlopen(self.ping_url, timeout=5)
            except Exception:
                pass

    def _loop(self, interval: float) -> None:
        while not self._stop.wait(interval):
            try:
                self.check()
                self._ping()
            except Exception:
                pass

    def start(self, interval: float = 30.0) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._loop, args=(interval,), daemon=True, name=f"sentinel-heartbeat-{self.name}"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
