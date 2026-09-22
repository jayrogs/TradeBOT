"""backburner_legs.py -- what each LEG of the backburner earns (2026-09-22, his ask: "what's 'most of it' mean?!").

Every trade on /backburners split into its two pieces: the half sold at the hourly 12 EMA, and the rest (stop under
the low of the drop, walked under each higher low). Both measured on the whole position, so the two add up to the
trade's result. Trades where the bounce never reached the 12 EMA have no half; all of that trade is "the rest".

    pythonw studies/backburner_legs.py --procs 8 --log logs/backburner_legs.log
Writes validation/backburner_legs.json
"""
import concurrent.futures as cf
import io
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as S      # noqa: E402
import trend_ride as R            # noqa: E402
import pics_backburner_tcg as PB  # noqa: E402

OUT = os.path.join("validation", "backburner_legs.json")


def _work(args):
    sym, kind = args
    out = []
    try:
        for r in PB.trades_for(sym, kind):
            e = r["entry"]
            if r["half_at"] is None:
                out.append((r["pct"], 0.0, r["pct"], 0.0, 0.0 if kind in ("stock", "etf") else 1.0))
            else:
                half = 0.5 * (r["half_px"] - e) / e * 100
                out.append((r["pct"], half, r["pct"] - half, 1.0, 0.0 if kind in ("stock", "etf") else 1.0))
    except Exception:
        pass
    return out


def main():
    procs, log = 8, None
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            log = sys.argv[i + 1]
            sys.stdout = sys.stderr = io.open(log, "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    names = R._by_size([(s_, k_) for s_, k_ in S.universe() if k_ in ("stock", "etf", "crypto") and s_ not in PB.T.SUSPECT])
    R.quiet_workers()
    rows = []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for o in ex.map(_work, names, chunksize=2):
            rows += o
    a = np.asarray(rows, dtype=float)
    out = {}
    for cut, sel in (("everything", a[:, 4] >= 0), ("stocks + ETFs", a[:, 4] == 0), ("crypto", a[:, 4] == 1)):
        b = a[sel]
        tot, half, rest, took = b[:, 0], b[:, 1], b[:, 2], b[:, 3]
        d = dict(n=int(len(b)), total=float(tot.mean()),
                 half=float(half.mean()), half_share=float(half.mean() / tot.mean()) if tot.mean() else None,
                 half_won=float((half[took == 1] > 0).mean()), half_middle=float(np.median(half[took == 1])),
                 rest=float(rest.mean()), rest_share=float(rest.mean() / tot.mean()) if tot.mean() else None,
                 rest_won=float((rest > 0).mean()), rest_middle=float(np.median(rest)),
                 no_bounce=float((took == 0).mean()), no_bounce_avg=float(tot[took == 0].mean()) if (took == 0).any() else 0.0,
                 no_bounce_cost=float(tot[took == 0].sum() / len(b)))
        out[cut] = d
        print("  %s   %d trades, total %+.3f%% a trade" % (cut, d["n"], d["total"]))
        print("     the half at the 12 EMA   %+.3f%%  = %3.0f%% of the total   won %2.0f%%   middle %+.3f%%" % (
            d["half"], 100 * d["half_share"], 100 * d["half_won"], d["half_middle"]))
        print("     the rest, walked         %+.3f%%  = %3.0f%% of the total   won %2.0f%%   middle %+.3f%%" % (
            d["rest"], 100 * d["rest_share"], 100 * d["rest_won"], d["rest_middle"]))
        print("     never bounced to the EMA %2.0f%% of trades, avg %+.2f%% each, costing %+.3f%% per trade overall" % (
            100 * d["no_bounce"], d["no_bounce_avg"], d["no_bounce_cost"]))
    json.dump(dict(generated=time.strftime("%Y-%m-%d %H:%M"), table=out), io.open(OUT, "w", encoding="utf-8"))
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
