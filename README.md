# Sentinel

**A broker-agnostic safety + observability layer you wrap around a trading bot you already wrote.**

> Your paper results are lying to you. Sentinel tells you *by how much* — before you risk a dollar.

Paper and backtest fills are optimistic: instant, mid-price, no spread. Live fills cross the spread and slip — and that gap is the **#1 reason a bot that looked great in paper bleeds money live.** Almost nobody measures it before going live. Sentinel does, in three lines:

```python
sentinel.record_paper_fill("ETH/USDT", "buy", qty=2, paper_price=2500, bid=2499.5, ask=2501.0)
print(sentinel.fill_report()["headline"])
# Across 1,240 fills, live execution ran ~14 bps worse than paper
# — 1.8% of traded value ($3,140) your backtest never showed.
```

That's the headline feature. Then, once you *are* live, Sentinel catches the other **live-only** failures that blow up retail bots — and does the one thing Datadog, Sentry, and your homemade Telegram notifier can't: it **hard-stops the order path before the next order**, not after an alert.

- 📉 **Paper-vs-live fill reconciliation** — the one number for how much your fills degrade live, plus a per-strategy breakdown. The part backtesters and paper accounts structurally can't show you.
- 🛑 **Hard-stop cap enforcement** — daily-loss, position-size, order-size, open-position, and deployed-% caps, checked *synchronously inside your order function*. A breach raises before the order is sent. Fail-closed.
- 🫥 **Silent-death heartbeat** — "no fills in N minutes during market hours" while the process is alive and logs are writing. The failure mode generic monitoring is structurally blind to.
- ⚠️ **Position-vs-broker reconciliation** — diffs your bot's view against the broker's truth and halts on divergence: ghost positions, orphan positions, quantity mismatches.
- 🔌 **Broker-agnostic** — one ~10-line callback. ccxt and IBKR examples included; Alpaca / Polymarket / Kalshi are trivial.
- 🪶 **Zero required dependencies** in the core. It's a library, not a framework to migrate into.

> **Status: alpha.** A safety layer that sits in your order path is only as good as its tests — so read `tests/` (55 of them, covering fill reconciliation, the cap gate, PnL math, position reconciliation, and the end-to-end flow) before you trust it with a live account. Default behavior is **HALT, never auto-liquidate**.

## Install

```bash
pip install sentinel-trade
# extras: pip install "sentinel-trade[dashboard,ccxt,ibkr]"
```

## Measure fill degradation (before you go live)

The headline feature needs no broker connection — just the fills your paper run or backtest already produced. For each, log what you *assumed* and what live would *really* get (the actual price, or just the bid/ask — Sentinel models the crossing fill):

```python
import sentinel
sentinel.init(bot="eth-meanrev")

sentinel.record_paper_fill("ETH/USDT", "buy",  qty=2, paper_price=2500, bid=2499.5, ask=2501.0, strategy="meanrev")
sentinel.record_paper_fill("ETH/USDT", "sell", qty=2, paper_price=2520, live_price=2517.8, strategy="meanrev")

report = sentinel.fill_report()
print(report["headline"])      # the one number, e.g. "...live ran ~9 bps worse than paper..."
print(report["by_strategy"])   # which strategies actually survive real execution
```

`by_strategy` is where the truth hides: the strategy that's 95% in paper but bleeds 40 bps live is the one quietly killing you.

## Quickstart (going live)

```python
import sentinel

sentinel.init(
    bot="eth-meanrev-01",
    caps=sentinel.Caps(
        daily_loss_usd=200,      # halt BEFORE the next order, not after an alert
        max_position_usd=500,
        max_open_positions=8,
    ),
    heartbeat_minutes=15,        # "no fill in 15m during market hours" -> page me
    alerts=[sentinel.Console()], # or sentinel.Telegram(chat_id, token), Discord(webhook), Email(...)
)

# Tell Sentinel how to read YOUR broker. Any broker. ~10 lines.
@sentinel.broker_positions
def live_positions():
    return {p["symbol"]: p["qty"] for p in exchange.fetch_positions()}

# Wrap the function that places orders. The gate runs FIRST.
@sentinel.order
def submit(symbol, side, qty, price):
    # If a cap is breached, Sentinel raises CapBreached here and the order is never sent.
    return exchange.create_order(symbol, "limit", side, qty, price)

@sentinel.fill
def on_fill(symbol, side, qty, fill_price, expected_price):
    ...  # slippage_bps + P&L tracked automatically

# Background: every 30s, diff your state vs the broker. Drift -> halt + alert.
sentinel.watch_reconciliation(interval_seconds=30)
```

Don't like decorators? Call the same logic explicitly:

```python
sentinel.check_order("ETH/USDT", "buy", qty=2, price=2500)   # raises CapBreached to block
sentinel.record_fill("ETH/USDT", "buy", qty=2, fill_price=2501, expected_price=2500)
sentinel.record_paper_fill("ETH/USDT", "buy", qty=2, paper_price=2500, bid=2499.5, ask=2501)  # fill degradation
report = sentinel.fill_report()                              # the headline number + by_strategy
divergences = sentinel.sync_positions({"ETH/USDT": 2.0})     # one-shot reconcile
```

## The three guards

| Guard | What it catches | What others do |
|------|-----------------|----------------|
| **Cap gate** | over-sized order, breached daily loss, too much deployed | alert *after* the fact, if at all |
| **Heartbeat** | bot alive but placing zero trades (rounding-to-zero, stale signal) | nothing — there's no error to see |
| **Reconciliation** | bot thinks it holds X, broker shows Y (ghost / orphan / mismatch) | everyone hand-rolls it, badly |

The cap gate is a handful of in-memory comparisons (microseconds, no network) and **fails closed**: if it can't verify state, it blocks rather than waving an order through.

## Run the demo

```bash
python examples/quickstart.py     # simulates a bot and trips every guard, no broker needed
```

## Dashboard

Point your bot at a file db (`sentinel.init(..., db_path="sentinel.db")`), then:

```bash
streamlit run dashboard/app.py
```

## What it is NOT (honest scope)

- Not a trading framework — it wraps the bot you already wrote; it doesn't replace it.
- Not auto-liquidation — it HALTS (blocks new orders) by default. Closing positions is your call.
- Not a backtester — it's for **live** ops (but it *will* show you what your backtest's optimistic fills hid). Use vectorbt / quantstats for research.
- v1 ships ccxt + IBKR adapters; Alpaca / Polymarket / Kalshi are fast-follows.

## Development

```bash
pip install -e ".[dev]"
pytest
```

MIT licensed.
