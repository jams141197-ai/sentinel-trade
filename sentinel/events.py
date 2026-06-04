"""Append-only event log backed by SQLite (the dashboard reads this)."""

import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Event:
    type: str
    bot: str
    ts: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)


class EventStore:
    """Thread-safe SQLite event store. Use ``":memory:"`` for tests, a file path for real bots."""

    def __init__(self, path: str = ":memory:"):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS events ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, bot TEXT, type TEXT, data TEXT)"
        )
        self._conn.commit()

    def append(self, event: Event) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO events (ts, bot, type, data) VALUES (?, ?, ?, ?)",
                (event.ts, event.bot, event.type, json.dumps(event.data)),
            )
            self._conn.commit()

    def recent(self, n: int = 100, type: Optional[str] = None) -> List[Event]:
        with self._lock:
            if type:
                cur = self._conn.execute(
                    "SELECT ts, bot, type, data FROM events WHERE type = ? ORDER BY id DESC LIMIT ?",
                    (type, n),
                )
            else:
                cur = self._conn.execute(
                    "SELECT ts, bot, type, data FROM events ORDER BY id DESC LIMIT ?", (n,)
                )
            rows = cur.fetchall()
        return [Event(type=r[2], bot=r[1], ts=r[0], data=json.loads(r[3])) for r in rows]

    def count(self, type: Optional[str] = None) -> int:
        with self._lock:
            if type:
                return self._conn.execute("SELECT COUNT(*) FROM events WHERE type = ?", (type,)).fetchone()[0]
            return self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
