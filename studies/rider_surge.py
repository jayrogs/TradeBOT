"""rider_surge.py -- pre-registered one-shot: the surge gate on 2015-2022.

    python rider_surge.py

Registered from ride_study.py (2022-2026 exploration data) BEFORE running
this. No grid, no second attempt. The rule:

  GATE      relvol >= 2.210  (mean dollar volume of the last day vs the
            30-day rolling median dollar volume, computed exactly as in the
            study) AND 7-day return <= +4.81% -- the crowd is arriving, the
            price has not run yet. Plus the standard liquid-years gate
            ($1M/hour median, per calendar year) used in every frozen test.
  ENTRY     unchanged: live trend UP, 2 defended touches, rising EMA,
            buy the confirmed close of the next held touch
  EXIT      unchanged: body close under the EMA until +1%, then the 3% trail
  NULL      random bars passing the SAME gate, through the SAME exit
  SUCCESS   mean net > 0 AND edge over the null > 0.2% costs

On the exploration data this cell made +0.845%/trade (n=429), positive in
all five years, both timeframes, spread across names. If that was regime
luck, 2015-2022 says so now.
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

CUTOFF = pd.Timestamp("2022-07-01")
DOLLAR = 1e6
TOUCHES = 2
MODE = "promote1"
RELVOL = 2.210
RET7 = 0.0481


def liquid_years(df, mult):
    dv = (df["Close"] * df["Volume"]).groupby(df.index.year).median()
    return set(dv[dv >= DOLLAR * mult].index)


def main():
    rows, nulls = [], []
    rng = np.random.default_rng(2210)
    for f in sorted(glob.glob(os.path.join("history", "*_1h.csv.gz"))):
        sym = os.path.basename(f).split("_")[0]
        raw = pd.read_csv(f, index_col=0, parse_dates=True)
        raw = raw[raw.index < CUTOFF]
        if len(raw) < 2000:
            continue
        for tf, per_day, mult in (("1h", 24, 1), ("4h", 6, 4)):
            df = SC.resample(raw, "4h") if tf == "4h" else raw
            if df is None or len(df) < 800:
                continue
            ok = liquid_years(df, mult)
            if not ok:
                continue
            v = L.prep(df)
            c = v["c"]
            n = v["n"]
            years = df.index.year.values
            liq = np.isin(years, list(ok))
            dv = pd.Series(c * df["Volume"].values, index=df.index)
            dv30 = dv.rolling(30 * per_day, min_periods=per_day).median().values
            dv1 = dv.rolling(per_day, min_periods=2).mean().values
            lb7 = 7 * per_day
            with np.errstate(divide="ignore", invalid="ignore"):
                rv = np.where(dv30 > 0, dv1 / dv30, np.nan)
            r7 = np.full(n, np.nan)
            r7[lb7:] = c[lb7:] / c[:-lb7] - 1.0
            gate = liq & (rv >= RELVOL) & (r7 <= RET7)

            for entry, fill in L.entries(v, TOUCHES, MODE):
                if entry >= n - 2 or not gate[entry]:
                    continue
                r = L.run_exit(v, entry, fill, MODE)
                if r is None:
                    continue
                k, px, why = r
                rows.append(dict(sym=sym, tf=tf, year=int(years[entry]),
                                 bars=int(k - entry), why=why,
                                 net=float(px / fill - 1 - 2 * L.COST)))

            pool = np.flatnonzero(gate[:-5])
            if len(pool) > 30:
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
        print("no trades passed the gate")
        return
    R.to_csv("rider_surge_trades.csv", index=False)
    nn = float(N.null.mean()) if len(N) else np.nan
    edge = R.net.mean() - nn
    ok = R.net.mean() > 0 and edge > 2 * L.COST

    print("\n" + "=" * 78)
    print("  THE SURGE GATE ON 2015 -> 2022-07 -- one shot, pre-registered")
    print("=" * 78)
    print("  %d trades  mean %+.3f%%  median %+.3f%%  win %.0f%%"
          % (len(R), 100 * R.net.mean(), 100 * R.net.median(),
             100 * (R.net > 0).mean()))
    print("  null (same gate, random moments) %+.3f%%  ->  edge %+.3f%%"
          % (100 * nn, 100 * edge))
    print("  verdict: %s"
          % ("HOLDS -- profitable on untouched history" if ok else
             "does not hold"))
    print("\n  by year:")
    for y, g in R.groupby("year"):
        print("    %d  %5d trades  mean %+8.3f%%" % (y, len(g), 100 * g.net.mean()))
    print("\n  by name:")
    for s, g in sorted(R.groupby("sym"), key=lambda kv: -kv[1].net.mean()):
        print("    %-6s %5d trades  mean %+8.3f%%" % (s, len(g), 100 * g.net.mean()))
    print("\n  full table: rider_surge_trades.csv")


if __name__ == "__main__":
    main()
