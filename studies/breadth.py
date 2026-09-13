"""breadth.py -- how many names are actually going up, measured across the whole universe (2026-09-12).

Murphy's point, and the reason this exists: the index is a handful of big names, but BREADTH -- how many of the
names are above their own 200-day, and how many are making new highs against new lows -- turns BEFORE the index
does at a bottom. His words that sent me here: "is there anything you can use from trading in the zone or the
other book on ways to test when something is bullish vs bearish?". Douglas has nothing on this (he argues you
do not need to know what is next). Murphy has a chapter on it.

For every day, per market, measured with nothing but the bars that had already closed:

    above200   share of the market's names trading above their own 200-day
    above50    share above their own 50-day
    hi_lo      share at a new 1-year high minus the share at a new 1-year low
    turn20     is the above200 line higher than it was 20 days ago

THE CATCH, stated up front: this universe is the names that exist TODAY. A name that went to zero in 2018 is not
in it, so breadth measured this way is kinder than what a person saw at the time. It is usable for ranking one
day against another, not as an absolute level.

    python studies/breadth.py --procs 8
Writes validation/breadth.json
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
import exit_managers as XM        # noqa: E402

OUT = os.path.join("validation", "breadth.json")
# stocks and ETFs are one market for this purpose: they rise and fall together
GROUP = {"stock": "stocks", "etf": "stocks", "crypto": "crypto", "futures": "futures"}


def _work(args):
    sym, kind = args
    try:
        d = B.frames_for(sym, kind).get("1d")
    except Exception as ex:
        return None, "%s %s: %s" % (kind, sym, ex)
    if d is None or len(d) < 260:
        return None, None
    c = d["Close"].values.astype(float)
    h = d["High"].values.astype(float)
    l = d["Low"].values.astype(float)
    e200 = XM.ema(c, 200)
    e50 = XM.ema(c, 50)
    s = pd.Series(h)
    hi252 = s.rolling(252, min_periods=252).max().values
    lo252 = pd.Series(l).rolling(252, min_periods=252).min().values
    out = pd.DataFrame({"a200": np.where(np.isfinite(e200), (c > e200).astype(float), np.nan),
                        "a50": np.where(np.isfinite(e50), (c > e50).astype(float), np.nan),
                        "nh": np.where(np.isfinite(hi252), (h >= hi252).astype(float), np.nan),
                        "nl": np.where(np.isfinite(lo252), (l <= lo252).astype(float), np.nan)},
                       index=d.index)
    return (GROUP.get(kind, kind), out), None


def main():
    procs = 8
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            sys.stdout = sys.stderr = open(sys.argv[i + 1], "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    names = [(s_, k_) for s_, k_ in B.universe() if k_ != "forex"]
    R.quiet_workers()
    bags, errs = {}, []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got, err in ex.map(_work, names, chunksize=4):
            if err:
                errs.append(err)
            if got:
                bags.setdefault(got[0], []).append(got[1])
    out = {}
    for grp, frames in bags.items():
        tot = None
        cnt = None
        for f in frames:
            v = f.reindex(columns=["a200", "a50", "nh", "nl"])
            ok = v.notna().astype(float)
            v = v.fillna(0.0)
            tot = v if tot is None else tot.add(v, fill_value=0.0)
            cnt = ok if cnt is None else cnt.add(ok, fill_value=0.0)
        share = (tot / cnt.replace(0, np.nan)).dropna(how="all")
        share = share[cnt["a200"] >= 15]              # a reading off five names is noise
        a200 = share["a200"].values
        t20 = np.full(len(a200), np.nan)
        t20[20:] = (a200[20:] > a200[:-20]).astype(float)
        out[grp] = dict(dates=[str(x.date()) for x in share.index],
                        above200=[round(float(x), 4) for x in a200],
                        above50=[round(float(x), 4) for x in share["a50"].values],
                        hi_lo=[round(float(x), 4) for x in (share["nh"] - share["nl"]).values],
                        turn20=[None if not np.isfinite(x) else int(x) for x in t20],
                        names=int(cnt["a200"].max()))
        print("  %-8s %5d days, up to %d names, above200 now %.0f%%, low %.0f%%, high %.0f%%" % (
            grp, len(a200), out[grp]["names"], 100 * a200[-1], 100 * np.nanmin(a200), 100 * np.nanmax(a200)),
            flush=True)
    json.dump(out, open(OUT, "w"))
    print("  written (%.0fs)" % (time.time() - t0))
    for e_ in errs[:5]:
        print("  " + e_)


if __name__ == "__main__":
    main()
