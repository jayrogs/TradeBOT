"""yahoo_ice_recent.py -- keep the five ICE futures' hourly history current from Yahoo (2026-09-26).

Brent (BZ), cocoa (CC), coffee (KC), sugar (SB) and cotton (CT) are not on his Databento plan (CME only), and their files
came from Yahoo in the first place. Yahoo refused them from 2026-09-04 to about 2026-09-25, so the history stopped there
while the live page filled the gap in memory. This appends Yahoo's finished hourly bars after each file's last bar
(New York wall time, the stamp of the hour's start, as the files are). The hour still forming is never written.
A backup of each file is kept in history/_backup/futures_1h_ice/ before its first append.

    python yahoo_ice_recent.py        # bb_live.py calls it about once an hour
"""
import os
import shutil

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
ROOTS = ["BZ", "CC", "KC", "SB", "CT"]
BACKUP = os.path.join("history", "_backup", "futures_1h_ice")


def main(log=print):
    import yfinance as yf
    now = pd.Timestamp.now(tz="America/New_York").tz_localize(None)
    os.makedirs(BACKUP, exist_ok=True)
    for root in ROOTS:
        path = os.path.join("history", "futures", "%s_F_1h.csv.gz" % root)
        try:
            old = pd.read_csv(path, parse_dates=["Datetime"], index_col="Datetime")
            d = yf.download("%s=F" % root, interval="1h", period="60d", progress=False, auto_adjust=False, prepost=True)
            if d is None or not len(d):
                log("yahoo_ice_recent: %s nothing from Yahoo" % root)
                continue
            if isinstance(d.columns, pd.MultiIndex):
                d.columns = d.columns.get_level_values(0)
            d.index = d.index.tz_convert("America/New_York").tz_localize(None)
            d = d[["Open", "High", "Low", "Close", "Volume"]].dropna().astype(float)
            d = d[(d.index > old.index[-1]) & (d.index + pd.Timedelta(hours=1) <= now)]
            if not len(d):
                continue
            bk = os.path.join(BACKUP, os.path.basename(path))
            if not os.path.exists(bk):
                shutil.copy2(path, bk)
            d.index.name = "Datetime"
            both = pd.concat([old, d])
            both.to_csv(path + ".tmp.gz", compression="gzip")
            os.replace(path + ".tmp.gz", path)
            log("yahoo_ice_recent: %s +%d bars, %s .. %s" % (root, len(d), d.index[0], d.index[-1]))
        except Exception as ex:
            log("yahoo_ice_recent: %s failed: %s" % (root, ex))


if __name__ == "__main__":
    main()
