"""fetch_new_coins.py -- hourly history for every coin the exchanges list that has none on disk (2026-09-26; his standing
order "just keep getting data"). 135 coins in crypto.universe(250) had no history/<COIN>_1h.csv.gz, so neither the studies
nor the live page ever looked at them.

For each: the full hourly history the exchange serves (Coinbase, then Kraken, then OKX -- the source the universe names
first). NOT KEPT:
  - STABLECOINS and anything pegged: 90% or more of its daily closes within 2% of its own middle price (EURC, USDC ...);
  - COPIES of a coin we already have: a wrapped or staked version whose price stays within 3% of BTC's, ETH's or SOL's
    (or a fixed multiple of it) on 90%+ of days;
  - fewer than 60 days of bars.
Kept coins are written to history/<COIN>_1h.csv.gz; backfill_binance_all.py then adds any earlier Binance history.

    python fetch_new_coins.py
Log: logs/fetch_new_coins.log
"""
import concurrent.futures as cf
import glob
import io
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
BARS = 110000


def _daily(h):
    return h["Close"].resample("1D").last().dropna()


def one(args):
    import crypto
    sym, src, majors = args
    d = None
    for s_ in list(dict.fromkeys(([src] if src else []) + ["coinbase", "kraken", "okx"])):
        try:
            d = crypto._SOURCES[s_](sym, "1h", BARS)
        except Exception:
            d = None
        if d is not None and len(d) >= 24 * 60:
            break
    if d is None or len(d) < 24 * 60:
        # Kraken serves only 720 hours: take the whole history from Binance's public archive instead, if its recent
        # bars agree with the exchange's (median gap under 0.5%)
        import backfill_binance_all as BB
        b = BB.pull(sym, pd.Timestamp("2017-01-01"), pd.Timestamp.now())
        if b is None or len(b) < 24 * 60:
            return sym, "under 60 days of bars", None
        if d is not None and len(d):
            if getattr(d.index, "tz", None) is not None:
                d.index = d.index.tz_convert("UTC").tz_localize(None)
            j = d.index.intersection(b.index)
            if len(j) < 48 or np.median(np.abs(d.loc[j, "Close"].values / b.loc[j, "Close"].values - 1)) > 0.005:
                return sym, "Binance's %s does not match the exchange's -- a different token?" % sym, None
        d = b
    if getattr(d.index, "tz", None) is not None:
        d.index = d.index.tz_convert("UTC").tz_localize(None)
    d = d[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    d = d[~d.index.duplicated(keep="last")].sort_index()
    dc = _daily(d)
    mid = float(dc.median())
    if (np.abs(dc / mid - 1) <= 0.02).mean() >= 0.9:
        return sym, "pegged (a stablecoin)", None
    for m, mc in majors.items():
        j = dc.index.intersection(mc.index)
        if len(j) < 30:
            continue
        r = dc.loc[j] / mc.loc[j]
        if (np.abs(r / r.median() - 1) <= 0.03).mean() >= 0.9:
            return sym, "a copy of %s (wrapped or staked)" % m, None
    return sym, "kept, %d bars from %s" % (len(d), d.index[0].date()), d


def main():
    import crypto
    have = {os.path.basename(f).split("_")[0] for f in glob.glob(os.path.join("history", "*_1h.csv.gz"))}
    cu = crypto.universe(250)
    src = {str(x.sym): x.source for x in cu.itertuples()}
    want = sorted(s for s in src if s not in have)
    if "--short" in __import__("sys").argv:      # only the ones an earlier run found too short (Kraken's 720-hour cap)
        prev = io.open(os.path.join("logs", "fetch_new_coins.log"), encoding="utf-8").read().splitlines()
        want = [l.split()[0] for l in prev if "under 60 days" in l]
    majors = {m: _daily(pd.read_csv(os.path.join("history", "%s_1h.csv.gz" % m), index_col=0, parse_dates=True))
              for m in ("BTC", "ETH", "SOL")}
    log = io.open(os.path.join("logs", "fetch_new_coins%s.log" % ("_short" if "--short" in __import__("sys").argv else "")),
                  "w", encoding="utf-8", buffering=1)
    kept = 0
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        for sym, how, d in ex.map(one, [(s, src[s], majors) for s in want]):
            if d is not None:
                d.index.name = "t"
                d.to_csv(os.path.join("history", "%s_1h.csv.gz" % sym), compression="gzip")
                kept += 1
            log.write("%-10s %s\n" % (sym, how))
    log.write("\n%d of %d kept\n" % (kept, len(want)))
    log.close()
    print("%d of %d new coins kept" % (kept, len(want)))


if __name__ == "__main__":
    main()
