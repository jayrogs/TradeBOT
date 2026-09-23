"""backburner_run.py -- HOW BIG the run has to be, one variable, on the same backburner trades (2026-09-22).

He marked ten runs on /messymark (five that zig-zagged a little, five a lot). The zig-zag measure DIED: his three
keeps scored 1.9, 2.0 and 6.6, right across the range. But both of his written notes say the same thing and it is
not about candles at all -- COF "not really a good runup", XLK "this wasn't a good runup". He was judging the SIZE
of the run.

On those ten, run size splits his marks perfectly: his three keeps are 5.6, 6.8 and 6.9 normal bars, and the
biggest of the seven he threw out is 5.4. A perfect split on ten points is exactly how #43 and #44 fooled me, so
this is NOT a rule yet -- it is the one thing worth testing next, and this is that test.

The pool already requires run >= 4 (20 daily bars, in daily normal bars). This asks what each extra step is worth.

    pythonw studies/backburner_run.py --procs 8 --log logs/backburner_run.log
Writes validation/backburner_run.json
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

OUT = os.path.join("validation", "backburner_run.json")
WAYS = ["the run was 4 to 5 normal bars (the smallest the pool allows)",
        "5 to 6",
        "6 to 7",
        "7 to 9",
        "9 and up",
        "HIS TEN SAID 5.6+: everything from 5.6 up",
        "6 and up",
        "everything (what the page does now, 4+)"]
CUTS = [lambda x: (x >= 4) & (x < 5), lambda x: (x >= 5) & (x < 6), lambda x: (x >= 6) & (x < 7),
        lambda x: (x >= 7) & (x < 9), lambda x: x >= 9,
        lambda x: x >= 5.6, lambda x: x >= 6, lambda x: x == x]


def _work(args):
    sym, kind = args
    rows = []
    try:
        got = PB.trades_for(sym, kind)
        for w_i, sel in enumerate(CUTS):
            for r in got:
                if r.get("run") is None or not bool(sel(np.array([r["run"]]))[0]):
                    continue
                rows.append([w_i, r["pct"], r["risk_pct"], 1.0 if r["half_at"] is not None else 0.0,
                             1.0 if (r["half_at"] is None and "stop" in r["how"]) else 0.0,
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
                     columns=["way", "pct", "risk", "half", "early", "yr", "crypto", "bars"])

    def st(g):
        if len(g) < 40:
            return None
        v = g.pct.values
        blocks = [v[i:i + 20].sum() for i in range(0, len(v) - 19, 20)]
        yrs = g.groupby("yr").pct.mean()
        return dict(n=int(len(g)), avg=float(v.mean()), middle=float(np.median(v)), won=float((v > 0).mean()),
                    avg_R=float((g.pct / g.risk).mean()), worst=float(v.min()), p5=float(np.percentile(v, 5)),
                    early=float(g.early.mean()), half=float(g.half.mean()), bars=float(g.bars.median()),
                    years_up=int((yrs > 0).sum()), years=int(len(yrs)),
                    blocks_up=int(sum(1 for b in blocks if b > 0)), blocks=int(len(blocks)))

    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names),
                         seconds=int(time.time() - t0), ways=WAYS), table={})
    print("\n  HOW BIG DOES THE RUN HAVE TO BE   %d names  (%.0fs)\n" % (len(names), time.time() - t0))
    for cut, sel in (("everything", lambda g: g.pct == g.pct), ("stocks + ETFs", lambda g: g.crypto == 0),
                     ("crypto", lambda g: g.crypto == 1)):
        print("  " + cut)
        print("    %-56s %6s %7s %7s %4s %6s %7s %6s %5s %6s %7s" % (
            "the run", "n", "avg", "middle", "won", "R", "worst", "5%", "half", "yrs", "blocks"))
        for w_i, w in enumerate(WAYS):
            g = f[(f.way == w_i)]
            g = g[sel(g)].sort_values("yr", kind="stable")
            s = st(g)
            if not s:
                continue
            out["table"]["%s | %s" % (cut, w)] = s
            print("    %-56s %6d %+6.2f%% %+6.2f%% %3.0f%% %+5.2f %+6.1f%% %+5.1f%% %4.0f%% %2d/%-2d %3d/%-3d" % (
                w[:56], s["n"], s["avg"], s["middle"], 100 * s["won"], s["avg_R"], s["worst"], s["p5"],
                100 * s["half"], s["years_up"], s["years"], s["blocks_up"], s["blocks"]))
        print()
    json.dump(out, io.open(OUT, "w", encoding="utf-8"))
    for e_ in errs[:5]:
        print("  ERR " + e_)
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
