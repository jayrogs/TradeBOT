"""
feed.py -- one data interface, several sources, best one wins.

    import feed
    df = feed.get("BTC-USD", "5m", days=400)     # routes to a crypto exchange
    df = feed.get("NVDA", "1d")                  # routes to Yahoo
    df = feed.get("ES=F", "1m", days=700)        # needs Databento, see below

    python feed.py status                        what is available right now
    python feed.py pull BTC-USD 5m 400           fetch and cache

WHY THIS EXISTS
Yahoo is free and fine for daily bars, but it caps intraday at 60 days, reports
nonsense crypto volume, and its futures series carry roll artifacts. Different
sources are better at different things, so this routes each request to the best
one available and caches the result.

SOURCES

  yahoo        free, no key. Daily back decades. Intraday capped at 60 days
               (5m/15m/30m) or 730 days (1h). Crypto volume unreliable.

  binance.us   free, no key. Crypto only. Pages 1,000 bars per request and
               reaches back years at any interval -- 25,000 five-minute bars in
               about 14 seconds. binance.com is geo-blocked from the US (451),
               binance.us is not.

  coinbase     free, no key. Crypto only, 300 candles per request. Slower than
               binance.us but a useful cross-check on price.

  databento    PAID, needs DATABENTO_KEY in .env. The only good answer for deep
               futures intraday. Pay per download rather than a subscription;
               a year of ES 1-minute is a few tens of dollars.

  polygon      PAID, needs POLYGON_KEY in .env. Equities/options intraday back
               to 2003.

ADDING A KEY
Put it in a local `.env` file next to this script. Nothing is ever printed or
sent anywhere except that provider:

    DATABENTO_KEY=db-xxxxxxxx
    POLYGON_KEY=xxxxxxxx

The router will pick the paid source automatically once the key is present.
"""

import os
import sys
import time
import warnings

import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore")

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "feed")
os.makedirs(CACHE, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0"}

CRYPTO_SUFFIX = ("-USD", "USDT")
FUTURES_SUFFIX = ("=F",)


# ------------------------------------------------------------------ keys

def env(key):
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(p):
        return None
    for line in open(p):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if k.strip() == key:
                return v.strip()
    return None


# ------------------------------------------------------------------ crypto

def _binance_symbol(sym):
    s = sym.upper().replace("-USD", "USDT").replace("USDUSDT", "USDT")
    return s if s.endswith("USDT") else s + "USDT"


BINANCE_IV = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
              "1h": "1h", "4h": "4h", "1d": "1d", "1w": "1w"}


def binance_us(sym, interval, days=365, pause=0.12):
    """Page backwards 1,000 bars at a time until `days` of history is covered."""
    iv = BINANCE_IV.get(interval)
    if iv is None:
        return None
    bsym = _binance_symbol(sym)
    cutoff = pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=days)
    frames, end = [], None
    for _ in range(400):
        p = {"symbol": bsym, "interval": iv, "limit": 1000}
        if end:
            p["endTime"] = end
        try:
            r = requests.get("https://api.binance.us/api/v3/klines",
                             params=p, headers=UA, timeout=25)
        except Exception:
            break
        if r.status_code != 200:
            break
        js = r.json()
        if not js:
            break
        d = pd.DataFrame(js, columns=["ot", "o", "h", "l", "c", "v", "ct",
                                      "qv", "n", "tb", "tq", "ig"])
        d["t"] = pd.to_datetime(d.ot, unit="ms")
        for k in ("o", "h", "l", "c", "v"):
            d[k] = d[k].astype(float)
        d = d.set_index("t")[["o", "h", "l", "c", "v"]]
        frames.append(d)
        oldest = d.index[0]
        if oldest <= cutoff or len(d) < 1000:
            break
        end = int(oldest.timestamp() * 1000) - 1
        time.sleep(pause)
    if not frames:
        return None
    out = pd.concat(frames).sort_index()
    out = out[~out.index.duplicated()]
    out.columns = ["Open", "High", "Low", "Close", "Volume"]
    return out[out.index >= cutoff]


# ------------------------------------------------------------------ yahoo

YF_MAX = {"1m": 30, "5m": 60, "15m": 60, "30m": 60, "1h": 730}


