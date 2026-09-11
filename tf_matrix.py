"""
tf_matrix.py -- the user's actual method, tested as a TIMEFRAME PAIR.

    python tf_matrix.py

THE METHOD, in their words:
    "weekly OS into lower low with no follow through. this was with a healthy
     3-Month candle uptrend. So I wanted to apply that across all timeframes."

Two timeframes, not one:
    HIGHER TF   must be in a healthy uptrend
    LOWER TF    oversold RSI, a lower low, and NO FOLLOW THROUGH (it reclaims)

My earlier spring.py test omitted the higher-timeframe filter entirely, so it
measured the pattern in downtrends and chop as well -- exactly the contexts the
user would never take it in. That made the test meaningless for their method.
This corrects it.

TIMEFRAMES THEY TRACK: 3M, M, W, 3D, D, 4H, 1H, 30M, 15M, 5M
    3M / M / W / 3D / D   built from daily bars, ~16 years
    4H / 1H               built from hourly bars, ~2 years
    30M / 15M / 5M        only 60 days available -- cannot be tested honestly,
                          and that limit is reported rather than papered over.

HEALTHY UPTREND on the higher timeframe, frozen definition:
    close above its own EMA12, and that EMA12 rising

SIGNAL on the lower timeframe, frozen definition:
    1. RSI(14) below 40 at the break
    2. a candle low below a prior confirmed swing low
    3. reclaimed: a close back above that prior low within 4 bars
       (if it instead closes 8% further below, the setup is dead)
"""

import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

STOCKS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD", "JPM", "WMT", "XOM", "CVX",
          "SPY", "QQQ", "IWM", "GLD", "SLV", "GDX", "XLE", "TLT", "UUUU"]
CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD", "DOGE-USD",
          "LTC-USD", "LINK-USD"]

DAILY_RULES = {"3M": "QE", "M": "ME", "W": "W-FRI", "3D": "3D", "D": None}
HOURLY_RULES = {"4H": "4h", "1H": None}
AGG = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
PIVOT = 2


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs)


def fetch(sym, hourly=False):
    import yfinance as yf
    if hourly:
        d = yf.download(sym, interval="1h", period="730d", progress=False,
                        auto_adjust=False)
    else:
        d = yf.download(sym, start="2010-01-01", end="2026-08-20",
                        progress=False, auto_adjust=False)
    d = d.dropna()
    if len(d) < 200:
        return None
    d.columns = [x[0] if isinstance(x, tuple) else x for x in d.columns]
    if getattr(d.index, "tz", None) is not None:
        d.index = d.index.tz_localize(None)
    return d


def resample(d, rule):
    return d if rule is None else d.resample(rule).agg(AGG).dropna()


def healthy(df):
    """Higher-timeframe uptrend: above its own EMA12, and that EMA12 rising."""
    c = df["Close"].values.astype(float)
    e = pd.Series(c).ewm(span=12, adjust=False).mean().values
    rising = np.concatenate([[False], np.diff(e) > 0])
    return pd.Series((c > e) & rising, index=df.index)


def springs(df, oversold=40, reclaim=4, fail=0.08):
    """Oversold, lower low, no follow through. True on the reclaim bar."""
    c = df["Close"].values.astype(float)
    l = df["Low"].values.astype(float)
    r = rsi(c)
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
    return pd.Series(sig, index=df.index)


def run(syms, pairs, hourly, horizons):
    out = []
    for sym in syms:
        d = fetch(sym, hourly)
        if d is None:
            continue
        rules = HOURLY_RULES if hourly else DAILY_RULES
        for lo_tf, hi_tf in pairs:
            lo = resample(d, rules.get(lo_tf, DAILY_RULES.get(lo_tf)))
            hi = resample(d, rules.get(hi_tf, DAILY_RULES.get(hi_tf)))
            if len(lo) < 80 or len(hi) < 25:
                continue
            sig = springs(lo)
            hh = healthy(hi).reindex(lo.index, method="ffill").fillna(False)
            c = lo["Close"].values.astype(float)
            for h in horizons:
                fwd = pd.Series(c).shift(-h) / pd.Series(c) - 1
                ok = fwd.notna().values
                base = float(fwd[ok].mean())
                gated = sig.values & hh.values & ok
                raw = sig.values & ok
                if gated.sum() < 4:
                    continue
                out.append(dict(symbol=sym, pair="%s in %s" % (lo_tf, hi_tf),
                                h=h, n_gated=int(gated.sum()), n_raw=int(raw.sum()),
                                gated=float(fwd[gated].mean()) - base,
                                raw=float(fwd[raw].mean()) - base if raw.sum() >= 4 else np.nan,
                                hit=float((fwd[gated] > 0).mean())))
    return pd.DataFrame(out)


def report(R, title, horizons):
    print("\n" + "=" * 86)
    print("  %s" % title)
    print("=" * 86)
    print("  %-12s %6s %8s %16s %16s %8s"
          % ("pair", "horiz", "signals", "WITH trend gate", "without gate", "hit%"))
    for pair in R.pair.unique():
        for h in horizons:
            g = R[(R.pair == pair) & (R.h == h)]
            if g.empty or g.n_gated.sum() < 15:
                continue
            print("  %-12s %6d %8d %+15.2f%% %+15.2f%% %7.0f%%"
                  % (pair, h, int(g.n_gated.sum()), 100 * g.gated.mean(),
                     100 * g.raw.mean(), 100 * g.hit.mean()))


def main():
    daily_pairs = [("W", "3M"), ("W", "M"), ("3D", "M"), ("3D", "W"),
                   ("D", "W"), ("D", "M")]
    hourly_pairs = [("1H", "4H"), ("4H", "1H")]

    print("Timeframes trackable with available data:")
    print("  3M, M, W, 3D, D   -- from daily bars, ~16 years")
    print("  4H, 1H            -- from hourly bars, ~2 years")
    print("  30M, 15M, 5M      -- only 60 days exists. NOT TESTED.")

    for syms, nm in [(CRYPTO, "CRYPTO"), (STOCKS, "STOCKS")]:
        R = run(syms, daily_pairs, False, [4, 13, 26])
        if not R.empty:
            report(R, "%s -- lower-TF spring inside a healthy higher-TF uptrend"
                   % nm, [4, 13, 26])
            R.to_csv("tf_matrix_%s.csv" % nm.lower(), index=False)

    for syms, nm in [(CRYPTO, "CRYPTO"), (STOCKS, "STOCKS")]:
        R = run(syms, hourly_pairs, True, [24, 120])
        if not R.empty:
            report(R, "%s -- intraday pairs (2 years of hourly only)" % nm,
                   [24, 120])

    print("\n  'WITH trend gate' is the user's actual method.")
    print("  'without gate' is what I tested before, and it was the wrong test.")


if __name__ == "__main__":
    main()
