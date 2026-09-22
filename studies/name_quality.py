"""name_quality.py -- an AUTOMATIC screen for names whose daily chart is not worth trading (2026-09-22).

His words, after rejecting BTI, KEY, DOCN and BHP on their candles: "we should make an automatic filter to not have
shitty charting names, I'm not gonna manually filter every single stock name in existence for all of its history".
And on KEY: "technically a backburner but I wouldn't like this NAME."

THE MISTAKE I KEPT MAKING: measuring the 20-40 daily bars around each dip. Over 40 bars noise swamps everything, and
every measure I tried had his keeps scattered through his rejects. A name's character is a property of its WHOLE
history, so it is measured over every daily bar the name has, once, and the score attaches to the NAME.

Measured on the daily, each in the name's own normal bars so a $19 name and a $460 name are judged the same way:
    gaps      how often the open is far from the last close      ("gaps everywhere")
    wicks     the share of each candle that is wick, not body    ("long wicks both directions")
    body      the body as a share of the normal bar              ("long candle bodies")
    size      how big a daily bar is against its own 14-day norm ("candles are pretty big all the time")
    crosses   crosses of the 12 EMA per 100 days                 ("oscillating all over the place")
    chop      ground covered / net travel over 20 days           (the opposite of a staircase)
    dollars   median daily dollar volume

    pythonw studies/name_quality.py --procs 8 --log logs/name_quality.log
Writes validation/name_quality.json  (every name, every measure, plus its rank)
"""
import concurrent.futures as cf
import io
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as S      # noqa: E402
import trend_ride as R            # noqa: E402
import panel as P                 # noqa: E402
import exit_managers as XM        # noqa: E402
import eq_freeride2 as FR2        # noqa: E402

OUT = os.path.join("validation", "name_quality.json")
COLS = ["gaps", "wicks", "body", "size", "crosses", "chop", "dollars"]


def _work(args):
    sym, kind = args
    try:
        fr = S.frames_for(sym, kind)
        fr = {x: v for x, v in fr.items() if x == "1d"}
        if kind in ("stock", "etf"):
            fr = FR2.regular_hours(fr)
        d = fr.get("1d")
        if d is None or len(d) < 250:
            return None
        o, h, l, c = (d[x].values.astype(float) for x in ("Open", "High", "Low", "Close"))
        v = d["Volume"].values.astype(float) if "Volume" in d else np.zeros(len(c))
        a = P._atr(d)
        ok = np.isfinite(a) & (a > 0)
        if ok.sum() < 200:
            return None
        rng = h - l
        e12 = XM.ema(c, 12)
        above = c > e12
        cross = np.sum(above[1:] != above[:-1]) / max(1, len(c) - 1) * 100
        step = np.abs(np.diff(c))                     # len n-1
        net = np.abs(c[20:] - c[:-20])                # len n-20
        ground = pd.Series(step).rolling(20).sum().values[19:]   # len n-20, aligned with net
        with np.errstate(invalid="ignore", divide="ignore"):
            chop = np.nanmedian(ground / np.where(net > 0, net, np.nan))
            gaps = float(np.nanmean((np.abs(o[1:] - c[:-1]) / a[1:])[ok[1:]] > 0.30))
            wicks = float(np.nanmedian(((rng - np.abs(c - o)) / np.where(rng > 0, rng, np.nan))[ok]))
            body = float(np.nanmedian((np.abs(c - o) / a)[ok]))
            size = float(np.nanmedian((rng / a)[ok]))
        return dict(sym=sym, kind=kind, n=int(len(c)), gaps=gaps, wicks=wicks, body=body, size=size,
                    crosses=float(cross), chop=float(chop),
                    dollars=float(np.median((c * v)[-250:])) if v.any() else 0.0)
    except Exception:
        return None


def main():
    procs, log = 8, None
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            log = sys.argv[i + 1]
            sys.stdout = sys.stderr = io.open(log, "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    names = [(s_, k_) for s_, k_ in S.universe() if k_ != "forex"]
    R.quiet_workers()
    rows = []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got in ex.map(_work, names, chunksize=4):
            if got:
                rows.append(got)
    f = pd.DataFrame(rows)
    # rank inside each market: a coin is only compared with coins
    for col in COLS:
        f["r_" + col] = f.groupby("kind")[col].rank(pct=True)
    f["messy"] = f[["r_gaps", "r_wicks", "r_size", "r_crosses", "r_chop"]].mean(axis=1)
    f = f.sort_values("messy", ascending=False)
    json.dump(dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=int(len(f)),
                   rows=f.to_dict("records")), io.open(OUT, "w", encoding="utf-8"))
    print("  %d names measured over their whole daily history  (%.0fs)\n" % (len(f), time.time() - t0))
    HIS = {"BTI": "he rejected", "KEY": "he rejected", "DOCN": "he rejected", "BHP": "he rejected",
           "CW": "he kept", "ROL": "he kept", "CASY": "he kept", "GOOG": "he kept", "CDNS": "he kept",
           "EAT": "he kept", "MNST": "he kept", "TSLA": "he kept", "AZN": "he kept", "COP": "he kept",
           "KHC": "he kept", "FIS": "he kept", "RMD": "he kept", "DINO": "he kept", "LII": "he kept",
           "CRS": "he kept", "HIG": "he kept", "JBHT": "he kept", "BIDU": "he kept"}
    g = f[f.sym.isin(HIS)].copy()
    g["his"] = g.sym.map(HIS)
    print("  HIS NAMES, worst first by the combined score (1.00 = the messiest name in its market):")
    print(g[["sym", "his", "messy", "gaps", "wicks", "size", "crosses", "chop"]].to_string(index=False,
          float_format=lambda x: "%.2f" % x))
    print("\n  medians:")
    print(g.groupby("his")[["messy", "gaps", "wicks", "size", "crosses", "chop"]].median().round(2).to_string())
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
