"""backburner_bids.py -- WHERE THE BUYS GO (2026-09-22, his words: "I think it's just rsi 30 and 20. Maybe we try 25 also,
as long as the rsi hasn't closed above 31, aka cooled down").

First buy at the RSI-30 price inside the candle, always. Only the extra buys change: which RSI levels have an equal-size
order resting (for up to 12 hours), and when they are pulled (RSI closed above 40 = the page, or above 31 = his rule).
Same first-buy bar on every row, so the rows are PAIRED trade for trade.

Two money numbers, because more buys means more money in the trade:
    avg      the return on the position (all fills averaged), per trade
    bullets  that return times how many buys filled, per trade -- the money made counted in first-buy sizes.
             This is the one to compare when one version adds more.

    pythonw studies/backburner_bids.py --procs 8 --log logs/backburner_bids.log
Writes validation/backburner_bids.json
"""
import concurrent.futures as cf
import io
import json
import os
import sys
import time
import zlib

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as S      # noqa: E402
import trend_ride as R            # noqa: E402
import pics_backburner_tcg as PB  # noqa: E402

OUT = os.path.join("validation", "backburner_bids.json")
WAYS = {"NOW: 30 and 20, pulled when RSI closes over 40": dict(bids=[20], cancel_second=40),
        "A: 30 and 20, pulled when RSI closes over 31": dict(bids=[20], cancel_second=31),
        "B: 30, 25 and 20, pulled over 31": dict(bids=[25, 20], cancel_second=31),
        "C: 30 and 25, pulled over 31": dict(bids=[25], cancel_second=31),
        "D: 30 only (one buy)": dict(bids=[], cancel_second=31)}


def _work(args):
    sym, kind = args
    rows = []
    try:
        tag = zlib.crc32(("%s|%s" % (kind, sym)).encode()) * 1000000
        for w_i, (w, v) in enumerate(WAYS.items()):
            for r in PB.trades_for(sym, kind, dict(PB.STOP, **v)):
                rows.append([w_i, float(tag + r["k"]), r["pct"], float(len(r["fills"])),
                             float(pd.Timestamp(r["t"]).year), 0.0 if kind in ("stock", "etf") else 1.0,
                             r["risk_pct"]])
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    return (np.asarray(rows, dtype=np.float64) if rows else None), []


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
    parts, errs = [], []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for part, err in ex.map(_work, names, chunksize=2):
            errs += err
            if part is not None:
                parts.append(part)
    f = pd.DataFrame(np.concatenate(parts), columns=["way", "id", "pct", "fills", "yr", "crypto", "risk"])
    f["bullets"] = f.pct * f.fills
    base = f[f.way == 0].set_index("id")

    def st(g):
        gi = g.set_index("id")
        common = gi.index.intersection(base.index)
        d_b = gi.loc[common, "bullets"] - base.loc[common, "bullets"]
        yd = d_b.groupby(gi.loc[common, "yr"]).mean()
        v = g.pct.values
        return dict(n=int(len(g)), avg=float(v.mean()), middle=float(np.median(v)), won=float((v > 0).mean()),
                    worst=float(v.min()), p5=float(np.percentile(v, 5)), fills=float(g.fills.mean()),
                    bullets=float(g.bullets.mean()), worst_bullets=float(g.bullets.min()),
                    p5_bullets=float(np.percentile(g.bullets, 5)),
                    vs_now=float(d_b.mean()), years_better=int((yd > 0).sum()), years=int(len(yd)))

    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names),
                         seconds=int(time.time() - t0), ways=list(WAYS)), table={})
    print("\n  WHERE THE BUYS GO   %d names  (%.0fs)\n" % (len(names), time.time() - t0))
    for cut, sel in (("everything", lambda g: g.pct == g.pct), ("stocks + ETFs", lambda g: g.crypto == 0),
                     ("crypto", lambda g: g.crypto == 1)):
        print("  " + cut)
        print("    %-48s %5s %7s %7s %4s %6s %6s | %8s %9s %8s %8s %6s" % (
            "the buys", "n", "avg", "middle", "won", "5%", "buys", "bullets", "worst", "5%", "vs now", "yrs"))
        for w_i, w in enumerate(WAYS):
            g = f[f.way == w_i]
            g = g[sel(g)]
            if len(g) < 40:
                continue
            s = st(g)
            out["table"]["%s | %s" % (cut, w)] = s
            print("    %-48s %5d %+6.2f%% %+6.2f%% %3.0f%% %+5.1f%% %6.2f | %+7.2f%% %+8.1f%% %+7.1f%% %+7.2f%% %2d/%-2d" % (
                w[:48], s["n"], s["avg"], s["middle"], 100 * s["won"], s["p5"], s["fills"], s["bullets"],
                s["worst_bullets"], s["p5_bullets"], s["vs_now"], s["years_better"], s["years"]))
        print()
    print("  bullets = return x buys filled: money made per trade in first-buy sizes. vs now is paired, in bullets.")
    json.dump(out, io.open(OUT, "w", encoding="utf-8"))
    for e_ in errs[:5]:
        print("  ERR " + e_)
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
