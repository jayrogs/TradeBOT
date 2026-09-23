"""backburner_dipspeed.py -- "THE FASTER THE DIPS THE BETTER" (2026-09-22, his words: "that means bulls showed up to buy
discounted stock").

Selling a slow BOUNCE saved nothing (backburner_slow): by the time a bounce is known to be slow the loss is in the price.
His sentence is about the DROP, which is known BEFORE the buy. So at the first buy (the RSI-30 touch) measure:
    hours   hours since the highest high of the last 50 hourly bars (the top of this drop)
    fall    how far price fell from that top, in normal hourly bars
    speed   fall / hours = normal bars per hour
and split the page's own trades by them. Nothing after the buy is used to split.

    pythonw studies/backburner_dipspeed.py --procs 8 --log logs/backburner_dipspeed.log
Writes validation/backburner_dipspeed.json and _rows.parquet
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
import pics_backburner_tcg as PB  # noqa: E402
import eq_freeride2 as FR2        # noqa: E402
import panel as P                 # noqa: E402

OUT = os.path.join("validation", "backburner_dipspeed.json")
LOOK = 50


def _work(args):
    sym, kind = args
    rows = []
    try:
        got = PB.trades_for(sym, kind)
        if not got:
            return rows, []
        fr = {k_: v for k_, v in S.frames_for(sym, kind).items() if k_ == "1h"}
        if kind in ("stock", "etf"):
            fr = FR2.regular_hours(fr)
        df = fr["1h"]
        h = df["High"].values.astype(float)
        atr = P._atr(df)
        for r in got:
            k = r["k"]
            if k < LOOK + 1:
                continue
            a = atr[k - 1]
            if not np.isfinite(a) or a <= 0:
                continue
            w = h[k - LOOK:k]                                  # bars BEFORE the buy bar only
            ti = k - LOOK + int(np.argmax(w))
            top = float(h[ti])
            fill = r["fills"][0]
            hours = float(k - ti)
            fall = (top - fill) / a
            rows.append([0.0 if kind in ("stock", "etf") else 1.0, hours, fall, fall / max(hours, 1.0),
                         100 * (top - fill) / top, r["pct"], float(pd.Timestamp(r["t"]).year)])
    except Exception as ex:
        return [], ["%s %s: %s" % (kind, sym, ex)]
    return rows, []


def main():
    procs, log = 8, None
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            log = sys.argv[i + 1]
            sys.stdout = sys.stderr = io.open(log, "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    names = R._by_size([(s_, k_) for s_, k_ in S.universe()
                        if k_ in ("stock", "etf", "crypto") and s_ not in PB.T.SUSPECT])
    R.quiet_workers()
    rows, errs = [], []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got, err in ex.map(_work, names, chunksize=2):
            rows += got; errs += err
    f = pd.DataFrame(rows, columns=["crypto", "hours", "fall", "speed", "fall_pct", "pct", "yr"])
    f.to_parquet(os.path.splitext(OUT)[0] + "_rows.parquet")
    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names), n=int(len(f))),
               table={})

    def row(label, g):
        if len(g) < 30:
            return
        g = g.sort_values("yr", kind="stable")
        v = g.pct.values
        yrs = g.groupby("yr").pct.mean()
        blocks = [v[i:i + 20].sum() for i in range(0, len(v) - 19, 20)]
        d = dict(n=int(len(g)), avg=float(v.mean()), middle=float(np.median(v)), won=float((v > 0).mean()),
                 p5=float(np.percentile(v, 5)), years_up=int((yrs > 0).sum()), years=int(len(yrs)),
                 blocks_up=int(sum(1 for b in blocks if b > 0)), blocks=int(len(blocks)))
        out["table"][label] = d
        print("    %-46s %5d %+7.2f%% %+7.2f%% %4.0f%% %+6.1f%% %3d/%-3d %4d/%-4d" % (
            label, d["n"], d["avg"], d["middle"], 100 * d["won"], d["p5"], d["years_up"], d["years"],
            d["blocks_up"], d["blocks"]))

    for cut, sel in (("everything", f.pct == f.pct), ("stocks + ETFs", f.crypto == 0)):
        g0 = f[sel]
        print("\n  THE FASTER THE DIPS THE BETTER? %s, %d trades  (%.0fs)\n" % (cut, len(g0), time.time() - t0))
        print("    %-46s %5s %8s %8s %5s %7s %7s %9s" % ("the drop into the first buy", "n", "avg", "middle", "won",
                                                        "5%", "yrs", "blocks"))
        row("every trade (the page)", g0)
        print("  HOURS FROM THE TOP TO THE BUY")
        for lo, hi, lab in ((0, 6, "5 hours or less"), (6, 11, "6 to 10 hours"), (11, 21, "11 to 20 hours"),
                            (21, 999, "21 hours or more")):
            row(lab, g0[(g0.hours >= lo) & (g0.hours < hi)])
        print("  SPEED: normal bars fallen per hour (quarters of the pool)")
        q = g0.speed.quantile([0.25, 0.5, 0.75]).values
        row("slowest quarter (under %.2f)" % q[0], g0[g0.speed < q[0]])
        row("second quarter", g0[(g0.speed >= q[0]) & (g0.speed < q[1])])
        row("third quarter", g0[(g0.speed >= q[1]) & (g0.speed < q[2])])
        row("fastest quarter (%.2f and up)" % q[2], g0[g0.speed >= q[2]])
    json.dump(out, io.open(OUT, "w", encoding="utf-8"))
    for e_ in errs[:5]:
        print("  ERR " + e_)
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
