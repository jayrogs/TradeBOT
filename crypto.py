"""
crypto.py -- the crypto universe and its candles.

    python crypto.py universe            what is worth scanning today
    python crypto.py pull SOL 5m 2000    fetch candles

WHY THIS EXISTS SEPARATELY FROM feed.py
feed.py routes one symbol to one source. A scanner needs the other half: WHICH
symbols, ranked by something real. That turns out to need three services,
because no single one does both jobs.

    coingecko    ranking only. Aggregated volume across every exchange, so it
                 knows ENA traded $2.2B today. The only honest answer to "what
                 is hot right now"
    coinbase     candles, primary. A US venue, so its prints are closest to
                 what a US trader actually fills at, and it is the cleanest
                 source measured: 0-2% of 5m bars have open equal to close
    okx          candles, fallback only, for the handful Coinbase does not list
                 (TRX, JUP, LIT, GRAM, BOME). Same speed, but dirtier -- NEAR
                 ran 10% flat bars on OKX against 2% on Coinbase, and flat bars
                 are read by a candle detector as a long run of down candles

BINANCE.US WAS DROPPED AND IT IS WORTH SAYING WHY.
It pages 1,000 bars at a time and reaches back years, so it looked like the best
source. It is not. On the US arm, AAVE 5m candles had ZERO TRADES on 98% of
bars, and ONG on 100% -- open, high, low and close all identical, carried
forward. Any candle-pattern detector reads that as hundreds of consecutive
"down" candles. Only BTC was usable (2% flat). binance.com and bybit both
geo-block from the US (451 / 403), kraken runs 15% flat, kucoin caps at 100
bars per request.

Stablecoins are dropped from the universe. They rank near the top by volume and
never do anything a trend or a pivot could describe.
"""

import os
import time
import warnings

import pandas as pd
import requests

warnings.filterwarnings("ignore")

UA = {"User-Agent": "Mozilla/5.0"}
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "crypto")
os.makedirs(CACHE, exist_ok=True)

STABLE = {"USDT", "USDC", "USD1", "USDS", "USDG", "USDGO", "DAI", "FDUSD", "PYUSD",
          "TUSD", "USDE", "BUSD", "XAUT", "PAXG", "RLUSD"}

_UNUSED_BINANCE_IV = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
              "1h": "1h", "4h": "4h", "12h": "12h", "1d": "1d"}
COINBASE_GRAN = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "6h": 21600,
                 "1d": 86400}


# ------------------------------------------------------------------ universe

import json
import threading

# The owner trades on Coinbase and Kraken (2026-09-03), so those two
# exchanges ARE the universe. OKX stays only as a last-resort candle source.
KRAKEN_PAIRS = os.path.join(CACHE, "kraken_pairs.json")
UNIVERSE_CACHE = os.path.join(CACHE, "universe.json")
KRAKEN_IV = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240,
             "1d": 1440, "1w": 10080}
_KRAKEN_LOCK = threading.Lock()
_KRAKEN_LAST = [0.0]
KRAKEN_GAP = 0.6            # seconds between public calls (Kraken asks ~1/s)


def kraken_pairs(refresh=False):
    """base symbol -> Kraken pair name, USD pairs only. Kraken spells BTC as
    XBT and DOGE as XDG; everything else matches. Cached for a day."""
    try:
        if (not refresh and os.path.exists(KRAKEN_PAIRS)
                and time.time() - os.path.getmtime(KRAKEN_PAIRS) < 86400):
            return json.load(open(KRAKEN_PAIRS))
    except Exception:
        pass
    out = {}
    try:
        res = requests.get("https://api.kraken.com/0/public/AssetPairs",
                           headers=UA, timeout=30).json()["result"]
        for v in res.values():
            if (v.get("quote") not in ("ZUSD", "USD")
                    or v.get("status", "online") != "online"):
                continue
            ws = v.get("wsname") or ""
            base = ws.split("/")[0] if "/" in ws else v["altname"][:-3]
            base = {"XBT": "BTC", "XDG": "DOGE"}.get(base, base)
            out[base] = v["altname"]
    except Exception:
        return {}
    if out:
        os.makedirs(CACHE, exist_ok=True)
        json.dump(out, open(KRAKEN_PAIRS, "w"))
    return out


def _listed():
    """(kraken, coinbase): the base symbols each exchange trades against USD."""
    kr, cb = set(kraken_pairs()), set()
    try:
        prods = requests.get("https://api.exchange.coinbase.com/products",
                             headers=UA, timeout=25).json()
        cb = {p["base_currency"] for p in prods
              if p.get("quote_currency") == "USD"
              and p.get("status", "online") == "online"
              and not p.get("trading_disabled")}
    except Exception:
        pass
    return kr, cb


PAGES = 4                   # CoinGecko top 1000 by volume, 250 a page


