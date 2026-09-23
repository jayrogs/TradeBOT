"""backburner_split.py -- HOW MUCH GOES IN AT 30 AND HOW MUCH WAITS FOR 20 (2026-09-23, his words: "at 30 and 20 it would be
50/50 ... unless you can find out if a pyramid style works better").

ONE change: the split of the slot's money between the RSI-30 buy and the RSI-20 buy. The buy levels, when the 20 order
is pulled, the stop and the exits are the page's own. Same trades on every row.

THE CASH, done properly this time (backburner_bidwallet locked the unfilled buy's money for the WHOLE trade): the money
for the 20 buy is held back only until that order fills or is pulled -- at most 12 hours (the page pulls it sooner when
RSI closes over 40; here it is held the full 12, which is the cautious side). If it never fills, the money goes back.

Each buy's own return: every share sells at the same prices, so buy i returns (position price / fill i) x (1 + position
return + cost) - 1 - cost. Stocks + ETFs, cash account, equal slots, 60 runs, a year and the worst dip (at closes).

    pythonw studies/backburner_split.py --procs 8 --log logs/backburner_split.log
Writes validation/backburner_split.json
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
import backburner_dan as D        # noqa: E402

OUT = os.path.join("validation", "backburner_split.json")
SPLITS = {"all in at 30": 1.0, "heavier first: 67 / 33": 2 / 3, "NOW: 50 / 50": 0.5,
          "pyramid: 33 / 67": 1 / 3, "steeper pyramid: 25 / 75": 0.25}
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
        cost = PB.COST.get(kind, 0.05)
        for r in PB.trades_for(sym, kind):
            E = r["entry"]
            c = cost * (1.5 if r["half_at"] is not None else 1.0)
            gross = 1 + (r["pct"] + c) / 100                   # sale value per unit of position cost, before cost
            legs = [E / fx * gross - 1 - c / 100 for fx in r["fills"]]
            end = min(r["end"], len(idx) - 1)
            win = min(r["k"] + D.SECOND_BID_BARS, end, len(idx) - 1)
            out.append((int(idx[r["k"]]), int(idx[end]), int(idx[win]), legs[0], legs[1] if len(legs) > 1 else None))
    except Exception:
        pass
    return out


def wallet(tr, slots, w1, rng):
    """tr rows: (t_in, t_out, t_win, r1, r2 or nan). Equal share of free cash per free slot. The 30 buy takes w1 of it
    for the whole trade; the rest waits for the 20 buy until t_win: filled -> held to t_out at r2; not -> released."""
    eq, peak, dip = 1.0, 1.0, 0.0
    open_ = []          # (release_t, dollars, return, holds_slot)
    key = tr[:, 0] + rng.random(len(tr)) * 1e9
    for i in np.argsort(key, kind="stable"):
        t0, t1, tw, r1, r2 = tr[i]
        still = []
        for rel, dol, ret, hs in sorted(open_):
            if rel <= t0:
                eq += dol * ret
                peak = max(peak, eq); dip = min(dip, eq / peak - 1)
            else:
                still.append((rel, dol, ret, hs))
        open_ = still
        busy = sum(1 for x in open_ if x[3])
        if busy >= slots:
            continue
        free = eq - sum(x[1] for x in open_)
        dollars = free / (slots - busy)
        if dollars <= 0:
            continue
        open_.append((t1, dollars * w1, r1, True))
        if w1 < 1:
            if np.isfinite(r2):
                open_.append((t1, dollars * (1 - w1), r2, False))
            else:
                open_.append((tw, dollars * (1 - w1), 0.0, False))
    for rel, dol, ret, hs in open_:
        eq += dol * ret
    return eq, dip


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
    tr = np.array([(a, b, c, d, np.nan if e is None else e) for a, b, c, d, e in rows], dtype=float)
    tr = tr[np.argsort(tr[:, 0], kind="stable")]
    years = (tr[:, 0].max() - tr[:, 0].min()) / (365.25 * 86400 * 1e9)
    filled = np.isfinite(tr[:, 4])
    out = dict(meta=dict(generated=time.strftime("%Y-%m-%d %H:%M"), names=len(names), years=float(years), runs=RUNS,
                         trades=int(len(tr)), second_filled=float(filled.mean())), table={})
    print("\n  HOW MUCH AT 30, HOW MUCH WAITS FOR 20: stocks + ETFs, %d trades, %.1f years, the 20 buy fills on %.0f%%"
          "  (%.0fs)\n" % (len(tr), years, 100 * filled.mean(), time.time() - t0))
    print("    %-28s %10s %10s | %5s %8s %13s %7s" % ("the split", "per trade", "5% worst", "slots", "a year",
                                                    "10%-90%", "dip*"))
    for w, w1 in SPLITS.items():
        per = w1 * tr[:, 3] + (1 - w1) * np.where(filled, tr[:, 4], 0.0)      # per slot of money, unfilled = cash
        for n_ in SLOTS:
            res = [wallet(tr, n_, w1, np.random.default_rng(s_)) for s_ in range(RUNS)]
            ann = np.array([r[0] ** (1 / years) - 1 for r in res]); dips = np.array([r[1] for r in res])
            d = dict(a_year=float(np.median(ann)), p10=float(np.percentile(ann, 10)), p90=float(np.percentile(ann, 90)),
                     dip=float(np.median(dips)), per_trade=float(100 * per.mean()),
                     p5=float(100 * np.percentile(per, 5)))
            out["table"]["%s | %d" % (w, n_)] = d
            print("    %-28s %+9.2f%% %+9.1f%% | %5d %+7.1f%% %+5.1f/%+5.1f%% %+6.1f%%" % (
                w, d["per_trade"], d["p5"], n_, 100 * d["a_year"], 100 * d["p10"], 100 * d["p90"], 100 * d["dip"]))
        print()
    print("  per trade = return on the slot's money (an unfilled 20 buy counts as cash). * dip at closes only")
    json.dump(out, io.open(OUT, "w", encoding="utf-8"))
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
