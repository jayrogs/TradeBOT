"""backburner_runwallet.py -- only the BIGGEST runs, or all of them? Let the ACCOUNT decide (2026-09-22).

Per trade, runs of 20%+ make about double the pool (backburner_run_pct: +1.70% vs +0.84%), but they are only a third
of the trades. #29, his words: "the number of trades is everything". So the same cash account as backburner_slots
(every signal in time order, equal share per slot, nothing borrowed, 60 runs), stocks + ETFs, the page's own trade,
and only the run-size cut changes: 6%+ (the page, his line), 10%+, 20%+.

    pythonw studies/backburner_runwallet.py --procs 8 --log logs/backburner_runwallet.log
Writes validation/backburner_runwallet.json
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
from backburner_slots import wallet  # noqa: E402

OUT = os.path.join("validation", "backburner_runwallet.json")
WAYS = {"every run of 6%+ (the page, his line)": 6.0, "runs of 10%+": 10.0, "runs of 20%+": 20.0}
SLOTS = [5, 10, 20]
RUNS = 60


def _work(args):
    sym, kind = args
    out = []
    try:
        frames = S.frames_for(sym, kind)
        df = frames.get("1h")
        if df is None:
            return out
        if kind in ("stock", "etf"):
            import eq_freeride2 as FR2
            df = FR2.regular_hours({"1h": df})["1h"]
        idx = df.index.values.astype("datetime64[ns]").astype("int64")
        for r in PB.trades_for(sym, kind):
            if r.get("run_pct") is None:
                continue
            out.append((float(r["run_pct"]), int(idx[r["k"]]), int(idx[min(r["end"], len(idx) - 1)]), float(r["pct"])))
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
    names = R._by_size([(s_, k_) for s_, k_ in S.universe() if k_ in ("stock", "etf") and s_ not in PB.T.SUSPECT])
    R.quiet_workers()
    rows = []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for o in ex.map(_work, names, chunksize=2):
            rows += o
    f = pd.DataFrame(rows, columns=["run_pct", "t_in", "t_out", "pct"])
    years = (f.t_in.max() - f.t_in.min()) / (365.25 * 86400 * 1e9)
    out = dict(meta=dict(generated=time.strftime("%Y-%m-%d %H:%M"), names=len(names), years=float(years), runs=RUNS,
                         note="stocks and ETFs only; cash account; dip marked at trade closes only"), table={})
    print("\n  BIGGEST RUNS ONLY, OR ALL OF THEM: stocks + ETFs, %d names, %.1f years, cash, %d runs  (%.0fs)\n" % (
        len(names), years, RUNS, time.time() - t0))
    print("    %-40s %5s %8s %13s %9s %7s %7s" % ("the runs taken", "slots", "a year", "10%-90%", "trades/yr", "avg", "dip*"))
    for w, cut in WAYS.items():
        g = f[f.run_pct >= cut].sort_values("t_in")
        tr = g[["t_in", "t_out", "pct"]].values.astype(float)
        for n_ in SLOTS:
            res = [wallet(tr, n_, np.random.default_rng(s_)) for s_ in range(RUNS)]
            ann = np.array([r[0] ** (1 / years) - 1 for r in res]); dips = np.array([r[1] for r in res])
            tk = np.array([r[2] for r in res])
            d = dict(a_year=float(np.median(ann)), p10=float(np.percentile(ann, 10)), p90=float(np.percentile(ann, 90)),
                     trades_a_year=float(tk.mean() / years), avg_trade=float(g.pct.mean()),
                     dip=float(np.median(dips)), n_signals=int(len(tr)))
            out["table"]["%s | %d" % (w, n_)] = d
            print("    %-40s %5d %+7.1f%% %+5.1f/%+5.1f%% %8.0f %+6.2f%% %+6.1f%%" % (
                w, n_, 100 * d["a_year"], 100 * d["p10"], 100 * d["p90"], d["trades_a_year"], d["avg_trade"],
                100 * d["dip"]))
        print()
    print("  * dip marked at trade closes only (a daily mark is deeper, #37)")
    json.dump(out, io.open(OUT, "w", encoding="utf-8"))
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
