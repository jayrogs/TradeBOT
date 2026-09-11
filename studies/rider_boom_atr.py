"""rider_boom_atr.py -- the pre-registered final shot: ATR-scaled exits.

    python rider_boom_atr.py

Registered BEFORE running, no grid, no second attempt:
  everything identical to rider_boom.py (exploding names +25%/7d, liquid
  years, live trend UP, 2 defended touches, confirmed-close fill, body-close
  exit while unproven) EXCEPT the two fixed percentages become volatility
  units:
    promotion   at entry price + 1.0 x ATR(entry)   (was +1%)
    trail       EMA - 1.5 x ATR(now)                (was EMA - 3%)
  The null is random exploding-liquid bars through this identical exit.

If mean net > 0 and edge > costs, the chain survives history. Otherwise the
entry skill is real but unharvestable this way, and that is the report.
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
BOOM = 0.25
LOOK = {"1h": 168, "4h": 42}
PROM_ATR = 1.0
TRAIL_ATR = 1.5


def liquid_years(df, mult):
    dv = (df["Close"] * df["Volume"]).groupby(df.index.year).median()
    return set(dv[dv >= DOLLAR * mult].index)


def exit_atr(v, entry, fill):
    c, lo, e, hold, atr = v["c"], v["lo"], v["e"], v["hold"], v["atr"]
    if not np.isfinite(atr[entry]):
        return None
    prom_at = fill + PROM_ATR * atr[entry]
    promoted = False
    for k in range(entry + 1, v["n"]):
        floor = e[k] - TRAIL_ATR * (atr[k] if np.isfinite(atr[k]) else atr[entry])
        if lo[k] <= floor:
            return k, floor, "stop"
        if not promoted and c[k] >= prom_at:
            promoted = True
        if not promoted and not hold[k]:
            return k, c[k], "body"
    return None


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
            gate = boom & liq & np.isfinite(v["atr"])

            # same entries as rider_boom: L.entries at 2 touches, then gate
            for entry, fill in L.entries(v, TOUCHES, "promote1"):
                if entry >= v["n"] - 2 or not gate[entry]:
                    continue
                r = exit_atr(v, entry, fill)
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
                    r = exit_atr(v, i, c[i])
                    if r:
                        vals.append(r[1] / c[i] - 1 - 2 * L.COST)
                if vals:
                    nulls.append(dict(sym=sym, tf=tf, null=float(np.mean(vals))))
        print("  %-6s done" % sym, flush=True)

    R = pd.DataFrame(rows)
    N = pd.DataFrame(nulls)
    if R.empty:
        print("no trades")
        return
    R.to_csv("rider_boom_atr_trades.csv", index=False)
    nn = float(N.null.mean()) if len(N) else np.nan
    edge = R.net.mean() - nn

    print("\n" + "=" * 78)
    print("  ATR-SCALED RIDER IN EXPLODING NAMES -- 2015 -> 2022-07, one shot")
    print("=" * 78)
    print("  %d trades  mean %+.3f%%  median %+.3f%%  win %.0f%%  hold %d bars"
          % (len(R), 100 * R.net.mean(), 100 * R.net.median(),
             100 * (R.net > 0).mean(), int(R.bars.median())))
    print("  null (same exploding bars, same ATR exit) %+.3f%%" % (100 * nn))
    print("  ->  ENTRY EDGE %+.3f%%  |  ABSOLUTE %+.3f%% per trade"
          % (100 * edge, 100 * R.net.mean()))
    ok = R.net.mean() > 0 and edge > 2 * L.COST
    print("  verdict: %s"
          % ("PROFITABLE ON UNTOUCHED HISTORY -- the chain holds" if ok else
             "not harvestable this way -- skill without profit"))

    print("\n  by year:")
    for y, g in R.groupby("year"):
        print("    %d  %5d trades  mean %+8.3f%%" % (y, len(g), 100 * g.net.mean()))
    print("\n  by name:")
    for s, g in sorted(R.groupby("sym"), key=lambda kv: -kv[1].net.mean()):
        print("    %-6s %5d trades  mean %+8.3f%%" % (s, len(g), 100 * g.net.mean()))
    print("\n  exits: %s" % R.why.value_counts().to_dict())
    print("  full table: rider_boom_atr_trades.csv")


if __name__ == "__main__":
    main()
