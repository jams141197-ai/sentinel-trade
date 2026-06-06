"""Demo: measure how much your fills degrade live — no broker, no live account needed.

Simulates a paper run whose backtest assumed mid-price fills, then shows what the SAME
trades cost once you cross a realistic spread. This is the number you want *before* you
flip the bot live.

    python examples/fill_degradation.py
"""

import sentinel

sentinel.init(bot="demo-fills", alerts=[])

# A paper run: each row is what the backtest priced at mid, plus the live bid/ask at fill time.
# (Give Sentinel a live_price if you have it; otherwise bid/ask and it models the crossing fill.)
TRADES = [
    # symbol,     side,   qty,   paper(mid),  bid,       ask,       strategy
    ("ETH/USDT",  "buy",   3,    2500.0,      2499.0,    2501.5,    "meanrev"),
    ("ETH/USDT",  "sell",  3,    2516.0,      2514.5,    2517.0,    "meanrev"),
    ("SOL/USDT",  "buy",   40,   150.00,      149.92,    150.12,    "meanrev"),
    ("SOL/USDT",  "sell",  40,   151.20,      151.05,    151.30,    "meanrev"),
    ("BTC/USDT",  "buy",   1,    64000.0,     63980.0,   64030.0,   "momentum"),
    ("BTC/USDT",  "sell",  1,    64250.0,     64210.0,   64255.0,   "momentum"),
    ("ETH/USDT",  "buy",   3,    2490.0,      2489.0,    2491.8,    "momentum"),
    ("ETH/USDT",  "sell",  3,    2495.0,      2493.4,    2495.6,    "momentum"),
]
for sym, side, qty, paper, bid, ask, strat in TRADES:
    sentinel.record_paper_fill(sym, side, qty, paper, bid=bid, ask=ask, strategy=strat)

r = sentinel.fill_report()
print("\n" + r["headline"] + "\n")
print(f"  fills        : {r['fills']}")
print(f"  avg slippage : {r['avg_slippage_bps']} bps")
print(f"  total cost   : ${r['total_cost']:,.2f}")
print(f"  degradation  : {r['degradation_pct']}% of traded value\n")
print("  by strategy (which ones survive real execution):")
for name, s in r["by_strategy"].items():
    print(f"    {name:<10} {s['fills']} fills · {s['avg_bps']:>4} bps · ${s['cost']:,.2f}")
print("\nThat's the number your backtest never showed you.\n")

sentinel.stop()
