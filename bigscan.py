"""
bigscan.py -- scan EVERY market for the behaviors we have detectors for.

    python bigscan.py --build            assemble the universe (once a week)
    python bigscan.py                    scan it
    python bigscan.py --tier1-only       just the liquidity/activity pass
    python bigscan.py --json out.json

WHAT "EVERY MARKET" ACTUALLY MEANS
    US equities + ETFs   ~13,200 symbols from the Nasdaq daily symbol files
    crypto                 ~620 assets tradeable on Coinbase or OKX
    futures/commodities     57 continuous contracts -- index, rates, currency,
                            energy, metals, grains, softs, livestock
    forex                   32 pairs, majors and crosses

Every futures and forex symbol in the lists below was checked against Yahoo and
returns data. Eight plausible-looking ones did not and were removed rather than
left in to fail silently at scan time.

WHY IT IS TIERED
A full 5-minute sweep of 13,000 names is ~7 minutes of downloading and ~11
minutes of detector time, and most of it is wasted: thousands of those symbols
trade under $100k a day and have 5m candles that are mostly flat -- the same
problem that made binance.us useless, but from illiquidity rather than a bad
exchange. A flat candle is read by a candle detector as a run of down candles,
so scanning them does not just cost time, it produces garbage.

    TIER 1   daily bars for everything, cached. Filter on dollar volume and on
             whether the thing has actually moved. Cheap, and it cuts ~13,800
             names to the few thousand worth looking at intraday.
    TIER 2   5m/15m/1h/4h for the survivors, then every detector.

WHAT IT LOOKS FOR
The same behaviors as scanner.py -- trend state, the EMA rider, the oversold
backburner prints, stair steps, RSI relative to a name's own history. The trend engine and
the rider were each graded against blind chart samples. The backburner and the
stair-step counts are detectors only; fading a stair step tested negative on
25,000 events and is reported as context, never as a signal.

Ranking sorts attention. It is not a probability of profit.
"""

import argparse
import json
import os
import time
import warnings

import numpy as np
import pandas as pd

import panel as P
import scanner as SC

warnings.filterwarnings("ignore")

UNIVERSE = os.path.join("cache", "universe.csv")
TIER1 = os.path.join("cache", "tier1.csv")
UA = {"User-Agent": "Mozilla/5.0"}

FUTURES = ["ES=F", "NQ=F", "YM=F", "RTY=F", "NKD=F", "ZB=F", "ZN=F",
           "ZF=F", "ZT=F", "UB=F", "6E=F", "6J=F", "6B=F", "6A=F",
           "6C=F", "6S=F", "6N=F", "6M=F", "6L=F", "BTC=F", "ETH=F",
           "MES=F", "MNQ=F", "M2K=F", "MYM=F", "SI=F", "CL=F", "BZ=F",
           "NG=F", "RB=F", "HO=F", "QM=F", "QG=F", "GC=F", "MGC=F",
           "SIL=F", "HG=F", "PL=F", "PA=F", "ALI=F", "ZC=F", "ZS=F",
           "ZW=F", "ZM=F", "ZL=F", "ZO=F", "ZR=F", "KE=F", "KC=F",
           "SB=F", "CC=F", "CT=F", "OJ=F", "LE=F", "GF=F", "HE=F",
           "DC=F"]
FOREX = ["EURUSD=X", "USDJPY=X", "GBPUSD=X", "AUDUSD=X", "USDCAD=X", "USDCHF=X", "NZDUSD=X",
         "EURJPY=X", "GBPJPY=X", "EURGBP=X", "AUDJPY=X", "EURAUD=X", "EURCHF=X", "CADJPY=X",
         "CHFJPY=X", "NZDJPY=X", "AUDNZD=X", "AUDCAD=X", "GBPAUD=X", "GBPCAD=X", "GBPCHF=X",
         "EURCAD=X", "EURNZD=X", "USDMXN=X", "USDZAR=X", "USDTRY=X", "USDSEK=X", "USDNOK=X",
         "USDSGD=X", "USDHKD=X", "USDCNY=X", "USDINR=X"]

# 57 futures & commodities, 32 forex -- every one verified to return
# data from Yahoo. Eight candidates were dropped as delisted or 404:
# EMD=F GE=F SR3=F 6R=F DX=F VX=F MWE=F LBS=F


# ------------------------------------------------------------- the universe

