"""ride_study.py -- what conditions align with the EMA riders that work?

    python ride_study.py

Not a strategy test. Every rider entry (2 defended touches, live trend UP,
confirmed close) across all names on 1h and 4h, 2022-07 -> now -- the data
already burned by four months of tuning, so it is the honest place to HUNT.
Each entry gets ~15 conditions measured at that moment from past bars only,
and one outcome: the net of the standard exit (body-close until +1%, then
the 3% trail).

For every condition the trades are split into five buckets, worst to best.
A real driver shows a smooth staircase across the buckets; a jumble is noise.
Conditions are ranked by top-minus-bottom bucket spread.

Whatever wins here is a HYPOTHESIS. It gets frozen into one pre-registered
rule and shot once at 2015-2022, which this script never touches.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import glob
import os
import warnings

import numpy as np
import pandas as pd

import indicators as IND
import panel as P
import rider_lab as L
import scanner as SC

warnings.filterwarnings("ignore")

START = pd.Timestamp("2022-07-01")      # hunt AFTER the frozen years
TOUCHES = 2
MODE = "promote1"


def htf_state(df, rule):
    hi = SC.resample(df, rule)
    if hi is None or len(hi) < 60:
        return None
    st, _, _ = P.trend_state(hi)
    s = pd.Series(st, index=hi.index)
    # shift one HTF bar: bar k of the higher frame is only knowable at its
    # close, which is AFTER the lower-frame bars inside it
    return s.shift(1).reindex(df.index, method="ffill")


def main():
    rows = []
    for f in sorted(glob.glob(os.path.join("history", "*_1h.csv.gz"))):
        sym = os.path.basename(f).split("_")[0]
        raw = pd.read_csv(f, index_col=0, parse_dates=True)
        raw = raw[raw.index >= START]
        if len(raw) < 2000:
            continue
        for tf, per_day in (("1h", 24), ("4h", 6)):
            df = SC.resample(raw, "4h") if tf == "4h" else raw
            if df is None or len(df) < 800:
                continue
            v = L.prep(df)
            c, e, lo, atr = v["c"], v["e"], v["lo"], v["atr"]
            n = v["n"]
            rsi = IND.rsi(c)
            dv = pd.Series(c * df["Volume"].values, index=df.index)
            dv30 = dv.rolling(30 * per_day, min_periods=per_day).median().values
            dv1 = dv.rolling(per_day, min_periods=2).mean().values
            d1 = htf_state(df, "1D")
            d4 = htf_state(df, "4h") if tf == "1h" else None
            lb7, lb3, lb1 = 7 * per_day, 3 * per_day, per_day

            i = 0
            while i < n:
                if not v["armed"][i]:
                    i += 1
                    continue
                j = i
                while j + 1 < n and v["armed"][j + 1]:
                    j += 1
                seen, wicks, entry = 0, [], None
                for k in range(i, j + 1):
                    if v["touch"][k]:
                        seen += 1
                        wicks.append(max(0.0, (e[k] - lo[k]) / atr[k])
                                     if np.isfinite(atr[k]) else 0.0)
                        if seen > TOUCHES and v["rising"][k]:
                            entry = k
                            break
                if (entry is None or entry >= n - 2 or entry < lb7
                        or not np.isfinite(atr[entry])):
                    i = j + 1
                    continue
                r = L.run_exit(v, entry, c[entry], MODE)
                if r is None:
                    i = j + 1
                    continue
                _, px, why = r
                k = entry
                rows.append(dict(
                    sym=sym, tf=tf, year=int(df.index[k].year), why=why,
                    net=float(px / c[k] - 1 - 2 * L.COST),
                    ret_7d=float(c[k] / c[k - lb7] - 1),
                    ret_3d=float(c[k] / c[k - lb3] - 1),
                    ret_1d=float(c[k] / c[k - lb1] - 1),
                    slope3=float((e[k] - e[k - 3]) / atr[k]),
                    slope12=float((e[k] - e[k - 12]) / atr[k]),
                    atr_pct=float(atr[k] / c[k]),
                    dist_close=float((c[k] - e[k]) / atr[k]),
                    ride_age=int(k - i),
                    trend_age=int(v["upage"][k]),
                    touch_depth=float(np.mean(wicks)) if wicks else 0.0,
                    rsi=float(rsi[k]) if np.isfinite(rsi[k]) else np.nan,
                    relvol=float(dv1[k] / dv30[k])
                        if dv30[k] and np.isfinite(dv30[k]) else np.nan,
                    dollar_vol=float(dv30[k]) if np.isfinite(dv30[k]) else np.nan,
                    daily_up=int(d1.iloc[k] == "UP") if d1 is not None else np.nan,
                    h4_up=int(d4.iloc[k] == "UP") if d4 is not None else np.nan,
                ))
                i = j + 1
        print("  %-6s %5d entries so far" % (sym, len(rows)), flush=True)

    R = pd.DataFrame(rows)
    R.to_csv("ride_study.csv", index=False)
    print("\n%d rider entries, mean %+.3f%%, win %.0f%%"
          % (len(R), 100 * R.net.mean(), 100 * (R.net > 0).mean()))

    feats = ["ret_7d", "ret_3d", "ret_1d", "slope3", "slope12", "atr_pct",
             "dist_close", "ride_age", "trend_age", "touch_depth", "rsi",
             "relvol", "dollar_vol", "daily_up", "h4_up"]
    print("\n" + "=" * 86)
    print("  EACH CONDITION, SPLIT INTO 5 BUCKETS (bucket 1 low .. 5 high)")
    print("  mean net %% per bucket -- a real driver is a smooth staircase")
    print("=" * 86)
    ranked = []
    for ft in feats:
        d = R.dropna(subset=[ft])
        if d[ft].nunique() <= 2:
            g = d.groupby(ft).net.mean() * 100
            cells = "   low %+7.3f   high %+7.3f" % (g.get(0, np.nan), g.get(1, np.nan))
            spread = (g.get(1, np.nan) - g.get(0, np.nan))
        else:
            try:
                q = pd.qcut(d[ft], 5, labels=False, duplicates="drop")
            except ValueError:
                continue
            g = d.groupby(q).net.mean() * 100
            cells = "".join("  %+7.3f" % g.get(b, np.nan) for b in range(5))
            spread = g.iloc[-1] - g.iloc[0]
        ranked.append((abs(spread), spread, ft, cells, len(d)))
    ranked.sort(reverse=True)
    for _, spread, ft, cells, cnt in ranked:
        print("  %-11s%s   spread %+7.3f  (%d)" % (ft, cells, spread, cnt))

    print("\n  by timeframe: %s" %
          {t: "%+.3f%%" % (100 * g.net.mean()) for t, g in R.groupby("tf")})
    print("  full table: ride_study.csv")


if __name__ == "__main__":
    main()