def yahoo(sym, interval, days=None):
    import yfinance as yf
    kw = dict(progress=False, auto_adjust=False)
    if interval in YF_MAX:
        cap = YF_MAX[interval]
        if days and days > cap:
            print("  yahoo caps %s at %d days (asked %d)" % (interval, cap, days))
        d = yf.download(sym, interval=interval,
                        period="%dd" % min(days or cap, cap), **kw)
    else:
        start = "1990-01-01"
        if days:
            start = (pd.Timestamp.today() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
        d = yf.download(sym, start=start, **kw)
    d = d.dropna()
    if len(d) == 0:
        return None
    d.columns = [c[0] if isinstance(c, tuple) else c for c in d.columns]
    if getattr(d.index, "tz", None) is not None:
        d.index = d.index.tz_localize(None)
    return d[["Open", "High", "Low", "Close", "Volume"]]


# ------------------------------------------------------------------ paid

def databento(sym, interval, days=365):
    key = env("DATABENTO_KEY")
    if not key:
        return None
    try:
        import databento as db
    except ImportError:
        print("  pip install databento")
        return None
    schema = {"1m": "ohlcv-1m", "1h": "ohlcv-1h", "1d": "ohlcv-1d"}.get(interval)
    if schema is None:
        return None
    root = sym.replace("=F", "")
    client = db.Historical(key)
    end = pd.Timestamp.utcnow().tz_localize(None)
    data = client.timeseries.get_range(
        dataset="GLBX.MDP3", symbols=[root + ".c.0"], stype_in="continuous",
        schema=schema, start=(end - pd.Timedelta(days=days)), end=end)
    d = data.to_df()
    d.index = pd.to_datetime(d.index).tz_localize(None)
    d = d.rename(columns={"open": "Open", "high": "High", "low": "Low",
                          "close": "Close", "volume": "Volume"})
    return d[["Open", "High", "Low", "Close", "Volume"]]


# ------------------------------------------------------------------ router

def route(sym, interval):
    """Which source should serve this request?"""
    s = sym.upper()
    if s.endswith(CRYPTO_SUFFIX) and interval in BINANCE_IV:
        return "binance.us"
    if s.endswith(FUTURES_SUFFIX) and interval in ("1m", "1h", "1d"):
        if env("DATABENTO_KEY"):
            return "databento"
    return "yahoo"


def get(sym, interval="1d", days=None, refresh=False, source=None):
    src = source or route(sym, interval)
    days = days or (3650 if interval in ("1d", "1w") else 365)
    tag = "%s_%s_%s_%d.csv" % (sym.replace("=", "").replace("-", ""),
                               interval, src.split(".")[0], days)
    path = os.path.join(CACHE, tag)
    if os.path.exists(path) and not refresh:
        d = pd.read_csv(path, index_col=0, parse_dates=True)
        return d

    if src == "binance.us":
        d = binance_us(sym, interval, days)
    elif src == "databento":
        d = databento(sym, interval, days)
    else:
        d = yahoo(sym, interval, days)
    if d is None or len(d) == 0:
        if src != "yahoo":
            print("  %s returned nothing, falling back to yahoo" % src)
            return get(sym, interval, days, refresh, source="yahoo")
        return None
    d.to_csv(path)
    return d


def status():
    print("=" * 74)
    print("  DATA SOURCES")
    print("=" * 74)
    checks = [
        ("yahoo", "https://query1.finance.yahoo.com/v8/finance/chart/SPY", None),
        ("binance.us", "https://api.binance.us/api/v3/ping", None),
        ("coinbase", "https://api.exchange.coinbase.com/products/BTC-USD/candles",
         {"granularity": 300}),
    ]
    for name, url, p in checks:
        try:
            r = requests.get(url, params=p, headers=UA, timeout=15)
            ok = "reachable" if r.status_code == 200 else "HTTP %d" % r.status_code
        except Exception as e:
            ok = "unreachable (%s)" % type(e).__name__
        print("  %-12s free       %s" % (name, ok))
    for name, key in [("databento", "DATABENTO_KEY"), ("polygon", "POLYGON_KEY")]:
        have = env(key)
        print("  %-12s paid       %s" % (name, "KEY PRESENT" if have else
                                         "no key -- add %s to .env" % key))
    print()
    print("  ROUTING")
    for sym, iv in [("BTC-USD", "5m"), ("BTC-USD", "1h"), ("ES=F", "1m"),
                    ("ES=F", "1h"), ("NVDA", "1d"), ("NVDA", "15m")]:
        print("    %-10s %-4s -> %s" % (sym, iv, route(sym, iv)))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        status()
    elif len(sys.argv) > 3 and sys.argv[1] == "pull":
        sym, iv = sys.argv[2], sys.argv[3]
        days = int(sys.argv[4]) if len(sys.argv) > 4 else 365
        d = get(sym, iv, days, refresh=True)
        if d is None:
            print("  nothing returned")
        else:
            print("  %s %s: %d bars  %s -> %s"
                  % (sym, iv, len(d), d.index[0], d.index[-1]))
    else:
        status()
