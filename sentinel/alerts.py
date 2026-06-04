"""Alert channels. Network sends are best-effort and never raise into the bot.

A channel implements ``send(title, message, level)``. The :class:`AlertRouter` fans
out to all configured channels and swallows their exceptions — an alerting failure
must never take down the trading bot.
"""

import json
import urllib.parse
import urllib.request
from typing import List, Optional

_LEVELS = {"info": 10, "warning": 20, "critical": 30}


class Console:
    """Prints alerts to stdout. The zero-config default."""

    def __init__(self, min_level: str = "info"):
        self.min_level = min_level

    def send(self, title: str, message: str, level: str = "warning") -> None:
        if _LEVELS.get(level, 20) >= _LEVELS.get(self.min_level, 10):
            print(f"[sentinel:{level}] {title} — {message}")


class Telegram:
    """Telegram alerts. Needs a bot ``token`` (arg or set later); no-ops without one."""

    def __init__(self, chat_id: str, token: Optional[str] = None):
        self.chat_id = chat_id
        self.token = token

    def send(self, title: str, message: str, level: str = "warning") -> None:
        if not self.token:
            return
        try:
            data = urllib.parse.urlencode(
                {"chat_id": self.chat_id, "text": f"{title}\n{message}"}
            ).encode()
            urllib.request.urlopen(
                f"https://api.telegram.org/bot{self.token}/sendMessage", data=data, timeout=5
            )
        except Exception:
            pass


class Discord:
    """Discord webhook alerts."""

    def __init__(self, webhook: str):
        self.webhook = webhook

    def send(self, title: str, message: str, level: str = "warning") -> None:
        try:
            data = json.dumps({"content": f"**{title}**\n{message}"}).encode()
            req = urllib.request.Request(
                self.webhook, data=data, headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass


class Email:
    """SMTP email alerts (best-effort)."""

    def __init__(self, to, sender, host, port=587, username=None, password=None, use_tls=True):
        self.to = to
        self.sender = sender
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls

    def send(self, title: str, message: str, level: str = "warning") -> None:
        try:
            import smtplib
            from email.message import EmailMessage

            msg = EmailMessage()
            msg["Subject"] = f"[sentinel:{level}] {title}"
            msg["From"] = self.sender
            msg["To"] = self.to
            msg.set_content(message)
            with smtplib.SMTP(self.host, self.port, timeout=10) as s:
                if self.use_tls:
                    s.starttls()
                if self.username:
                    s.login(self.username, self.password)
                s.send_message(msg)
        except Exception:
            pass


class AlertRouter:
    def __init__(self, channels: Optional[List] = None):
        self.channels = list(channels or [])

    def send(self, title: str, message: str, level: str = "warning") -> None:
        for ch in self.channels:
            try:
                ch.send(title, message, level)
            except Exception:
                pass
