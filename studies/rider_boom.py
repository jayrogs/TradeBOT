"""rider_boom.py -- the last untested piece: the rider only in EXPLODING names.

    python rider_boom.py

The group's method was never "trade every liquid name all the time" -- it was
"when something blows up, buy its dips." The frozen 2015-2022 test ignored
that conditioning and failed. This is the same one-shot test WITH it.

PRE-REGISTERED, ONE CONFIGURATION, NO GRID:
  blowing up   close >= +25% vs 7 days ago (168 x 1h bars / 42 x 4h bars),
               measured at the entry bar from past data only
  the rule     unchanged from rider_2015: liquid years, live trend UP,
               2 defended touches, confirmed-close fill, body-close exit
               while unproven, promote at +1%, 3% trail
  the null     random bars drawn ONLY from blowing-up liquid bars, pushed
               through the identical exit. The gate's own tailwind cancels
               out; what is left is entry timing and nothing else.

Whatever prints, prints.
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
BOOM = 0.25                       # +25%...
LOOK = {"1h": 168, "4h": 42}      # ...over 7 days


def liquid_years(df, mult):
    dv = (df["Close"] * df["Volume"]).groupby(df.index.year).median()
    return set(dv[dv >= DOLLAR * mult].index)


def main():
    files = sorted(glob.glob(os.path.join("history", "*_1h.csv.gz")))
    rows, nulls = [], []
    rng = np.random.default_rng(7)
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
            c = v["c"]
            lb = LOOK[tf]
            boom = np.zeros(len(c), dtype=bool)
            boom[lb:] = c[lb:] / c[:-lb] - 1.0 >= BOOM
            gate = boom & liq

            for t in L.trades(v, TOUCHES, MODE):
                if gate[t["entry"]]:
                    rows.append(dict(sym=sym, tf=tf, year=int(years[t["entry"]]),
                                     bars=t["bars"], why=t["why"], net=t["net"]))

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
        print("no trades passed the boom gate")
        return
    R.to_csv("rider_boom_trades.csv", index=False)
    nn = float(N.null.mean()) if len(N) else np.nan

    print("\n" + "=" * 78)
    print("  THE RIDER, ONLY IN EXPLODING NAMES -- 2015 -> 2022-07, one shot")
    print("=" * 78)
    edge = R.net.mean() - nn
    print("  %d trades  mean %+.3f%%  median %+.3f%%  win %.0f%%"
          % (len(R), 100 * R.net.mean(), 100 * R.net.median(),
             100 * (R.net > 0).mean()))
    print("  null (random moments in the SAME exploding names) %+.3f%%" % (100 * nn))
    print("  ->  ENTRY EDGE %+.3f%% per trade after costs" % (100 * edge))
    print("  verdict: %s"
          % ("the entry times exploding names -- HOLDS" if edge > 2 * L.COST
             else "no entry edge beyond the explosion itself"))

    print("\n  by year:")
    for y, g in R.groupby("year"):
        print("    %d  %5d trades  mean %+8.3f%%  edge %+8.3f%%"
              % (y, len(g), 100 * g.net.mean(), 100 * (g.net.mean() - nn)))
    print("\n  by name:")
    for s, g in sorted(R.groupby("sym"), key=lambda kv: -kv[1].net.mean()):
        gn = N[N.sym == s].null.mean() if len(N[N.sym == s]) else nn
        print("    %-6s %5d trades  mean %+8.3f%%  edge %+8.3f%%"
              % (s, len(g), 100 * g.net.mean(), 100 * (g.net.mean() - gn)))
    print("\n  for scale: the exploding-moment null itself earns %+.3f%% "
          "per trade,\n  so the GATE without any entry skill is already "
          "worth that much vs the\n  all-times null (+0.271%%)." % (100 * nn))
    print("  full table: rider_boom_trades.csv")


if __name__ == "__main__":
    main()
