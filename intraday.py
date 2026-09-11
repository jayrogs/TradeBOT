"""
intraday.py -- the multi-timeframe setup, on hourly bars.

    python intraday.py

THE SETUP BEING TESTED, in the user's own words:
    "Oversold lower timeframes to mark higher lows on healthy uptrend higher
     timeframes. Trying to use indicators and candle psychology to catch entries
     for riding trends."

Mechanised as four conditions, all required, frozen before running:

    1. HIGHER TIMEFRAME HEALTHY UPTREND
       On the DAILY chart, as of yesterday's close:
       close > 50-day average > 200-day average

    2. LOWER TIMEFRAME OVERSOLD
       On the HOURLY chart: RSI(14) dipped to 30 or below at some point in the
       last 12 hourly bars (roughly two sessions)

    3. HIGHER LOW
       The most recent confirmed hourly swing low is ABOVE the one before it.
       A swing low is a bar whose low is the lowest of the 7 bars centred on it,
       and it is only treated as known 3 bars later -- so the pattern is never
       used before a chart reader could have seen it.

    4. CANDLE CONFIRMATION
       The trigger bar closes above its own open AND above the previous bar's
       high. Buyers took control and made a new local high.

Entry at the NEXT hourly bar's open. Held 6 bars (about a day), 30 bars (about a
week) or 78 bars (about two weeks). Scored against SPY over the identical hours,
and against an equal-weight book of the whole universe.

WHY THIS IS WORTH RUNNING SEPARATELY
Every other test in this project used daily bars. Conditions 2, 3 and 4 happen
INSIDE the day and are invisible on a daily chart. The daily-bar approximations
tried earlier -- trend_pullback, ema_ride_20 -- fired 74,000 times and came out
flat, but they were not testing this.

DECOMPOSITION
Each condition is added one at a time, so if anything works it is clear which
part is doing it. That is attribution, not a menu to pick from: the full
four-condition setup is the one being judged.
"""

import os
import time
import warnings

import numpy as np
import pandas as pd

import data as D

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache", "hourly.pkl")

DISCOVERY = ("2023-09-19", "2025-12-31")
CONFIRM = ("2026-01-01", "2026-12-31")
HOLDS = [6, 30, 78]          # ~1 day, ~1 week, ~2 weeks

RSI_LEN = 14
OVERSOLD = 30
OVERSOLD_WINDOW = 12         # bars back within which the dip must have happened
PIVOT = 3                    # bars either side defining a swing low


# ---------------------------------------------------------------- data

def load_hourly(refresh=False):
    if os.path.exists(CACHE) and not refresh:
        return pd.read_pickle(CACHE)
    import yfinance as yf
    syms = sorted(set(D.sp500_current()["symbol"]))
    print("downloading hourly bars for %d symbols..." % len(syms))
    frames = {}
    for i in range(0, len(syms), 50):
        chunk = syms[i:i + 50]
        try:
            raw = yf.download(chunk + ["SPY"], interval="1h", period="730d",
                              progress=False, auto_adjust=False,
                              group_by="ticker", threads=True)
        except Exception as e:
            print("  batch failed: %s" % type(e).__name__)
            continue
        for s in chunk + ["SPY"]:
            try:
                b = raw[s].dropna(subset=["Close"])
                if len(b) > 500:
                    frames[s] = b[["Open", "High", "Low", "Close", "Volume"]]
            except Exception:
                pass
        print("  %d/%d" % (min(i + 50, len(syms)), len(syms)))
        time.sleep(0.4)

    spy = frames.pop("SPY")
    idx = spy.index
    out = {}
    for f in ("Open", "High", "Low", "Close"):
        out[f.lower()] = pd.DataFrame({s: b[f].reindex(idx)
                                       for s, b in frames.items()})
    out["spy_close"] = spy["Close"]
    pd.to_pickle(out, CACHE)
    print("  cached %d symbols x %d hourly bars" % (out["close"].shape[1], len(idx)))
    return out


# ---------------------------------------------------------------- conditions

def hourly_rsi(close, n=RSI_LEN):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1.0 / n, adjust=False).mean()
    dn = (-d).clip(lower=0).ewm(alpha=1.0 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).where(dn != 0, 100.0)


def daily_uptrend_on_hourly(h_index, bars_daily):
    """Condition 1. Daily uptrend as of the PREVIOUS daily close, mapped onto
    the hourly index. Using today's daily close would be lookahead: it is not
    known until the session ends."""
    dates = pd.DatetimeIndex(pd.Series(h_index).dt.tz_localize(None).dt.normalize())
    out = {}
    for s, b in bars_daily.items():
        c = b["Close"].astype(float)
        up = (c > c.rolling(50).mean()) & \
             (c.rolling(50).mean() > c.rolling(200).mean())
        up = up.shift(1)                      # yesterday's completed daily bar
        out[s] = up.reindex(dates, method="ffill").values
    return pd.DataFrame(out, index=h_index)


def higher_low(low):
    """Condition 3. Most recent confirmed swing low above the previous one.

    A swing low at bar i needs PIVOT bars either side, so it cannot be known
    until bar i+PIVOT. Everything below is shifted to respect that.
    """
    is_piv = low.rolling(2 * PIVOT + 1, center=True).min().eq(low)
    is_piv = is_piv.shift(PIVOT).fillna(False)       # known only PIVOT bars later
    piv_val = low.shift(PIVOT).where(is_piv)
    last = piv_val.ffill()                           # most recent confirmed pivot
    prev = piv_val.apply(                            # the pivot before that one
        lambda col: col.dropna().shift(1).reindex(col.index).ffill())
    return (last > prev) & last.notna() & prev.notna()


