"""rider_short.py -- the inverse: EMA12 as RESISTANCE in bear conditions.

    python rider_short.py

Pre-registered exact mirror of the long rule, zero new parameters:
  live trend DOWN, EMA12 falling, 2 defended rejections (high reaches the
  EMA, body closes below), short the confirmed close of the next rejection.
  Cover on a body close above the EMA while unproven; once 1% in favor,
  only the 3% trail above the EMA covers.

IMPLEMENTATION BY INVERSION: prices are mapped p -> 1/p (High and Low swap),
and the untouched long machinery runs on the inverted series. A long there
IS a short here, with identical percentage math. EMA(1/p) differs from
1/EMA(p) by a second-order convexity term, far below the noise floor -- a
fair price for reusing code that has survived five rounds of bug-hunting
instead of writing a mirrored copy that has survived none.

Shorts have never been tested on ANY era, so the full 2015-2026 history is
clean for this. One run. Costs stay 0.2% RT (real shorting costs more --
borrow/funding -- so a marginal pass is a fail in practice).
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import glob
import os
import warnings

import numpy as np
import pandas as pd

import rider_lab as L
import scanner as SC

warnings.filterwarnings("ignore")

SPLIT = pd.Timestamp("2022-07-01")
DOLLAR = 1e6
TOUCHES = 2
MODE = "promote1"


def liquid_years(df, mult):
    dv = (df["Close"] * df["Volume"]).groupby(df.index.year).median()
    return set(dv[dv >= DOLLAR * mult].index)


def invert(df):
    return pd.DataFrame(dict(Open=1.0 / df["Open"], High=1.0 / df["Low"],
                             Low=1.0 / df["High"], Close=1.0 / df["Close"],
                             Volume=df["Volume"]), index=df.index)


def main():
    rows, nulls = [], []
    rng = np.random.default_rng(1212)
    for f in sorted(glob.glob(os.path.join("history", "*_1h.csv.gz"))):
        sym = os.path.basename(f).split("_")[0]
        raw = pd.read_csv(f, index_col=0, parse_dates=True)
        if len(raw) < 2000:
            continue
        for tf, mult in (("1h", 1), ("4h", 4)):
            df = SC.resample(raw, "4h") if tf == "4h" else raw
            if df is None or len(df) < 800:
                continue
            ok = liquid_years(df, mult)          # liquidity on REAL prices
            if not ok:
                continue
            inv = invert(df)
            v = L.prep(inv)
            c = v["c"]
            n = v["n"]
            years = df.index.year.values
            liq = np.isin(years, list(ok))

            for entry, fill in L.entries(v, TOUCHES, MODE):
                if entry >= n - 2 or not liq[entry]:
                    continue
                r = L.run_exit(v, entry, fill, MODE)
                if r is None:
                    continue
                k, px, why = r
                rows.append(dict(sym=sym, tf=tf, year=int(years[entry]),
                                 era="new" if df.index[entry] >= SPLIT else "old",
                                 bars=int(k - entry), why=why,
                                 net=float(px / fill - 1 - 2 * L.COST)))

            pool = np.flatnonzero(liq[:-5])
            if len(pool) > 50:
                vals = []
                for _ in range(240):
                    i = int(rng.choice(pool))
                    r = L.run_exit(v, i, c[i], MODE)
                    if r:
                        vals.append(r[1] / c[i] - 1 - 2 * L.COST)
                if vals:
                    nulls.append(dict(sym=sym, tf=tf, null=float(np.mean(vals))))
        print("  %-6s done" % sym, flush=True)

    R = pd.DataFrame(rows)
    N = pd.DataFrame(nulls)
    if R.empty:
        print("no short setups found")
        return
    R.to_csv("rider_short_trades.csv", index=False)
    nn = float(N.null.mean()) if len(N) else np.nan

    print("\n" + "=" * 78)
    print("  THE INVERSE RIDER (SHORTS) -- full 2015-2026, one pre-registered shot")
    print("=" * 78)
    print("  %d trades  mean %+.3f%%  median %+.3f%%  win %.0f%%"
          % (len(R), 100 * R.net.mean(), 100 * R.net.median(),
             100 * (R.net > 0).mean()))
    print("  null (random shorts, same exit) %+.3f%%  ->  edge %+.3f%%"
          % (100 * nn, 100 * (R.net.mean() - nn)))
    ok = R.net.mean() > 0 and (R.net.mean() - nn) > 2 * L.COST
    print("  verdict: %s" % ("HOLDS" if ok else "does not hold"))

    for era, lab in (("old", "2015 -> 2022-07"), ("new", "2022-07 -> now")):
        g = R[R.era == era]
        if len(g):
            print("    %s: %4d trades  mean %+8.3f%%" % (lab, len(g), 100 * g.net.mean()))
    print("\n  by year:")
    for y, g in R.groupby("year"):
        print("    %d  %5d trades  mean %+8.3f%%" % (y, len(g), 100 * g.net.mean()))
    print("\n  best/worst names:")
    by = sorted(R.groupby("sym"), key=lambda kv: -kv[1].net.mean())
    for s, g in by[:4] + by[-3:]:
        print("    %-6s %5d trades  mean %+8.3f%%" % (s, len(g), 100 * g.net.mean()))
    print("\n  full table: rider_short_trades.csv")


if __name__ == "__main__":
    main()
