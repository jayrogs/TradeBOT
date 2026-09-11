"""partial_study.py -- does selling a partial improve the rider exit?

    python partial_study.py

The group sells part of the position once the trade is going their way, to
lock profit against a later stopout. This is EXIT ARITHMETIC on the same
trades, not a new entry claim -- so it runs on BOTH eras. If the answer
agrees on 2022-2026 and 2015-2022, it does not depend on the regime.

Variants (fraction sold at trigger; remainder rides the standard exit):
  base        no partial (the current rule)
  half@+1%    sell 1/2 the moment the trade is +1% (the promotion moment)
  half@+2%    sell 1/2 at +2%
  half@+4%    sell 1/2 at +4%
  third@+2%   sell 1/3 at +2%

Entry population: the standard rider (liquid years, live UP, 2 defended
touches, confirmed close). Exit walk replicates promote1 exactly.
Also reported: P(a trade that reaches the trigger still ends below it).
"""

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
STOP = 0.03
PROM = 1.01
VARIANTS = [("base", 0.0, 0.0), ("half@+1%", 0.5, 0.01),
            ("half@+2%", 0.5, 0.02), ("half@+4%", 0.5, 0.04),
            ("third@+2%", 1 / 3, 0.02)]


def liquid_years(df, mult):
    dv = (df["Close"] * df["Volume"]).groupby(df.index.year).median()
    return set(dv[dv >= DOLLAR * mult].index)


def walk(v, entry, fill):
    """Replicates the promote1 exit, returning the exit price and the full
    list of (bar, close) along the way so partials can be priced."""
    c, lo, e, hold = v["c"], v["lo"], v["e"], v["hold"]
    import numpy as np
    promoted = False
    path = []
    for k in range(entry + 1, v["n"]):
        floor = e[k] * (1 - STOP)
        if lo[k] <= floor:
            return floor, path
        path.append((k, c[k]))
        if not promoted and c[k] >= fill * PROM:
            promoted = True
        buf = L.EXIT_TOL_ATR * (v["atr"][k] if np.isfinite(v["atr"][k])
                                else 0.0)
        if not promoted and c[k] < e[k] - buf:
            return c[k], path
    return None, path


def era_trades(lo_t, hi_t):
    out = []
    for f in sorted(glob.glob(os.path.join("history", "*_1h.csv.gz"))):
        raw = pd.read_csv(f, index_col=0, parse_dates=True)
        raw = raw[(raw.index >= lo_t) & (raw.index < hi_t)]
        if len(raw) < 2000:
            continue
        for tf, mult in (("1h", 1), ("4h", 4)):
            df = SC.resample(raw, "4h") if tf == "4h" else raw
            if df is None or len(df) < 800:
                continue
            ok = liquid_years(df, mult)
            if not ok:
                continue
            v = L.prep(df)
            liq = np.isin(df.index.year.values, list(ok))
            for entry, fill in L.entries(v, TOUCHES, "promote1"):
                if entry >= v["n"] - 2 or not liq[entry]:
                    continue
                px, path = walk(v, entry, fill)
                if px is None:
                    continue
                out.append((fill, px, path))
    return out


def score(trades, frac, trig):
    nets, saved = [], 0
    hit = 0
    for fill, px, path in trades:
        final = px / fill - 1
        part = None
        if frac > 0:
            for _, cc in path:
                if cc >= fill * (1 + trig):
                    part = cc / fill - 1
                    break
        if part is None:
            nets.append(final - 2 * L.COST)
        else:
            hit += 1
            if final < part:
                saved += 1
            nets.append(frac * part + (1 - frac) * final - 2 * L.COST)
    a = np.array(nets)
    return dict(n=len(a), mean=a.mean(), med=np.median(a),
                win=(a > 0).mean(), std=a.std(), worst=a.min(),
                hit=hit, saved=saved)


def main():
    for label, lo_t, hi_t in (
            ("2022-07 -> now (the mined years)", SPLIT, pd.Timestamp("2100-01-01")),
            ("2015 -> 2022-07 (the frozen years)", pd.Timestamp("2000-01-01"), SPLIT)):
        trades = era_trades(lo_t, hi_t)
        print("\n" + "=" * 78)
        print("  %s -- %d trades" % (label, len(trades)))
        print("=" * 78)
        print("  %-10s %9s %9s %6s %8s %9s %22s"
              % ("variant", "mean", "median", "win%", "std", "worst",
                 "reached trig / died back"))
        for name, frac, trig in VARIANTS:
            s = score(trades, frac, trig)
            extra = ("%5d / %d (%.0f%%)"
                     % (s["hit"], s["saved"], 100 * s["saved"] / s["hit"])
                     if s["hit"] else "")
            print("  %-10s %+8.3f%% %+8.3f%% %5.0f%% %7.2f%% %+8.1f%% %22s"
                  % (name, 100 * s["mean"], 100 * s["med"], 100 * s["win"],
                     100 * s["std"], 100 * s["worst"], extra))


if __name__ == "__main__":
    main()
