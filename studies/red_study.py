"""red_study.py -- should the rider hold through red trends? Both eras.

    python red_study.py

The oldest graded instruction still untested under the CURRENT rule ("its
holding after the trend goes red. already said to not do that"). The early
test that damned exit-on-red ran on a rule with lookahead bugs and no
promotion; it proves nothing about today's rule.

Variants, applied on top of the adopted rule (quarter-ATR exit tolerance,
5-bar wind, promote at +1%, 3% trail):

  base        hold through anything once promoted (current behavior)
  notup_all   exit at the close whenever the live trend leaves UP
  notup_prom  same, but only once promoted (unproven trades already die
              fast via the body exit)
  down_all    exit only on outright DOWN -- losing the green zone to
              BALANCE is tolerated
  down_prom   DOWN-only, promoted trades only

Same entries, same disaster stop. Exit arithmetic on both eras; a variant
earns adoption only if it helps (or is flat) in each.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import glob
import os
import warnings

import numpy as np
import pandas as pd

import panel as P
import rider_lab as L
import scanner as SC

warnings.filterwarnings("ignore")

SPLIT = pd.Timestamp("2022-07-01")
DOLLAR = 1e6
STOP = 0.03
PROM = 1.01
VARIANTS = ["base", "notup_all", "notup_prom", "down_all", "down_prom"]


def liquid_years(df, mult):
    dv = (df["Close"] * df["Volume"]).groupby(df.index.year).median()
    return set(dv[dv >= DOLLAR * mult].index)


def walk(v, st, entry, fill, mode):
    c, lo, e, atr = v["c"], v["lo"], v["e"], v["atr"]
    promoted = False
    for k in range(entry + 1, v["n"]):
        floor = e[k] * (1 - STOP)
        if lo[k] <= floor:
            return floor, k - entry
        if not promoted and c[k] >= fill * PROM:
            promoted = True
        red = st[k] == "DOWN" if mode.startswith("down") else st[k] != "UP"
        if mode != "base" and red and (mode.endswith("all") or promoted):
            return c[k], k - entry
        if not promoted:
            buf = L.EXIT_TOL_ATR * (atr[k] if np.isfinite(atr[k]) else 0.0)
            if c[k] < e[k] - buf:
                return c[k], k - entry
    return None, None


def main():
    for label, lo_t, hi_t in (
            ("2022-07 -> now (mined)", SPLIT, pd.Timestamp("2100-01-01")),
            ("2015 -> 2022-07 (frozen)", pd.Timestamp("2000-01-01"), SPLIT)):
        rows = {m: [] for m in VARIANTS}
        bars = {m: [] for m in VARIANTS}
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
                st, _, _ = P.trend_state(df)
                liq = np.isin(df.index.year.values, list(ok))
                for entry, fill in L.entries(v, 2, "promote1"):
                    if entry >= v["n"] - 2 or not liq[entry]:
                        continue
                    for m in VARIANTS:
                        px, nb = walk(v, st, entry, fill, m)
                        if px is not None:
                            rows[m].append(px / fill - 1 - 2 * L.COST)
                            bars[m].append(nb)
        print("\n" + "=" * 78)
        print("  %s" % label)
        print("=" * 78)
        print("  %-11s %7s %9s %9s %6s %7s" %
              ("variant", "n", "mean", "median", "win%", "bars"))
        for m in VARIANTS:
            a = np.array(rows[m])
            if not len(a):
                continue
            print("  %-11s %7d %+8.3f%% %+8.3f%% %5.0f%% %7.0f"
                  % (m, len(a), 100 * a.mean(), 100 * np.median(a),
                     100 * (a > 0).mean(), float(np.median(bars[m]))))


if __name__ == "__main__":
    main()
