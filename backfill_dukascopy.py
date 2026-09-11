"""backfill_dukascopy.py -- deep intraday forex (and index / commodity CFD)
history from Dukascopy's free datafeed. No key. Minute bars back ~20 years.

    python backfill_dukascopy.py --test                  # one month of EURUSD, checked against Yahoo daily closes
    python backfill_dukascopy.py                         # every pair in bigscan.FOREX + the CFD proxies, 4 years
    python backfill_dukascopy.py --names EURUSD XAUUSD --years 2

Format: one LZMA-compressed file per instrument per day,
  https://datafeed.dukascopy.com/datafeed/<INSTR>/<YYYY>/<MM-1>/<DD>/BID_candles_min_1.bi5
  records of 24 bytes, big-endian: time offset (ms), open, close, low, high
  (ints, scaled), volume (float). Month is ZERO-based in the URL.
Scaling differs per instrument (1e5 for most FX, 1e3 for JPY pairs and most
CFDs); --test derives it by matching Yahoo's daily close, and the chosen
scale is stored beside the data so the study never has to guess.

Writes history/forex/<NAME>_{5m,15m,1h}.csv.gz resampled from the minutes
(UTC), where NAME is the Yahoo-style symbol with '=' -> '_' so the study's
loaders find them, plus history/futures_cfd/<NAME>_*.csv.gz for the proxies.
Resumable: skips days already on disk (kept in a per-instrument parquet of
minute bars).
"""

import argparse
import io
import lzma
import os
import struct
import sys
import time

import numpy as np
import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0"}
URL = "https://datafeed.dukascopy.com/datafeed/%s/%04d/%02d/%02d/BID_candles_min_1.bi5"
REC = struct.Struct(">3i2if")

# Yahoo symbol -> Dukascopy instrument. FX pairs are the same letters.
FX = {"EURUSD=X": "EURUSD", "USDJPY=X": "USDJPY", "GBPUSD=X": "GBPUSD",
      "AUDUSD=X": "AUDUSD", "USDCAD=X": "USDCAD", "USDCHF=X": "USDCHF",
      "NZDUSD=X": "NZDUSD", "EURGBP=X": "EURGBP", "EURJPY=X": "EURJPY",
      "GBPJPY=X": "GBPJPY", "EURCHF=X": "EURCHF", "AUDJPY=X": "AUDJPY",
      "EURAUD=X": "EURAUD", "EURCAD=X": "EURCAD", "GBPCHF=X": "GBPCHF",
      "CADJPY=X": "CADJPY", "CHFJPY=X": "CHFJPY", "NZDJPY=X": "NZDJPY",
      "GBPAUD=X": "GBPAUD", "GBPCAD=X": "GBPCAD", "AUDCAD=X": "AUDCAD",
      "AUDNZD=X": "AUDNZD", "EURNZD=X": "EURNZD", "USDMXN=X": "USDMXN",
      "USDZAR=X": "USDZAR", "USDSEK=X": "USDSEK", "USDNOK=X": "USDNOK",
      "USDSGD=X": "USDSGD", "USDHKD=X": "USDHKD", "USDTRY=X": "USDTRY",
      "USDPLN=X": "USDPLN", "USDINR=X": "USDINR"}
# futures the owner watches -> the Dukascopy CFD that tracks them
CFD = {"ES=F": "USA500IDXUSD", "NQ=F": "USATECHIDXUSD", "YM=F": "USA30IDXUSD",
       "RTY=F": "USSC2000IDXUSD", "GC=F": "XAUUSD", "SI=F": "XAGUSD",
       "CL=F": "LIGHTCMDUSD", "BZ=F": "BRENTCMDUSD", "NG=F": "GASCMDUSD",
       "HG=F": "COPPERCMDUSD", "ZB=F": "USTBONDTRUSD", "ZN=F": "USTNOTETRUSD",
       "FDAX": "DEUIDXEUR", "FESX": "EUSIDXEUR", "NKD=F": "JPNIDXJPY",
       "PL=F": "XPTCMDUSD", "PA=F": "XPDCMDUSD"}
SCALES = (1e5, 1e3, 1e2, 1e1, 1.0)


def fetch_day(instr, day):
    """Minute bars for one UTC day, prices UNSCALED (ints), or None."""
    url = URL % (instr, day.year, day.month - 1, day.day)
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=30)
        except Exception:
            time.sleep(1.5)
            continue
        if r.status_code == 404 or (r.status_code == 200 and not r.content):
            return pd.DataFrame()                 # weekend / holiday
        if r.status_code != 200:
            time.sleep(1.5)
            continue
        try:
            raw = lzma.decompress(r.content)
        except lzma.LZMAError:
            return pd.DataFrame()
        n = len(raw) // REC.size
        rows = [REC.unpack_from(raw, k * REC.size) for k in range(n)]
        d = pd.DataFrame(rows, columns=["ms", "o", "c", "l", "h", "v"])
        # BUG until 2026-09-08: this field is SECONDS from midnight, not milliseconds. Reading it
        # as ms put a whole day's 1440 bars inside the first 86 seconds, so the "1h" files came out
        # with one bar a day. Repaired stores with fix_dukascopy_clock.py; nothing was re-downloaded.
        d["t"] = pd.Timestamp(day) + pd.to_timedelta(d["ms"], unit="s")
        return d.set_index("t")[["o", "h", "l", "c", "v"]]
    return None


