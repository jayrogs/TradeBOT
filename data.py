"""
data.py -- universe + price data layer.

Everything here is cached to ./cache so a rerun costs nothing. Nothing here
knows anything about the strategy; it just supplies bars, sectors, earnings
dates, and point-in-time index membership.

PRICE CONVENTION (deliberate deviation from strategy_spec_v1 section 7 -- see NOTES.md):
Yahoo returns split-adjusted, NOT dividend-adjusted OHLC when auto_adjust=False.
That is what we use. The spec asked for nominal (un-split) prices because the
ChartGuys study had to match published price levels; our strategy computes every
level from the series itself, so un-splitting would only inject fake -50% gaps on
split dates, which RSI would read as real weakness. Split-adjusted is the correct
series here. Dividends are excluded from both the strategy and the SPY benchmark
so the comparison is like-for-like.
"""

import io
import json
import os
import time
import warnings

import pandas as pd

warnings.filterwarnings("ignore")

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
BARS = os.path.join(CACHE, "bars")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

for d in (CACHE, BARS):
    os.makedirs(d, exist_ok=True)


def yf_symbol(s):
    """BRK.B -> BRK-B. Yahoo uses dashes for share classes."""
    return str(s).strip().upper().replace(".", "-")


# ---------------------------------------------------------------- universe

def sp500_current(refresh=False):
    """Current S&P 500 members with GICS sector."""
    p = os.path.join(CACHE, "sp500_current.csv")
    if os.path.exists(p) and not refresh:
        return pd.read_csv(p)
    import requests
    r = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                     headers=UA, timeout=30)
    r.raise_for_status()
    t = pd.read_html(io.StringIO(r.text))[0]
    out = pd.DataFrame({"symbol": t["Symbol"].map(yf_symbol),
                        "sector": t["GICS Sector"]})
    out.to_csv(p, index=False)
    return out


def sp500_changes(refresh=False):
    """Historical add/remove events. Used to rebuild point-in-time membership."""
    p = os.path.join(CACHE, "sp500_changes.csv")
    if os.path.exists(p) and not refresh:
        d = pd.read_csv(p)
        d["date"] = pd.to_datetime(d["date"])
        return d
    import requests
    r = requests.get(
        "https://en.wikipedia.org/wiki/Historical_components_of_the_S%26P_500",
        headers=UA, timeout=30)
    r.raise_for_status()
    t = pd.read_html(io.StringIO(r.text))[0]
    t.columns = ["_".join(str(x) for x in c) if isinstance(c, tuple) else str(c)
                 for c in t.columns]
    col = {c.lower(): c for c in t.columns}

    def pick(*keys):
        for k in keys:
            for lc, c in col.items():
                if all(part in lc for part in k):
                    return c
        return None

    d = pd.DataFrame({
        "date": pd.to_datetime(t[pick(("effective",))], errors="coerce"),
        "added": t[pick(("added", "ticker"))],
        "removed": t[pick(("removed", "ticker"))],
    })
    d = d.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    d["added"] = d["added"].apply(lambda x: yf_symbol(x) if pd.notna(x) else None)
    d["removed"] = d["removed"].apply(lambda x: yf_symbol(x) if pd.notna(x) else None)
    d.to_csv(p, index=False)
    return d


def membership_intervals(start, end):
    """
    Rebuild point-in-time S&P 500 membership by walking the change log backwards
    from today's list. Returns ({symbol: [(start_ts, end_ts), ...]}, {symbol: sector}).

    Without this the universe is survivorship-biased, and a buy-the-dip strategy
    is exactly what that bias flatters most: the names that fell and kept falling
    are the ones that got removed from the index.
    """
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    cur = sp500_current()
    sectors = dict(zip(cur["symbol"], cur["sector"]))
    members = set(cur["symbol"])
    today = pd.Timestamp.today().normalize()

    changes = sp500_changes().sort_values("date")
    # Wikipedia's "current" list already reflects announced-but-not-yet-effective
    # changes, so start the walk-back from the latest event, not from today.
    if len(changes):
        cursor_start = max(today, changes["date"].max())
    else:
        cursor_start = today

    intervals = {}
    cursor = cursor_start
    for _, ev in changes.iloc[::-1].iterrows():
        d = ev["date"]
        if d > cursor:
            continue
        for s in members:
            intervals.setdefault(s, []).append((d, cursor))
        cursor = d - pd.Timedelta(days=1)
        # undo the event to recover the membership that held just before d
        if isinstance(ev["added"], str) and ev["added"] in members:
            members.discard(ev["added"])
        if isinstance(ev["removed"], str):
            members.add(ev["removed"])
        if cursor < start:
            break
    for s in members:
        intervals.setdefault(s, []).append((pd.Timestamp("1990-01-01"), cursor))

    out = {}
    for s, iv in intervals.items():
        merged = []
        for a, b in sorted(iv):
            a, b = max(a, start), min(b, end)
            if a > b:
                continue
            if merged and a <= merged[-1][1] + pd.Timedelta(days=1):
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        if merged:
            out[s] = merged
    return out, sectors


