"""backburner_dollars.py -- THE BUYS IN PLAIN DOLLARS (2026-09-23, his words: "let's say it's increments of $10k ... only look
at total percentage return. So not to get confused. 30rsi buy is 10k, if it goes to 25 is 10k more, 20rsi 10k more. Try
variations or pyramid if you want with that").

No account, no slots. Every trade the page takes, with a fixed dollar amount resting at each RSI level. Add up the money
made over all trades, and the return on the money that actually went in. The cancel rule (pulled once RSI closes over
40), the stop and the exits are the page's; only which levels have an order and how many dollars sit on each change.
Only trades that exist in every version are counted, so the rows are the same trades.

Each buy's own return: every share sells at the same prices, so buy i returns
    (position price / fill i) x (1 + position return + cost) - 1 - cost.

    pythonw studies/backburner_dollars.py --procs 8 --log logs/backburner_dollars.log
Writes validation/backburner_dollars.json
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

OUT = os.path.join("validation", "backburner_dollars.json")
RUNS_ = {"30": [], "30/20": [20], "30/25": [25], "30/25/20": [25, 20]}      # which orders rest
# version: (which run, dollars at each filled level in order 30, 25, 20)
WAYS = {"30 only: $10k": ("30", {30: 10}),
        "NOW 30 + 20: $10k + $10k": ("30/20", {30: 10, 20: 10}),
        "30 + 25: $10k + $10k": ("30/25", {30: 10, 25: 10}),
        "30 + 25 + 20: $10k each": ("30/25/20", {30: 10, 25: 10, 20: 10}),
        "pyramid 30 + 25 + 20: $10k / $20k / $30k": ("30/25/20", {30: 10, 25: 20, 20: 30}),
        "pyramid 30 + 20: $10k / $20k": ("30/20", {30: 10, 20: 20}),
        "top-heavy 30 + 25 + 20: $30k / $20k / $10k": ("30/25/20", {30: 30, 25: 20, 20: 10})}


def _work(args):
    sym, kind = args
    out = []
    try:
        tag = zlib.crc32(("%s|%s" % (kind, sym)).encode()) * 1000000
        cost = PB.COST.get(kind, 0.05)
        runs = {}
        for rn, bids in RUNS_.items():
            runs[rn] = {r["k"]: r for r in PB.trades_for(sym, kind, dict(PB.STOP, bids=bids))}
        common = set.intersection(*[set(v) for v in runs.values()])
        for k in common:
            yr = float(pd.Timestamp(runs["30"][k]["t"]).year)
            for w, (rn, dollars) in WAYS.items():
                r = runs[rn][k]
                E = r["entry"]
                c = cost * (1.5 if r["half_at"] is not None else 1.0)
                gross = 1 + (r["pct"] + c) / 100
                levels = [30] + sorted(RUNS_[rn], reverse=True)          # the order fills happen in
                inv = made = 0.0
                for lv, fx in zip(levels, r["fills"]):
                    d = dollars.get(lv, 0.0)
                    inv += d
                    made += d * (E / fx * gross - 1 - c / 100)
                out.append((w, float(tag + k), 0.0 if kind in ("stock", "etf") else 1.0, yr, inv, made))
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
    names = R._by_size([(s_, k_) for s_, k_ in S.universe()
                        if k_ in ("stock", "etf", "crypto") and s_ not in PB.T.SUSPECT])
    R.quiet_workers()
    rows = []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for o in ex.map(_work, names, chunksize=2):
            rows += o
    f = pd.DataFrame(rows, columns=["way", "id", "crypto", "yr", "inv", "made"])     # dollars in thousands
    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names),
                         trades=int(f.id.nunique())), table={})
    for cut, sel in (("every market", f.crypto >= 0), ("stocks + ETFs", f.crypto == 0), ("crypto", f.crypto == 1)):
        g0 = f[sel]
        print("\n  %s: %d trades, each buy a fixed dollar amount  (%.0fs)\n" % (cut, g0.id.nunique(), time.time() - t0))
        print("    %-44s %11s %11s %9s %9s %11s %6s" % ("the buys", "money in", "money made", "return",
                                                       "per trade", "worst trade", "yrs up"))
        for w in WAYS:
            g = g0[g0.way == w]
            yrs = g.groupby("yr").made.sum()
            d = dict(invested=float(g.inv.sum() * 1000), made=float(g.made.sum() * 1000),
                     ret=float(100 * g.made.sum() / g.inv.sum()), per_trade=float(g.made.mean() * 1000),
                     worst=float(g.made.min() * 1000), years_up=int((yrs > 0).sum()), years=int(len(yrs)))
            out["table"]["%s | %s" % (cut, w)] = d
            print("    %-44s %10s %11s %+8.2f%% %9s %11s %2d/%-2d" % (
                w, "${:,.0f}".format(d["invested"]), "${:+,.0f}".format(d["made"]), d["ret"],
                "${:+,.0f}".format(d["per_trade"]), "${:+,.0f}".format(d["worst"]), d["years_up"], d["years"]))
    print("\n  money in = every dollar that went into a buy, summed over all trades; return = money made / money in")
    json.dump(out, io.open(OUT, "w", encoding="utf-8"))
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
