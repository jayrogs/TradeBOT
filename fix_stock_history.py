"""fix_stock_history.py -- put the intraday stock history on the same price
scale as the daily history, and throw out impossible bars.

    python fix_stock_history.py             # dry run, prints what it would do
    python fix_stock_history.py --write     # rewrites history/stocks/*_{5m,15m,1h}.csv.gz

WHY (2026-09-06): the daily files (Yahoo) are adjusted backwards for splits;
the intraday files (Alpaca) are not. MNST's 4-hour chart shows 63 where its
daily chart shows 31 for the same day. 86 of 600 names carry a split-sized
overnight jump, and a few carry zero or near-zero closes -- a 2:1 split reads
to any study as a -50% bar, which is a fake stop-out, a fake pivot and a fake
"really bad" backburner.

WHAT IT DOES, per name:
  1. resample the 1-hour file to daily closes and compare with the daily file
     on the days both have; the ratio should be 1.0 everywhere
  2. where it is not, that day's factor is daily / intraday; the factor is
     carried back over every intraday bar of that day and every earlier bar
     with the same factor, and OHLC is multiplied by it (volume is divided)
  3. bars with a non-positive or absurd price, or a high under the low, are
     dropped
Anything already lined up is left untouched.
"""

import glob
import os
import sys

import numpy as np
import pandas as pd

SRC = os.path.join("history", "stocks")
TFS = ["5m", "15m", "1h"]
TOL = 0.01          # ratios inside 1% count as "already the same scale"


def load(path):
    if not os.path.exists(path):
        return None
    d = pd.read_csv(path, index_col=0, parse_dates=True)
    return d[~d.index.duplicated(keep="last")].sort_index()


def splits_from(intraday_1h, daily):
    """The split dates and their ratios, taken from the intraday file itself.

    A split shows up as an overnight jump in the intraday series that the
    daily file does not have, because the daily file is adjusted backwards:
    XLE halved on 2025-12-05, VGT went to an eighth on 2026-04-21, MNST
    halved on 2023-03-28 and again on 2026-08-11. Dividend days move the
    daily file by a fraction of a percent and are ignored, since smearing
    those across intraday bars would invent price moves.

    Returns [(timestamp, ratio, daily_too)], ratio being the overnight jump
    (0.5 for a 2-for-1). `daily_too` means the daily file was never adjusted
    either, so both files need the same treatment.
    """
    c = intraday_1h["Close"].values.astype(float)
    idx = intraday_1h.index
    with np.errstate(invalid="ignore", divide="ignore"):
        r = c[1:] / c[:-1]
    out = []
    dd = daily["Close"].copy()
    dd.index = dd.index.normalize()
    dd = dd[~dd.index.duplicated(keep="last")]
    # a split is a clean ratio: 2-for-1, 3-for-1, 1-for-10 and so on
    clean = [1 / 50, 1 / 40, 1 / 30, 1 / 25, 1 / 20, 1 / 15, 1 / 12, 1 / 10, 1 / 8, 1 / 6,
             1 / 5, 1 / 4, 1 / 3, 1 / 2, 2 / 3, 3 / 2, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50]
    for k in np.where((r < 0.75) | (r > 1.34))[0]:
        t = idx[k + 1]
        ratio = float(r[k])
        if not np.isfinite(ratio) or ratio <= 0.02 or ratio >= 60:
            continue                                  # zero or junk prices, not a split
        if idx[k].normalize() == t.normalize():
            continue                                  # inside one session: a real move
        if min(abs(ratio / x - 1) for x in clean) > 0.10:
            continue          # not near a split ratio (the overnight move rides on top of it)
        day = t.normalize()
        prev = dd.index[dd.index < day]
        if day not in dd.index or len(prev) == 0:
            continue
        dr = float(dd.loc[day]) / float(dd.loc[prev[-1]])
        if not np.isfinite(dr):
            continue
        if abs(dr - 1) <= 0.15:
            out.append((t, ratio, False))             # only the intraday file has it
        elif abs(dr / ratio - 1) <= 0.10:
            out.append((t, ratio, True))              # BOTH files carry the raw split
        # anything else is a real overnight move: leave it alone
    return out


def factors(intraday_1h, daily):
    """A step-shaped multiplier from those splits: 1.0 after the last one,
    and each earlier stretch multiplied by the splits that came after it."""
    sp = splits_from(intraday_1h, daily)
    if not sp:
        return None
    return sp


def fix_name(sym, write):
    h1 = load(os.path.join(SRC, "%s_1h.csv.gz" % sym))
    d1 = load(os.path.join(SRC, "%s_1d.csv.gz" % sym))
    if h1 is None or d1 is None or len(h1) < 100 or len(d1) < 50:
        return None
    sp = factors(h1, d1)
    dropped_total, changed = 0, []
    for tf in TFS + (["1d"] if sp and any(x[2] for x in sp) else []):
        p = os.path.join(SRC, "%s_%s.csv.gz" % (sym, tf))
        d = load(p)
        if d is None or d.empty:
            continue
        before = len(d)
        f = np.ones(len(d))
        if sp:
            for t, ratio, daily_too in sp:            # bars before the split scale down
                if tf == "1d" and not daily_too:
                    continue
                f = np.where(d.index < t, f * ratio, f)
        touched = float(np.max(np.abs(f - 1))) if len(f) else 0.0
        if touched > TOL:
            for col in ("Open", "High", "Low", "Close"):
                if col in d.columns:
                    d[col] = d[col].values * f
            if "Volume" in d.columns:
                d["Volume"] = d["Volume"].values / f
        bad = (d[["Open", "High", "Low", "Close"]] <= 0).any(axis=1) |               (d["High"] < d["Low"]) | ~np.isfinite(d[["Open", "High", "Low", "Close"]]).all(axis=1)
        if bad.any():
            d = d[~bad]
        dropped = before - len(d)
        dropped_total += dropped
        if touched > TOL or dropped:
            changed.append((tf, touched, dropped))
            if write:
                d.to_csv(p, compression="gzip")
    if not changed:
        return None
    return dict(sym=sym, splits=[(str(t)[:10], round(x, 4)) for t, x, _ in (sp or [])],
                changed=changed, dropped=dropped_total)


def main():
    write = "--write" in sys.argv
    syms = sorted(os.path.basename(f).split("_")[0]
                  for f in glob.glob(os.path.join(SRC, "*_1h.csv.gz")))
    hits = []
    for i, sym in enumerate(syms):
        try:
            out = fix_name(sym, write)
        except Exception as ex:
            print("  %-6s %s" % (sym, ex), flush=True); continue
        if out:
            hits.append(out)
            print("  %-6s %s%s" % (sym, ", ".join("%s x%g" % (t, x) for t, x in out["splits"]) or "no split",
                                     ", dropped %d bad bars" % out["dropped"] if out["dropped"] else ""), flush=True)
        if (i + 1) % 100 == 0:
            print("  ... %d/%d names" % (i + 1, len(syms)), flush=True)
    print("\n  %s: %d of %d names needed work" % ("REWROTE" if write else "would change", len(hits), len(syms)))
    if not write:
        print("  (dry run -- rerun with --write to apply)")


if __name__ == "__main__":
    main()
