"""stock_recent.py -- keep the stock and fund hourly AND daily history on disk current from his Polygon / Massive feed
(2026-09-26). The files ended 2026-09-07 (the last full pull); the live page filled the gap in memory, the studies could
not. Appends each name's bars after its last bar -- the 2018-2021 Databento bars in front are never touched (a full
re-pull with backfill_polygon.py would have overwritten them). Before appending, the days / hours both have must agree
(median close gap under 0.5%); a name that does not (a split since, a ticker change) is skipped and named.
The hour or day still forming is never written.

    python stock_recent.py [--folder history/stocks_more]     # bb_live.py runs it about every 6 hours on history/stocks
Log: printed, and logs/stock_recent.log when run on its own
"""
import concurrent.futures as cf
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
import backfill_polygon as BP     # noqa: E402


def _one(sym, folder, k, now):
    out = []
    for tf, span, step in (("1h", "1h", pd.Timedelta(hours=1)), ("1d", "1d", pd.Timedelta(days=1))):
        path = os.path.join(folder, "%s_%s.csv.gz" % (sym, tf))
        if not os.path.exists(path):
            continue
        old = pd.read_csv(path, index_col=0, parse_dates=True)
        if getattr(old.index, "tz", None) is not None:
            old.index = old.index.tz_localize(None)
        last = pd.Timestamp(old.index[-1])
        start = (last - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
        try:
            new = BP.pull(sym, span, k, start=start)
        except Exception as ex:
            out.append("%s failed: %s" % (tf, str(ex)[:60]))
            continue
        if new is None or not len(new):
            out.append("%s nothing" % tf)
            continue
        if tf == "1d":
            new.index = new.index.normalize()
        cols = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in old.columns]
        both = old.index.intersection(new.index)
        if len(both) < 3:
            out.append("%s no overlap -- skipped" % tf)
            continue
        gap = float(np.median(np.abs(old.loc[both, "Close"].values.astype(float) / new.loc[both, "Close"].values - 1)))
        if gap > 0.005:
            out.append("%s does not match (median gap %.2f%%) -- skipped" % (tf, 100 * gap))
            continue
        cut = now if tf == "1h" else now.normalize()
        add = new[(new.index > last) & (new.index + step <= cut)]
        if not len(add):
            out.append("%s current" % tf)
            continue
        add = add[["Open", "High", "Low", "Close", "Volume"]]
        add.columns = ["Open", "High", "Low", "Close", "Volume"]
        for c in old.columns:
            if c not in add.columns:
                add[c] = add["Close"] if c == "Adj Close" else np.nan
        add = add[old.columns]
        add.index.name = old.index.name
        pd.concat([old, add]).to_csv(path + ".tmp.gz", compression="gzip")
        os.replace(path + ".tmp.gz", path)
        out.append("%s +%d" % (tf, len(add)))
    return sym, out


def main(log=print, folder=os.path.join("history", "stocks")):
    k = BP.key()
    now = pd.Timestamp.now(tz="America/New_York").tz_localize(None)
    syms = sorted({os.path.basename(f).split("_")[0] for f in glob.glob(os.path.join(folder, "*_1h.csv.gz"))})
    bad, n = [], 0
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for sym, out in ex.map(lambda s: _safe(s, folder, k, now), syms):
            n += any("+" in o for o in out)
            bad += ["%s %s" % (sym, o) for o in out if "skipped" in o or "failed" in o]
    log("stock_recent: %d of %d names topped up in %s; %d problems" % (n, len(syms), folder, len(bad)))
    for b in bad:
        log("  " + b)
    return n, bad


def _safe(s, folder, k, now):
    try:
        return _one(s, folder, k, now)
    except Exception as ex:
        return s, ["failed: %s" % str(ex)[:80]]


if __name__ == "__main__":
    f = sys.argv[sys.argv.index("--folder") + 1] if "--folder" in sys.argv else os.path.join("history", "stocks")
    main(folder=f)
