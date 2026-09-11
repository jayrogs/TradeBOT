"""
reverse_engineer.py -- what do the user's actual entries have in common?

    python reverse_engineer.py

Rather than guessing at their intuition, this takes their 102 real filled buy
orders, measures the state of each chart on the day they bought, and compares
that against every other day in the same instrument. Anything they do
systematically shows up as a percentile far from 50.

FEATURES MEASURED ON THE ENTRY DAY
    rsi_d          daily RSI(14)
    rsi_w          weekly RSI(14) -- the timeframe the user cites
    vs_ma200       distance above/below the 200-day average
    vs_ma50        distance above/below the 50-day average
    dd_52w         drawdown from the 52-week high
    range_pos      position in the 52-week low-to-high range
    ret_20d        trailing one-month return
    ret_60d        trailing three-month return
    vol_pct        realised-volatility percentile
    div_bull       bullish RSI divergence present (price makes a lower low
                   while RSI makes a HIGHER low) -- the pattern the user
                   described on BTC: "a lower low without follow through"

The last one matters most: every backtest in this project used an ABSOLUTE
oversold threshold (RSI < 35). Divergence is a relationship between two series,
not a level, and it has never been tested here.
"""

import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs)


def bullish_divergence(c, r, look=40, sep=5):
    """
    Price makes a lower low than a prior swing low, but RSI at that new low is
    HIGHER than RSI at the old one. Sellers pushed price lower and momentum did
    not follow -- the user's "lower low without follow through".
    Computed only from data up to each bar.
    """
    n = len(c)
    out = np.zeros(n, dtype=bool)
    for i in range(look + sep, n):
        w = c[i - look:i + 1]
        rw = r[i - look:i + 1]
        j = int(np.argmin(w))                       # the recent low
        if j < len(w) - 4:                          # must be near the right edge
            continue
        prior = w[:max(1, j - sep)]
        if len(prior) < 5:
            continue
        k = int(np.argmin(prior))
        if w[j] < prior[k] and rw[j] > rw[k] and rw[j] < 50:
            out[i] = True
    return out


def features(d):
    c = d["Close"].values.astype(float)
    idx = d.index
    f = pd.DataFrame(index=idx)
    f["rsi_d"] = rsi(c)
    wk = d["Close"].resample("W-FRI").last()
    f["rsi_w"] = pd.Series(rsi(wk.values.astype(float)),
                           index=wk.index).reindex(idx, method="ffill")
    f["vs_ma200"] = c / pd.Series(c).rolling(200).mean().values - 1
    f["vs_ma50"] = c / pd.Series(c).rolling(50).mean().values - 1
    hi = pd.Series(c).rolling(252).max().values
    lo = pd.Series(c).rolling(252).min().values
    f["dd_52w"] = c / hi - 1
    f["range_pos"] = (c - lo) / (hi - lo)
    f["ret_20d"] = pd.Series(c).pct_change(20).values
    f["ret_60d"] = pd.Series(c).pct_change(60).values
    v = pd.Series(c).pct_change().rolling(20).std()
    f["vol_pct"] = v.rank(pct=True).values
    f["div_bull"] = bullish_divergence(c, f["rsi_d"].values)
    return f


def main():
    import yfinance as yf
    buys = pd.read_csv("my_buys.csv", parse_dates=["date"])
    buys = buys[buys.symbol.notna()]
    syms = sorted(buys.symbol.unique())
    print("analysing %d buy orders across %d symbols\n" % (len(buys), len(syms)))

    rows, base = [], []
    for s in syms:
        d = yf.download(s, start="2018-01-01", end="2026-08-20",
                        progress=False, auto_adjust=False).dropna()
        if len(d) < 300:
            continue
        d.columns = [x[0] if isinstance(x, tuple) else x for x in d.columns]
        if getattr(d.index, "tz", None) is not None:
            d.index = d.index.tz_localize(None)
        f = features(d)
        f = f.dropna()
        for _, b in buys[buys.symbol == s].iterrows():
            j = f.index.searchsorted(b.date)
            if j >= len(f):
                continue
            r = f.iloc[j].to_dict()
            r["symbol"] = s
            r["date"] = f.index[j]
            rows.append(r)
        bb = f.copy()
        bb["symbol"] = s
        base.append(bb)

    E = pd.DataFrame(rows)
    B = pd.concat(base)
    E.to_csv("entry_features.csv", index=False)

    cols = ["rsi_d", "rsi_w", "vs_ma200", "vs_ma50", "dd_52w", "range_pos",
            "ret_20d", "ret_60d", "vol_pct"]

    print("=" * 78)
    print("  WHAT YOUR ENTRIES LOOK LIKE  (n=%d) vs every other day (n=%d)"
          % (len(E), len(B)))
    print("=" * 78)
    print("  %-12s %12s %12s %10s" % ("feature", "your entries", "typical day",
                                      "percentile"))
    for c in cols:
        me = E[c].median()
        allv = B[c].median()
        pct = (B[c] < me).mean() * 100
        print("  %-12s %12.3f %12.3f %9.0f%%" % (c, me, allv, pct))

    print("\n  percentile = where your typical entry sits in the full history")
    print("  of that measure. 50%% means you are not selecting on it at all.")

    print("\n" + "=" * 78)
    print("  BULLISH RSI DIVERGENCE -- the pattern you described on BTC")
    print("=" * 78)
    print("  present on %.0f%% of your entry days" % (100 * E.div_bull.mean()))
    print("  present on %.0f%% of all days" % (100 * B.div_bull.mean()))
    lift = E.div_bull.mean() / max(B.div_bull.mean(), 1e-9)
    print("  you enter on a divergence %.1fx more often than chance" % lift)

    print("\n" + "=" * 78)
    print("  YOUR ENTRIES, ONE BY ONE (non-SLV)")
    print("=" * 78)
    print("  %-6s %-12s %7s %7s %9s %9s %6s"
          % ("sym", "date", "rsi_d", "rsi_w", "vs200d", "dd52w", "div"))
    for _, r in E[E.symbol != "SLV"].sort_values("date").iterrows():
        print("  %-6s %-12s %7.1f %7.1f %+8.1f%% %+8.1f%% %6s"
              % (r.symbol, str(r.date.date()), r.rsi_d, r.rsi_w,
                 100 * r.vs_ma200, 100 * r.dd_52w, "YES" if r.div_bull else ""))


if __name__ == "__main__":
    main()