def _serve(lst, n, min_volume, rank):
    keep = [x for x in lst if (x.get("volume") or 0) >= min_volume]
    if rank == "movers":
        # the owner's "great mover" view: biggest 24h gainers first
        keep.sort(key=lambda x: -(x.get("chg24") or 0))
    return pd.DataFrame(keep[:n])


def universe(n=40, min_volume=5e6, max_age=1800, rank="volume"):
    """Every Coinbase-or-Kraken USD name CoinGecko ranks in its top 1000 by
    volume, with 24h / 7d change. Coinbase is the candle source when it
    lists the name (deep history), Kraken otherwise (720 bars per
    timeframe, its API's cap).

    rank="volume" (default): most traded first, above min_volume.
    rank="movers": biggest 24h gainers first, above min_volume -- the
    "am I missing a great mover" pass (owner 2026-09-03).

    The full list is rebuilt at most every max_age seconds and cached; the
    floor and the ranking are applied when serving. CoinGecko's free tier
    throttles fast and a throttled page silently shrinks the universe
    (2026-09-03: 172 of 270 names scanned), so a partial pull is refused
    whenever a complete list is on disk."""
    cached = None
    try:
        if os.path.exists(UNIVERSE_CACHE):
            cached = json.load(open(UNIVERSE_CACHE)) or None
            if cached and time.time() - os.path.getmtime(UNIVERSE_CACHE) < max_age:
                return _serve(cached, n, min_volume, rank)
    except Exception:
        cached = None
    rows, pages = [], 0
    for page in range(1, PAGES + 1):
        try:
            r = requests.get("https://api.coingecko.com/api/v3/coins/markets",
                             params={"vs_currency": "usd", "order": "volume_desc",
                                     "per_page": 250, "page": page,
                                     "price_change_percentage": "24h,7d"},
                             headers=UA, timeout=30).json()
        except Exception:
            break
        if not isinstance(r, list):
            break
        rows += r
        pages += 1
        time.sleep(1.5)
    if pages < PAGES and cached:
        return _serve(cached, n, min_volume, rank)
    kr, cb = _listed()
    out, seen = [], set()
    for x in rows:
        s = str(x.get("symbol", "")).upper()
        if s in STABLE or not s or s in seen:
            continue
        src = "coinbase" if s in cb else ("kraken" if s in kr else None)
        if src is None:
            continue
        seen.add(s)
        out.append(dict(sym=s, source=src, volume=x.get("total_volume") or 0,
                        price=x.get("current_price"),
                        chg24=x.get("price_change_percentage_24h") or 0.0,
                        chg7d=x.get("price_change_percentage_7d_in_currency")
                        or 0.0))
    if out:
        try:
            os.makedirs(CACHE, exist_ok=True)
            json.dump(out, open(UNIVERSE_CACHE, "w"))
        except Exception:
            pass
    elif cached:
        out = cached
    return _serve(out, n, min_volume, rank)


# ------------------------------------------------------------------ candles

OKX_BAR = {"1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m",
           "1h": "1H", "2h": "2H", "4h": "4H", "6h": "6H", "12h": "12H",
           "1d": "1D"}


