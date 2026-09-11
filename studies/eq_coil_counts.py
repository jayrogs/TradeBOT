"""eq_coil_counts.py -- how many EQs there are to trade, per chart size.

Not a result, just supply: how often the shape happens, how long it takes to build, and how
many bars are left once the last pivot confirms and you could actually know it was there.

    pythonw studies/eq_coil_counts.py --procs 20 --log logs/eq_coil_counts.log
    --all   the whole universe instead of the focus list

Writes validation/eq_coil_counts.json, which /eqcoils reads.
"""
import collections
import concurrent.futures as cf
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as B      # noqa: E402
from eq_coil import coils         # noqa: E402

TFS = ["5m", "15m", "1h", "4h", "1d", "1w"]


def one(args):
    sym, kind = args
    out = {}
    try:
        fr = B.frames_for(sym, kind)
    except Exception:
        return out
    for tf in TFS:
        df = fr.get(tf)
        if df is None or len(df) < 300:
            continue
        try:
            _, _, _, rs, _ = coils(df)
        except Exception:
            continue
        live = [r for r in rs if r["tradeable"]]
        yrs = max((df.index[-1] - df.index[0]).days / 365.25, 0.1)
        out[tf] = (len(rs), len(live), yrs, [r["live_bars"] for r in live], [r["bars"] for r in live])
    return out


def main():
    procs, log = max(1, os.cpu_count() or 4), None
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            log = sys.argv[i + 1]
            sys.stdout = sys.stderr = open(log, "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    if "--all" in sys.argv:
        names = [(s_, k_) for s_, k_ in B.universe() if k_ != "forex"]
    else:
        import focus
        names = [(s_, k_) for s_, k_ in focus.names() if focus.have(s_, k_)]
    agg = collections.defaultdict(lambda: [0, 0, 0.0, [], []])
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for res in ex.map(one, names, chunksize=1):
            for tf, (n, l, y, lb, sb) in res.items():
                a = agg[tf]
                a[0] += n; a[1] += l; a[2] += y; a[3] += lb; a[4] += sb
    out = {}
    for tf in TFS:
        if tf not in agg:
            continue
        n, l, y, lb, sb = agg[tf]
        lb = sorted(lb); sb = sorted(sb)
        out[tf] = dict(found=n, tradeable=l, per_name_year=round(l / max(y, 0.1), 2),
                       shape_bars=int(sb[len(sb) // 2]) if sb else 0,
                       live_bars=int(lb[len(lb) // 2]) if lb else 0)
    out["meta"] = dict(names=len(names), seconds=int(time.time() - t0),
                       generated=time.strftime("%Y-%m-%d %H:%M"))
    json.dump(out, open(os.path.join("validation", "eq_coil_counts.json"), "w"), indent=1)
    print("  EQs per chart size, %d names  (%.0fs)" % (len(names), time.time() - t0))
    print("  %-4s %9s %12s %16s %12s %11s" % ("", "found", "tradeable", "per name a year", "shape bars", "live bars"))
    for tf in TFS:
        if tf in out:
            r = out[tf]
            print("  %-4s %9d %12d %16.1f %12d %11d" % (tf, r["found"], r["tradeable"], r["per_name_year"],
                                                        r["shape_bars"], r["live_bars"]))
    if log:
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
