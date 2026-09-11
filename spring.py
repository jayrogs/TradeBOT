"""
spring.py -- the failed weekly breakdown, tested across 40 markets.

    python spring.py

THE USER'S PATTERN, corrected to their own words:
    "price level higher lows but using oversold levels of weekly rsi alongside
     lower weekly candle lows without follow through"

So NOT an RSI divergence. The sequence is:

    1. weekly RSI(14) is OVERSOLD
    2. a weekly candle prints a LOW BELOW a prior swing low  -- a lower low
    3. the break DOES NOT FOLLOW THROUGH: price closes back above that prior
       low within a few weeks
    4. the higher-timeframe structure therefore holds a HIGHER low

That is a failed breakdown -- a bear trap, or a Wyckoff spring. The sellers who
pressed the low get trapped, and the reclaim is the signal.

DEFINITION, frozen before running
    prior low     a confirmed weekly swing low (lowest of the 5 weeks centred
                  on it, treated as known only 2 weeks later)
    break         a later week whose LOW is below that prior low
    oversold      weekly RSI(14) below the threshold at the break week
    reclaim       within RECLAIM_MAX weeks, a weekly CLOSE back above the prior
                  low. This is the entry, and it is the confirmation the user
                  describes as "no follow through"
    fail          if price closes a further FAIL_PCT below the prior low first,
                  the breakdown was real and no signal is generated

Thresholds are conventional, not fitted, and sensitivity to every one of them is
reported.
"""

import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

UNIVERSE = [
    "SPY", "QQQ", "IWM", "DIA", "EEM", "EFA",
    "GLD", "SLV", "GDX", "UUUU", "GC=F",
    "XLE", "CVX", "XOM", "USO", "UNG", "CL=F",
    "AAPL", "MSFT", "NVDA", "TSLA", "AMD", "JPM", "WMT", "KO", "PFE", "INTC",
    "TLT", "HYG", "VNQ",
    "BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "ADA-USD", "XRP-USD",
    "EURUSD=X", "USDJPY=X", "GBPUSD=X",
]
PIVOT = 2
OVERSOLD = 40
RECLAIM_MAX = 4          # weeks allowed for the reclaim
FAIL_PCT = 0.08          # a close this far below the prior low kills the setup
MAX_GAP = 52             # the prior low must be within a year
HORIZONS = [4, 13, 26, 52]


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs)


def weekly(d):
    return d.resample("W-FRI").agg({"Open": "first", "High": "max",
                                    "Low": "min", "Close": "last"}).dropna()


def find_springs(c, l, r, oversold=OVERSOLD, reclaim_max=RECLAIM_MAX,
                 fail_pct=FAIL_PCT):
    """True on the week the reclaim confirms."""
    n = len(c)
    piv = [i for i in range(PIVOT, n - PIVOT)
           if l[i] == np.nanmin(l[i - PIVOT:i + PIVOT + 1])]
    sig = np.zeros(n, dtype=bool)
    for pi in piv:
        known = pi + PIVOT                      # pivot visible only now
        lvl = l[pi]
        for j in range(known + 1, min(known + MAX_GAP, n)):
            if l[j] >= lvl:
                continue
            if not (r[j] < oversold):           # must be oversold at the break
                break
            for k in range(j, min(j + reclaim_max + 1, n)):
                if c[k] < lvl * (1 - fail_pct):
                    break                       # real breakdown, setup dead
                if c[k] > lvl:
                    sig[k] = True               # reclaimed -> no follow through
                    break
            break
    return sig


def load(sym):
    import yfinance as yf
    d = yf.download(sym, start="2005-01-01", end="2026-08-20",
                    progress=False, auto_adjust=False).dropna()
    if len(d) < 500:
        return None
    d.columns = [x[0] if isinstance(x, tuple) else x for x in d.columns]
    if getattr(d.index, "tz", None) is not None:
        d.index = d.index.tz_localize(None)
    return d


def evaluate(params=None, verbose=True):
    p = dict(oversold=OVERSOLD, reclaim_max=RECLAIM_MAX, fail_pct=FAIL_PCT)
    if params:
        p.update(params)
    rows, evs = [], []
    for s in UNIVERSE:
        d = load(s)
        if d is None:
            continue
        w = weekly(d)
        if len(w) < 150:
            continue
        c = w["Close"].values.astype(float)
        l = w["Low"].values.astype(float)
        r = rsi(c)
        sig = find_springs(c, l, r, p["oversold"], p["reclaim_max"], p["fail_pct"])
        half = len(w) // 2
        pos = np.arange(len(w))
        for h in HORIZONS:
            fwd = pd.Series(c).shift(-h) / pd.Series(c) - 1
            m = sig & fwd.notna().values
            if m.sum() < 2:
                continue
            rows.append(dict(symbol=s, h=h, n=int(m.sum()),
                             sig=float(fwd[m].mean()),
                             base=float(fwd.mean()),
                             edge=float(fwd[m].mean() - fwd.mean()),
                             hit=float((fwd[m] > 0).mean()),
                             bhit=float((fwd > 0).mean()),
                             first=float(fwd[m & (pos < half)].mean())
                             if (m & (pos < half)).sum() else np.nan,
                             second=float(fwd[m & (pos >= half)].mean())
                             if (m & (pos >= half)).sum() else np.nan))
        for i in np.where(sig)[0]:
            evs.append(dict(symbol=s, date=w.index[i], price=c[i], rsi=r[i]))
    return pd.DataFrame(rows), pd.DataFrame(evs)


