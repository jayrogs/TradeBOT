"""Repair the forex minute stores written before 2026-09-08.

The downloader read Dukascopy's time field as milliseconds when it is seconds, so a whole
day's 1440 minute bars landed inside the first 86 seconds of that day and every resampled
"1h" file came out with one bar a day. The prices are fine; only the clock was wrong, so
this multiplies each bar's time-since-midnight by 1000 and rewrites the CSVs. Nothing is
re-downloaded.

    pythonw fix_dukascopy_clock.py --log logs/fix_duka.log
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backfill_dukascopy as D

CACHE = os.path.join("cache", "dukascopy")
OUT = os.path.join("history", "forex")


def fix_store(path):
    m = pd.read_parquet(path)
    if not len(m):
        return None, "empty"
    off = m.index - m.index.normalize()
    if off.max() > pd.Timedelta(hours=2):
        return m, "already correct"          # a real day spans ~24h, a broken one ~86 seconds
    m = m.copy()
    m.index = m.index.normalize() + off * 1000
    m = m[~m.index.duplicated()].sort_index()
    m.index.name = "t"
    m.to_parquet(path)
    return m, "repaired"


def main():
    for i, a in enumerate(sys.argv):
        if a == "--log" and i + 1 < len(sys.argv):
            sys.stdout = sys.stderr = open(sys.argv[i + 1], "w", buffering=1, encoding="utf-8", errors="replace")
    back = {v: k for k, v in list(D.FX.items()) + list(D.CFD.items())}
    os.makedirs(OUT, exist_ok=True)
    for fn in sorted(os.listdir(CACHE)):
        if not fn.endswith(".parquet"):
            continue
        instr = fn[:-8]
        path = os.path.join(CACHE, fn)
        m, how = fix_store(path)
        if m is None:
            print("  %-10s %s" % (instr, how)); continue
        ysym = back.get(instr)
        if ysym is None:
            print("  %-10s %s, no symbol" % (instr, how)); continue
        scale, err = D.pick_scale(instr, m)
        frames = D.resample(m, scale)
        name = ysym.replace("=", "_")
        for tf, f in frames.items():
            f.to_csv(os.path.join(OUT, "%s_%s.csv.gz" % (name, tf)), compression="gzip")
        h = frames["1h"]
        print("  %-10s %-9s %s  scale 1e%d  match %s  1h bars %d  %s -> %s  (%.1f bars a day)" % (
            instr, ysym, how, int(round(__import__("numpy").log10(scale))),
            "n/a" if err is None else "%.2f%%" % (100 * err), len(h),
            h.index[0].date(), h.index[-1].date(),
            len(h) / max((h.index[-1] - h.index[0]).days, 1)), flush=True)


if __name__ == "__main__":
    main()
