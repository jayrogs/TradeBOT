"""backfill_yahoo.py -- futures and forex history from Yahoo, for the studies.

    python backfill_yahoo.py                # futures + forex, 1h (2y) and 1d (10y)

Yahoo is the only free source for continuous futures and FX bars. Its caps:
hourly goes back 730 days, daily 10+ years, 15m only 60 days (skipped -- two
months is one regime, not a study). Writes history/futures/<SYM>_<tf>.csv.gz
and history/forex/<SYM>_<tf>.csv.gz (naive exchange time, tz stripped).
"""

import os
import time

import pandas as pd
import yfinance as yf

import bigscan

PULLS = (("1h", "2y"), ("1d", "10y"))


def pull(names, kind):
    out_dir = os.path.join("history", kind)
    os.makedirs(out_dir, exist_ok=True)
    for tf, period in PULLS:
        for i in range(0, len(names), 40):
            part = names[i:i + 40]
            t0 = time.time()
            try:
                d = yf.download(part, interval=tf, period=period, progress=False,
                                auto_adjust=False, group_by="ticker", threads=True)
            except Exception as ex:
                print("  %s %s chunk failed: %s" % (kind, tf, ex), flush=True)
                continue
            got = 0
            for s in part:
                try:
                    f = (d[s] if len(part) > 1 else d).dropna()
                except Exception:
                    continue
                if getattr(f.index, "tz", None) is not None:
                    f.index = f.index.tz_localize(None)
                f = f[["Open", "High", "Low", "Close", "Volume"]]
                if len(f) < 100:
                    continue
                safe = s.replace("=", "_")
                f.to_csv(os.path.join(out_dir, "%s_%s.csv.gz" % (safe, tf)),
                         compression="gzip")
                got += 1
            print("  %-7s %-3s %3d/%3d names  %s  (%.0fs)" % (
                kind, tf, got, len(part), part[0] + ".." + part[-1], time.time() - t0),
                flush=True)


def pull_stock_daily():
    """Ten years of daily bars (consolidated volume) for every tier1 stock
    and ETF -- the daily/weekly rows of the studies need years, not days."""
    k = pd.read_csv(os.path.join("cache", "tier1.csv"))
    names = k[k.kind.isin(["equity", "etf"])].symbol.dropna().astype(str).tolist()
    out_dir = os.path.join("history", "stocks")
    os.makedirs(out_dir, exist_ok=True)
    for i in range(0, len(names), 200):
        part = names[i:i + 200]
        t0 = time.time()
        try:
            d = yf.download(part, interval="1d", period="10y", progress=False,
                            auto_adjust=False, group_by="ticker", threads=True)
        except Exception as ex:
            print("  stocks 1d chunk failed: %s" % ex, flush=True)
            continue
        got = 0
        for s in part:
            try:
                f = (d[s] if len(part) > 1 else d).dropna()
            except Exception:
                continue
            if len(f) < 100:
                continue
            f = f[["Open", "High", "Low", "Close", "Volume"]]
            f.to_csv(os.path.join(out_dir, "%s_1d.csv.gz" % s), compression="gzip")
            got += 1
        print("  stocks 1d %4d/%4d  %3d/%3d names  (%.0fs)" % (
            i + len(part), len(names), got, len(part), time.time() - t0), flush=True)


if __name__ == "__main__":
    import sys
    if "--stocks-daily" in sys.argv:
        pull_stock_daily()
    else:
        pull(bigscan.FUTURES, "futures")
        pull(bigscan.FOREX, "forex")
    print("  done", flush=True)
