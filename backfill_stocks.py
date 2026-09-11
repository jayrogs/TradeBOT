"""backfill_stocks.py -- research history for US stocks via Alpaca.

    python backfill_stocks.py AAPL MSFT NVDA            # hourly since 2021
    python backfill_stocks.py --top 50                  # most liquid 50 from tier1
    python backfill_stocks.py AAPL --tf 5m --since 2024-01-01

Writes history/stocks/<SYM>_<tf>.csv.gz, the same shape as the crypto
history (Open High Low Close Volume, naive New York time). Needs
livelog/alpaca.json (see alpaca.py). Re-running refreshes a file only from
its last bar onward.

Cost: about one request per 20 trading days per symbol, any timeframe
(Alpaca pages by bar-minutes). Hourly since 2021 is ~65 requests a symbol,
~25 seconds; 50 names is ~20 minutes. Volume is IEX-only -- use it for
price structure, not for dollar-volume gates.
"""

import argparse
import os
import sys
import time

import pandas as pd

import alpaca

OUT = os.path.join("history", "stocks")


def top_names(n):
    p = os.path.join("cache", "tier1.csv")
    if not os.path.exists(p):
        sys.exit("  no cache/tier1.csv -- run: python bigscan.py --tier1-only")
    k = pd.read_csv(p)
    k = k[k.kind.isin(["equity", "etf"])].dropna(subset=["dollar"])
    return k.sort_values("dollar", ascending=False).head(n).symbol.tolist()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbols", nargs="*")
    ap.add_argument("--top", type=int, default=0)
    ap.add_argument("--tf", default="1h")
    ap.add_argument("--since", default="2021-01-01")
    a = ap.parse_args()
    if not alpaca.enabled():
        sys.exit("  no Alpaca keys: create livelog/alpaca.json first "
                 "(python alpaca.py --check)")
    syms = [s.upper() for s in a.symbols] + (top_names(a.top) if a.top else [])
    if not syms:
        sys.exit("  give symbols or --top N")
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    for i in range(0, len(syms), 25):
        part = syms[i:i + 25]
        starts = {}
        for s in part:
            p = os.path.join(OUT, "%s_%s.csv.gz" % (s, a.tf))
            if os.path.exists(p):
                try:
                    old = pd.read_csv(p, index_col=0, parse_dates=True)
                    starts[s] = old.index[-1]
                except Exception:
                    pass
        fresh = [s for s in part if s not in starts]
        got = {}
        if fresh:
            got.update(alpaca.bars(fresh, a.tf, a.since))
        for s, last in starts.items():
            got.update(alpaca.bars([s], a.tf, last))
        for s in part:
            d = got.get(s)
            p = os.path.join(OUT, "%s_%s.csv.gz" % (s, a.tf))
            if d is None or d.empty:
                print("  %-6s nothing new" % s)
                continue
            if s in starts and os.path.exists(p):
                old = pd.read_csv(p, index_col=0, parse_dates=True)
                d = pd.concat([old, d])
                d = d[~d.index.duplicated(keep="last")].sort_index()
            d.to_csv(p, compression="gzip")
            print("  %-6s %6d bars  %s -> %s" % (s, len(d), d.index[0], d.index[-1]))
    print("  done: %d names in %.0fs -> %s" % (len(syms), time.time() - t0, OUT))


if __name__ == "__main__":
    main()
