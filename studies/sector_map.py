"""sector_map.py -- give every name its sector leader, so relative strength is measured against the right thing
(2026-09-12, his words: "The bench arm is obvious dude, whatever is the sector leader or etf of the sector. Like we
compare to BTC for all crypto to see if it's performing better or worse").

No sector list is shipped with the data, so each name is assigned the leader whose DAILY returns it moves with
most, measured on the FIRST HALF of its history only (the second half is what studies trade, so the map cannot
peek). Crypto is measured against BTC, futures against the closest of the index / metal / energy leaders.

    python studies/sector_map.py --procs 20
Writes validation/sector_map.json  ->  {"stock|NVDA": ["etf|XLK", 0.71], ...}
THE LEADER CARRIES ITS MARKET. Ticker BTC is a crypto AND an ETF (a bitcoin trust) in this data, so a
symbol on its own is not enough to find the right file (2026-09-12: looking it up by symbol handed every
crypto name a 527-bar $35 ETF to be measured against, and the flag came out 0 for all of them).
"""
import concurrent.futures as cf
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as B      # noqa: E402
import trend_ride as R            # noqa: E402

OUT = os.path.join("validation", "sector_map.json")
# the eleven S&P sectors, plus the two industry ones the desk trades a lot of
LEADERS = {"stock": [("XLK", "etf"), ("XLE", "etf"), ("XLF", "etf"), ("XLV", "etf"), ("XLI", "etf"),
                     ("XLY", "etf"), ("XLP", "etf"), ("XLU", "etf"), ("XLB", "etf"), ("XLRE", "etf"),
                     ("XLC", "etf"), ("XBI", "etf"), ("KRE", "etf")],
           "etf": [("SPY", "etf"), ("IWM", "etf")],
           "crypto": [("BTC", "crypto")],
           "futures": [("ES_F", "futures"), ("GC_F", "futures"), ("CL_F", "futures")]}


def daily_returns(sym, kind):
    d = B.frames_for(sym, kind).get("1d")
    if d is None or len(d) < 200:
        return None
    s = pd.Series(d["Close"].values.astype(float), index=d.index).pct_change()
    return s[np.isfinite(s.values)]


def _work(args):
    sym, kind, leaders = args
    try:
        me = daily_returns(sym, kind)
    except Exception as ex:
        return None, "%s %s: %s" % (kind, sym, ex)
    if me is None:
        return None, None
    half = me.index[len(me) // 2]
    me = me[me.index <= half]                       # first half only
    best, best_r = None, -2.0
    for name, ser in leaders.items():
        if name == "%s|%s" % (kind, sym):
            continue
        both = pd.concat([me, ser], axis=1, join="inner").dropna()
        if len(both) < 120:
            continue
        r = float(np.corrcoef(both.iloc[:, 0].values, both.iloc[:, 1].values)[0, 1])
        if np.isfinite(r) and r > best_r:
            best, best_r = name, r
    if best is None:
        return None, None
    return ("%s|%s" % (kind, sym), (best, round(best_r, 3))), None


def main():
    procs = 20
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
    t0 = time.time()
    names = [(s_, k_) for s_, k_ in B.universe() if k_ != "forex"]
    leaders = {}
    for kd, lst in LEADERS.items():
        for ls, lk in lst:
            key = "%s|%s" % (lk, ls)
            if key in leaders:
                continue
            try:
                ser = daily_returns(ls, lk)
                if ser is not None:
                    leaders[key] = ser
            except Exception:
                pass
    print("  leaders loaded: %s" % ", ".join(sorted(k.split("|")[1] for k in leaders)))
    R.quiet_workers()
    jobs = []
    for s_, k_ in names:
        pool = {("%s|%s" % (lk, ls)): leaders["%s|%s" % (lk, ls)]
                for ls, lk in LEADERS.get(k_, []) if "%s|%s" % (lk, ls) in leaders}
        if pool:
            jobs.append((s_, k_, pool))
    out, errs = {}, []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got, err in ex.map(_work, jobs, chunksize=4):
            if err:
                errs.append(err)
            if got:
                out[got[0]] = got[1]
    json.dump(out, open(OUT, "w"), indent=1)
    counts = {}
    for k, (lead, r) in out.items():
        counts[lead] = counts.get(lead, 0) + 1
    print("  %d names mapped (%.0fs)" % (len(out), time.time() - t0))
    for lead, c in sorted(counts.items(), key=lambda x: -x[1]):
        print("    %-14s %4d names" % (lead, c))
    for e in errs[:5]:
        print("  " + e)


if __name__ == "__main__":
    main()
