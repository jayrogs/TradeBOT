"""backburner_long.py -- THE PAGE'S ACCOUNT OVER THE LONGEST WINDOW THE DATA ALLOWS, and how much of each year was crypto
(2026-09-26, his words: "How much was the crypto run. I want to backtest this longer than 4 years, since it's requirements
are a large pump, it shouldn't fire much in bad times").

The 4-year window (2022-09 on) was set by the futures data. Stocks have hourly bars from 2021-09 (his Polygon plan serves
5 years), crypto from 2015-2022 depending on the coin, futures from 2022-09. Same account as backburner_curve (5 buckets,
the whole bucket at 30, later buys on top, at most 3 buckets a coin, cash, marked daily, 20 runs); a market joins the
account on the day its data starts, and each window shows SPY or BTC held over the same days.
    A. everything from 2021-10-01            (stocks + crypto; futures join 2022-09)
    B. the same without crypto               -> each year's crypto share
    C. crypto alone from 2017-01-01          (the 2018 and 2022 crypto bears; ~16 coins before 2022)

    pythonw studies/backburner_long.py --procs 8 --log logs/backburner_long.log
Writes validation/backburner_long.json
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
import backburner_sizing as SZ    # noqa: E402
import backburner_curve as CV     # noqa: E402
from backburner_account import stats  # noqa: E402

OUT = os.path.join("validation", "backburner_long.json")
RUNS = 20
EARLY = pd.Timestamp("2015-01-01")


def _work(args):
    SZ.START = EARLY                  # take every trade the data has; each window cuts its own start
    return SZ._work(args)


def run(trades, closes, start, end):
    tr = [CV.cap_coin(t, PB.ACCOUNT.get("crypto_max_buckets", 3)) for t in trades if t["t_in"] >= start]
    days = pd.date_range(start, end, freq="D")
    res = [SZ.account(tr, closes, days, s_, slots=PB.ACCOUNT["buckets"], on_top=True) for s_ in range(RUNS)]
    st = [stats(r[0], days) for r in res]
    ann = np.array([x["a_year"] for x in st]); dips = np.array([x["dip"] for x in st])
    years = pd.DataFrame([x["years"] for x in st]).median().to_dict()
    return dict(a_year=float(np.median(ann)), p10=float(np.percentile(ann, 10)), p90=float(np.percentile(ann, 90)),
                dip=float(np.median(dips)), trades=len(tr), years={int(k): float(v) for k, v in years.items()},
                end_x=float(np.median([r[0][-1] for r in res])))


def held(closes, key, start, end):
    days = pd.date_range(start, end, freq="D")
    c = closes[key].reindex(days, method="ffill").values
    c = c / c[np.isfinite(c)][0]
    st = stats(np.nan_to_num(c, nan=1.0), days)
    return dict(a_year=st["a_year"], dip=st["dip"], years=st["years"])


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
                        if (k_ in ("stock", "etf", "crypto") or (k_ == "futures" and s_ in PB.COMMODITY_FUTURES))
                        and s_ not in PB.T.SUSPECT])
    R.quiet_workers()
    trades, closes = [], {}
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for a_, _b, c_, sym, kind in ex.map(_work, names, chunksize=2):
            trades += a_
            if c_ is not None:
                closes[(kind, sym)] = c_
    end = max(t["t_out"] for t in trades).normalize()
    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), runs=RUNS), rows={})
    a0, c0 = pd.Timestamp("2021-10-01"), pd.Timestamp("2017-01-01")
    l0 = pd.Timestamp("2018-06-01")      # stocks from 2018-05 since the Databento purchase (join_xnas_history.py, #59)
    out["rows"]["L. everything from 2018-06"] = run(trades, closes, l0, end)
    out["rows"]["L. without crypto from 2018-06"] = run([t for t in trades if t["kind"] != "crypto"], closes, l0, end)
    out["rows"]["SPY held from 2018-06"] = held(closes, ("etf", "SPY"), l0, end)
    out["rows"]["A. everything from 2021-10"] = run(trades, closes, a0, end)
    out["rows"]["B. without crypto from 2021-10"] = run([t for t in trades if t["kind"] != "crypto"], closes, a0, end)
    out["rows"]["C. crypto alone from 2017-01"] = run([t for t in trades if t["kind"] == "crypto"], closes, c0, end)
    out["rows"]["SPY held from 2021-10"] = held(closes, ("etf", "SPY"), a0, end)
    out["rows"]["BTC held from 2017-01"] = held(closes, ("crypto", "BTC"), c0, end)
    # how many signals each year, by market: does it go quiet in bad years?
    df = pd.DataFrame([(t["kind"], t["t_in"].year) for t in trades], columns=["kind", "year"])
    out["signals_a_year"] = {k: {int(y): int(n) for y, n in g.groupby("year").size().items()} for k, g in df.groupby("kind")}
    print("\n  THE PAGE'S ACCOUNT, LONGEST WINDOW (%.0fs)\n" % (time.time() - t0))
    for lab, d in out["rows"].items():
        print("  %-36s a year %+6.1f%%  worst drop %+6.1f%%  %s" % (lab, 100 * d["a_year"], 100 * d["dip"],
              "  ".join("%d %+.0f%%" % (k, 100 * v) for k, v in sorted(d["years"].items()))))
    print("\n  signals a year:")
    for k, v in out["signals_a_year"].items():
        print("   %-8s %s" % (k, "  ".join("%d %d" % (y, n) for y, n in sorted(v.items()))))
    json.dump(out, io.open(OUT, "w", encoding="utf-8"), indent=1)
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
