"""backburner_markets_years.py -- each market on its own, year by year, 2018-06 on (2026-09-26, his ask: "break down per
market over those years"). The page's rules. Per trade (count, average) and each market's OWN account (5 buckets,
backburner_long.run, 20 runs), plus what it held ALONE would have done: SPY for stocks and funds, BTC for crypto.

    python studies/backburner_markets_years.py --procs 16
Writes validation/backburner_markets_years.json
"""
import concurrent.futures as cf
import io
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as S      # noqa: E402
import trend_ride as R            # noqa: E402
import pics_backburner_tcg as PB  # noqa: E402
import backburner_long as BL      # noqa: E402

START = pd.Timestamp("2018-06-01")


def main():
    procs = int(sys.argv[sys.argv.index("--procs") + 1]) if "--procs" in sys.argv else 8
    names = R._by_size([(s_, k_) for s_, k_ in S.universe()
                        if (k_ in ("stock", "etf", "crypto") or (k_ == "futures" and s_ in PB.COMMODITY_FUTURES))
                        and s_ not in PB.T.SUSPECT])
    R.quiet_workers()
    trades, closes = [], {}
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for a_, _b, c_, sym, kind in ex.map(BL._work, names, chunksize=2):
            trades += a_
            if c_ is not None:
                closes[(kind, sym)] = c_
    end = max(t["t_out"] for t in trades).normalize()
    tr = [t for t in trades if t["t_in"] >= START]
    df = pd.DataFrame([(t["kind"], t["t_in"].year, t["pct"]) for t in tr], columns=["kind", "year", "pct"])
    out = dict(per_trade={}, account={})
    for k, g in df.groupby("kind"):
        out["per_trade"][k] = {int(y): dict(n=int(len(x)), avg=float(x.pct.mean()), won=float((x.pct > 0).mean()))
                               for y, x in g.groupby("year")}
    for k in ("stock", "etf", "crypto", "futures"):
        out["account"][k] = BL.run([t for t in trades if t["kind"] == k], closes, START, end)
    out["account"]["SPY held"] = BL.held(closes, ("etf", "SPY"), START, end)
    out["account"]["BTC held"] = BL.held(closes, ("crypto", "BTC"), START, end)
    json.dump(out, io.open(os.path.join("validation", "backburner_markets_years.json"), "w", encoding="utf-8"), indent=1)
    yrs = sorted(df.year.unique())
    print("\nPER TRADE (trades / average)")
    print("%-9s " % "" + " ".join("%13d" % y for y in yrs))
    for k, v in out["per_trade"].items():
        print("%-9s " % k + " ".join("%13s" % ("%d / %+.2f%%" % (v[y]["n"], v[y]["avg"]) if y in v else "-") for y in yrs))
    print("\nEACH MARKET'S OWN ACCOUNT (a year, worst drop, by year)")
    for k, d in out["account"].items():
        print("%-9s %+6.1f%% %+6.1f%%  %s" % (k, 100 * d["a_year"], 100 * d["dip"],
              " ".join("%d %+.0f%%" % (y, 100 * v) for y, v in sorted(d["years"].items()))))


if __name__ == "__main__":
    main()
