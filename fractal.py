"""
fractal.py -- two questions at once.

    python fractal.py

QUESTION 1: is the setup scale-invariant?
    The user: "hourly weakness to set a healthy daily higher low... weekly
    weakness for a healthy 1M/3M higher low. works on every timeframe."
    spring.py tested ONE pairing (weekly). This tests the pattern at every
    timeframe available -- hourly, 4-hour, daily, weekly, monthly -- to see
    whether the effect is genuinely fractal or an artifact of one scale.

QUESTION 2: does the 12-period EMA act as support in bull trends and
    resistance in bear trends?
    The user reports this holds in crypto and asks whether it holds in stocks.
    Measured as: when price touches the EMA12 from above during an uptrend, how
    often does it hold, and what happens next -- against the same measurement in
    downtrends, and against a random-touch baseline.
"""

import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

STOCKS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD", "JPM", "WMT", "KO", "XOM",
          "CVX", "SPY", "QQQ", "IWM", "GLD", "SLV", "XLE", "GDX", "TLT"]
CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "ADA-USD", "XRP-USD",
          "LTC-USD", "LINK-USD"]
PIVOT = 2


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs)


def get(sym, interval, period=None, start="2005-01-01"):
    import yfinance as yf
    kw = dict(progress=False, auto_adjust=False)
    if interval == "1h":
        d = yf.download(sym, interval="1h", period="730d", **kw)
    else:
        d = yf.download(sym, start=start, end="2026-08-20", **kw)
    d = d.dropna()
    if len(d) < 200:
        return None
    d.columns = [x[0] if isinstance(x, tuple) else x for x in d.columns]
    if getattr(d.index, "tz", None) is not None:
        d.index = d.index.tz_localize(None)
    if interval in ("4h", "1wk", "1mo"):
        rule = {"4h": "4h", "1wk": "W-FRI", "1mo": "ME"}[interval]
        d = d.resample(rule).agg({"Open": "first", "High": "max",
                                  "Low": "min", "Close": "last"}).dropna()
    return d


def springs(c, l, r, oversold=40, reclaim=4, fail=0.08):
    n = len(c)
    piv = [i for i in range(PIVOT, n - PIVOT)
           if l[i] == np.nanmin(l[i - PIVOT:i + PIVOT + 1])]
    sig = np.zeros(n, dtype=bool)
    for pi in piv:
        known, lvl = pi + PIVOT, l[pi]
        for j in range(known + 1, min(known + 52, n)):
            if l[j] >= lvl:
                continue
            if not r[j] < oversold:
                break
            for k in range(j, min(j + reclaim + 1, n)):
                if c[k] < lvl * (1 - fail):
                    break
                if c[k] > lvl:
                    sig[k] = True
                    break
            break
    return sig


def q1():
    print("=" * 82)
    print("  QUESTION 1: IS THE SETUP FRACTAL?")
    print("  same failed-breakdown rule, every timeframe, 26 markets")
    print("=" * 82)
    print("  %-9s %8s %8s %13s %12s %10s %8s"
          % ("timeframe", "markets", "signals", "after signal", "baseline",
             "EDGE", "hit%"))
    syms = STOCKS + CRYPTO
    for tf, hor, lab in [("1h", 120, "hourly"), ("4h", 60, "4-hour"),
                         ("1d", 60, "daily"), ("1wk", 13, "weekly"),
                         ("1mo", 6, "monthly")]:
        sig_r, base_r, hits, n_sig, n_mkt = [], [], [], 0, 0
        for s in syms:
            try:
                d = get(s, tf)
            except Exception:
                continue
            if d is None or len(d) < 200:
                continue
            c = d["Close"].values.astype(float)
            l = d["Low"].values.astype(float)
            sg = springs(c, l, rsi(c))
            fwd = pd.Series(c).shift(-hor) / pd.Series(c) - 1
            m = sg & fwd.notna().values
            if m.sum() < 3:
                continue
            n_mkt += 1
            n_sig += int(m.sum())
            sig_r.append(fwd[m].mean())
            base_r.append(fwd.mean())
            hits.append((fwd[m] > 0).mean())
        if not sig_r:
            continue
        print("  %-9s %8d %8d %+12.2f%% %+11.2f%% %+9.2f%% %7.0f%%"
              % (lab, n_mkt, n_sig, 100 * np.mean(sig_r), 100 * np.mean(base_r),
                 100 * (np.mean(sig_r) - np.mean(base_r)), 100 * np.mean(hits)))
    print("\n  If the effect were genuinely fractal the EDGE column would be")
    print("  positive at every scale, not just one.")


def ema_test(group, name):
    rows = []
    for s in group:
        d = get(s, "1d")
        if d is None:
            continue
        c = d["Close"].values.astype(float)
        h = d["High"].values.astype(float)
        l = d["Low"].values.astype(float)
        e12 = pd.Series(c).ewm(span=12, adjust=False).mean().values
        ma200 = pd.Series(c).rolling(200).mean().values
        bull = c > ma200
        bear = c < ma200
        # a touch: bar's range contains the EMA, having closed above it before
        prev_above = np.roll(c, 1) > np.roll(e12, 1)
        prev_below = np.roll(c, 1) < np.roll(e12, 1)
        touch = (l <= e12) & (h >= e12)
        fwd5 = pd.Series(c).shift(-5) / pd.Series(c) - 1
        held = (pd.Series(c).shift(-3).values > e12)   # still above 3 bars later

        for lab, mask in [("bull, touch from above", touch & bull & prev_above),
                          ("bear, touch from below", touch & bear & prev_below)]:
            m = mask & np.isfinite(fwd5.values) & np.isfinite(e12)
            if m.sum() < 20:
                continue
            rows.append(dict(symbol=s, case=lab, n=int(m.sum()),
                             fwd=float(fwd5[m].mean()),
                             base=float(fwd5.mean()),
                             hold=float(np.nanmean(held[m]))))
    R = pd.DataFrame(rows)
    print("\n  %s" % name)
    print("  %-26s %7s %13s %12s %10s %12s"
          % ("case", "touches", "fwd 5 bars", "baseline", "edge", "held above"))
    for case, g in R.groupby("case"):
        print("  %-26s %7d %+12.2f%% %+11.2f%% %+9.2f%% %11.0f%%"
              % (case, g.n.sum(), 100 * g.fwd.mean(), 100 * g.base.mean(),
                 100 * (g.fwd.mean() - g.base.mean()), 100 * g.hold.mean()))
    return R


def q2():
    print("\n" + "=" * 82)
    print("  QUESTION 2: DOES THE 12-EMA ACT AS SUPPORT / RESISTANCE?")
    print("  'held above' = still above the EMA12 three bars after touching it")
    print("=" * 82)
    a = ema_test(CRYPTO, "CRYPTO  (where you say it works)")
    b = ema_test(STOCKS, "STOCKS  (what you asked me to verify)")
    print("\n  A level that is real 'support' should show a POSITIVE edge and a")
    print("  hold rate well above the ~50%% you would get by coin flip.")
    return a, b


if __name__ == "__main__":
    q1()
    q2()
