"""backburner_chop.py -- the MESSY CHART filter, one variable, on the same backburner trades (2026-09-22).

His ask: "we should make an automatic filter to not have shitty charting names, I'm not gonna manually filter every
single stock name in existence". Five of his rejects were about the candles, not the trade: BTI "oscillating all over
the place, gaps everywhere", KEY "candles all over the place, lots of gaps, long bodies and wicks", DOCN "the size of
daily candles is pretty big all the time, long wicks both directions", BHP "very messy chart", UNP "really wild daily
candles ... too hectic for a clean backburner play".

Sixteen measures failed on his 25 marks (#44). So 160 runs were drawn and labelled BY EYE against his own five
rejects, and every measure re-fitted on those. The only one that agrees with BOTH sets is CHOP: the ground the run
covered day to day over the 55 days into the dip, divided by how far it actually travelled. A march is near 2, a
fight is 5 and up. Separation: 0.81 on the 155 eye labels, 0.79 on his own 32 marks (0.50 = a coin flip). The
`clean` higher-low share already in the code, fitted on two examples, manages 0.60 and 0.62.

THE OPEN QUESTION THIS ANSWERS: a cut that catches all five of his rejects also throws out twelve of his
twenty-seven keeps. So the eye says one thing; this asks whether the MONEY agrees, on the same trades, one variable.

    pythonw studies/backburner_chop.py --procs 8 --log logs/backburner_chop.log
Writes validation/backburner_chop.json
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

OUT = os.path.join("validation", "backburner_chop.json")
WAYS = ["a march: the run covered under 3x the ground it travelled",
        "3 to 4x",
        "4 to 5x",
        "a fight: 5x and up (what he rejected)",
        "CUT AT 4.5x: everything under it",
        "CUT AT 5x: everything under it",
        "everything (what the page does now)"]
CUTS = [lambda x: x < 3, lambda x: (x >= 3) & (x < 4), lambda x: (x >= 4) & (x < 5), lambda x: x >= 5,
        lambda x: x < 4.5, lambda x: x < 5, lambda x: x == x]


def _work(args):
    sym, kind = args
    rows = []
    try:
        got = PB.trades_for(sym, kind)
        for w_i, sel in enumerate(CUTS):
            for r in got:
                if r.get("chop") is None or not bool(sel(np.array([r["chop"]]))[0]):
                    continue
                rows.append([w_i, r["pct"], r["risk_pct"], 1.0 if r["half_at"] is not None else 0.0,
                             1.0 if (r["half_at"] is None and "stop" in r["how"]) else 0.0,
                             1.0 if r["how"] == "the rest reached the old high" else 0.0,
                             float(pd.Timestamp(r["t"]).year), 0.0 if kind in ("stock", "etf") else 1.0,
                             r["end"] - r["k"]])
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
    f = pd.DataFrame(np.concatenate(parts),
                     columns=["way", "pct", "risk", "half", "early", "high", "yr", "crypto", "bars"])

    def st(g):
        if len(g) < 40:
            return None
        v = g.pct.values
        blocks = [v[i:i + 20].sum() for i in range(0, len(v) - 19, 20)]
        yrs = g.groupby("yr").pct.mean()
        streak = mx = 0
        for x in v:
            streak = streak + 1 if x <= 0 else 0
            mx = max(mx, streak)
        return dict(n=int(len(g)), avg=float(v.mean()), middle=float(np.median(v)), won=float((v > 0).mean()),
                    avg_R=float((g.pct / g.risk).mean()), worst=float(v.min()), p5=float(np.percentile(v, 5)),
                    early=float(g.early.mean()), half=float(g.half.mean()), high=float(g.high.mean()),
                    bars=float(g.bars.median()), streak=int(mx),
                    years_up=int((yrs > 0).sum()), years=int(len(yrs)),
                    blocks_up=int(sum(1 for b in blocks if b > 0)), blocks=int(len(blocks)))

    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names),
                         seconds=int(time.time() - t0), ways=WAYS), table={})
    print("\n  MESSY CANDLES: HOW MUCH GROUND THE RUN COVERED vs HOW FAR IT WENT   %d names  (%.0fs)\n"
          % (len(names), time.time() - t0))
    for cut, sel in (("everything", lambda g: g.pct == g.pct), ("stocks + ETFs", lambda g: g.crypto == 0),
                     ("crypto", lambda g: g.crypto == 1)):
        print("  " + cut)
        print("    %-58s %6s %7s %7s %4s %6s %7s %6s %5s %5s %5s %6s %7s" % (
            "the run", "n", "avg", "middle", "won", "R", "worst", "5%", "early", "half", "high", "yrs", "blocks"))
        for w_i, w in enumerate(WAYS):
            g = f[(f.way == w_i)]
            g = g[sel(g)].sort_values("yr", kind="stable")
            s = st(g)
            if not s:
                continue
            out["table"]["%s | %s" % (cut, w)] = s
            print("    %-58s %6d %+6.2f%% %+6.2f%% %3.0f%% %+5.2f %+6.1f%% %+5.1f%% %4.0f%% %4.0f%% %4.0f%% %2d/%-2d %3d/%-3d" % (
                w[:58], s["n"], s["avg"], s["middle"], 100 * s["won"], s["avg_R"], s["worst"], s["p5"],
                100 * s["early"], 100 * s["half"], 100 * s["high"], s["years_up"], s["years"],
                s["blocks_up"], s["blocks"]))
        print()
    json.dump(out, io.open(OUT, "w", encoding="utf-8"))
    f.to_parquet(os.path.splitext(OUT)[0] + "_rows.parquet")
    for e_ in errs[:5]:
        print("  ERR " + e_)
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