def _okx(sym, interval, bars):
    """OKX history-candles, paginated. Newest first, 300 per request."""
    bar = OKX_BAR.get(interval)
    if bar is None:
        return None
    rows, after = [], None
    for _ in range(max(40, bars // 300 + 8)):
        p = {"instId": "%s-USDT" % sym, "bar": bar, "limit": 300}
        if after:
            p["after"] = after
        try:
            r = requests.get("https://www.okx.com/api/v5/market/history-candles",
                             params=p, headers=UA, timeout=25)
        except Exception:
            break
        if r.status_code != 200:
            break
        js = (r.json() or {}).get("data") or []
        if not js:
            break
        rows += js
        after = js[-1][0]
        if len(rows) >= bars:
            break
        time.sleep(0.12)
    if not rows:
        return None
    d = pd.DataFrame(rows).iloc[:, :6]
    d.columns = ["ts", "Open", "High", "Low", "Close", "Volume"]
    d["t"] = pd.to_datetime(d.ts.astype("int64"), unit="ms")
    for k in ("Open", "High", "Low", "Close", "Volume"):
        d[k] = d[k].astype(float)
    d = d.set_index("t")[["Open", "High", "Low", "Close", "Volume"]].sort_index()
    d = d[~d.index.duplicated()]
    return d.tail(bars)


def _coinbase(sym, interval, bars):
    g = COINBASE_GRAN.get(interval)
    if g is None:
        return None
    frames = []
    end = pd.Timestamp.utcnow().tz_localize(None)
    for _ in range(max(40, bars // 300 + 8)):
        start = end - pd.Timedelta(seconds=g * 300)
        try:
            r = requests.get(
                "https://api.exchange.coinbase.com/products/%s-USD/candles" % sym,
                params={"granularity": g, "start": start.isoformat(),
                        "end": end.isoformat()}, headers=UA, timeout=25)
        except Exception:
            break
        if r.status_code != 200:
            break
        js = r.json()
        if not js:
            break
        d = pd.DataFrame(js, columns=["t", "low", "high", "open", "close", "vol"])
        d["t"] = pd.to_datetime(d.t, unit="s")
        frames.append(d.set_index("t")[["open", "high", "low", "close", "vol"]])
        if sum(len(f) for f in frames) >= bars:
            break
        end = start
        time.sleep(0.25)
    if not frames:
        return None
    out = pd.concat(frames).sort_index()
    out = out[~out.index.duplicated()]
    out.columns = ["Open", "High", "Low", "Close", "Volume"]
    return out.tail(bars)


def _kraken(sym, interval, bars):
    """Kraken serves at most 720 bars per interval (plus the live one) and
    wants roughly one public call a second, so one lock paces every worker
    thread through it. Same frame shape as _coinbase (UTC-naive index)."""
    iv = KRAKEN_IV.get(interval)
    pair = kraken_pairs().get(sym)
    if iv is None or pair is None:
        return None
    r = {}
    for attempt in range(2):
        with _KRAKEN_LOCK:
            wait = _KRAKEN_LAST[0] + KRAKEN_GAP - time.time()
            if wait > 0:
                time.sleep(wait)
            try:
                r = requests.get("https://api.kraken.com/0/public/OHLC",
                                 params={"pair": pair, "interval": iv},
                                 headers=UA, timeout=30).json()
            except Exception:
                r = {}
            _KRAKEN_LAST[0] = time.time()
        err = " ".join(r.get("error") or [])
        if "Too many" in err or "Rate limit" in err:
            time.sleep(3.0)
            continue
        break
    res = r.get("result") or {}
    key = next((k for k in res if k != "last"), None)
    if key is None or not res[key]:
        return None
    d = pd.DataFrame(res[key], columns=["t", "open", "high", "low", "close",
                                        "vwap", "vol", "n"])
    d["t"] = pd.to_datetime(d["t"].astype(int), unit="s")
    out = d.set_index("t")[["open", "high", "low", "close", "vol"]].astype(float)
    out = out[~out.index.duplicated()].sort_index()
    out.columns = ["Open", "High", "Low", "Close", "Volume"]
    return out.tail(bars)


_SOURCES = {"coinbase": _coinbase, "kraken": _kraken, "okx": _okx}
_ORDER = {"kraken": ("kraken", "coinbase", "okx"),
          "okx": ("okx", "coinbase", "kraken")}


def candles(sym, interval="5m", bars=1000, source=None, refresh=False):
    """OHLCV for one coin. Cached, because a scan asks for the same bars often."""
    tag = "%s_%s_%d.csv" % (sym, interval, bars)
    path = os.path.join(CACHE, tag)
    if os.path.exists(path) and not refresh:
        age = time.time() - os.path.getmtime(path)
        if age < 240:                       # 4 minutes is fresh enough to scan on
            try:
                return pd.read_csv(path, index_col=0, parse_dates=True)
            except Exception:
                pass
    d = None
    order = _ORDER.get(source, ("coinbase", "kraken", "okx"))
    if source == "kraken" and bars > 720:
        # Kraken's API stops at 720 bars. For deep history (the forward log
        # needs 900 hourly, the monthly frame 1600 daily) try OKX's longer
        # series of the same market first, then settle for Kraken's 720.
        order = ("okx", "kraken", "coinbase")
    for src in order:
        d = _SOURCES[src](sym, interval, bars)
        if d is not None and len(d) >= 30:
            break
    if d is None or len(d) < 30:
        return None
    d.to_csv(path)
    d.attrs["source"] = src          # which exchange actually served it
    return d


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "pull":
        sym = sys.argv[2].upper()
        iv = sys.argv[3] if len(sys.argv) > 3 else "5m"
        n = int(sys.argv[4]) if len(sys.argv) > 4 else 1000
        d = candles(sym, iv, n, refresh=True)
        print("  %s %s: %s bars" % (sym, iv, len(d) if d is not None else "none"))
        if d is not None:
            print("  %s -> %s" % (d.index[0], d.index[-1]))
    else:
        u = universe(40)
        print("=" * 66)
        print("  CRYPTO UNIVERSE -- %d names, ranked by real 24h volume" % len(u))
        print("=" * 66)
        print("  %-8s %10s %12s %9s %s" % ("sym", "price", "24h vol", "chg", "source"))
        for _, x in u.iterrows():
            print("  %-8s %10.4g %11.0fM %+8.1f%% %s"
                  % (x["sym"], x["price"], x["volume"] / 1e6, x["chg24"], x["source"]))
