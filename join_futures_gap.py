"""join_futures_gap.py -- the four futures whose files start 2024-09 (ZL soybean oil, ZM soybean meal, KE KC wheat, GF feeder
cattle; their first two years came from Yahoo): 2022-09 .. 2024-09 bought from Databento (2026-09-26, his "Buy", ~$0.31),
put together with the 2018-2022 hours already bought (join_futures_2018.py) and joined in front of each file where the
overlap week agrees (median close gap under 0.5% -- the file's early bars are Yahoo's, a different roll). Backups in
history/_backup/futures_1h_pre_2018/.

    python join_futures_gap.py
"""
import io
import json
import os
import shutil

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
ROOTS = ["ZL", "ZM", "KE", "GF"]
RAW18 = os.path.join("cache", "databento", "glbx_1h_2018-01_2022-09.dbn.zst")
RAW = os.path.join("cache", "databento", "glbx_1h_gap_2022-09_2024-09.dbn.zst")
BACKUP = os.path.join("history", "_backup", "futures_1h_pre_2018")


def frame(path, root):
    import databento as db
    x = db.DBNStore.from_file(path).to_df()
    x = x[x["symbol"] == "%s.v.0" % root]
    idx = pd.DatetimeIndex(x.index).tz_convert("America/New_York").tz_localize(None)
    return pd.DataFrame({"Open": x["open"].astype(float).values, "High": x["high"].astype(float).values,
                         "Low": x["low"].astype(float).values, "Close": x["close"].astype(float).values,
                         "Volume": x["volume"].astype(float).values}, index=idx)


def main():
    import databento as db
    if not os.path.exists(RAW):
        c = db.Historical(json.load(open(os.path.join("livelog", "databento.json")))["key"])
        kw = dict(dataset="GLBX.MDP3", symbols=["%s.v.0" % r for r in ROOTS], stype_in="continuous", schema="ohlcv-1h",
                  start="2022-09-01", end="2024-09-12")
        cost = c.metadata.get_cost(**kw)
        print("cost %.2f" % cost)
        assert cost < 0.5, cost
        c.timeseries.get_range(path=RAW, **kw)
        log = os.path.join("livelog", "databento_oneoff.json")
        L = json.load(io.open(log)) if os.path.exists(log) else []
        L.append(dict(at=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), usd=round(cost, 4),
                      what="GLBX.MDP3 ohlcv-1h ZL ZM KE GF 2022-09..2024-09 (the gap)", ok="Jay 2026-09-26: 'Buy'"))
        json.dump(L, io.open(log, "w", encoding="utf-8"), indent=1)
    os.makedirs(BACKUP, exist_ok=True)
    for r in ROOTS:
        new = pd.concat([frame(RAW18, r), frame(RAW, r)])
        new = new[~new.index.duplicated(keep="last")].sort_index()
        path = os.path.join("history", "futures", "%s_F_1h.csv.gz" % r)
        have = pd.read_csv(path, index_col=0, parse_dates=True)
        j = have.index.intersection(new.index)
        if len(j) < 24:
            print("  %s skipped: only %d overlap hours" % (r, len(j)))
            continue
        gap = float(np.median(np.abs(have.loc[j, "Close"].values / new.loc[j, "Close"].values - 1)))
        if gap > 0.005:
            print("  %s skipped: overlap does not agree (median gap %.3f%%)" % (r, 100 * gap))
            continue
        add = new[new.index < have.index[0]]
        bk = os.path.join(BACKUP, os.path.basename(path))
        if not os.path.exists(bk):
            shutil.copy2(path, bk)
        add.index.name = have.index.name
        pd.concat([add, have]).to_csv(path + ".tmp.gz", compression="gzip")
        os.replace(path + ".tmp.gz", path)
        holes = add.index.to_series().diff().max()
        print("  %s +%d bars %s .. %s  (overlap gap %.3f%%, longest hole %s)" % (r, len(add), add.index[0].date(),
                                                                                  add.index[-1].date(), 100 * gap, holes))


if __name__ == "__main__":
    main()
