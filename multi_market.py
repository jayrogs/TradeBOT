"""
multi_market.py -- the hourly system sweep, run across ten independent markets.

    python multi_market.py

WHY THIS IS A STRONGER TEST THAN MORE CONFIGURATIONS
Adding configurations to one instrument samples the same noise harder -- already
demonstrated: going from 396 to 1,586 configs on ES made the NULL win, not the
real data. Running the SAME configurations across unrelated markets asks a
different and much harder question:

    does anything survive on markets it was never tuned to?

A rule that works on ES, Bitcoin, crude, the yen and a uranium miner is
describing something about markets. A rule that works on one is describing that
one sample.

MARKETS (ten, deliberately unalike)
    ES=F      S&P 500 futures        BTC-USD   Bitcoin, 24/7
    QQQ       Nasdaq ETF             TSLA      single large-cap stock
    UUUU      small-cap uranium      CL=F      crude oil
    NG=F      natural gas            EURUSD=X  euro
    USDJPY=X  yen                    GBPUSD=X  sterling

Each gets its own realistic cost, its own 60/40 search-and-holdout split, and
the same ~1,700 configurations.

THE HEADLINE TEST
For every configuration, average its Sharpe across all ten markets in the search
period, rank by that, then look at what those same configurations did in the
held-back period across all ten. If the top cross-market configs hold up, that
is real. If they collapse the way single-market winners did, the answer is the
same as it has been.

CAVEAT RECORDED IN ADVANCE: NG=F carries heavy contract-roll contamination
(48% of its large moves land in roll windows against an 8% baseline). Its
results are reported but should not be trusted on their own.
"""

import os
import warnings

import numpy as np
import pandas as pd

import es_hourly as E
import es_hourly2 as E2

warnings.filterwarnings("ignore")

CACHE = os.path.join("cache", "multi_hourly.pkl")

# realistic round-trip cost per market, as a fraction of notional
MARKETS = {
    "ES=F":     ("S&P futures",   0.000043),
    "QQQ":      ("Nasdaq ETF",    0.000100),
    "TSLA":     ("Tesla",         0.000200),
    "UUUU":     ("uranium small", 0.001500),
    "BTC-USD":  ("Bitcoin",       0.000600),
    "CL=F":     ("crude oil",     0.000140),
    "NG=F":     ("nat gas",       0.000400),
    "EURUSD=X": ("EUR/USD",       0.000100),
    "USDJPY=X": ("USD/JPY",       0.000100),
    "GBPUSD=X": ("GBP/USD",       0.000120),
}


def load_all(refresh=False):
    if os.path.exists(CACHE) and not refresh:
        return pd.read_pickle(CACHE)
    import yfinance as yf
    out = {}
    for s in MARKETS:
        d = yf.download(s, interval="1h", period="730d", progress=False,
                        auto_adjust=False).dropna()
        if len(d) < 2000:
            print("  skipping %s (%d bars)" % (s, len(d)))
            continue
        d.columns = [c[0] if isinstance(c, tuple) else c for c in d.columns]
        try:
            d.index = d.index.tz_convert("America/New_York")
        except Exception:
            d.index = d.index.tz_localize("UTC").tz_convert("America/New_York")
        out[s] = d
        print("  %-10s %6d bars  %s -> %s"
              % (s, len(d), d.index[0].date(), d.index[-1].date()))
    pd.to_pickle(out, CACHE)
    return out


def run_market(sym, d, cost):
    """All configurations on one market. Returns a tidy frame."""
    E.COST = cost
    c = d["Close"].values.astype(float)
    ret = np.zeros(len(c))
    ret[1:] = c[1:] / c[:-1] - 1
    n = len(c)
    cut = int(n * E.SPLIT)
    m1 = np.zeros(n, bool); m1[:cut] = True
    m2 = np.zeros(n, bool); m2[cut:] = True

    base = E.build_all(d)
    systems = E2.build_more(d, base)

    bh1 = E.evaluate(np.ones(n), ret, m1, min_trades=0)
    bh2 = E.evaluate(np.ones(n), ret, m2, min_trades=0)

    rows = []
    for fam, name, pos in systems:
        a = E.evaluate(pos, ret, m1)
        b = E.evaluate(pos, ret, m2)
        if a is None or b is None:
            continue
        rows.append(dict(symbol=sym, config="%s | %s" % (fam, name), family=fam,
                         s1=a["sharpe"], s2=b["sharpe"], c2=b["cagr"], dd2=b["dd"]))
    r = pd.DataFrame(rows)
    return r, bh1, bh2


