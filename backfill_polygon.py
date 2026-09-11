r"""backfill_polygon.py -- all-hours US stock bars from Polygon (owner 2026-09-07:
"we need to trade all hours"), replacing the Alpaca free-feed intraday files,
which had almost no pre-market or after-hours bars.

    pythonw backfill_polygon.py --log logs\polygon.log            # every stock that has intraday files (604)
    python  backfill_polygon.py --names NVDA AAPL --tfs 5m 15m 1h   # a few
    python  backfill_polygon.py --check                             # key works? one small request

Key: livelog/polygon.json  {"key": "..."}  (owner-written, never printed).
Bars: 5m, 15m, 1h back 5 years, every session (04:00-20:00 New York), split-adjusted
(Polygon "adjusted=true"), timestamps converted to New York time, naive, like the
other files. The old files are moved to history/stocks_iex/ once, untouched.
Writes history/stocks/<SYM>_{5m,15m,1h}.csv.gz and history/stocks/SOURCE.json
{"source": "polygon", "all_hours": true}; frames_for() reads that flag and stops
dropping pre/after-hours bars. Resumable: a file whose last bar is within 3 days
of today is skipped unless --force.
"""
import argparse
import glob
import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
OUT = os.path.join("history", "stocks")
OLD = os.path.join("history", "stocks_iex")
SPAN = {"5m": (5, "minute"), "15m": (15, "minute"), "1h": (1, "hour")}
START = "2021-06-01"


def key():
    return json.load(open(os.path.join("livelog", "polygon.json")))["key"]


def pull(sym, tf, k, start=START, end=None):
    """Every bar for one name and size, paginated."""
    mult, span = SPAN[tf]
    end = end or pd.Timestamp.now(tz="America/New_York").strftime("%Y-%m-%d")
    url = ("https://api.polygon.io/v2/aggs/ticker/%s/range/%d/%s/%s/%s?adjusted=true&sort=asc&limit=50000"
           % (sym, mult, span, start, end))
    rows = []
    while url:
        for attempt in range(6):
            r = requests.get(url, params={"apiKey": k}, timeout=60)
            if r.status_code == 429:
                time.sleep(2 + 3 * attempt)
                continue
            break
        if r.status_code != 200:
            raise RuntimeError("%s %s: HTTP %s %s" % (sym, tf, r.status_code, r.text[:120]))
        j = r.json()
        rows += j.get("results", []) or []
        url = j.get("next_url")
    if not rows:
        return None
    d = pd.DataFrame(rows)
    t = pd.to_datetime(d["t"], unit="ms", utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
    d = pd.DataFrame({"Open": d["o"].astype(float).values, "High": d["h"].astype(float).values,
                      "Low": d["l"].astype(float).values, "Close": d["c"].astype(float).values,
                      "Volume": d["v"].astype(float).values}, index=pd.DatetimeIndex(t.values))
    if d["Close"].isna().all():
        raise RuntimeError("%s %s: blank prices" % (sym, tf))
    d.index.name = "t"
    d = d[~d.index.duplicated(keep="last")].sort_index()
    return d


def fresh(path, days=3):
    if not os.path.exists(path):
        return False
    try:
        d = pd.read_csv(path, index_col=0, parse_dates=True)
        polygon = d.index[0] >= pd.Timestamp("2021-09-01")      # the old free-feed files start 2021-01-04
        return (pd.Timestamp.now() - d.index[-1]).days <= days and polygon
    except Exception:
        return False


def one(args):
    sym, tfs, k, force = args
    out = []
    for tf in tfs:
        path = os.path.join(OUT, "%s_%s.csv.gz" % (sym, tf))
        if not force and fresh(path):
            out.append("%s fresh" % tf); continue
        try:
            d = pull(sym, tf, k)
        except Exception as ex:
            out.append("%s ERR %s" % (tf, str(ex)[:80])); continue
        if d is None or len(d) < 100:
            out.append("%s none" % tf); continue
        d.to_csv(path)
        out.append("%s %d bars %s..%s" % (tf, len(d), d.index[0].date(), d.index[-1].date()))
    return sym, " | ".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", nargs="*")
    ap.add_argument("--tfs", nargs="*", default=["5m", "15m", "1h"])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--log")
    a = ap.parse_args()
    if a.log:
        sys.stdout = sys.stderr = open(a.log, "a", buffering=1)
    k = key()
    if a.check:
        d = pull("AAPL", "1h", k, start=(pd.Timestamp.now() - pd.Timedelta(days=5)).strftime("%Y-%m-%d"))
        print("ok: AAPL 1h last 5 days ->", None if d is None else (len(d), str(d.index[0]), str(d.index[-1]),
              "hours", sorted(set(d.index.hour))))
        return
    names = a.names or sorted({os.path.basename(f).split("_")[0] for f in glob.glob(os.path.join(OUT, "*_5m.csv.gz"))
                               + glob.glob(os.path.join(OUT, "*_15m.csv.gz"))})
    # keep the old free-feed files once, untouched
    if not os.path.exists(OLD):
        os.makedirs(OLD)
        for f in glob.glob(os.path.join(OUT, "*_5m.csv.gz")) + glob.glob(os.path.join(OUT, "*_15m.csv.gz")) + glob.glob(os.path.join(OUT, "*_1h.csv.gz")):
            shutil.copy2(f, OLD)
        print("copied the old intraday files to", OLD, flush=True)
    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=a.threads) as ex:
        for sym, msg in ex.map(one, [(s, a.tfs, k, a.force) for s in names]):
            done += 1
            print("  %-7s %s   [%d/%d  %.0fs]" % (sym, msg, done, len(names), time.time() - t0), flush=True)
    json.dump(dict(source="polygon", all_hours=True, pulled=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                   tfs=a.tfs, names=len(names)), open(os.path.join(OUT, "SOURCE.json"), "w"))
    print("done %d names in %.0fs" % (len(names), time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
