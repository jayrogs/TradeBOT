"""backfill_databento.py -- CME futures minute bars from Databento, for the
studies. The one data source here that costs money, so it QUOTES first.

    python backfill_databento.py --quote              # exact USD cost of the full pull, no download
    python backfill_databento.py --pull               # download (owner has approved the quote)
    python backfill_databento.py --pull --roots ES NQ  # a subset

Key: livelog/databento.json  {"key": "db-..."}  (owner-written, never printed)
Dataset GLBX.MDP3 (CME, CBOT, NYMEX, COMEX), schema ohlcv-1m, continuous
active-contract symbols ("ES.v.0", highest volume). ICE products (KC SB CC CT OJ BZ) live in a
different dataset and are skipped here. Minute bars are cached per root in
cache/databento/<ROOT>.parquet, converted to New York time (matches the
Yahoo files), and written as history/futures/<YAHOO>_{5m,15m,1h}.csv.gz --
Yahoo's 10-year daily file stays the daily source.
"""

import argparse
import json
import os
import sys
import time

import pandas as pd

KEYS = os.path.join("livelog", "databento.json")
DATASET = "GLBX.MDP3"
SCHEMA = "ohlcv-1m"
YEARS = 4
# Yahoo symbol -> CME root. Same letters for all of these.
# micros/minis (MES MNQ M2K MYM QM QG MGC SIL) are the same charts as the
# full-size contracts and are not pulled
CME = ["ES", "NQ", "YM", "RTY", "NKD", "ZB", "ZN", "ZF", "ZT", "UB",
       "6E", "6J", "6B", "6A", "6C", "6S", "6N", "6M", "6L", "BTC", "ETH",
       "SI", "CL", "NG", "RB", "HO", "GC", "HG", "PL", "PA", "ALI",
       "ZC", "ZS", "ZW", "ZM", "ZL", "ZO", "ZR", "KE", "LE", "GF", "HE", "DC"]
MAJORS = ["ES", "NQ", "YM", "RTY", "ZB", "ZN", "GC", "SI", "CL", "NG", "HG",
          "6E", "6J", "6B", "6A", "BTC", "ETH", "ZC", "ZS", "ZW"]
ICE_SKIPPED = ["BZ", "KC", "SB", "CC", "CT", "OJ"]


def key():
    try:
        k = str(json.load(open(KEYS)).get("key") or "").strip()
        return k if k.startswith("db-") else None
    except Exception:
        return None


def client():
    import databento as db
    k = key()
    if not k:
        sys.exit("  no Databento key in livelog/databento.json")
    return db.Historical(k)


def window(years=YEARS):
    end = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize() - pd.Timedelta(days=1)
    return end - pd.Timedelta(days=365 * years), end


def quote(roots, years=YEARS):
    c = client()
    start, end = window(years)
    total, rows = 0.0, []
    for r in roots:
        try:
            cost = c.metadata.get_cost(dataset=DATASET, symbols=["%s.v.0" % r],
                                       stype_in="continuous", schema=SCHEMA,
                                       start=start.strftime("%Y-%m-%d"),
                                       end=end.strftime("%Y-%m-%d"))
        except Exception as ex:
            rows.append((r, None, str(ex)[:80]))
            continue
        total += float(cost)
        rows.append((r, float(cost), ""))
    for r, cost, err in rows:
        print("  %-4s %s" % (r, ("$%.2f" % cost) if cost is not None else "ERROR " + err))
    print("  TOTAL for %d roots, %d years of minute bars: $%.2f" % (
        len([x for x in rows if x[1] is not None]), years, total))
    return total


def pull(roots, years=YEARS):
    c = client()
    start, end = window(years)
    os.makedirs(os.path.join("cache", "databento"), exist_ok=True)
    os.makedirs(os.path.join("history", "futures"), exist_ok=True)
    for r in roots:
        store = os.path.join("cache", "databento", "%s.parquet" % r)
        t0 = time.time()
        if os.path.exists(store):
            m = pd.read_parquet(store)
        else:
            try:
                data = c.timeseries.get_range(dataset=DATASET, symbols=["%s.v.0" % r],
                                              stype_in="continuous", schema=SCHEMA,
                                              start=start.strftime("%Y-%m-%d"),
                                              end=end.strftime("%Y-%m-%d"))
                m = data.to_df()
            except Exception as ex:
                print("  %-4s FAILED: %s" % (r, str(ex)[:120]), flush=True)
                continue
            if m is None or m.empty:
                print("  %-4s no data" % r, flush=True)
                continue
            m = m[["open", "high", "low", "close", "volume"]].astype(float)
            m.index = pd.to_datetime(m.index, utc=True).tz_convert("America/New_York").tz_localize(None)
            m = m[~m.index.duplicated()].sort_index()
            m.to_parquet(store)
        m.columns = ["Open", "High", "Low", "Close", "Volume"]
        yname = "%s_F" % r
        for tf, rule in (("5m", "5min"), ("15m", "15min"), ("1h", "1h")):
            o = m.resample(rule).agg({"Open": "first", "High": "max", "Low": "min",
                                      "Close": "last", "Volume": "sum"}).dropna()
            o.to_csv(os.path.join("history", "futures", "%s_%s.csv.gz" % (yname, tf)),
                     compression="gzip")
        print("  %-4s %8d minute bars  %s -> %s  (%.0fs)" % (
            r, len(m), m.index[0].date(), m.index[-1].date(), time.time() - t0), flush=True)
    print("  done", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quote", action="store_true")
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--roots", nargs="*")
    ap.add_argument("--majors", action="store_true", help="the 20 most-watched roots only")
    ap.add_argument("--years", type=float, default=YEARS)
    a = ap.parse_args()
    roots = a.roots or (MAJORS if a.majors else CME)
    if a.quote:
        quote(roots, a.years)
    elif a.pull:
        pull(roots, a.years)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
