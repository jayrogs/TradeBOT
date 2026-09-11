"""
divergence.py -- does weekly bullish RSI divergence actually predict?

    python divergence.py

THE USER'S THESIS, in their words:
    "BTC made a 3M higher low because of weekly oversold rsi and then a lower
     low without follow through. that happened last time at 15k."

Mechanically that is a BULLISH WEEKLY RSI DIVERGENCE:
    - weekly RSI got oversold at some swing low
    - price later made a LOWER low
    - but weekly RSI made a HIGHER low -- the selling had no follow-through

This has never been tested in this project. Every prior test used an ABSOLUTE
oversold level (RSI < 35). Divergence is a relationship between two series, not
a threshold, so it is a genuinely different signal.

DEFINITION (frozen before running)
    On weekly bars:
      1. find confirmed swing lows in price (lowest of the 5 weeks centred on
         it, known only 2 weeks later so nothing is used before it is visible)
      2. a divergence fires when the newest swing low is BELOW the previous one
         while weekly RSI(14) at the newest low is ABOVE its value at the
         previous one
      3. the earlier low must have been oversold: weekly RSI < 40 there
      4. the two lows must be 3 to 52 weeks apart

TESTED ACROSS 40 instruments -- equities, indices, metals, energy, FX and
crypto -- with forward returns at 4, 13 and 26 weeks, measured against both a
naive baseline and the instrument's own average.

Split into first half and second half of each history. A signal that only works
in one half is noise.
"""

import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

UNIVERSE = [
    "SPY", "QQQ", "IWM", "DIA", "EEM", "EFA",
    "GLD", "SLV", "GDX", "PPLT", "UUUU",
    "XLE", "CVX", "XOM", "USO", "UNG",
    "AAPL", "MSFT", "NVDA", "TSLA", "AMD", "JPM", "WMT", "KO", "PFE", "INTC",
    "TLT", "IEF", "HYG", "VNQ",
    "BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "ADA-USD", "XRP-USD",
    "EURUSD=X", "USDJPY=X", "GBPUSD=X", "GC=F",
]
PIVOT = 2
RSI_OVERSOLD = 40
MIN_GAP, MAX_GAP = 3, 52
HORIZONS = [4, 13, 26]


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs)


def weekly(d):
    return d.resample("W-FRI").agg({"Open": "first", "High": "max",
                                    "Low": "min", "Close": "last"}).dropna()


def find_divergence(c, l, r):
    """Returns a boolean array: True on the week the divergence is CONFIRMED."""
    n = len(c)
    piv = []
    for i in range(PIVOT, n - PIVOT):
        if l[i] == np.nanmin(l[i - PIVOT:i + PIVOT + 1]):
            piv.append(i)
    sig = np.zeros(n, dtype=bool)
    for a in range(1, len(piv)):
        j = piv[a]
        for b in range(a - 1, -1, -1):
            k = piv[b]
            gap = j - k
            if gap < MIN_GAP:
                continue
            if gap > MAX_GAP:
                break
            if l[j] < l[k] and r[j] > r[k] and r[k] < RSI_OVERSOLD:
                conf = j + PIVOT               # only visible PIVOT weeks later
                if conf < n:
                    sig[conf] = True
                break
    return sig


