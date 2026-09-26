"""backfill_binance_all.py -- the early hourly history of EVERY coin, from Binance's free public archive (2026-09-26, his "go":
test the crypto backburner through the 2018 and 2020 crashes; most of our coin files start in 2022).

For each history/<COIN>_1h.csv.gz: pull <COIN>USDT 1h from Binance's public mirror (data-api.binance.vision; the main API
answers 451 from the US) from 2017-01 to 30 days after the file begins, then:
  - the 30 days both have must AGREE (median close gap under 0.5%) -- a different token under the same ticker, a
    redenomination, or a thin pair is skipped and named, never joined;
  - the Binance bars must reach the file's first bar (no hole);
  - only bars BEFORE the file's first bar are added; the existing bars are never changed.
USDT is priced a hair off USD; for returns and RSI that is nothing. Backups in history/_backup/crypto_1h_pre_binance/.

    python backfill_binance_all.py          (Binance)
    python backfill_binance_all.py --okx    (OKX, for the coins Binance does not carry)
Log: logs/backfill_binance_all.log
"""
import concurrent.futures as cf
import glob
import io
import json
import os
import shutil
import time
import urllib.error
import urllib.request

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
URL = "https://data-api.binance.vision/api/v3/klines?symbol=%sUSDT&interval=1h&startTime=%d&endTime=%d&limit=1000"
BACKUP = os.path.join("history", "_backup", "crypto_1h_pre_binance")
FROM = pd.Timestamp("2017-01-01")


def pull(coin, start, end):
    rows, t, end_ms = [], int(start.value // 10 ** 6), int(end.value // 10 ** 6)
    while t < end_ms:
        for attempt in range(4):
            try:
                with urllib.request.urlopen(URL % (coin, t, end_ms), timeout=30) as r:
                    got = json.loads(r.read())
                break
            except urllib.error.HTTPError as ex:
                if ex.code == 400:          # no such pair on Binance
                    return None
                time.sleep(2 + 3 * attempt)
            except Exception:
                time.sleep(2 + 3 * attempt)
        else:
            return None
        if not got:
            break
        rows += got
        t = got[-1][0] + 3600 * 1000
        time.sleep(0.2)
    if not rows:
        return None
    f = pd.DataFrame([(pd.Timestamp(k[0], unit="ms"), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5]))
                      for k in rows], columns=["t", "Open", "High", "Low", "Close", "Volume"])
    return f.drop_duplicates("t").set_index("t").sort_index()


def pull_okx(coin, start, end):
    """OKX's history candles (paginated inside crypto._okx), for the coins Binance does not carry."""
    import crypto
    bars = int((pd.Timestamp.now() - start) / pd.Timedelta(hours=1))
    d = crypto._okx(coin, "1h", min(bars, 90000))
    if d is None or not len(d):
        return None
    if getattr(d.index, "tz", None) is not None:
        d.index = d.index.tz_convert("UTC").tz_localize(None)
    d = d[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    return d[(d.index >= start) & (d.index <= end)]


SOURCE = {"binance": pull, "okx": pull_okx}
WHICH = ["binance"]


def one(path):
    coin = os.path.basename(path).split("_")[0]
    have = pd.read_csv(path, index_col=0, parse_dates=True)
    first = pd.Timestamp(have.index[0])
    if first <= FROM + pd.Timedelta(days=30):
        return coin, 0, "already starts %s" % first.date()
    new = SOURCE[WHICH[0]](coin, FROM, first + pd.Timedelta(days=30))
    if new is None or len(new) < 100:
        return coin, 0, "not on %s" % WHICH[0]
    both = have.index.intersection(new.index)
    if len(both) < 48:
        return coin, 0, "Binance bars do not reach the file's start (%s .. %s) -- a hole" % (new.index[0].date(), new.index[-1].date())
    gap = float(np.median(np.abs(have.loc[both, "Close"].values / new.loc[both, "Close"].values - 1)))
    if gap > 0.005:
        return coin, 0, "Binance does not match the file (median gap %.2f%%) -- a different token?" % (100 * gap)
    add = new[new.index < first]
    if len(add) < 24:
        return coin, 0, "nothing earlier on Binance"
    bk = os.path.join(BACKUP, os.path.basename(path))
    if not os.path.exists(bk):
        shutil.copy2(path, bk)
    add.index.name = have.index.name
    out = pd.concat([add, have])
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out.to_csv(path + ".tmp.gz", compression="gzip")
    os.replace(path + ".tmp.gz", path)
    return coin, len(add), "from %s (was %s), overlap gap %.3f%%" % (add.index[0].date(), first.date(), 100 * gap)


def main():
    import sys
    if "--okx" in sys.argv:
        WHICH[0] = "okx"
    os.makedirs(BACKUP, exist_ok=True)
    files = sorted(glob.glob(os.path.join("history", "*_1h.csv.gz")))
    log = io.open(os.path.join("logs", "backfill_%s_all.log" % WHICH[0]), "w", encoding="utf-8", buffering=1)
    done = 0
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        for coin, n, how in ex.map(lambda p: _safe(p), files):
            done += bool(n)
            log.write("%-8s %6d  %s\n" % (coin, n, how))
    log.write("\n%d of %d coins got earlier history\n" % (done, len(files)))
    log.close()
    print("%d of %d coins got earlier history" % (done, len(files)))


def _safe(p):
    try:
        return one(p)
    except Exception as ex:
        return os.path.basename(p).split("_")[0], 0, "failed: %s" % ex


if __name__ == "__main__":
    main()