def build_universe():
    """Every symbol we could possibly look at, with its asset class."""
    import io
    import requests
    rows = []

    for url, col, kind in [
            ("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
             "Symbol", "equity"),
            ("https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
             "ACT Symbol", "equity")]:
        try:
            r = requests.get(url, headers=UA, timeout=40)
            d = pd.read_csv(io.StringIO(r.text), sep="|")
            d = d[~d[col].astype(str).str.startswith("File Creation")]
            if "Test Issue" in d:
                d = d[d["Test Issue"] != "Y"]
            etf = d["ETF"] if "ETF" in d else pd.Series("N", index=d.index)
            for s, e in zip(d[col].astype(str), etf.astype(str)):
                if s and s.isalpha() and len(s) <= 5:
                    rows.append(dict(symbol=s, kind="etf" if e == "Y" else kind,
                                     source="yahoo"))
        except Exception as ex:
            print("  %s failed: %s" % (url.rsplit("/", 1)[-1], ex))

    try:
        import crypto
        kr, cb = crypto._listed()
        for s in sorted(cb | kr):
            rows.append(dict(symbol=s, kind="crypto",
                             source="coinbase" if s in cb else "kraken"))
    except Exception as ex:
        print("  crypto list failed: %s" % ex)

    for s in FUTURES:
        rows.append(dict(symbol=s, kind="future", source="yahoo"))
    for s in FOREX:
        rows.append(dict(symbol=s, kind="forex", source="yahoo"))

    u = pd.DataFrame(rows).drop_duplicates("symbol")
    os.makedirs("cache", exist_ok=True)
    u.to_csv(UNIVERSE, index=False)
    print("  universe: %d symbols" % len(u))
    print(u.kind.value_counts().to_string())
    return u


# ------------------------------------------------------------- tier 1

def tier1(u, chunk=200, min_dollar=2e6, min_atr=0.005):
    """Daily bars for everything. Keep what is liquid and actually moves."""
    import yfinance as yf
    yh = u[u.source == "yahoo"].symbol.tolist()
    kind = dict(zip(u.symbol, u.kind))
    # Futures and forex are already a curated, hand-verified list, and Yahoo
    # reports no volume for FX and inconsistent volume for continuous futures.
    # Filtering them on dollar volume dropped all 32 FX pairs and 32 of 57
    # futures on the first run.
    exempt = {"future", "forex"}
    keep = []
    t0 = time.time()
    for i in range(0, len(yh), chunk):
        part = yh[i:i + chunk]
        try:
            d = yf.download(part, period="3mo", interval="1d", progress=False,
                            auto_adjust=False, group_by="ticker", threads=True)
        except Exception:
            continue
        for s in part:
            try:
                c = d[(s, "Close")].dropna()
                v = d[(s, "Volume")].dropna()
                h = d[(s, "High")].dropna()
                l = d[(s, "Low")].dropna()
            except Exception:
                continue
            if len(c) < (10 if kind.get(s) in exempt else 30):
                continue
            dollar = float(np.nanmedian(c.values[-30:] * v.values[-30:]))
            rng = float(np.nanmedian((h.values[-30:] - l.values[-30:])
                                     / np.where(c.values[-30:] > 0,
                                                c.values[-30:], np.nan)))
            if kind.get(s) in exempt or (dollar >= min_dollar
                                         and rng >= min_atr):
                keep.append(dict(symbol=s, dollar=dollar, rng=rng,
                                 price=float(c.values[-1])))
        done = min(i + chunk, len(yh))
        print("  tier1 %d/%d  kept %d  (%.0fs)" % (done, len(yh), len(keep),
                                                   time.time() - t0))

    for _, x in u[u.source != "yahoo"].iterrows():
        keep.append(dict(symbol=x["symbol"], dollar=np.nan, rng=np.nan,
                         price=np.nan))

    k = pd.DataFrame(keep)
    k = k.merge(u[["symbol", "kind", "source"]], on="symbol", how="left")
    k.to_csv(TIER1, index=False)
    print("  tier1 kept %d of %d" % (len(k), len(u)))
    return k


# ------------------------------------------------------------- tier 2

def fetch_yahoo_batch(syms, interval, period, chunk=120):
    import yfinance as yf
    out = {}
    for i in range(0, len(syms), chunk):
        part = syms[i:i + chunk]
        try:
            d = yf.download(part, interval=interval, period=period,
                            progress=False, auto_adjust=False,
                            group_by="ticker", threads=True)
        except Exception:
            continue
        for s in part:
            try:
                f = d[s].dropna()
            except Exception:
                continue
            if len(f) >= 60:
                out[s] = f
    return out