def minutes(instr, start, end, store):
    """All minute bars from start to end, cached per instrument in parquet."""
    have = None
    if os.path.exists(store):
        try:
            have = pd.read_parquet(store)
        except Exception:
            have = None
    days = pd.date_range(start.normalize(), end.normalize(), freq="D")
    done = set(have.index.normalize().unique()) if have is not None else set()
    frames = [have] if have is not None else []
    t0, got = time.time(), 0
    for k, day in enumerate(days):
        if day in done or day.weekday() == 5:      # saturday: closed
            continue
        d = fetch_day(instr, day)
        if d is None:
            continue
        if len(d):
            frames.append(d)
            got += 1
        if k % 200 == 0 and frames:
            pd.concat(frames).sort_index().to_parquet(store)
    if not frames:
        return None
    out = pd.concat(frames)
    out = out[~out.index.duplicated()].sort_index()
    out.to_parquet(store)
    print("    %s: %d minute bars, %d new days (%.0fs)" % (instr, len(out), got,
                                                          time.time() - t0), flush=True)
    return out


def pick_scale(instr, m):
    """Which divisor makes the daily close agree with Yahoo? Falls back to the
    JPY/FX rule when Yahoo has nothing."""
    ysym = next((y for y, d in list(FX.items()) + list(CFD.items()) if d == instr), None)
    try:
        import yfinance as yf
        y = yf.download(ysym, period="1mo", interval="1d", progress=False,
                        auto_adjust=False)["Close"].dropna()
        y = y.iloc[:, 0] if hasattr(y, "columns") else y
        y.index = pd.to_datetime(y.index).tz_localize(None)
        ours = m["c"].resample("1D").last().dropna()
        common = ours.index.intersection(y.index)
        if len(common) >= 5:
            best = min(SCALES, key=lambda s: float(np.median(np.abs(
                ours.loc[common].values / s / y.loc[common].values - 1))))
            err = float(np.median(np.abs(ours.loc[common].values / best / y.loc[common].values - 1)))
            return best, err
    except Exception:
        pass
    return (1e3 if ("JPY" in instr or not instr.isalpha() or len(instr) > 6) else 1e5), None


def resample(m, scale):
    p = m[["o", "h", "l", "c"]].astype(float) / scale
    p.columns = ["Open", "High", "Low", "Close"]
    p["Volume"] = m["v"].astype(float)
    out = {}
    for tf, rule in (("5m", "5min"), ("15m", "15min"), ("1h", "1h")):
        o = p.resample(rule).agg({"Open": "first", "High": "max", "Low": "min",
                                  "Close": "last", "Volume": "sum"}).dropna()
        out[tf] = o
    return out


def run(pairs, years, out_dir, tag):
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join("cache", "dukascopy"), exist_ok=True)
    end = pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=1)
    start = end - pd.Timedelta(days=365 * years)
    for ysym, instr in pairs.items():
        store = os.path.join("cache", "dukascopy", instr + ".parquet")
        m = minutes(instr, start, end, store)
        if m is None or len(m) < 1000:
            print("  %-10s %-16s nothing" % (ysym, instr), flush=True)
            continue
        scale, err = pick_scale(instr, m)
        frames = resample(m, scale)
        name = ysym.replace("=", "_")
        for tf, f in frames.items():
            f.to_csv(os.path.join(out_dir, "%s_%s.csv.gz" % (name, tf)), compression="gzip")
        print("  %-10s %-16s scale 1e%d  yahoo-match err %s  1h bars %d  %s -> %s" % (
            ysym, instr, int(np.log10(scale)), "n/a" if err is None else "%.2f%%" % (100 * err),
            len(frames["1h"]), frames["1h"].index[0].date(), frames["1h"].index[-1].date()),
            flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--names", nargs="*")
    ap.add_argument("--years", type=float, default=4.1)
    a = ap.parse_args()
    os.makedirs(os.path.join("cache", "dukascopy"), exist_ok=True)
    if a.test:
        end = pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=1)
        m = minutes("EURUSD", end - pd.Timedelta(days=31), end,
                    os.path.join("cache", "dukascopy", "EURUSD_test.parquet"))
        scale, err = pick_scale("EURUSD", m)
        print("  EURUSD: scale 1e%d, median error vs Yahoo daily close %s" % (
            int(np.log10(scale)), "n/a" if err is None else "%.3f%%" % (100 * err)))
        print(resample(m, scale)["1h"].tail(3).to_string())
        return
    fx = {k: v for k, v in FX.items() if not a.names or k in a.names or v in a.names}
    cfd = {k: v for k, v in CFD.items() if not a.names or k in a.names or v in a.names}
    if fx:
        run(fx, a.years, os.path.join("history", "forex"), "forex")
    if cfd:
        run(cfd, a.years, os.path.join("history", "futures_cfd"), "cfd")
    print("  done", flush=True)


if __name__ == "__main__":
    main()