# ---------------------------------------------------------------- bars

def download_bars(symbols, start, end, batch=60, refresh=False):
    """Fetch daily OHLCV, cached one CSV per symbol. Returns {sym: DataFrame}."""
    import yfinance as yf
    need = [s for s in symbols
            if refresh or not os.path.exists(os.path.join(BARS, s + ".csv"))]
    if need:
        print("  downloading bars for %d symbols (%d cached)..."
              % (len(need), len(symbols) - len(need)))
    for i in range(0, len(need), batch):
        chunk = need[i:i + batch]
        try:
            raw = yf.download(chunk, start=start, end=end, auto_adjust=False,
                              actions=True, group_by="ticker", progress=False,
                              threads=True)
        except Exception as e:
            print("    batch failed (%s), skipping" % type(e).__name__)
            continue
        for s in chunk:
            try:
                d = raw[s] if isinstance(raw.columns, pd.MultiIndex) else raw
                d = d.dropna(subset=["Close"])
                if len(d) < 30:
                    continue
                d = d[["Open", "High", "Low", "Close", "Volume"]].copy()
                if getattr(d.index, "tz", None) is not None:
                    d.index = d.index.tz_localize(None)
                d.index.name = "Date"
                d.to_csv(os.path.join(BARS, s + ".csv"))
            except Exception:
                continue
        print("    %d/%d" % (min(i + batch, len(need)), len(need)))
        time.sleep(0.3)

    out = {}
    for s in symbols:
        p = os.path.join(BARS, s + ".csv")
        if not os.path.exists(p):
            continue
        d = pd.read_csv(p, index_col=0, parse_dates=True)
        d = d[~d.index.duplicated(keep="last")].sort_index()
        if len(d) >= 30:
            out[s] = d
    return out


def download_earnings(symbols, refresh=False, max_attempts=3, pause=0.6):
    """
    Past + scheduled earnings dates per symbol, cached.

    Yahoo rate-limits this endpoint hard. An earlier version hammered it with no
    pause, got throttled, and cached an empty list for all 520 symbols -- which
    silently disabled the earnings blackout entirely while looking like a
    successful run. So: throttle, retry, and record how many attempts a symbol
    has had so a throttled empty is retried on the next run instead of being
    mistaken for "this company never reports earnings".
    """
    import yfinance as yf
    p = os.path.join(CACHE, "earnings.json")
    store = {}
    if os.path.exists(p) and not refresh:
        raw = json.load(open(p))
        for k, v in raw.items():
            store[k] = v if isinstance(v, dict) else {"dates": v, "attempts": 99}

    need = [s for s in symbols
            if s not in store or (not store[s]["dates"]
                                  and store[s]["attempts"] < max_attempts)]
    if need:
        print("  fetching earnings dates for %d symbols (%d cached)..."
              % (len(need), len(symbols) - len(need)))
    for i, s in enumerate(need, 1):
        rec = store.get(s, {"dates": [], "attempts": 0})
        try:
            ed = yf.Ticker(s).get_earnings_dates(limit=100)
            if ed is not None and len(ed):
                idx = pd.to_datetime(ed.index)
                try:
                    idx = idx.tz_localize(None)
                except Exception:
                    idx = idx.tz_convert(None)
                rec["dates"] = sorted({d.strftime("%Y-%m-%d") for d in idx})
        except Exception:
            pass
        rec["attempts"] = rec.get("attempts", 0) + 1
        store[s] = rec
        time.sleep(pause)
        if i % 50 == 0:
            got = sum(1 for v in store.values() if v["dates"])
            print("    %d/%d  (%d with dates so far)" % (i, len(need), got))
            json.dump(store, open(p, "w"))
    json.dump(store, open(p, "w"))
    return {s: pd.to_datetime(store.get(s, {}).get("dates", [])) for s in symbols}


def fill_missing_sectors(symbols, known, refresh=False):
    """Removed index members have no row on the current-constituents page, so
    look their sector up individually. Needed for the max-2-per-sector rule."""
    import yfinance as yf
    p = os.path.join(CACHE, "sectors_extra.json")
    store = json.load(open(p)) if os.path.exists(p) and not refresh else {}
    out = dict(known)
    need = [s for s in symbols if s not in out and s not in store]
    if need:
        print("  looking up sector for %d delisted/removed names..." % len(need))
    for s in need:
        try:
            store[s] = yf.Ticker(s).info.get("sector") or "Unknown"
        except Exception:
            store[s] = "Unknown"
    if need:
        json.dump(store, open(p, "w"))
    for s in symbols:
        if s not in out:
            out[s] = store.get(s, "Unknown")
    return out