def tier2(names, tfs=("5m", "15m", "1h", "4h", "12h", "1d", "1w", "1mo"),
          limit=None):
    """Intraday for the survivors, then every detector.

    Only the four BASE frames are downloaded; 4h/12h come off the 1h and
    weekly/monthly off the daily, exactly as scanner.py does it. An earlier
    version fetched each timeframe directly, which meant 4h, 12h, weekly and
    monthly were simply absent -- Yahoo serves none of them.
    """
    if limit:
        names = names.head(limit)
    yh = names[names.source == "yahoo"].symbol.tolist()
    cx = names[names.source != "yahoo"]

    period = {"5m": "1mo", "15m": "59d", "1h": "2y", "1d": "10y"}
    need = sorted({SC.BASE[t] for t in tfs if t in SC.BASE} |
                  {SC.BASE[SC.DERIVE[t][0]] for t in tfs if t in SC.DERIVE})
    pre = {}
    for base in need:
        t0 = time.time()
        got = fetch_yahoo_batch(yh, base, period.get(base, "1mo"))
        for sym, f in got.items():
            pre[(sym, base)] = f
        print("  %s: %d/%d symbols in %.0fs" % (base, len(got), len(yh),
                                                time.time() - t0))

    def prefetched(sym, source, base):
        return pre.get((sym, base))

    rows = []
    for s in yh:
        fr = SC.frames_for(s, "yahoo", list(tfs), prefetched)
        per = {}
        for tf in tfs:
            try:
                per[tf] = SC.read_tf(fr.get(tf))
            except Exception:
                per[tf] = None
        if not any(per.values()):
            continue
        fl = SC.flags(per)
        if not fl:
            continue
        row = names[names.symbol == s].iloc[0]
        rows.append(dict(sym=s, kind=row["kind"], price=row.get("price"),
                         dollar=row.get("dollar"), tfs=per,
                         source=row.get("source"),
                         flags=[{"key": k, "why": w, "wt": t} for k, w, t in fl],
                         score=SC.score(fl)))

    if len(cx):
        from concurrent.futures import ThreadPoolExecutor
        pairs = [(x["symbol"], x["source"]) for _, x in cx.iterrows()]
        jobs = [(sym, src, b) for sym, src in pairs
                for b in ("5m", "15m", "1h", "1d")]

        def grab(job):
            sym, src, b = job
            try:
                return (sym, b), SC._crypto_fetch(sym, src, b)
            except Exception:
                return (sym, b), None

        cpre = {}
        with ThreadPoolExecutor(max_workers=8) as ex:
            for key, df in ex.map(grab, jobs):
                if df is not None:
                    cpre[key] = df

        def cfetch(sym, source, base):
            return cpre.get((sym, base))

        for sym, src in pairs:
            fr = SC.frames_for(sym, src, list(tfs), cfetch)
            per = {}
            for tf in tfs:
                try:
                    per[tf] = SC.read_tf(fr.get(tf))
                except Exception:
                    per[tf] = None
            if not any(per.values()):
                continue
            fl = SC.flags(per)
            if not fl:
                continue
            rows.append(dict(sym=sym, kind="crypto", price=None, dollar=None,
                             tfs=per,
                             flags=[{"key": k, "why": w, "wt": t}
                                    for k, w, t in fl],
                             score=SC.score(fl)))

    rows.sort(key=lambda r: (-r["score"],
                             -(r["dollar"] if r["dollar"] and
                               np.isfinite(r["dollar"]) else 0)))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--tier1", action="store_true")
    ap.add_argument("--tier1-only", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--tf", default="5m,15m,1h,4h,12h,1d,1w,1mo")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    if a.build or not os.path.exists(UNIVERSE):
        u = build_universe()
    else:
        u = pd.read_csv(UNIVERSE)
        print("  universe: %d symbols (cached)" % len(u))

    if a.tier1 or a.tier1_only or not os.path.exists(TIER1):
        k = tier1(u)
    else:
        k = pd.read_csv(TIER1)
        print("  tier1: %d liquid names (cached)" % len(k))
    if a.tier1_only:
        return

    tfs = [t.strip() for t in a.tf.split(",") if t.strip()]
    t0 = time.time()
    rows = tier2(k, tfs, a.limit)
    print("\n  scanned in %.0fs -- %d names firing something" % (time.time() - t0,
                                                                len(rows)))
    if a.json:
        json.dump(rows, open(a.json, "w"), indent=1, default=float)
        print("  wrote %s" % a.json)

    short = {"UP": "U", "DOWN": "D", "BALANCE": "E", "FLAT": "."}
    print("\n" + "=" * 104)
    print("  ALL-MARKET SCAN  %s   %s" %
          (pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), "/".join(tfs)))
    print("=" * 104)
    print("  %-8s %-7s %10s %11s  %-10s %s"
          % ("sym", "kind", "price", "$vol/day", " ".join(tfs), "firing"))
    print("  " + "-" * 100)
    for r in rows[:60]:
        seq = " ".join(short.get((r["tfs"].get(t) or {}).get("trend", "FLAT"), ".")
                       for t in tfs)
        dv = ("%10.0fM" % (r["dollar"] / 1e6)) if r["dollar"] and \
            np.isfinite(r["dollar"]) else "         -"
        px = ("%10.4g" % r["price"]) if r["price"] and np.isfinite(r["price"]) \
            else "         -"
        print("  %-8s %-7s %s %s  %-10s %s"
              % (r["sym"], r["kind"], px, dv, seq,
                 ", ".join(f["key"] for f in r["flags"][:4] if f["wt"])))


if __name__ == "__main__":
    main()
