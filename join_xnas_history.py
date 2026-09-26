"""join_xnas_history.py -- put the 2018-05 .. 2021-09 Nasdaq-exchange hourly bars in front of the Polygon stock history
(2026-09-26, bought with his OK: "Buy it", $6.16 from Databento, XNAS.ITCH ohlcv-1h, cache/databento_stocks/).

The bars are the trades on the Nasdaq exchange only (every US stock trades there; about 15% of the volume), RAW prices.
The history files are split-adjusted. For each name:
  1. the raw daily close = the close of its 15:00 New York bar (the last regular-session hour);
  2. the adjustment for each day = the name's own daily file close / that raw close, as a CENTRED 5-day median, so a split
     flips on its own day and a single odd print cannot move it;
  3. CHECKED before anything is written: day-to-day moves of the raw closes and the daily file must agree (correlation
     0.97+ on days without a split) -- a ticker that belonged to a different company then (META was a fund until FB
     took the name) fails and is skipped; renamed companies are read under their old ticker (FB -> META, SQ -> XYZ);
  4. the LEVEL is set on the weeks both sources have (2021-09-07 .. 09-30), which must agree hour by hour;
  5. only bars BEFORE the file's first Polygon bar are added; the seam is logged.
A backup of every file is kept in history/_backup/stocks_1h_pre_xnas/ before it is changed.

    python join_xnas_history.py
Writes history/stocks/<SYM>_1h.csv.gz and logs/join_xnas_history.log
"""
import io
import os
import shutil
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, os.path.join(HERE, "studies"))
import backburner_study as S      # noqa: E402

SRC = os.path.join("cache", "databento_stocks", "xnas_1h_2018-05_2021-10.dbn.zst")
BACKUP = os.path.join("history", "_backup", "stocks_1h_pre_xnas")
OLD_NAME = {"META": "FB", "XYZ": "SQ"}


def main():
    import databento as db
    os.makedirs(BACKUP, exist_ok=True)
    raw = db.DBNStore.from_file(SRC).to_df()
    raw.index = raw.index.tz_convert("America/New_York").tz_localize(None)
    raw = raw[["symbol", "open", "high", "low", "close", "volume"]]
    groups = dict(tuple(raw.groupby("symbol")))
    out = io.open(os.path.join("logs", "join_xnas_history.log"), "w", encoding="utf-8")
    done, skipped = 0, []
    for f in sorted(os.listdir(os.path.join("history", "stocks"))):
        if not f.endswith("_1h.csv.gz"):
            continue
        sym = f.split("_")[0]
        x = groups.get(OLD_NAME.get(sym, sym))
        if x is None or len(x) < 200:
            continue
        path = os.path.join("history", "stocks", f)
        h1 = S.load_csv(path)
        d1 = S.load_csv(os.path.join("history", "stocks", "%s_1d.csv.gz" % sym))
        if h1 is None or d1 is None or not len(h1):
            continue
        first = pd.Timestamp(h1.index[0])
        over = x[x.index >= first]            # the weeks both sources have (Polygon from ~2021-09-07, these to 2021-09-30)
        x = x[x.index < first]
        if len(x) < 200:
            continue
        if first - pd.Timestamp(x.index[-1]) > pd.Timedelta(days=7):
            skipped.append((sym, "the Polygon file starts %s, long after these bars end -- a hole" % first.date()))
            continue
        # raw daily close from the 15:00 bar
        rc = x[x.index.hour == 15]["close"]
        rc.index = rc.index.normalize()
        dc = pd.Series(d1["Close"].values.astype(float), index=pd.DatetimeIndex(d1.index).normalize())
        dc = dc[~dc.index.duplicated(keep="last")]
        both = rc.index.intersection(dc.index)
        if len(both) < 100:
            skipped.append((sym, "only %d shared days with the daily file" % len(both)))
            continue
        ratio = (dc.loc[both] / rc.loc[both]).rolling(5, center=True, min_periods=1).median()
        jumps = np.abs(np.diff(np.log(ratio.values))) > 0.03
        ra, rd = np.diff(np.log(rc.loc[both].values)), np.diff(np.log(dc.loc[both].values))
        ok = ~jumps
        corr = float(np.corrcoef(ra[ok], rd[ok])[0, 1]) if ok.sum() > 50 else 0.0
        if not np.isfinite(corr) or corr < 0.97:
            skipped.append((sym, "moves do not match the daily file (correlation %.2f) -- a different company then?" % corr))
            continue
        fac = ratio.reindex(pd.DatetimeIndex(x.index).normalize(), method="ffill").values
        fac = np.where(np.isfinite(fac), fac, ratio.iloc[0])
        # THE LEVEL COMES FROM THE HOURLY FILE, not the daily one: some daily files are adjusted for spin-offs the hourly
        # ones are not (DHR, BHP: 11-12% apart in 2021). The daily ratio only places the SPLITS; the overlap weeks with
        # Polygon set the level, and they must agree hour by hour or the name is skipped (META's Polygon hours before
        # 2022-06 are a different fund that held the ticker).
        oh = over[(over.index.hour >= 9) & (over.index.hour <= 15)]
        j = oh.index.intersection(h1.index)
        if len(j) < 20:
            skipped.append((sym, "only %d overlap hours with the Polygon file" % len(j)))
            continue
        last_fac = float(ratio.iloc[-1])
        k_ = h1.loc[j, "Close"].values.astype(float) / (oh.loc[j, "close"].values * last_fac)
        k = float(np.median(k_))
        if np.median(np.abs(k_ / k - 1)) > 0.003:
            skipped.append((sym, "the overlap hours do not agree with the Polygon file (spread %.2f%%)"
                            % (100 * np.median(np.abs(k_ / k - 1)))))
            continue
        fac = fac * k
        add = pd.DataFrame({"Open": x["open"].values * fac, "High": x["high"].values * fac, "Low": x["low"].values * fac,
                            "Close": x["close"].values * fac, "Volume": x["volume"].values / fac}, index=x.index)
        seam = float(add["Close"].iloc[-1] / h1["Close"].iloc[0] - 1)
        bk = os.path.join(BACKUP, f)
        if not os.path.exists(bk):
            shutil.copy2(path, bk)
        add.index.name = h1.index.name
        both_ = pd.concat([add, h1[["Open", "High", "Low", "Close", "Volume"]]])
        both_ = both_[~both_.index.duplicated(keep="last")].sort_index()
        both_.to_csv(path + ".tmp.gz", compression="gzip")
        os.replace(path + ".tmp.gz", path)
        done += 1
        out.write("%-6s +%6d bars %s .. %s  splits %d  corr %.3f  seam %+.2f%%\n" % (
            sym, len(add), add.index[0], add.index[-1], int(jumps.sum()), corr, 100 * seam))
    out.write("\n%d names joined, %d skipped\n" % (done, len(skipped)))
    for s_, why in skipped:
        out.write("  skipped %-6s %s\n" % (s_, why))
    out.close()
    print("%d names joined, %d skipped" % (done, len(skipped)))


if __name__ == "__main__":
    main()
