"""rider_2015.py -- the ONE clean test. Run once, believe the answer.

    python rider_2015.py

Everything so far was tuned and re-tuned on roughly 2022-2026. This runs the
FROZEN rule -- liquid names, live trend UP, 2 defended touches, buy the
confirmed close of the next held touch, body-close exit while unproven,
promote at +1% to the 3% EMA trail, no targets -- on hourly history STRICTLY
BEFORE 2022-07-01, which no version of any rule in this project has ever seen.

The rule is imported from rider_lab (mode "promote1", touches=2), not
re-implemented, so there is nothing to quietly adjust.

LIQUIDITY BELONGS TO ITS ERA. $1M/hour in 2026 was an absurd bar in 2016, so
the gate is applied per name-year: a trade only counts if the median dollar
volume of ITS calendar year clears the bar. The null draws its random entries
from those same liquid bars and exits through the identical rule.

If the edge holds here -- across 2017 mania, 2018 collapse, 2020 covid, 2021
mania, 2022 collapse -- it is real. If it does not, the last four months of
results were curve-fitting, and that is the answer we report.
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

CUTOFF = pd.Timestamp("2022-07-01")     # everything we ever tuned on is after
DOLLAR = 1e6                            # per hour, scaled by timeframe
TOUCHES = 2
MODE = "promote1"


def liquid_years(df, mult):
    dv = (df["Close"] * df["Volume"]).groupby(df.index.year).median()
    return set(dv[dv >= DOLLAR * mult].index)


def main():
    files = sorted(glob.glob(os.path.join("history", "*_1h.csv.gz")))
    if not files:
        print("no history/ files -- run backfill.py first")
        return

    rows, nulls = [], []
    rng = np.random.default_rng(2015)
    for f in files:
        sym = os.path.basename(f).split("_")[0]
        raw = pd.read_csv(f, index_col=0, parse_dates=True)
        raw = raw[raw.index < CUTOFF]
        if len(raw) < 2000:
            continue
        for tf, mult in (("1h", 1), ("4h", 4)):
            df = SC.resample(raw, "4h") if tf == "4h" else raw
            if df is None or len(df) < 800:
                continue
            ok_years = liquid_years(df, mult)
            if not ok_years:
                continue
            v = L.prep(df)
            years = df.index.year.values
            liq = np.isin(years, list(ok_years))

            for t in L.trades(v, TOUCHES, MODE):
                if liq[t["entry"]]:
                    rows.append(dict(sym=sym, tf=tf, year=int(years[t["entry"]]),
                                     bars=t["bars"], why=t["why"], net=t["net"]))

            # matched null: random LIQUID bars through the identical exit
            pool = np.flatnonzero(liq[:-5])
            if len(pool) > 50:
                vals = []
                for _ in range(240):
                    i = int(rng.choice(pool))
                    r = L.run_exit(v, i, v["c"][i], MODE)
                    if r:
                        vals.append(r[1] / v["c"][i] - 1 - 2 * L.COST)
                if vals:
                    nulls.append(dict(sym=sym, tf=tf,
                                      null=float(np.mean(vals))))
        print("  %-6s done" % sym, flush=True)

    R = pd.DataFrame(rows)
    N = pd.DataFrame(nulls)
    if R.empty:
        print("no trades survived the liquidity gate before %s" % CUTOFF.date())
        return
    R.to_csv("rider_2015_trades.csv", index=False)
    nn = float(N.null.mean()) if len(N) else np.nan

    print("\n" + "=" * 78)
    print("  THE FROZEN RULE ON 2015 -> 2022-07 -- data no rule here has seen")
    print("=" * 78)
    edge = R.net.mean() - nn
    print("  %d trades  mean %+.3f%%  median %+.3f%%  win %.0f%%"
          % (len(R), 100 * R.net.mean(), 100 * R.net.median(),
             100 * (R.net > 0).mean()))
    print("  null %+.3f%%  ->  EDGE %+.3f%% per trade after %.1f%% costs"
          % (100 * nn, 100 * edge, 200 * L.COST))
    print("  verdict: %s"
          % ("HOLDS on untouched history" if edge > 2 * L.COST else
             "does not hold -- the 2022-2026 result was curve-fit"))

    print("\n  by year:")
    for y, g in R.groupby("year"):
        gn = N.null.mean()
        print("    %d  %5d trades  mean %+8.3f%%  edge %+8.3f%%"
              % (y, len(g), 100 * g.net.mean(), 100 * (g.net.mean() - gn)))
    print("\n  by name:")
    for s, g in sorted(R.groupby("sym"), key=lambda kv: -kv[1].net.mean()):
        gn = N[N.sym == s].null.mean() if len(N[N.sym == s]) else nn
        print("    %-6s %5d trades  mean %+8.3f%%  edge %+8.3f%%"
              % (s, len(g), 100 * g.net.mean(), 100 * (g.net.mean() - gn)))
    print("\n  by timeframe:")
    for tf, g in R.groupby("tf"):
        gn = N[N.tf == tf].null.mean() if len(N[N.tf == tf]) else nn
        print("    %-4s %5d trades  mean %+8.3f%%  edge %+8.3f%%"
              % (tf, len(g), 100 * g.net.mean(), 100 * (g.net.mean() - gn)))
    print("\n  full table: rider_2015_trades.csv")


if __name__ == "__main__":
    main()
