"""alpaca.py -- US stock bars from Alpaca Market Data (the free IEX feed).

Keys live ONLY in livelog/alpaca.json, written by the owner, never by code:

    {"key": "PK...", "secret": "..."}

This module never prints them.  `python alpaca.py --check` proves they work
and reports how far back the feed reaches.

Why it exists (2026-09-03): Yahoo caps intraday history (5m 30d, 15m 60d,
1h 2y) and throttles big pulls. Alpaca's free tier serves every US stock and
ETF with intraday bars back to 2021-01 (measured), 200 requests a minute.

What it is FOR: research history (backfill_stocks.py). What it is NOT for:
the live scanner, measured the day it was wired --
  * volume is IEX-only, ~2% of consolidated (SPY 1.4M vs ~60M a day), so
    every volume flag and liquidity gate would misfire on it;
  * a page covers ~10,000 bar-minutes whatever the timeframe, so 300 days
    of hourly is ~9 requests per symbol -- slower than Yahoo's batch.
The scanner therefore stays on Yahoo unless the key file says
{"scanner": true}. Daily bars are cheap (thousands per request).
"""

import json
import os
import sys
import time

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = os.path.join(HERE, "livelog", "alpaca.json")
URL = "https://data.alpaca.markets/v2/stocks/bars"
TF = {"1m": "1Min", "5m": "5Min", "15m": "15Min", "30m": "30Min",
      "1h": "1Hour", "4h": "4Hour", "1d": "1Day", "1w": "1Week"}
# how far back the scanner's base frames reach, in days
SCAN_DAYS = {"5m": 30, "15m": 60, "1h": 300, "1d": 6 * 365}
GAP = 0.35                  # ~170 requests/min, under the free 200/min
_LAST = [0.0]
CALLS = [0]                 # request counter, for timing studies


def keys():
    try:
        k = json.load(open(KEYS))
        key, sec = str(k.get("key") or "").strip(), str(k.get("secret") or "").strip()
        # the template file ships with PASTE_... placeholders: not keys
        if key and sec and "PASTE" not in key and "PASTE" not in sec:
            return key, sec
    except Exception:
        pass
    return None


def enabled():
    return keys() is not None


def opt(name):
    """Extra switches in the key file, e.g. {"scanner": true}."""
    try:
        return bool(json.load(open(KEYS)).get(name))
    except Exception:
        return False


_SESSION = [None]


def _session():
    # one keep-alive connection: a fresh TLS handshake per page was slow and
    # got reset mid-pull on the first timing run
    if _SESSION[0] is None:
        _SESSION[0] = requests.Session()
    return _SESSION[0]


def _get(params):
    k = keys()
    if k is None:
        raise RuntimeError("no Alpaca keys in livelog/alpaca.json")
    hdr = {"APCA-API-KEY-ID": k[0], "APCA-API-SECRET-KEY": k[1],
           "Accept": "application/json"}
    for attempt in range(4):
        wait = _LAST[0] + GAP - time.time()
        if wait > 0:
            time.sleep(wait)
        try:
            r = _session().get(URL, params=params, headers=hdr, timeout=60)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            _LAST[0] = time.time()
            CALLS[0] += 1
            if attempt == 3:
                raise RuntimeError("Alpaca connection kept failing: %s"
                                   % type(e).__name__)
            _SESSION[0] = None
            time.sleep(2 * (attempt + 1))
            continue
        _LAST[0] = time.time()
        CALLS[0] += 1
        if r.status_code == 429:
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code in (401, 403):
            raise RuntimeError("Alpaca refused the keys (HTTP %d): %s"
                               % (r.status_code, r.text[:160]))
        r.raise_for_status()
        return r.json()
    raise RuntimeError("Alpaca kept rate-limiting (HTTP 429 x4)")


def _rfc(ts):
    ts = pd.Timestamp(ts)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def bars(symbols, tf, start, end=None, feed="iex", chunk=100):
    """{symbol: OHLCV DataFrame}, index = naive New York time, oldest first.
    Many symbols per request, paginated; the same frame shape as Yahoo's."""
    if isinstance(symbols, str):
        symbols = [symbols]
    raw = {}
    for i in range(0, len(symbols), chunk):
        params = {"symbols": ",".join(symbols[i:i + chunk]),
                  "timeframe": TF[tf], "start": _rfc(start), "limit": 10000,
                  "adjustment": "raw", "feed": feed, "sort": "asc"}
        if end is not None:
            params["end"] = _rfc(end)
        while True:
            js = _get(params)
            for s, rows in (js.get("bars") or {}).items():
                raw.setdefault(s, []).extend(rows)
            tok = js.get("next_page_token")
            if not tok:
                break
            params["page_token"] = tok
    out = {}
    for s, rows in raw.items():
        if not rows:
            continue
        d = pd.DataFrame(rows)
        t = (pd.to_datetime(d["t"], utc=True)
             .dt.tz_convert("America/New_York").dt.tz_localize(None))
        # .values, not Series: a Series would be re-aligned against the new
        # datetime index and come out all-NaN (bit us on the first pull)
        f = pd.DataFrame({"Open": d["o"].astype(float).values,
                          "High": d["h"].astype(float).values,
                          "Low": d["l"].astype(float).values,
                          "Close": d["c"].astype(float).values,
                          "Volume": d["v"].astype(float).values},
                         index=pd.DatetimeIndex(t.values, name="Date"))
        out[s] = f[~f.index.duplicated()].sort_index()
    return out


def scan_bars(symbols, base):
    """The scanner's base frame for many names in one paginated pull."""
    start = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=SCAN_DAYS.get(base, 60))
    return bars(symbols, base, start)


def check():
    if not enabled():
        print("  no keys yet: create livelog/alpaca.json as "
              '{"key": "...", "secret": "..."}')
        return 1
    try:
        f = bars("SPY", "1d", pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=10))
    except Exception as e:
        print("  Alpaca check FAILED: %s" % e)
        return 1
    d = f.get("SPY")
    if d is None or d.empty:
        print("  keys accepted but no SPY bars came back")
        return 1
    print("  Alpaca OK: SPY daily, last bar %s, close %.2f"
          % (d.index[-1], d["Close"].iloc[-1]))
    # how deep does the free hourly feed go?
    for yr in range(2015, 2025):
        try:
            h = bars("SPY", "1h", "%d-01-01" % yr, end="%d-02-01" % yr)
        except Exception as e:
            print("  depth probe stopped: %s" % e)
            break
        if h.get("SPY") is not None and len(h["SPY"]):
            print("  hourly history reaches back to at least %s"
                  % h["SPY"].index[0].date())
            break
    else:
        print("  no hourly bars found before 2025")
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv or len(sys.argv) == 1:
        sys.exit(check())
    sym = sys.argv[1].upper()
    tf = sys.argv[2] if len(sys.argv) > 2 else "1h"
    days = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    f = bars(sym, tf, pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days))
    d = f.get(sym)
    print("  %s %s: %s" % (sym, tf, "none" if d is None else
                           "%d bars, %s -> %s" % (len(d), d.index[0], d.index[-1])))
