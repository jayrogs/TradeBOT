"""crypto_recent.py -- keep the crypto hourly history on disk current (2026-09-26).

Nothing topped up history/<SYM>_1h.csv.gz after its pull (every file ended 2026-09-07). The studies read these files and
bb_live joins them in front of the exchanges' last 720 hourly bars; once a file is 30+ days behind that join leaves a hole.
This appends each coin's finished hourly bars after its last bar, from the exchange that serves it (Coinbase, then Kraken,
then OKX), UTC, as the files are. The hour still forming is never written. Before appending, the bars both sides have must
agree (median gap under 0.5%); a coin whose feed does not match its file is skipped and named, never spliced.
A backup of each file is kept in history/_backup/crypto_1h/ before its first append.

    python crypto_recent.py            # bb_live.py calls it about every 6 hours
"""
import concurrent.futures as cf
import glob
import os
import shutil

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
BACKUP = os.path.join("history", "_backup", "crypto_1h")


def _one(path, src, now):
    import crypto
    sym = os.path.basename(path).split("_")[0]
    old = pd.read_csv(path, index_col=0, parse_dates=True)
    last = pd.Timestamp(old.index[-1])
    need = int((now - last) / pd.Timedelta(hours=1)) + 48
    if need <= 49:
        return sym, 0, "current"
    # try each exchange, keep the first whose bars reach back to the file's end AND agree with it where both have bars
    why, new = "no data from any exchange", None
    for s_ in list(dict.fromkeys(([src] if src else []) + ["coinbase", "kraken", "okx"])):
        try:
            d = crypto._SOURCES[s_](sym, "1h", min(max(need, 300), 2000))
        except Exception:
            d = None
        if d is None or len(d) < 30:
            continue
        if getattr(d.index, "tz", None) is not None:
            d.index = d.index.tz_convert("UTC").tz_localize(None)
        d = d[["Open", "High", "Low", "Close", "Volume"]].astype(float)
        both = old.index.intersection(d.index)
        if len(both) < 12:
            why = "%s starts after the file ends (%s), a hole" % (s_, d.index[0])
            continue
        gap = float(np.median(np.abs(old.loc[both, "Close"].values / d.loc[both, "Close"].values - 1)))
        if gap > 0.005:
            why = "%s does not match the file (median gap %.2f%%)" % (s_, 100 * gap)
            continue
        new = d
        break
    if new is None:
        return sym, 0, why + " -- skipped"
    add = new[(new.index > last) & (new.index + pd.Timedelta(hours=1) <= now)]
    if not len(add):
        return sym, 0, "nothing new"
    bk = os.path.join(BACKUP, os.path.basename(path))
    if not os.path.exists(bk):
        shutil.copy2(path, bk)
    add.index.name = old.index.name
    out = pd.concat([old, add])
    out.to_csv(path + ".tmp.gz", compression="gzip")
    os.replace(path + ".tmp.gz", path)
    return sym, len(add), "to %s" % add.index[-1]


def main(log=print, workers=8):
    import crypto
    os.makedirs(BACKUP, exist_ok=True)
    try:
        src = {str(x.sym): x.source for x in crypto.universe(250).itertuples()}
    except Exception:
        src = {}
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    files = sorted(glob.glob(os.path.join("history", "*_1h.csv.gz")))
    done, skipped = 0, []
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for sym, n, how in ex.map(lambda f: _safe(f, src, now), files):
            if n:
                done += 1
            elif how not in ("current", "nothing new"):
                skipped.append("%s: %s" % (sym, how))
    log("crypto_recent: %d of %d files topped up; %d skipped" % (done, len(files), len(skipped)))
    for s_ in skipped:
        log("  " + s_)
    return done, skipped


def _safe(f, src, now):
    sym = os.path.basename(f).split("_")[0]
    try:
        return _one(f, src.get(sym), now)
    except Exception as ex:
        return sym, 0, "failed: %s" % ex


if __name__ == "__main__":
    main()
