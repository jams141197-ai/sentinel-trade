"""Position reconciliation: diff the bot's internal state against the broker's truth.

This is the part everyone hand-rolls and gets wrong. ``diff_positions`` is pure and
fully tested; :class:`Reconciler` wraps it with a broker-read callback, alerting, and
an optional halt-on-divergence policy (used by the background watcher in core).
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

GHOST = "ghost"        # bot thinks it holds it; broker shows nothing
ORPHAN = "orphan"      # broker holds it; bot doesn't know
MISMATCH = "mismatch"  # both hold it, but quantities differ


@dataclass
class Divergence:
    symbol: str
    kind: str
    internal_qty: float
    broker_qty: float

    def describe(self) -> str:
        if self.kind == GHOST:
            return f"{self.symbol}: bot thinks {self.internal_qty:g}, broker shows none (ghost)"
        if self.kind == ORPHAN:
            return f"{self.symbol}: broker holds {self.broker_qty:g}, bot doesn't know (orphan)"
        return f"{self.symbol}: bot {self.internal_qty:g} vs broker {self.broker_qty:g} (mismatch)"


def diff_positions(
    internal: Dict[str, float], broker: Dict[str, float], tol: float = 1e-6
) -> List[Divergence]:
    """Return divergences between the bot's positions and the broker's.

    Quantities within ``tol`` are treated as equal; positions within ``tol`` of zero
    are treated as flat.
    """
    out: List[Divergence] = []
    for symbol in sorted(set(internal) | set(broker)):
        i = float(internal.get(symbol, 0.0))
        b = float(broker.get(symbol, 0.0))
        i_flat, b_flat = abs(i) <= tol, abs(b) <= tol
        if i_flat and b_flat:
            continue
        if not i_flat and b_flat:
            out.append(Divergence(symbol, GHOST, i, b))
        elif i_flat and not b_flat:
            out.append(Divergence(symbol, ORPHAN, i, b))
        elif abs(i - b) > tol:
            out.append(Divergence(symbol, MISMATCH, i, b))
    return out


class Reconciler:
    """Polls a broker-read callback and reports divergence from internal state.

    Args:
        internal_fn: returns ``{symbol: signed_qty}`` from the bot's own state.
        broker_fn: returns ``{symbol: signed_qty}`` from the broker (your ~10-line callback).
        on_divergence: called with the list of divergences when any are found.
        tol: quantity tolerance.
    """

    def __init__(
        self,
        internal_fn: Callable[[], Dict[str, float]],
        broker_fn: Optional[Callable[[], Dict[str, float]]] = None,
        on_divergence: Optional[Callable[[List[Divergence]], None]] = None,
        tol: float = 1e-6,
    ):
        self.internal_fn = internal_fn
        self.broker_fn = broker_fn
        self.on_divergence = on_divergence
        self.tol = tol

    def run_once(self, broker_state: Optional[Dict[str, float]] = None) -> List[Divergence]:
        """Compute divergences once. ``broker_state`` overrides ``broker_fn`` if given."""
        if broker_state is None:
            if self.broker_fn is None:
                raise ValueError("no broker_fn registered and no broker_state passed")
            broker_state = self.broker_fn()
        divs = diff_positions(self.internal_fn(), broker_state, tol=self.tol)
        if divs and self.on_divergence is not None:
            self.on_divergence(divs)
        return divs
