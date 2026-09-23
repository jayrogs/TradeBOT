"""backburner_bidwallet.py -- the buy levels, one change at a time, in a SAME-CASH account (2026-09-23).

backburner_bids found "30 + 25 + 20, pulled when RSI closes over 31" makes the most a trade -- but that row changed TWO
things (the 25 buy AND pulling at 31 instead of 40), and on its own pulling at 31 was slightly worse. And per dollar it
was a wash: it made more by putting more money in. So:
  1. every combination, so each change is seen alone;
  2. a CASH account where every version gets the SAME money per slot. A slot is split into as many equal buys as the
     version allows; buys that never fill stay in cash. Slot return = trade return x buys filled / buys allowed.
Stocks + ETFs, 60 runs, same wallet as backburner_slots.

    pythonw studies/backburner_bidwallet.py --procs 8 --log logs/backburner_bidwallet.log
Writes validation/backburner_bidwallet.json
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

OUT = os.path.join("validation", "backburner_bidwallet.json")
WAYS = {"NOW: 30 + 20, pulled over 40": dict(bids=[20], cancel_second=40),
        "30 + 20, pulled over 31 (only the cancel changes)": dict(bids=[20], cancel_second=31),
        "30 + 25 + 20, pulled over 40 (only the 25 added)": dict(bids=[25, 20], cancel_second=40),
        "30 + 25 + 20, pulled over 31 (both)": dict(bids=[25, 20], cancel_second=31),
        "30 only": dict(bids=[], cancel_second=40)}
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
        for w, v in WAYS.items():
            mx = 1 + len(v["bids"])
            for r in PB.trades_for(sym, kind, dict(PB.STOP, **v)):
                out.append((w, int(idx[r["k"]]), int(idx[min(r["end"], len(idx) - 1)]), float(r["pct"]),
                            float(len(r["fills"])), float(mx)))
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
    f = pd.DataFrame(rows, columns=["way", "t_in", "t_out", "pct", "fills", "mx"])
    f["slot_pct"] = f.pct * f.fills / f.mx
    years = (f.t_in.max() - f.t_in.min()) / (365.25 * 86400 * 1e9)
    out = dict(meta=dict(generated=time.strftime("%Y-%m-%d %H:%M"), names=len(names), years=float(years), runs=RUNS),
               table={})
    print("\n  THE BUY LEVELS, SAME CASH: stocks + ETFs, %d names, %.1f years, %d runs  (%.0fs)\n" % (
        len(names), years, RUNS, time.time() - t0))
    print("    %-50s %6s %9s %9s | %5s %8s %13s %7s" % ("the buys", "n", "per trade", "per slot", "slots", "a year",
                                                     "10%-90%", "dip*"))
    for w in WAYS:
        g = f[f.way == w].sort_values("t_in")
        tr = g[["t_in", "t_out", "slot_pct"]].values.astype(float)
        for n_ in SLOTS:
            res = [wallet(tr, n_, np.random.default_rng(s_)) for s_ in range(RUNS)]
            ann = np.array([r[0] ** (1 / years) - 1 for r in res]); dips = np.array([r[1] for r in res])
            d = dict(a_year=float(np.median(ann)), p10=float(np.percentile(ann, 10)), p90=float(np.percentile(ann, 90)),
                     dip=float(np.median(dips)), per_trade=float(g.pct.mean()), per_slot=float(g.slot_pct.mean()),
                     n=int(len(g)))
            out["table"]["%s | %d" % (w, n_)] = d
            print("    %-50s %6d %+8.2f%% %+8.2f%% | %5d %+7.1f%% %+5.1f/%+5.1f%% %+6.1f%%" % (
                w[:50], d["n"], d["per_trade"], d["per_slot"], n_, 100 * d["a_year"], 100 * d["p10"], 100 * d["p90"],
                100 * d["dip"]))
        print()
    print("  per slot = trade return x buys filled / buys allowed (unfilled buys stay cash). * dip at closes only")
    json.dump(out, io.open(OUT, "w", encoding="utf-8"))
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