def main():
    print("loading hourly bars for %d markets..." % len(MARKETS))
    data = load_all()

    all_rows, bh = [], {}
    for sym, (name, cost) in MARKETS.items():
        if sym not in data:
            continue
        print("\nsweeping %-10s (%s, cost %.4f%% round trip)"
              % (sym, name, 100 * cost))
        r, b1, b2 = run_market(sym, data[sym], cost)
        bh[sym] = (b1, b2)
        all_rows.append(r)
        best = r.loc[r.s1.idxmax()]
        print("  %d configs | buy&hold search %.2f held %.2f | best search %.2f -> held %.2f"
              % (len(r), b1["sharpe"], b2["sharpe"], best.s1, best.s2))

    R = pd.concat(all_rows, ignore_index=True)
    R.to_csv("multi_market_results.csv", index=False)

    # ---------------------------------------------------------- per market
    print("\n" + "=" * 84)
    print("  PER MARKET: best configuration found, and what it did held back")
    print("=" * 84)
    print("  %-10s %-30s %8s %8s %9s %9s"
          % ("market", "best config in search", "search", "HELD", "b&h held", "CAGR held"))
    for sym in R.symbol.unique():
        g = R[R.symbol == sym]
        b = g.loc[g.s1.idxmax()]
        print("  %-10s %-30s %8.2f %8.2f %9.2f %+8.1f%%"
              % (sym, b.config[:30], b.s1, b.s2, bh[sym][1]["sharpe"], 100 * b.c2))

    # ---------------------------------------------- cross-market consistency
    print("\n" + "=" * 84)
    print("  THE REAL TEST: configurations averaged across all ten markets")
    print("=" * 84)
    piv1 = R.pivot_table(index="config", columns="symbol", values="s1")
    piv2 = R.pivot_table(index="config", columns="symbol", values="s2")
    common = piv1.dropna(thresh=int(0.8 * piv1.shape[1])).index
    piv1, piv2 = piv1.loc[common], piv2.loc[common]
    m1 = piv1.mean(axis=1)
    m2 = piv2.mean(axis=1)
    print("  %d configurations ran on at least 8 of the 10 markets" % len(m1))
    print("  correlation of cross-market mean Sharpe, search vs held back: %+.3f"
          % m1.corr(m2))

    top = m1.nlargest(25)
    print("\n  top 25 by AVERAGE search Sharpe across markets:")
    print("    mean search Sharpe   %+.2f" % top.mean())
    print("    mean HELD-BACK       %+.2f" % m2.loc[top.index].mean())
    print("    still positive held  %d of 25" % (m2.loc[top.index] > 0).sum())
    bh_held = np.mean([bh[s][1]["sharpe"] for s in bh])
    print("    average buy & hold held back across markets: %+.2f" % bh_held)
    print("    of the top 25, beat buy & hold held back: %d"
          % (m2.loc[top.index] > bh_held).sum())

    print("\n  %-42s %8s %8s %7s" % ("config", "search", "HELD", "n mkts"))
    for cfg in top.index[:15]:
        print("  %-42s %8.2f %8.2f %7d"
              % (cfg[:42], m1[cfg], m2[cfg], int(piv1.loc[cfg].notna().sum())))

    # how many markets does each top config actually work on?
    print("\n  BREADTH: of the top 25 by search, how many markets are they")
    print("  positive on in the HELD-BACK period?")
    breadth = (piv2.loc[top.index] > 0).sum(axis=1)
    print("    median %d of 10 markets, best %d, worst %d"
          % (breadth.median(), breadth.max(), breadth.min()))
    print("    (a coin flip would give 5 of 10)")

    # ---------------------------------------------------------- by family
    print("\n" + "=" * 84)
    print("  BY FAMILY, averaged across all markets")
    print("=" * 84)
    R["fam0"] = R.family.str.replace(r"_(rth|onx|tf|tf2|short|stop)$", "",
                                     regex=True)
    fam = R.groupby("fam0").agg(n=("s1", "size"), s1=("s1", "mean"),
                                s2=("s2", "mean"),
                                corr=("s1", lambda x: np.nan))
    for f in fam.index:
        g = R[R.fam0 == f]
        fam.loc[f, "corr"] = g.s1.corr(g.s2)
    print("  %-16s %7s %9s %9s %9s" % ("family", "n", "search", "HELD", "corr"))
    for f, x in fam.sort_values("s2", ascending=False).iterrows():
        print("  %-16s %7d %9.2f %9.2f %9.2f" % (f, x.n, x.s1, x.s2, x["corr"]))

    print("\n  NOTE: NG=F carries heavy roll contamination; treat its rows with suspicion.")


if __name__ == "__main__":
    main()
