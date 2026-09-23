"""databento_recent.py -- keep the CME futures hourly history current from Databento, on a strict budget (2026-09-23).

His OK: "yes u can handle 1.50 a year". The 4-year history came from his Databento credit ($119.66 of $125). Without a paid
subscription Databento serves CME bars only up to about 6 hours ago (exchange licensing), which is fine for history; the
last few hours come from Yahoo in bb_live.py.

Pulls ohlcv-1h for the continuous front contract ("CL.v.0") of the 19 CME roots in the backburner pool, from each file's
last bar up to 6.5 hours ago, and appends them to history/futures/<ROOT>_F_1h.csv.gz (New York wall time, the stamp of the
hour's start -- the convention of the files). The minute cache the history was built from is not touched.

THE BUDGET, enforced before any money is spent: the price is asked first (free); a pull over $0.05 is refused; every
dollar is logged in livelog/databento_spend.json and no pull happens once the last 365 days reach $2.00.

    python databento_recent.py            # the live page calls this about once an hour
"""
import io
import json
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
ROOTS = ["CL", "NG", "HO", "RB", "GC", "SI", "HG", "PL", "MGC", "SIL", "ZC", "ZS", "ZW", "ZL", "ZM", "KE", "LE", "GF", "HE"]
DATASET, SCHEMA = "GLBX.MDP3", "ohlcv-1h"
PER_PULL, PER_YEAR = 0.05, 2.00
SPEND = os.path.join("livelog", "databento_spend.json")


def spent_last_year():
    if not os.path.exists(SPEND):
        return 0.0, []
    log = json.load(io.open(SPEND, encoding="utf-8"))
    cut = pd.Timestamp.now() - pd.Timedelta(days=365)
    return sum(x["usd"] for x in log if pd.Timestamp(x["at"]) >= cut), log


def main(log=print):
    import databento as db
    key = json.load(open(os.path.join("livelog", "databento.json")))["key"]
    c = db.Historical(key)
    end_utc = (pd.Timestamp.now("UTC") - pd.Timedelta(hours=7)).floor("h").tz_localize(None)
    starts = {}
    for r in ROOTS:
        p = os.path.join("history", "futures", "%s_F_1h.csv.gz" % r)
        if not os.path.exists(p):
            continue
        last_ny = pd.read_csv(p, usecols=[0]).iloc[-1, 0]
        last_utc = pd.Timestamp(last_ny).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None)
        if last_utc + pd.Timedelta(hours=1) < end_utc:
            starts[r] = last_utc + pd.Timedelta(hours=1)
    if not starts:
        log("databento_recent: nothing to pull")
        return 0.0
    start = min(starts.values())
    syms = ["%s.v.0" % r for r in starts]
    kw = dict(dataset=DATASET, symbols=syms, stype_in="continuous", schema=SCHEMA,
              start=start.strftime("%Y-%m-%dT%H:%M"), end=end_utc.strftime("%Y-%m-%dT%H:%M"))
    try:
        cost = float(c.metadata.get_cost(**kw))
    except Exception as ex:
        # the unlicensed window moves; Databento says where it ends ("... an end time before 2026-09-23T13:00:29Z")
        import re
        m = re.search(r"end time before (\d{4}-\d\d-\d\dT\d\d:\d\d)", str(ex))
        if not m:
            raise
        end_utc = pd.Timestamp(m.group(1)).floor("h") - pd.Timedelta(hours=1)
        kw["end"] = end_utc.strftime("%Y-%m-%dT%H:%M")
        cost = float(c.metadata.get_cost(**kw))
    year, book = spent_last_year()
    if cost > PER_PULL or year + cost > PER_YEAR:
        log("databento_recent: REFUSED -- this pull $%.4f, last 365 days $%.4f (limits $%.2f a pull, $%.2f a year)"
            % (cost, year, PER_PULL, PER_YEAR))
        return 0.0
    data = c.timeseries.get_range(**kw).to_df()
    book.append(dict(at=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), usd=round(cost, 6), bars=int(len(data)),
                     roots=len(syms), start=kw["start"], end=kw["end"]))
    os.makedirs("livelog", exist_ok=True)
    json.dump(book, io.open(SPEND, "w", encoding="utf-8"), indent=1)
    if data.empty:
        log("databento_recent: $%.4f, no new bars" % cost)
        return cost
    sym_col = "symbol" if "symbol" in data.columns else None
    added = 0
    for r in starts:
        d = data[data[sym_col] == "%s.v.0" % r] if sym_col else data
        if d.empty:
            continue
        idx = pd.DatetimeIndex(d.index).tz_convert("America/New_York").tz_localize(None)
        new = pd.DataFrame({"Open": d["open"].astype(float).values, "High": d["high"].astype(float).values,
                            "Low": d["low"].astype(float).values, "Close": d["close"].astype(float).values,
                            "Volume": d["volume"].astype(float).values}, index=idx)
        p = os.path.join("history", "futures", "%s_F_1h.csv.gz" % r)
        old = pd.read_csv(p, index_col=0, parse_dates=True)
        new = new[new.index > old.index[-1]]
        if new.empty:
            continue
        new.index.name = old.index.name
        both = pd.concat([old, new[old.columns.intersection(new.columns)]])
        both.to_csv(p + ".tmp", compression="gzip")
        os.replace(p + ".tmp", p)
        added += len(new)
    y2, _ = spent_last_year()
    log("databento_recent: $%.4f for %d new hourly bars on %d roots, through %s UTC; last 365 days $%.4f of $%.2f"
        % (cost, added, len(starts), kw["end"], y2, PER_YEAR))
    return cost


if __name__ == "__main__":
    main()
