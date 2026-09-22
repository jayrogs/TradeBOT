"""messy_label.py -- draw a big set of runs so the MESSY/CLEAN labels can be made by EYE, then fitted (2026-09-22).

His four rejects (BTI, KEY, DOCN, BHP) against twenty-one keeps were not enough for any measure to separate, and
the raw-shape method scored worse than guessing (#44). But the difference is obvious to look at. So: draw 160 runs
the same way /cleanruns draws them (daily, the 55 bars before the dip, stopped at the dip), label them by eye using
his four rejects as the standard, and fit on 160 labels instead of 25.

    python studies/messy_label.py --procs 8 --n 160
Writes validation/messy_label/*.png + index.json (with every measure recorded, hidden until the labels exist)
"""
import concurrent.futures as cf
import io
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "studies"))
import backburner_study as S      # noqa: E402
import eq_freeride2 as FR2        # noqa: E402
import panel as P                 # noqa: E402
import exit_managers as XM        # noqa: E402
import pics_cleanrun as CR        # noqa: E402
import pics_backburner_tcg as PB  # noqa: E402

OUT = os.path.join("validation", "messy_label")


def facts(d, i, W=55):
    """Every ingredient I can name, on exactly the bars the picture shows. Recorded now, fitted after the labels."""
    o, h, l, c = (d[x].values.astype(float) for x in ("Open", "High", "Low", "Close"))
    a = P._atr(d); e = XM.ema(c, 12)
    w = slice(i - 1 - W, i - 1)
    rng = h[w] - l[w]
    ab = c[w] > e[w]
    step = np.abs(np.diff(c[i - 2 - W:i - 1])); net = abs(c[i - 2] - c[i - 2 - W])
    with np.errstate(invalid="ignore", divide="ignore"):
        return dict(
            crosses=int(np.sum(ab[1:] != ab[:-1])),
            above=float(np.mean(ab)),
            chop=float(np.sum(step) / net) if net > 0 else None,
            gaps=float(np.mean(np.abs(o[w] - c[i - 2 - W:i - 2]) / a[w] > 0.30)),
            wicks=float(np.nanmedian((rng - np.abs(c[w] - o[w])) / np.where(rng > 0, rng, np.nan))),
            size=float(np.nanmedian(rng / a[w])),
            body=float(np.nanmedian(np.abs(c[w] - o[w]) / a[w])),
            biggest=float(np.max(step) / (np.mean(step) or np.nan)),
            emaup=float(np.mean(np.diff(e[i - 2 - W:i - 1]) > 0)),
            flat=float(np.mean(np.abs(np.diff(e[i - 2 - W:i - 1])) / a[w] < 0.05)),
            net_atr=float(net / a[i - 2]))


def _one(args):
    sym, kind = args
    out = []
    try:
        for r in PB.trades_for(sym, kind):
            out.append(dict(sym=sym, kind=kind, k=r["k"], t=r["t"]))
    except Exception:
        pass
    return out


def _draw(args):
    sym, kind, picks = args
    got = []
    try:
        fr = S.frames_for(sym, kind)
        fr = {x: v for x, v in fr.items() if x in ("1h", "1d")}
        if kind in ("stock", "etf"):
            fr = FR2.regular_hours(fr)
        for p in picks:
            png = "%04d_%s_%s_%d.png" % (p["n"], kind, sym, p["k"])
            probs, _m = CR.draw(sym, kind, p["k"], p["t"], os.path.join(OUT, png))
            i = int(fr["1d"].index.searchsorted(fr["1h"].index[p["k"]]))
            got.append(dict(p, png=png, problems=probs, hidden=facts(fr["1d"], i)))
    except Exception as ex:
        for p in picks:
            got.append(dict(p, png="", problems=["%s" % ex], hidden={}))
    return got


def main():
    procs, n = 8, 160
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--n" and i + 1 < len(sys.argv):
            n = int(sys.argv[i + 1])
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    names = [(s_, k_) for s_, k_ in S.universe() if k_ in ("stock", "etf", "crypto") and s_ not in PB.T.SUSPECT]
    rows = []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got in ex.map(_one, names, chunksize=4):
            rows += got
    print("  %d runs to choose from  (%.0fs)" % (len(rows), time.time() - t0), flush=True)
    rng = np.random.default_rng(6022)
    picks = [rows[i] for i in rng.choice(len(rows), n, replace=False)]
    for j, p in enumerate(picks, 1):
        p["n"] = j
    by = {}
    for p in picks:
        by.setdefault((p["sym"], p["kind"]), []).append(p)
    drawn = []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got in ex.map(_draw, [(s_, k_, v) for (s_, k_), v in by.items()], chunksize=1):
            drawn += got
    drawn = [d for d in drawn if d["png"]]
    drawn.sort(key=lambda x: x["n"])
    keep = {d["png"] for d in drawn} | {"index.json"}
    for f in os.listdir(OUT):
        if f not in keep and os.path.isfile(os.path.join(OUT, f)):
            os.remove(os.path.join(OUT, f))

    def plain(v):
        return v.item() if hasattr(v, "item") else v
    json.dump(dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                   charts=[{k: (plain(v) if k != "hidden" else {a: plain(b) for a, b in v.items()})
                            for k, v in d.items()} for d in drawn]),
              io.open(os.path.join(OUT, "index.json"), "w", encoding="utf-8"), indent=1)
    print("  drawn %d, problems %d  (%.0fs)" % (len(drawn), sum(1 for d in drawn if d["problems"]), time.time() - t0))


if __name__ == "__main__":
    main()
