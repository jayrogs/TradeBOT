"""wind_study.py -- two owner-spec knobs, measured on both eras.

    python wind_study.py

KNOB 1, exit tolerance ("it just baaaaarely didnt hold the ema12"):
  body        current rule: body close under the EMA (10% body grace) exits
  close10     exit only if the close is under the EMA by > 0.10 ATR
  close25     exit only if the close is under the EMA by > 0.25 ATR
  share50     exit only if more than HALF the body sits under the EMA

KNOB 2, wind at our backs ("minimum green uptrends for greenlighting"):
  entries also require the live trend to have been UP for >= AGE bars:
  0 (current), 5, 10, 20.

Same entry population otherwise, promotion and 3% trail unchanged. Every
cell reported for BOTH eras -- a knob earns its place only if it helps (or
at least does not hurt) in each. This is exit/gate arithmetic on the same
trades, not a new edge claim.
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
STOP = 0.03
PROM = 1.01
EXITS = ["body", "close10", "close25", "share50"]
AGES = [0, 5, 10, 20]


def liquid_years(df, mult):
    dv = (df["Close"] * df["Volume"]).groupby(df.index.year).median()
    return set(dv[dv >= DOLLAR * mult].index)


def walk(v, entry, fill, exit_mode):
    c, lo, e, hold, o, atr = (v["c"], v["lo"], v["e"], v["hold"], v["o"],
                              v["atr"])
    promoted = False
    for k in range(entry + 1, v["n"]):
        floor = e[k] * (1 - STOP)
        if lo[k] <= floor:
            return floor
        if not promoted and c[k] >= fill * PROM:
            promoted = True
        if promoted:
            continue
        if exit_mode == "body":
            out = not hold[k]
        elif exit_mode == "close10":
            buf = 0.10 * (atr[k] if np.isfinite(atr[k]) else 0.0)
            out = c[k] < e[k] - buf
        elif exit_mode == "close25":
            buf = 0.25 * (atr[k] if np.isfinite(atr[k]) else 0.0)
            out = c[k] < e[k] - buf
        else:                                   # share50
            b_lo, b_hi = min(o[k], c[k]), max(o[k], c[k])
            body = b_hi - b_lo
            if body <= 0:
                out = c[k] < e[k]
            else:
                share = max(0.0, min(e[k] - b_lo, body)) / body
                out = not (b_hi > e[k] and share <= 0.5)
        if out:
            return c[k]
    return None


def era_trades(lo_t, hi_t):
    """(upage, {exit_mode: net}) per entry."""
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
            for entry, fill in L.entries(v, 2, "promote1"):
                if entry >= v["n"] - 2 or not liq[entry]:
                    continue
                nets = {}
                for em in EXITS:
                    px = walk(v, entry, fill, em)
                    if px is not None:
                        nets[em] = px / fill - 1 - 2 * L.COST
                if nets:
                    out.append((int(v["upage"][entry]), nets))
    return out


def main():
    for label, lo_t, hi_t in (
            ("2022-07 -> now (mined)", SPLIT, pd.Timestamp("2100-01-01")),
            ("2015 -> 2022-07 (frozen)", pd.Timestamp("2000-01-01"), SPLIT)):
        trades = era_trades(lo_t, hi_t)
        print("\n" + "=" * 78)
        print("  %s -- %d entries" % (label, len(trades)))
        print("=" * 78)
        print("  %-9s %-6s %7s %9s %9s %6s" %
              ("exit", "age>=", "n", "mean", "median", "win%"))
        for em in EXITS:
            for age in AGES:
                a = np.array([nets[em] for up, nets in trades
                              if up >= age and em in nets])
                if len(a) < 30:
                    continue
                print("  %-9s %-6d %7d %+8.3f%% %+8.3f%% %5.0f%%"
                      % (em, age, len(a), 100 * a.mean(),
                         100 * np.median(a), 100 * (a > 0).mean()))
            print()


if __name__ == "__main__":
    main()
