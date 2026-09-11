"""name_traits.py -- his point (2026-09-08): "it's not really about how much a stock goes up,
it's about how much a name moves, and how predictable its moves can be."

Measures three things about each name that have nothing to do with the trading rule, using
ONLY the first half of the window, then tests each against how the trend ride actually did on
that name in the second half. That keeps "what you could have known" separate from "what
happened", and it separates going up from moving from moving predictably.

    goes_up      what the name did over the first half. Pure drift.
    moves        a normal bar as a share of price. Pure movement, nothing to do with direction.
    straight     of all the ground a name covers in 20 bars, how much of it ends up as net
                 travel. 1.0 = a straight line, 0.1 = it covered ten times the distance it
                 actually went. This is "how predictable the moves are" as a shape.
    follows      after a higher low confirms, how often price is higher 10 bars later. This is
                 predictability measured with HIS OWN rule, not a generic one.
    swing        the average size of one bar's move, in per cent. A cruder "moves".

    pythonw studies/name_traits.py --procs 20 --log logs/name_traits.log

Writes validation/name_traits.json.
"""
import concurrent.futures as cf
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as B      # noqa: E402
import structure as ST            # noqa: E402

TF = "1h"                         # the only chart where picking names carried (CLAUDE #30)
WIN = 20                          # bars in the straightness window
AHEAD = 10                        # bars to look ahead for follow-through


def traits(args):
    sym, kind, mid = args
    try:
        df = B.frames_for(sym, kind).get(TF)
    except Exception:
        return None
    if df is None:
        return None
    d = df[df.index < mid]
    if len(d) < 400:
        return None
    c = d["Close"].values.astype(float)
    h = d["High"].values.astype(float); l = d["Low"].values.astype(float)
    n = len(c)
    atr = B.atr(h, l, c)
    px = np.where(c > 0, c, np.nan)
    moves = float(np.nanmean(atr / px))                       # a normal bar as a share of price
    swing = float(np.nanmean(np.abs(np.diff(c)) / px[:-1]))
    goes_up = float(c[-1] / c[0] - 1)
    # straightness: net travel over WIN bars divided by the ground actually covered
    step = np.abs(np.diff(c))
    cov = np.convolve(step, np.ones(WIN), "valid")
    net = np.abs(c[WIN:] - c[:-WIN])
    ok = cov > 0
    straight = float(np.mean(net[ok] / cov[ok])) if ok.any() else np.nan
    # follow-through on HIS rule: after a higher low confirms, is price higher AHEAD bars later?
    good = tot = 0
    up_after = []
    for ci, j, p, k_, lab in ST.pivots(d):
        if k_ != "low" or lab not in ("HL", "EL") or ci + 1 + AHEAD >= n:
            continue
        e = ci + 1
        r = c[e + AHEAD] / c[e] - 1
        up_after.append(r)
        tot += 1
        good += 1 if r > 0 else 0
    follows = float(good / tot) if tot >= 20 else np.nan
    after_mean = float(np.mean(up_after)) if tot >= 20 else np.nan
    return dict(sym=sym, kind=kind, bars=int(n), goes_up=goes_up, moves=moves, swing=swing,
                straight=straight, follows=follows, after_mean=after_mean, pivots=int(tot))


def main():
    procs = max(1, os.cpu_count() or 4)
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            sys.stdout = sys.stderr = open(sys.argv[i + 1], "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * B.YEARS)
    end = pd.Timestamp.now().normalize()
    mid = start + (end - start) / 2
    names = [(s_, k_) for s_, k_ in B.universe()]
    rows, done = [], 0
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for r in ex.map(traits, [(s_, k_, mid) for s_, k_ in names], chunksize=4):
            done += 1
            if r:
                rows.append(r)
            if done % 200 == 0 or done == len(names):
                print("  %d/%d  (%.0fs)" % (done, len(names), time.time() - t0), flush=True)
    json.dump(dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), tf=TF,
                             half_ends=str(mid), names=len(rows), seconds=int(time.time() - t0)),
                   rows=rows), open(os.path.join("validation", "name_traits.json"), "w"))
    print("  %d names measured on the first half  (%.0fs)" % (len(rows), time.time() - t0))


if __name__ == "__main__":
    main()