def main():
    R, E = evaluate()
    R.to_csv("spring_results.csv", index=False)
    E.to_csv("spring_events.csv", index=False)

    n_sig = int(R[R.h == HORIZONS[0]].n.sum())
    print("=" * 80)
    print("  FAILED WEEKLY BREAKDOWN  --  %d markets, %d signals"
          % (R.symbol.nunique(), n_sig))
    print("  oversold weekly RSI < %d, lower weekly low, reclaimed within %d weeks"
          % (OVERSOLD, RECLAIM_MAX))
    print("=" * 80)
    print("  %-9s %8s %13s %12s %10s %8s %10s"
          % ("horizon", "signals", "after signal", "baseline", "EDGE", "hit%",
             "base hit%"))
    for h in HORIZONS:
        g = R[R.h == h]
        print("  %-9s %8d %+12.2f%% %+11.2f%% %+9.2f%% %7.0f%% %9.0f%%"
              % ("%d wk" % h, int(g.n.sum()), 100 * g.sig.mean(),
                 100 * g.base.mean(), 100 * g.edge.mean(),
                 100 * g.hit.mean(), 100 * g.bhit.mean()))

    print("\n" + "=" * 80)
    print("  BOTH HALVES OF HISTORY?  (a signal that works in one half is noise)")
    print("=" * 80)
    print("  %-9s %14s %14s %10s" % ("horizon", "first half", "second half", "sign"))
    for h in HORIZONS:
        g = R[R.h == h]
        a, b = g["first"].mean(), g["second"].mean()
        print("  %-9s %+13.2f%% %+13.2f%% %10s"
              % ("%d wk" % h, 100 * a, 100 * b,
                 "same" if np.sign(a) == np.sign(b) else "FLIPPED"))

    print("\n" + "=" * 80)
    print("  BY ASSET CLASS  (13 weeks, edge over that market's own average)")
    print("=" * 80)
    groups = {"equity index": ["SPY", "QQQ", "IWM", "DIA", "EEM", "EFA"],
              "metals": ["GLD", "SLV", "GDX", "UUUU", "GC=F"],
              "energy": ["XLE", "CVX", "XOM", "USO", "UNG", "CL=F"],
              "single stocks": ["AAPL", "MSFT", "NVDA", "TSLA", "AMD", "JPM",
                                "WMT", "KO", "PFE", "INTC"],
              "bonds/REIT": ["TLT", "HYG", "VNQ"],
              "crypto": ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD",
                         "ADA-USD", "XRP-USD"],
              "FX": ["EURUSD=X", "USDJPY=X", "GBPUSD=X"]}
    g = R[R.h == 13]
    print("  %-16s %8s %13s %11s %9s" % ("class", "signals", "after", "edge", "hit%"))
    for k, syms in groups.items():
        x = g[g.symbol.isin(syms)]
        if len(x) == 0:
            continue
        print("  %-16s %8d %+12.2f%% %+10.2f%% %8.0f%%"
              % (k, int(x.n.sum()), 100 * x.sig.mean(), 100 * x.edge.mean(),
                 100 * x.hit.mean()))

    print("\n" + "=" * 80)
    print("  SENSITIVITY -- is it knife-edge on any threshold? (13 weeks)")
    print("=" * 80)
    print("  %-28s %8s %12s %10s" % ("variant", "signals", "after", "edge"))
    for lab, prm in [("baseline", {}),
                     ("oversold < 30", {"oversold": 30}),
                     ("oversold < 50", {"oversold": 50}),
                     ("reclaim within 2 wk", {"reclaim_max": 2}),
                     ("reclaim within 8 wk", {"reclaim_max": 8}),
                     ("fail cutoff 4%", {"fail_pct": 0.04}),
                     ("fail cutoff 15%", {"fail_pct": 0.15})]:
        r2, _ = evaluate(prm)
        x = r2[r2.h == 13]
        print("  %-28s %8d %+11.2f%% %+9.2f%%"
              % (lab, int(x.n.sum()), 100 * x.sig.mean(), 100 * x.edge.mean()))

    print("\n" + "=" * 80)
    print("  RECENT SIGNALS")
    print("=" * 80)
    for _, r in E.sort_values("date").tail(15).iterrows():
        print("  %-10s %s  price %11.2f  weekly RSI %.1f"
              % (r.symbol, str(r.date.date()), r.price, r.rsi))


if __name__ == "__main__":
    main()
