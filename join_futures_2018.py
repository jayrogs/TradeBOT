"""join_futures_2018.py -- CME futures hours back to 2018 (2026-09-26, bought with his OK: "Buy", ~$3.72, Databento
GLBX.MDP3 ohlcv-1h, the continuous front contract "<ROOT>.v.0", the same series the files were built from, #50).
Pulls 2018-01-01 .. 2022-09-12 (a week past each file's start, for the overlap check), then for each root: the overlap
hours must agree (median close gap under 0.2%), and only bars before the file's first bar are added. Backups in
history/_backup/futures_1h_pre_2018/. The spend is logged in livelog/databento_oneoff.json.

    python join_futures_2018.py
"""
import io
import json
import os
import shutil

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
ROOTS = ["CL", "NG", "HO", "RB", "GC", "SI", "HG", "PL", "ZC", "ZS", "ZW", "ZL", "ZM", "KE", "LE", "GF", "HE"]
RAW = os.path.join("cache", "databento", "glbx_1h_2018-01_2022-09.dbn.zst")
BACKUP = os.path.join("history", "_backup", "futures_1h_pre_2018")


def main():
    import databento as db
    if not os.path.exists(RAW):
        c = db.Historical(json.load(open(os.path.join("livelog", "databento.json")))["key"])
        kw = dict(dataset="GLBX.MDP3", symbols=["%s.v.0" % r for r in ROOTS], stype_in="continuous", schema="ohlcv-1h",
                  start="2018-01-01", end="2022-09-12")
        cost = c.metadata.get_cost(**kw)
        print("cost %.2f" % cost)
        assert cost < 4.5, cost
        c.timeseries.get_range(path=RAW, **kw)
        log = os.path.join("livelog", "databento_oneoff.json")
        L = json.load(io.open(log)) if os.path.exists(log) else []
        L.append(dict(at=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), usd=round(cost, 4),
                      what="GLBX.MDP3 ohlcv-1h continuous front, 17 CME roots, 2018-01..2022-09", ok="Jay 2026-09-26: 'Buy'"))
        json.dump(L, io.open(log, "w", encoding="utf-8"), indent=1)
    raw = db.DBNStore.from_file(RAW).to_df()
    raw.index = pd.DatetimeIndex(raw.index).tz_convert("America/New_York").tz_localize(None)
    os.makedirs(BACKUP, exist_ok=True)
    for r in ROOTS:
        x = raw[raw["symbol"] == "%s.v.0" % r]
        path = os.path.join("history", "futures", "%s_F_1h.csv.gz" % r)
        have = pd.read_csv(path, index_col=0, parse_dates=True)
        new = pd.DataFrame({"Open": x["open"].astype(float).values, "High": x["high"].astype(float).values,
                            "Low": x["low"].astype(float).values, "Close": x["close"].astype(float).values,
                            "Volume": x["volume"].astype(float).values}, index=x.index)
        new = new[~new.index.duplicated()].sort_index()
        j = have.index.intersection(new.index)
        if len(j) < 24:
            print("  %-3s skipped: only %d overlap hours" % (r, len(j)))
            continue
        gap = float(np.median(np.abs(have.loc[j, "Close"].values / new.loc[j, "Close"].values - 1)))
        if gap > 0.002:
            print("  %-3s skipped: overlap does not agree (median gap %.3f%%)" % (r, 100 * gap))
            continue
        add = new[new.index < have.index[0]]
        bk = os.path.join(BACKUP, os.path.basename(path))
        if not os.path.exists(bk):
            shutil.copy2(path, bk)
        add.index.name = have.index.name
        pd.concat([add, have]).to_csv(path + ".tmp.gz", compression="gzip")
        os.replace(path + ".tmp.gz", path)
        print("  %-3s +%6d bars %s .. %s  (overlap gap %.4f%%)" % (r, len(add), add.index[0].date(), add.index[-1].date(), 100 * gap))


if __name__ == "__main__":
    main()
