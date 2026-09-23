"""backburner_coolshape.py -- WHICH cooling bounces are the BURL kind (2026-09-22).

His BURL rule as I coded it (back over RSI 31 before the half sold, then out on the next close under 30) fixes BURL
and costs the pool -0.26% a trade (#44e). I measured the bounce crudely: only whether RSI got over 31. His correction:
"I noticed burl cooled off rsi pretty quickly with its bounce". BURL's RSI went 26.5 -> 34.9 in three hours while price
rose only 0.8% and never got near the 12 EMA -- the RSI reset without a real bounce.

So for every trade the rule would have acted on, measure the bounce the moment RSI first closed over 31:
    rise   how far PRICE had bounced off the low of the drop, in normal hourly bars
    speed  hours from the lowest RSI to that close
    gap    how far the 12 EMA still sat above price, in normal bars
and split by them. Each row pairs the page (no rule) with the rule on the SAME trades: "saved" > 0 means the rule helps
that group. Only facts known at the cooling close are used to split.

    pythonw studies/backburner_coolshape.py --procs 8 --log logs/backburner_coolshape.log
Writes validation/backburner_coolshape.json and _rows.parquet
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
import indicators as IND          # noqa: E402
import exit_managers as XM        # noqa: E402
import panel as P                 # noqa: E402
import backburner_dan as D        # noqa: E402

OUT = os.path.join("validation", "backburner_coolshape.json")
COOL = 31


def _work(args):
    sym, kind = args
    rows = []
    try:
        base = {r["k"]: r for r in PB.trades_for(sym, kind)}
        rule = {r["k"]: r for r in PB.trades_for(sym, kind, dict(PB.STOP, cool=(COOL, "exit")))}
        if not base:
            return rows, []
        fr = {k_: v for k_, v in S.frames_for(sym, kind).items() if k_ in ("1h",)}
        if kind in ("stock", "etf"):
            fr = FR2.regular_hours(fr)
        df = fr["1h"]
        c = df["Close"].values.astype(float); l = df["Low"].values.astype(float)
        rsi = IND.rsi_parts(c, D.N_RSI)[0]
        e12 = XM.ema(c, 12)
        atr = P._atr(df)
        for k, b in base.items():
            r = rule.get(k)
            if r is None:
                continue
            e = b["e"]
            a = atr[k - 1]
            stop_at = b["half_at"] if b["half_at"] is not None else b["end"]
            cb = None
            for j in range(e + 1, min(stop_at, len(c) - 1) + 1):
                if rsi[j - 1] >= COOL:
                    cb = j - 1
                    break
            if cb is None or cb < k or not np.isfinite(a) or a <= 0:
                continue                                   # the rule never acts on this trade
            lo_i = k + int(np.argmin(rsi[k:cb + 1]))
            low = float(np.min(l[k:cb + 1]))
            rows.append([0.0 if kind in ("stock", "etf") else 1.0,
                         (c[cb] - low) / a,                  # rise, in normal bars
                         100 * (c[cb] / low - 1),            # rise, percent
                         float(cb - lo_i),                   # speed, hours
                         (e12[cb] - c[cb]) / a,              # gap to the 12 EMA, normal bars
                         float(rsi[cb] - rsi[lo_i]),         # how many RSI points it cooled
                         b["pct"], r["pct"], 1.0 if b["half_at"] is not None else 0.0,
                         1.0 if r["how"].startswith("out: the bounce cooled") else 0.0])
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
    f = pd.DataFrame(rows, columns=["crypto", "rise", "rise_pct", "speed", "gap", "cooled_pts",
                                    "page", "rule", "reached_ema", "fired"])
    f["saved"] = f.rule - f.page
    f.to_parquet(os.path.splitext(OUT)[0] + "_rows.parquet")
    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names), n=int(len(f))),
               table={})

    def row(label, g):
        if len(g) < 30:
            return
        d = dict(n=int(len(g)), page=float(g.page.mean()), rule=float(g.rule.mean()), saved=float(g.saved.mean()),
                 reached=float(g.reached_ema.mean()), page_middle=float(g.page.median()))
        out["table"][label] = d
        print("    %-52s %5d %+7.2f%% %+7.2f%% %+7.2f%% %6.0f%%" % (label, d["n"], d["page"], d["rule"], d["saved"],
                                                                 100 * d["reached"]))

    print("\n  WHICH COOLING BOUNCES ARE THE BURL KIND: %d trades where RSI got back over %d before the half  (%.0fs)\n"
          % (len(f), COOL, time.time() - t0))
    print("    %-52s %5s %8s %8s %8s %7s" % ("the bounce when RSI got back over 31", "n", "page", "rule", "saved",
                                           "reached EMA"))
    row("every one of them", f)
    print("\n  HOW FAR PRICE HAD BOUNCED (normal hourly bars)")
    for lo, hi, lab in ((0, 0.5, "under half a bar (BURL: price barely moved)"), (0.5, 1, "half to one bar"),
                        (1, 2, "one to two bars"), (2, 99, "two bars or more")):
        row(lab, f[(f.rise >= lo) & (f.rise < hi)])
    print("\n  HOW FAST RSI COOLED (hours from its lowest point)")
    for lo, hi, lab in ((0, 4, "3 hours or less (BURL: 3)"), (4, 7, "4 to 6 hours"), (7, 999, "7 hours or more")):
        row(lab, f[(f.speed >= lo) & (f.speed < hi)])
    print("\n  HOW FAR THE 12 EMA STILL WAS (normal hourly bars)")
    for lo, hi, lab in ((-99, 1, "under one bar"), (1, 2, "one to two bars"), (2, 99, "two bars or more")):
        row(lab, f[(f.gap >= lo) & (f.gap < hi)])
    print("\n  BOTH: FAST AND SMALL")
    row("fast (3h or less) AND price under half a bar", f[(f.speed < 4) & (f.rise < 0.5)])
    row("fast (3h or less) AND price under one bar", f[(f.speed < 4) & (f.rise < 1)])
    row("everything else", f[~((f.speed < 4) & (f.rise < 1))])
    print("\n  (saved > 0 = the rule helps that group; page = the trade as it is now; rule = out on the roll back under 30)")
    json.dump(out, io.open(OUT, "w", encoding="utf-8"))
    for e_ in errs[:5]:
        print("  ERR " + e_)
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
