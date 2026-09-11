"""backfill_okx.py -- deep intraday history for the crypto names Kraken lists
but Coinbase does not. Kraken's API stops at 720 bars; OKX serves years of
5m / 15m / 1h for most of the same names, free (owner 2026-09-05: "run all
that shit as long as you can").

    python backfill_okx.py                 # every Kraken-only name in the universe, most traded first
    python backfill_okx.py --names TRX JUP --tf 15m

Writes the same layout the study reads: history/<SYM>_1h.csv.gz,
history/crypto_15m/<SYM>_15m.csv.gz, history/crypto_5m/<SYM>_5m.csv.gz.
Resumable (extends from the last bar). 100 bars a request, ~8 requests a
second: about 1 min per name for hourly, 4 for 15m, 11 for 5m.
"""

import argparse
import json
import os
import time

import pandas as pd
import requests

import crypto

UA = crypto.UA
BAR = {"5m": "5m", "15m": "15m", "1h": "1H"}
OUT = {"1h": "history", "15m": os.path.join("history", "crypto_15m"),
       "5m": os.path.join("history", "crypto_5m")}


def pull(sym, tf, since):
    """OKX history-candles back to `since`, oldest first, or None."""
    rows, after, misses = [], None, 0
    inst = "%s-USDT" % sym
    while True:
        p = {"instId": inst, "bar": BAR[tf], "limit": 100}
        if after:
            p["after"] = after
        try:
            r = requests.get("https://www.okx.com/api/v5/market/history-candles",
                             params=p, headers=UA, timeout=25)
        except Exception:
            misses += 1
            if misses > 5:
                break
            time.sleep(2)
            continue
        if r.status_code == 429:
            time.sleep(2)
            continue
        if r.status_code != 200:
            break
        js = (r.json() or {}).get("data") or []
        if not js:
            break
        rows += js
        after = js[-1][0]
        if pd.to_datetime(int(after), unit="ms") <= since:
            break
        time.sleep(0.12)
    if not rows:
        return None
    d = pd.DataFrame(rows).iloc[:, :6]
    d.columns = ["ts", "Open", "High", "Low", "Close", "Volume"]
    d["t"] = pd.to_datetime(d.ts.astype("int64"), unit="ms")
    for k in ("Open", "High", "Low", "Close", "Volume"):
        d[k] = d[k].astype(float)
    d = d.set_index("t")[["Open", "High", "Low", "Close", "Volume"]].sort_index()
    d = d[~d.index.duplicated()]
    return d[d.index >= since]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", nargs="*")
    ap.add_argument("--tf", default=None)
    ap.add_argument("--years", type=float, default=4.1)
    ap.add_argument("--fast-5m", type=int, default=30,
                    help="5m only for the N most traded (it is the slow one)")
    a = ap.parse_args()
    if a.names:
        names = a.names
    else:
        u = json.load(open(os.path.join(crypto.CACHE, "universe.json")))
        names = [x["sym"] for x in u if x["source"] == "kraken"]     # volume order
    since = pd.Timestamp.now(tz="UTC").tz_localize(None) - pd.Timedelta(days=365 * a.years)
    passes = [(a.tf, names)] if a.tf else [("1h", names), ("15m", names),
                                            ("5m", names[:a.fast_5m])]
    listed = set(names)
    for tf, syms in passes:
        os.makedirs(OUT[tf], exist_ok=True)
        for sym in syms:
            if sym not in listed:
                continue
            p = os.path.join(OUT[tf], "%s_%s.csv.gz" % (sym, tf))
            start, old = since, None
            if os.path.exists(p):
                try:
                    old = pd.read_csv(p, index_col=0, parse_dates=True)
                    start = old.index[-1]
                except Exception:
                    old = None
            t0 = time.time()
            d = pull(sym, tf, start)
            if d is None or d.empty:
                if tf == "1h" and old is None:
                    listed.discard(sym)             # OKX does not list it: skip its other frames
                print("  %-8s %-3s nothing (%s)" % (sym, tf, "not on OKX" if sym not in listed else "no new bars"), flush=True)
                continue
            if old is not None:
                d = pd.concat([old, d])
                d = d[~d.index.duplicated(keep="last")].sort_index()
            d.to_csv(p, compression="gzip")
            print("  %-8s %-3s %7d bars  %s -> %s  (%.0fs)" % (
                sym, tf, len(d), d.index[0], d.index[-1], time.time() - t0), flush=True)
    print("  done", flush=True)


if __name__ == "__main__":
    main()