def main():
    import yfinance as yf
    rows, evs = [], []
    for s in UNIVERSE:
        try:
            d = yf.download(s, start="2005-01-01", end="2026-08-20",
                            progress=False, auto_adjust=False).dropna()
        except Exception:
            continue
        if len(d) < 500:
            continue
        d.columns = [x[0] if isinstance(x, tuple) else x for x in d.columns]
        if getattr(d.index, "tz", None) is not None:
            d.index = d.index.tz_localize(None)
        w = weekly(d)
        if len(w) < 150:
            continue
        c = w["Close"].values.astype(float)
        l = w["Low"].values.astype(float)
        r = rsi(c)
        sig = find_divergence(c, l, r)
        half = len(w) // 2
        for h in HORIZONS:
            fwd = pd.Series(c).shift(-h) / pd.Series(c) - 1
            base = fwd.mean()
            m = sig & fwd.notna().values
            if m.sum() < 3:
                continue
            rows.append(dict(symbol=s, h=h, n=int(m.sum()),
                             sig_ret=float(fwd[m].mean()),
                             base_ret=float(base),
                             edge=float(fwd[m].mean() - base),
                             hit=float((fwd[m] > 0).mean()),
                             base_hit=float((fwd > 0).mean()),
                             first=float(fwd[m & (np.arange(len(w)) < half)].mean()),
                             second=float(fwd[m & (np.arange(len(w)) >= half)].mean())))
        for i in np.where(sig)[0]:
            evs.append(dict(symbol=s, date=w.index[i], price=c[i], rsi=r[i]))

    R = pd.DataFrame(rows)
    E = pd.DataFrame(evs)
    R.to_csv("divergence_results.csv", index=False)
    E.to_csv("divergence_events.csv", index=False)

    print("=" * 78)
    print("  WEEKLY BULLISH RSI DIVERGENCE  -- %d instruments, %d signals total"
          % (R.symbol.nunique(), int(R[R.h == HORIZONS[0]].n.sum())))
    print("=" * 78)
    print("  %-8s %7s %12s %12s %10s %9s %10s"
          % ("horizon", "signals", "after signal", "baseline", "EDGE", "hit%",
             "base hit%"))
    for h in HORIZONS:
        g = R[R.h == h]
        print("  %-8s %7d %+11.2f%% %+11.2f%% %+9.2f%% %8.0f%% %9.0f%%"
              % ("%d weeks" % h, int(g.n.sum()), 100 * g.sig_ret.mean(),
                 100 * g.base_ret.mean(), 100 * g.edge.mean(),
                 100 * g.hit.mean(), 100 * g.base_hit.mean()))

    print("\n" + "=" * 78)
    print("  DOES IT HOLD IN BOTH HALVES OF HISTORY?")
    print("=" * 78)
    print("  %-8s %14s %14s %12s" % ("horizon", "first half", "second half",
                                     "same sign?"))
    for h in HORIZONS:
        g = R[R.h == h]
        a, b = g["first"].mean(), g["second"].mean()
        print("  %-8s %+13.2f%% %+13.2f%% %12s"
              % ("%d weeks" % h, 100 * a, 100 * b,
                 "yes" if np.sign(a) == np.sign(b) else "NO"))

    print("\n" + "=" * 78)
    print("  BY ASSET CLASS (13-week horizon, edge over that asset's own average)")
    print("=" * 78)
    groups = {"equity index": ["SPY", "QQQ", "IWM", "DIA", "EEM", "EFA"],
              "metals": ["GLD", "SLV", "GDX", "PPLT", "UUUU", "GC=F"],
              "energy": ["XLE", "CVX", "XOM", "USO", "UNG"],
              "single stocks": ["AAPL", "MSFT", "NVDA", "TSLA", "AMD", "JPM",
                                "WMT", "KO", "PFE", "INTC"],
              "bonds/REIT": ["TLT", "IEF", "HYG", "VNQ"],
              "crypto": ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD",
                         "ADA-USD", "XRP-USD"],
              "FX": ["EURUSD=X", "USDJPY=X", "GBPUSD=X"]}
    g13 = R[R.h == 13]
    print("  %-16s %8s %13s %11s %9s" % ("class", "signals", "after signal",
                                         "edge", "hit%"))
    for k, syms in groups.items():
        x = g13[g13.symbol.isin(syms)]
        if len(x) == 0:
            continue
        print("  %-16s %8d %+12.2f%% %+10.2f%% %8.0f%%"
              % (k, int(x.n.sum()), 100 * x.sig_ret.mean(),
                 100 * x.edge.mean(), 100 * x.hit.mean()))

    print("\n" + "=" * 78)
    print("  MOST RECENT SIGNALS")
    print("=" * 78)
    for _, r in E.sort_values("date").tail(12).iterrows():
        print("  %-10s %s  price %10.2f  weekly RSI %.1f"
              % (r.symbol, str(r.date.date()), r.price, r.rsi))


if __name__ == "__main__":
    main()
