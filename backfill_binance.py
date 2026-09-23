"""backfill_binance.py -- fill in the early hourly history of a coin our exchanges listed late (2026-09-23).

Our crypto history comes from Coinbase and Kraken, the exchanges he trades on. A coin they listed late only has history
from its listing: BNB here started 2025-10-22, although it has traded since 2017 ("BNB's been around forever tho"). This
pulls the missing hours from Binance's PUBLIC market-data mirror (data-api.binance.vision; the main api.binance.com answers
451 from the US) for the <COIN>USDT pair, and joins it IN FRONT of the existing file -- the existing bars are never
changed. The original is kept as history/_backup/<COIN>_1h.orig.csv.gz. USDT is priced a hair off USD; for returns and
RSI that is nothing.

    python backfill_binance.py BNB
"""
import io
import json
import os
import shutil
import sys
import time
import urllib.request

import pandas as pd

URL = "https://data-api.binance.vision/api/v3/klines?symbol=%sUSDT&interval=1h&startTime=%d&endTime=%d&limit=1000"


def pull(coin, start_ms, end_ms):
    rows, t = [], start_ms
    while t < end_ms:
        with urllib.request.urlopen(URL % (coin, t, end_ms), timeout=30) as r:
            got = json.loads(r.read())
        if not got:
            break
        rows += got
        t = got[-1][0] + 3600 * 1000
        time.sleep(0.15)
    f = pd.DataFrame([(pd.Timestamp(k[0], unit="ms"), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5]))
                      for k in rows], columns=["t", "Open", "High", "Low", "Close", "Volume"])
    return f.drop_duplicates("t")


def main():
    coin = sys.argv[1].upper()
    path = os.path.join("history", "%s_1h.csv.gz" % coin)
    have = pd.read_csv(path, parse_dates=["t"])
    first = have.t.min()
    os.makedirs(os.path.join("history", "_backup"), exist_ok=True)
    bak = os.path.join("history", "_backup", "%s_1h.orig.csv.gz" % coin)
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
    new = pull(coin, int(pd.Timestamp("2017-01-01").value // 10 ** 6), int(first.value // 10 ** 6))
    new = new[new.t < first]
    both = pd.concat([new, have], ignore_index=True).sort_values("t").drop_duplicates("t")
    both.to_csv(path, index=False, compression="gzip")
    json.dump(dict(coin=coin, filled_from="binance public mirror %sUSDT 1h" % coin, filled=[str(new.t.min()), str(new.t.max())],
                   bars_added=int(len(new)), original_from=str(first), when=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")),
              io.open(os.path.join("history", "_backup", "%s_1h.filled.json" % coin), "w", encoding="utf-8"), indent=1)
    print("%s: added %d hourly bars %s .. %s in front of the existing %d (from %s). Now %d bars." % (
        coin, len(new), new.t.min(), new.t.max(), len(have), first, len(both)))
    # the seam: the last Binance bar and the first existing bar should be close in price
    print("seam: binance last close %.2f  |  existing first open %.2f" % (new.Close.iloc[-1], have.Open.iloc[0]))


if __name__ == "__main__":
    main()
