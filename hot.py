"""
hot.py -- which markets have actually been worth trading since 2020?

    python hot.py

Screens the whole universe on the things that matter for a discretionary swing
trader: is it liquid, does it move, and does it TREND rather than chop.

    return      annualised, 2020 onward
    vol         annualised daily volatility
    liquidity   median daily dollar volume
    trending    share of days the trend engine reads UP or DOWN
                (the rest is FLAT or BALANCE -- chop, where nothing works)
    run         average bars a trend label holds before flipping
    drawdown    worst peak-to-trough

"Hot" here means trending and liquid, not just volatile. A market that doubles
and halves every quarter without ever holding a direction is untradeable for
this method.
"""

import warnings

import numpy as np
import pandas as pd

import panel as P

warnings.filterwarnings("ignore")

START = "2020-01-01"
MIN_ADV = 20e6          # $20M/day
FUT_OK = {"ES=F", "NQ=F", "CL=F", "NG=F", "GC=F", "SI=F", "HG=F", "ZN=F", "ZB=F"}


def measure(sym, d):
    d = d[d.index >= pd.Timestamp(START)]
    if len(d) < 400:
        return None
    c = d["Close"].values.astype(float)
    if not np.all(np.isfinite(c)) or c.min() <= 0:
        return None
    r = pd.Series(c).pct_change().dropna()
    yrs = (d.index[-1] - d.index[0]).days / 365.25
    eq = pd.Series(c)
    dd = float((eq / eq.cummax() - 1).min())
    adv = np.nan
    if "Volume" in d:
        v = d["Volume"].values.astype(float)
        adv = float(np.nanmedian(c * v))
    st, _, _ = P.trend_state(d)
    trending = float(np.mean((st == "UP") | (st == "DOWN")))
    flips = sum(1 for i in range(1, len(st)) if st[i] != st[i - 1])
    return dict(symbol=sym, cagr=(c[-1] / c[0]) ** (1 / yrs) - 1,
                vol=r.std() * np.sqrt(252), adv=adv, dd=dd,
                trending=trending, run=len(st) / max(flips, 1),
                up=float(np.mean(st == "UP")), down=float(np.mean(st == "DOWN")),
                bars=len(d))


def main():
    store = pd.read_pickle("cache/scan_prices.pkl")
    rows = []
    for sym, d in store.items():
        try:
            m = measure(sym, d)
        except Exception:
            continue
        if m:
            rows.append(m)
    R = pd.DataFrame(rows)
    # keep only things you can actually trade in size
    liquid = R[(R.adv >= MIN_ADV) | (R.symbol.isin(FUT_OK)) |
               (R.symbol.str.endswith("-USD") & (R.adv >= 1e8))]
    R.to_csv("hot_markets.csv", index=False)

    def show(title, df, n=18, sort="trending"):
        print("\n" + "=" * 88)
        print("  " + title)
        print("=" * 88)
        print("  %-10s %9s %8s %10s %9s %8s %9s"
              % ("symbol", "return/yr", "vol", "liquidity", "trending", "run",
                 "max DD"))
        for _, x in df.sort_values(sort, ascending=False).head(n).iterrows():
            liq = ("$%.0fM" % (x.adv / 1e6)) if np.isfinite(x.adv) else "  -"
            print("  %-10s %+8.1f%% %7.0f%% %10s %8.0f%% %8.1f %8.0f%%"
                  % (x.symbol, 100 * x.cagr, 100 * x.vol, liq,
                     100 * x.trending, x.run, 100 * x.dd))

    print("universe: %d markets, %d liquid enough to trade"
          % (len(R), len(liquid)))
    print("median 'trending' across everything: %.0f%%  (rest is chop)"
          % (100 * R.trending.median()))

    show("MOST TRENDING, liquid only -- these hold a direction", liquid)
    show("BIGGEST MOVERS since 2020 (liquid)", liquid, sort="cagr")
    show("CHOPPIEST -- avoid these for trend methods", liquid.assign(
        trending=-liquid.trending), sort="trending")

    print("\n" + "=" * 88)
    print("  BY GROUP")
    print("=" * 88)
    groups = {
        "crypto": lambda s: s.endswith("-USD"),
        "futures": lambda s: s.endswith("=F"),
        "metals/miners": lambda s: s in ("GLD", "SLV", "GDX", "GDXJ", "UUUU",
                                         "URA", "PPLT", "PALL", "GC=F", "SI=F"),
        "energy": lambda s: s in ("XLE", "XOP", "OIH", "USO", "UNG", "CL=F",
                                  "NG=F", "CVX", "XOM"),
        "index ETF": lambda s: s in ("SPY", "QQQ", "IWM", "DIA", "MDY"),
        "single stocks": lambda s: not (s.endswith("-USD") or s.endswith("=F")),
    }
    print("  %-16s %7s %11s %9s %9s" % ("group", "n", "return/yr", "trending", "vol"))
    for g, fn in groups.items():
        x = liquid[liquid.symbol.map(fn)]
        if len(x) < 2:
            continue
        print("  %-16s %7d %+10.1f%% %8.0f%% %8.0f%%"
              % (g, len(x), 100 * x.cagr.median(), 100 * x.trending.median(),
                 100 * x.vol.median()))
    print("\n  full table: hot_markets.csv")


if __name__ == "__main__":
    main()
