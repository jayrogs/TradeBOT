"""fetch_more_stocks.py -- the next tier of US stocks and funds, $100M-$186M traded a day (2026-09-26, his "get whatever
else you can"). The trading universe (history/stocks/) holds every name over ~$186M a day (cache/tier1.csv); these 347
are kept APART in history/stocks_more/ so the page's list does not change without his say -- a study compares them first.
Hourly bars from his Polygon plan (5 years, all hours), the daily file copied from history/stocks/ where one exists
(back to 2016) else Polygon's 5 years of days; stock_recent.py --folder history/stocks_more keeps them current.

    python fetch_more_stocks.py
"""
import concurrent.futures as cf
import glob
import os
import shutil

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
import backfill_polygon as BP     # noqa: E402

OUT = os.path.join("history", "stocks_more")


def one(sym, k):
    p1 = os.path.join(OUT, "%s_1h.csv.gz" % sym)
    try:
        if not os.path.exists(p1):
            d = BP.pull(sym, "1h", k)
            if d is None or len(d) < 500:
                return sym, "too few hourly bars"
            d.to_csv(p1, compression="gzip")
        pd_ = os.path.join(OUT, "%s_1d.csv.gz" % sym)
        src = os.path.join("history", "stocks", "%s_1d.csv.gz" % sym)
        if not os.path.exists(pd_):
            if os.path.exists(src):
                shutil.copy2(src, pd_)
            else:
                d = BP.pull(sym, "1d", k)
                if d is None or len(d) < 120:
                    os.remove(p1)
                    return sym, "too few days"
                d.index = d.index.normalize()
                d.index.name = "Date"
                d.to_csv(pd_, compression="gzip")
        return sym, "ok"
    except Exception as ex:
        return sym, "failed: %s" % str(ex)[:80]


def main():
    os.makedirs(OUT, exist_ok=True)
    t = pd.read_csv(os.path.join("cache", "tier1.csv"))
    have = {os.path.basename(f).split("_")[0] for f in glob.glob(os.path.join("history", "stocks", "*_1h.csv.gz"))}
    want = t[(t.dollar >= 1e8) & (t.kind.isin(["equity", "etf"])) & (~t.symbol.isin(have))]
    k = BP.key()
    kinds = dict(zip(want.symbol, want.kind))
    res = {}
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for sym, how in ex.map(lambda s: one(s, k), list(want.symbol)):
            res[sym] = how
    pd.Series(kinds).rename("kind").to_csv(os.path.join(OUT, "KINDS.csv"))
    ok = sum(v == "ok" for v in res.values())
    print("%d of %d names saved in %s" % (ok, len(res), OUT))
    for s_, v in res.items():
        if v != "ok":
            print("  %s %s" % (s_, v))


if __name__ == "__main__":
    main()
