"""backfill.py -- pull the FULL Coinbase/OKX hourly history, back to listing.

    python backfill.py

One file per name in history/, reused on later runs. This is the data the
frozen rider rule gets tested on ONCE -- years none of our rules have seen.
"""
import os
import warnings

import pandas as pd

import crypto

warnings.filterwarnings("ignore")

OUT = "history"
BARS = 110000                # ~12.5 years of hourly; more than exists


def grab(p):
    sym, src = p
    f = os.path.join(OUT, "%s_1h.csv.gz" % sym)
    if os.path.exists(f):
        try:
            return sym, pd.read_csv(f, index_col=0, parse_dates=True), "cached"
        except Exception:
            pass
    d = None
    if src == "coinbase":
        d = crypto._coinbase(sym, "1h", BARS)
    if d is None or len(d) < 30:
        d = crypto._okx(sym, "1h", BARS)
    if d is not None and len(d) >= 30:
        d.to_csv(f)
    return sym, d, src


def main():
    os.makedirs(OUT, exist_ok=True)
    u = crypto.universe(30)
    pairs = [(x["sym"], x["source"]) for _, x in u.iterrows()]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=6) as ex:
        for sym, d, how in ex.map(grab, pairs):
            if d is None or len(d) < 30:
                print("%-6s FAILED" % sym, flush=True)
                continue
            print("%-6s %6d bars   %s -> %s   (%s)"
                  % (sym, len(d), d.index[0].date(), d.index[-1].date(), how),
                  flush=True)


if __name__ == "__main__":
    main()
