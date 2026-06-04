"""The decorators that bolt Sentinel onto a bot you already wrote.

- ``@order``  — runs the cap gate synchronously BEFORE your order function. A breach
  raises CapBreached and your order is never sent.
- ``@fill``   — records the fill (position, PnL, slippage) when your fill handler runs.
- ``@position`` — registers a callback returning the bot's own view of positions
  (overrides Sentinel's fill-derived view for reconciliation).
- ``@broker_positions`` — registers the ~10-line callback that reads the broker.

``@order``/``@fill`` resolve the active monitor at CALL time, so they can be applied
before or after ``sentinel.init()``. ``@position``/``@broker_positions`` register at
decoration time and require ``init()`` first.
"""

import functools
import inspect
from typing import Callable, List


def _extract(fn: Callable, args, kwargs, names: List[str]) -> dict:
    """Best-effort: bind args by name from the wrapped function's signature."""
    try:
        bound = inspect.signature(fn).bind_partial(*args, **kwargs)
        bound.apply_defaults()
        return {n: bound.arguments.get(n) for n in names}
    except Exception:
        return {n: kwargs.get(n) for n in names}


def order(fn: Callable) -> Callable:
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        from sentinel import get_monitor

        m = get_monitor()
        p = _extract(fn, args, kwargs, ["symbol", "side", "qty", "price"])
        if p["side"] is None or p["qty"] is None or p["price"] is None:
            m.warn_once(
                f"order:{fn.__name__}",
                f"@order could not read side/qty/price from {fn.__name__}() — caps NOT enforced "
                f"for it. Pass them as named args, or call sentinel.check_order(...) explicitly.",
            )
            return fn(*args, **kwargs)
        m.check_order(p["symbol"], p["side"], p["qty"], p["price"])  # raises CapBreached to block
        return fn(*args, **kwargs)

    return wrapper


def fill(fn: Callable) -> Callable:
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        from sentinel import get_monitor

        m = get_monitor()
        p = _extract(fn, args, kwargs, ["symbol", "side", "qty", "fill_price", "expected_price"])
        if p["symbol"] is None or p["side"] is None or p["qty"] is None or p["fill_price"] is None:
            m.warn_once(
                f"fill:{fn.__name__}",
                f"@fill could not read symbol/side/qty/fill_price from {fn.__name__}() — fill NOT "
                f"recorded. Use named args or call sentinel.record_fill(...) explicitly.",
            )
        else:
            m.record_fill(p["symbol"], p["side"], p["qty"], p["fill_price"], p.get("expected_price"))
        return fn(*args, **kwargs)

    return wrapper


def position(fn: Callable) -> Callable:
    """Register the bot's own positions source (overrides the fill-derived view)."""
    from sentinel import get_monitor

    get_monitor().reconciler.internal_fn = fn
    return fn


def broker_positions(fn: Callable) -> Callable:
    """Register the broker-read callback used by reconciliation."""
    from sentinel import get_monitor

    get_monitor().broker_positions_fn = fn
    return fn