def build_conditions(h, bars_daily):
    o, hi, lo, c = h["open"], h["high"], h["low"], h["close"]
    cond = {}
    cond["uptrend"] = daily_uptrend_on_hourly(c.index, bars_daily).reindex(
        columns=c.columns).fillna(False)
    r = hourly_rsi(c)
    cond["oversold"] = (r <= OVERSOLD).rolling(OVERSOLD_WINDOW,
                                               min_periods=1).max().astype(bool)
    cond["higher_low"] = higher_low(lo)
    cond["candle"] = (c > o) & (c > hi.shift(1))
    return cond


# ---------------------------------------------------------------- study

def study(trig, h, hold, start, end):
    """Equal-weight book of everything triggered in the last `hold` bars,
    entered at the next bar's open, scored against SPY over the same bars."""
    c = h["close"]
    ret = c.pct_change()
    fired = trig.fillna(False)
    book = fired.shift(1).fillna(False).astype(float) \
                .rolling(hold, min_periods=1).max()
    w = book.div(book.sum(axis=1).replace(0, np.nan), axis=0)

    naive = c.notna().astype(float)
    naive = naive.div(naive.sum(axis=1).replace(0, np.nan), axis=0)

    idx = c.index
    sel = (idx >= pd.Timestamp(start).tz_localize(idx.tz)) & \
          (idx <= pd.Timestamp(end).tz_localize(idx.tz))
    port = (w * ret).sum(axis=1).where(book.sum(axis=1) > 0)
    uni = (naive * ret).sum(axis=1)
    spy = h["spy_close"].pct_change()

    df = pd.DataFrame({"port": port, "spy": spy, "uni": uni})[sel].dropna()
    df["vs_spy"] = df["port"] - df["spy"]
    df["vs_uni"] = df["port"] - df["uni"]
    return df, int(fired[sel].sum().sum())


def stats(r, bars_per_year=1638):
    """1638 = 6.5 hourly bars x 252 sessions."""
    n = len(r)
    if n < 200 or r.std(ddof=1) == 0:
        return dict(n=n, ann=np.nan, t=np.nan)
    mu, sd = r.mean(), r.std(ddof=1)
    t = mu / (sd / np.sqrt(n))
    return dict(n=n, ann=(1 + mu) ** bars_per_year - 1, t=t)


def run(cond, h, start, end, title):
    print("\n" + "=" * 76)
    print("  %s   %s to %s" % (title, start, end))
    print("=" * 76)
    steps = [
        ("1 uptrend only", ["uptrend"]),
        ("2 + oversold", ["uptrend", "oversold"]),
        ("3 + higher low", ["uptrend", "oversold", "higher_low"]),
        ("4 + candle  <-- THE SETUP", ["uptrend", "oversold", "higher_low", "candle"]),
    ]
    print("  %-26s %8s %5s %11s %7s %11s %7s"
          % ("conditions", "events", "hold", "vs SPY/yr", "t", "vs univ/yr", "t"))
    print("  " + "-" * 72)
    rows = []
    for label, keys in steps:
        trig = cond[keys[0]]
        for k in keys[1:]:
            trig = trig & cond[k]
        first = True
        for hold in HOLDS:
            df, n_ev = study(trig, h, hold, start, end)
            if len(df) < 200:
                continue
            a, b = stats(df["vs_spy"]), stats(df["vs_uni"])
            rows.append(dict(step=label, hold=hold, events=n_ev,
                             spy=a["ann"], t_spy=a["t"],
                             uni=b["ann"], t_uni=b["t"]))
            print("  %-26s %8d %5d %+10.2f%% %7.2f %+10.2f%% %7.2f"
                  % (label if first else "", n_ev, hold,
                     100 * a["ann"], a["t"], 100 * b["ann"], b["t"]))
            first = False
    return pd.DataFrame(rows)


def main():
    h = load_hourly()
    print("hourly panel: %d symbols, %d bars, %s -> %s"
          % (h["close"].shape[1], len(h["close"]),
             h["close"].index[0], h["close"].index[-1]))

    memb, _ = D.membership_intervals("2023-01-01", "2026-12-31")
    bars_daily = D.download_bars(sorted(set(h["close"].columns)),
                                 "2022-01-01", "2026-08-18")
    keep = [s for s in h["close"].columns if s in bars_daily]
    for k in ("open", "high", "low", "close"):
        h[k] = h[k][keep]
    print("  %d symbols have both hourly and daily history" % len(keep))

    cond = build_conditions(h, {s: bars_daily[s] for s in keep})
    for k, v in cond.items():
        print("  condition '%s' true on %.1f%% of bars" % (k, 100 * v.values.mean()))

    d = run(cond, h, *DISCOVERY, title="DISCOVERY -- hourly, through 2025")
    d.to_csv("intraday_discovery.csv", index=False)
    c = run(cond, h, *CONFIRM, title="CONFIRMATION -- 2026, untouched until now")
    c.to_csv("intraday_confirm.csv", index=False)

    print("\n" + "=" * 76)
    print("  THE SETUP, both windows")
    print("=" * 76)
    dd = d[d.step.str.startswith("4")]
    cc = c[c.step.str.startswith("4")]
    m = dd.merge(cc, on="hold", suffixes=("_d", "_c"))
    print("  %5s %10s %8s %7s %10s %8s %7s"
          % ("hold", "events_d", "2023-25", "t", "events_c", "2026", "t"))
    for _, r in m.iterrows():
        print("  %5d %10d %+7.2f%% %7.2f %10d %+7.2f%% %7.2f"
              % (r.hold, r.events_d, 100 * r.uni_d, r.t_uni_d,
                 r.events_c, 100 * r.uni_c, r.t_uni_c))


if __name__ == "__main__":
    main()
