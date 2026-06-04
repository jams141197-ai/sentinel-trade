"""Fill-quality / slippage tracking.

``slippage_bps`` is signed so that POSITIVE always means a worse fill (you paid more
on a buy, or received less on a sell). :class:`SlippageTracker` flags degradation when
the recent average blows past a baseline.
"""

from collections import deque
from typing import Deque


def slippage_bps(side: str, expected: float, fill: float) -> float:
    """Slippage in basis points. Positive = worse than expected."""
    if not expected:
        return 0.0
    if side == "buy":
        return (fill - expected) / expected * 1e4
    return (expected - fill) / expected * 1e4


class SlippageTracker:
    def __init__(
        self,
        window: int = 20,
        baseline_bps: float = 0.0,
        alert_factor: float = 3.0,
        min_samples: int = 5,
    ):
        self.samples: Deque[float] = deque(maxlen=window)
        self.baseline_bps = baseline_bps
        self.alert_factor = alert_factor
        self.min_samples = min_samples

    def record(self, side: str, expected: float, fill: float) -> float:
        bps = slippage_bps(side, expected, fill)
        self.samples.append(bps)
        return bps

    def recent_avg(self) -> float:
        return sum(self.samples) / len(self.samples) if self.samples else 0.0

    def degraded(self) -> bool:
        """True if recent average slippage exceeds baseline * alert_factor."""
        if len(self.samples) < self.min_samples:
            return False
        base = self.baseline_bps if self.baseline_bps else 1.0
        return self.recent_avg() > base * self.alert_factor
