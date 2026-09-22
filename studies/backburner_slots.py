"""backburner_slots.py -- more per trade, or more trades? Let the ACCOUNT decide (2026-09-22, his ask: "why wouldn't I
want more per trade").

The first-sell targets from backburner_firstsell, run into a CASH account with N slots: every signal in time order,
a trade takes a slot from its buy to its exit, an equal share of the account per slot, nothing borrowed, skipped
when no slot is free. 60 runs with a random pick when signals collide. Reports a year, trades a year, share of
signals taken, and the worst dip (marked at trade closes only; a daily mark is the honest one, #37).

    pythonw studies/backburner_slots.py --procs 8 --log logs/backburner_slots.log
Writes validation/backburner_slots.json
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

OUT = os.path.join("validation", "backburner_slots.json")
WAYS = {"hourly 12 EMA touch": "ema12", "hourly RSI 60": "rsi60", "61.8% of the drop won back": "fib618",
        "hourly RSI 70": "rsi70", "the top of the drop": "top", "hourly 50 EMA": "ema50"}
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
        idx = df.index.values.astype("datetime64[ns]").astype("int64")     # some frames are stored in microseconds
        for w, code in WAYS.items():
            for r in PB.trades_for(sym, kind, dict(PB.STOP, first_sell=code)):
                out.append((w, int(idx[r["k"]]), int(idx[min(r["end"], len(idx) - 1)]), float(r["pct"])))
    except Exception:
        pass
    return out


def wallet(tr, slots, rng):
    """tr: array of (t_in, t_out, pct) sorted by t_in. Equal share per slot, compounding at each close."""
    eq, peak, dip = 1.0, 1.0, 0.0
    open_ = []                                   # (t_out, share of the account, pct)
    taken = 0
    order = np.arange(len(tr))
    # signals at the same time: random order
    t_in = tr[:, 0]
    key = t_in + rng.random(len(tr)) * 1e9          # up to a second of jitter: breaks ties on the same bar, never reorders bars
    order = np.argsort(key, kind="stable")
    for i in order:
        t0, t1, pct = tr[i]
        # close what has exited by now
        still = []
        for (to, dollars, p_) in sorted(open_):
            if to <= t0:
                eq += dollars * p_ / 100
                peak = max(peak, eq); dip = min(dip, eq / peak - 1)
            else:
                still.append((to, dollars, p_))
        open_ = still
        if len(open_) >= slots:
            continue
        dollars = (eq - sum(d for _t, d, _p in open_)) / (slots - len(open_))   # free cash spread over free slots
        if dollars <= 0:
            continue
        open_.append((t1, dollars, pct)); taken += 1
    for (to, dollars, p_) in open_:
        eq += dollars * p_ / 100
    return eq, dip, taken


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
    f = pd.DataFrame(rows, columns=["way", "t_in", "t_out", "pct"])
    years = (f.t_in.max() - f.t_in.min()) / (365.25 * 86400 * 1e9)
    out = dict(meta=dict(generated=time.strftime("%Y-%m-%d %H:%M"), names=len(names), years=float(years), runs=RUNS,
                         note="stocks and ETFs only; cash account; dip marked at trade closes only"), table={})
    print("\n  THE ACCOUNT DECIDES: first-sell targets, stocks + ETFs, %d names, %.1f years, cash, %d runs  (%.0fs)\n" % (
        len(names), years, RUNS, time.time() - t0))
    print("    %-30s %5s %8s %9s %9s %10s %7s %7s" % ("the half sells at", "slots", "a year", "10%-90%", "trades/yr", "of signals", "avg", "dip*"))
    for w in WAYS:
        g = f[f.way == w].sort_values("t_in")
        tr = g[["t_in", "t_out", "pct"]].values.astype(float)
        for n_ in SLOTS:
            res = [wallet(tr, n_, np.random.default_rng(s_)) for s_ in range(RUNS)]
            ann = np.array([r[0] ** (1 / years) - 1 for r in res]); dips = np.array([r[1] for r in res])
            tk = np.array([r[2] for r in res])
            d = dict(a_year=float(np.median(ann)), p10=float(np.percentile(ann, 10)), p90=float(np.percentile(ann, 90)),
                     trades_a_year=float(tk.mean() / years), share_taken=float(tk.mean() / len(tr)),
                     avg_trade=float(g.pct.mean()), dip=float(np.median(dips)), n_signals=int(len(tr)))
            out["table"]["%s | %d" % (w, n_)] = d
            print("    %-30s %5d %+7.1f%% %+4.1f/%+4.1f%% %8.0f %9.0f%% %+6.2f%% %+6.1f%%" % (
                w, n_, 100 * d["a_year"], 100 * d["p10"], 100 * d["p90"], d["trades_a_year"], 100 * d["share_taken"],
                d["avg_trade"], 100 * d["dip"]))
        print()
    print("  * dip marked at trade closes only (a daily mark is deeper, #37)")
    json.dump(out, io.open(OUT, "w", encoding="utf-8"))
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
