"""backfill_crypto_intraday.py -- 4 years of 15m (and 5m) crypto bars from
Coinbase, for the backburner study (owner 2026-09-04: "scan as many tickers
as possible in the last 4 years ... from the 5m to the 1 week").

    python backfill_crypto_intraday.py                 # 15m for every history name, 5m for the majors
    python backfill_crypto_intraday.py --tf 15m --names BTC ETH

Coinbase serves 300 bars a request with no history cap, so 4 years of 15m
is ~470 requests a name (~4 min), 4 years of 5m ~1,400 (~10 min). Writes
history/crypto_15m/<SYM>_15m.csv.gz and history/crypto_5m/<SYM>_5m.csv.gz,
resumable: an existing file is extended from its last bar only.
"""

import argparse
import glob
import os
import sys
import time

import pandas as pd
import requests

import crypto

UA = crypto.UA
GRAN = {"5m": 300, "15m": 900, "1h": 3600}
MAJORS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "LINK", "AVAX", "LTC", "SUI"]


def extra_names(top):
    """Coinbase names in the scanner universe that have no hourly history yet
    -- 'as many tickers as possible'."""
    have = {os.path.basename(f).split("_")[0]
            for f in glob.glob(os.path.join("history", "*_1h.csv.gz"))}
    u = crypto.universe(top)
    return [x["sym"] for _, x in u.iterrows()
            if x["source"] == "coinbase" and x["sym"] not in have]


def pull(sym, tf, since, until=None):
    """All Coinbase bars for sym from `since` to now, oldest first."""
    g = GRAN[tf]
    end = until or pd.Timestamp.utcnow().tz_localize(None)
    frames, empty = [], 0
    while end > since:
        start = max(since, end - pd.Timedelta(seconds=g * 300))
        try:
            r = requests.get(
                "https://api.exchange.coinbase.com/products/%s-USD/candles" % sym,
                params={"granularity": g, "start": start.isoformat(),
                        "end": end.isoformat()}, headers=UA, timeout=30)
        except Exception:
            time.sleep(2)
            continue
        if r.status_code == 429:
            time.sleep(3)
            continue
        if r.status_code != 200:
            break
        js = r.json()
        if not js:
            empty += 1
            if empty >= 3:          # three empty windows in a row: before listing
                break
        else:
            empty = 0
            d = pd.DataFrame(js, columns=["t", "low", "high", "open", "close", "vol"])
            d["t"] = pd.to_datetime(d.t, unit="s")
            frames.append(d.set_index("t")[["open", "high", "low", "close", "vol"]])
        end = start
        time.sleep(0.25)
    if not frames:
        return None
    out = pd.concat(frames).sort_index()
    out = out[~out.index.duplicated()]
    out.columns = ["Open", "High", "Low", "Close", "Volume"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default=None, help="15m or 5m; default both passes")
    ap.add_argument("--names", nargs="*")
    ap.add_argument("--years", type=float, default=4.1)
    ap.add_argument("--top", type=int, default=0,
                    help="add Coinbase names from the top-N universe that have no history yet (1h then 15m)")
    a = ap.parse_args()
    hist = sorted(os.path.basename(f).split("_")[0]
                  for f in glob.glob(os.path.join("history", "*_1h.csv.gz")))
    if a.top:
        new = extra_names(a.top)
        print("  %d new Coinbase names: %s" % (len(new), " ".join(new)), flush=True)
        passes = [("1h", new), ("15m", new)]
    else:
        passes = ([(a.tf, a.names or (hist if a.tf == "15m" else MAJORS))] if a.tf
                  else [("15m", a.names or hist), ("5m", a.names or MAJORS)])
    since0 = pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=365 * a.years)
    for tf, names in passes:
        # hourly lives in history/ itself (where the study finds crypto names)
        out_dir = "history" if tf == "1h" else os.path.join("history", "crypto_%s" % tf)
        os.makedirs(out_dir, exist_ok=True)
        for sym in names:
            p = os.path.join(out_dir, "%s_%s.csv.gz" % (sym, tf))
            since, old = since0, None
            if os.path.exists(p):
                try:
                    old = pd.read_csv(p, index_col=0, parse_dates=True)
                    since = old.index[-1]
                except Exception:
                    old = None
            t0 = time.time()
            d = pull(sym, tf, since)
            if d is None:
                print("  %-6s %s: nothing new" % (sym, tf), flush=True)
                continue
            if old is not None:
                d = pd.concat([old, d])
                d = d[~d.index.duplicated(keep="last")].sort_index()
            d.to_csv(p, compression="gzip")
            print("  %-6s %s: %7d bars  %s -> %s  (%.0fs)" % (
                sym, tf, len(d), d.index[0], d.index[-1], time.time() - t0),
                flush=True)
    print("  done", flush=True)


if __name__ == "__main__":
    main()
