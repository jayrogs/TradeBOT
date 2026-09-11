"""
analyze_my_trades.py -- the user's own realised trades, pulled from Robinhood.

This is the only dataset in the project that measures the thing every backtest
could not: what this person actually does, and which parts of it make money.
"""

import pandas as pd
import numpy as np

d = pd.read_csv("my_trades.csv", parse_dates=["date"])
tot = d.gain.sum()

print("=" * 70)
print("  YOUR REALISED TRADES")
print("=" * 70)
print("  %d closes, %s to %s" % (len(d), d.date.min().date(), d.date.max().date()))
print("  total realised P&L: $%s" % format(tot, ",.2f"))
print("  win rate: %.0f%%   average trade: $%.2f   median: $%.2f"
      % (100 * (d.gain > 0).mean(), d.gain.mean(), d.gain.median()))

print("\n" + "=" * 70)
print("  HOW CONCENTRATED IS THE PROFIT?")
print("=" * 70)
s = d.gain.sort_values(ascending=False)
for k in [1, 3, 5, 10, 20]:
    print("  top %2d trades  $%9s   = %3.0f%% of everything you made"
          % (k, format(s.head(k).sum(), ",.0f"), 100 * s.head(k).sum() / tot))
print("  the other %d trades combined  $%s"
      % (len(d) - 10, format(s.tail(len(d) - 10).sum(), ",.0f")))

print("\n" + "=" * 70)
print("  POSITION TRADES vs SCALPS")
print("=" * 70)
big = d[d.gain.abs() >= 100]
small = d[d.gain.abs() < 100]
print("  %-30s %5s %12s %10s %8s" % ("", "n", "total", "avg", "win%"))
for lab, g in [("position trades (>=$100)", big), ("scalps (<$100)", small)]:
    print("  %-30s %5d %12s %10.2f %7.0f%%"
          % (lab, len(g), "$" + format(g.gain.sum(), ",.0f"),
             g.gain.mean(), 100 * (g.gain > 0).mean()))
print("\n  %.0f%% of your trades are scalps. They produced %.1f%% of your profit."
      % (100 * len(small) / len(d), 100 * small.gain.sum() / tot))

print("\n" + "=" * 70)
print("  THE SLV EPISODE -- the same instrument, traded two ways")
print("=" * 70)
slv = d[d.symbol == "SLV"]
cut = pd.Timestamp("2026-02-06")
held = slv[slv.date < cut]
scalped = slv[slv.date >= cut]
print("  HELD as positions (through Feb 5):")
print("     %3d trades   $%9s   avg $%8.2f   win %3.0f%%"
      % (len(held), format(held.gain.sum(), ",.0f"), held.gain.mean(),
         100 * (held.gain > 0).mean()))
print("  DAY-TRADED (Feb 6 - Mar 6):")
print("     %3d trades   $%9s   avg $%8.2f   win %3.0f%%"
      % (len(scalped), format(scalped.gain.sum(), ",.0f"), scalped.gain.mean(),
         100 * (scalped.gain > 0).mean()))
print("\n  Same asset. Same person. Same month.")
print("  Holding it made $%s across %d trades."
      % (format(held.gain.sum(), ",.0f"), len(held)))
print("  Trading it made $%s across %d trades."
      % (format(scalped.gain.sum(), ",.0f"), len(scalped)))

print("\n" + "=" * 70)
print("  BY SYMBOL")
print("=" * 70)
g = d.groupby("symbol").agg(n=("gain", "size"), total=("gain", "sum"),
                            avg=("gain", "mean"),
                            win=("gain", lambda x: (x > 0).mean()))
g = g.sort_values("total", ascending=False)
print("  %-8s %5s %12s %10s %7s" % ("symbol", "n", "total", "avg", "win%"))
for sym, r in g.iterrows():
    print("  %-8s %5d %12s %10.2f %6.0f%%"
          % (sym, r.n, "$" + format(r.total, ",.0f"), r.avg, 100 * r.win))

print("\n" + "=" * 70)
print("  WHERE THE MONEY CAME FROM")
print("=" * 70)
metals = d[d.symbol.isin(["SLV", "GLD", "UUUU", "PLG"])]
crypto = d[d.symbol.isin(["ETH", "BTC", "DOGE", "SOL", "XLM", "HBAR", "ETHA"])]
equity = d[~d.symbol.isin(["SLV", "GLD", "UUUU", "PLG", "ETH", "BTC", "DOGE",
                           "SOL", "XLM", "HBAR", "ETHA", "EVENT"])]
event = d[d.symbol == "EVENT"]
for lab, x in [("metals & miners", metals), ("equities", equity),
               ("crypto", crypto), ("event contracts", event)]:
    print("  %-18s %4d trades  $%9s  (%3.0f%% of total profit)"
          % (lab, len(x), format(x.gain.sum(), ",.0f"), 100 * x.gain.sum() / tot))
