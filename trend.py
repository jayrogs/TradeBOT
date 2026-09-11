"""
trend.py -- cross-asset trend following, per trend_spec.md.

    python trend.py

Hold an asset while its own 12-month return is positive, size inversely to its
volatility, rebalance monthly, otherwise sit in cash. Fourteen ETFs across
equities, bonds, commodities and currencies.

The point is not to beat SPY on return. It is to earn a decent return that is
NOT the same bet as SPY. Judged on Sharpe, drawdown and correlation, per spec
section 7.
"""

import argparse
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache", "etf_prices.csv")

UNIVERSE = {
    "SPY": "equity", "QQQ": "equity", "IWM": "equity",
    "EFA": "equity", "EEM": "equity",
    "TLT": "bond", "IEF": "bond", "LQD": "bond", "HYG": "bond",
    "GLD": "commodity", "SLV": "commodity", "DBC": "commodity", "DBA": "commodity",
    "UUP": "currency", "VNQ": "real assets",
}

DISCOVERY = ("2007-01-01", "2018-12-31")
CONFIRM = ("2019-01-01", "2025-12-31")

LOOKBACK = 252         # spec sec.3, frozen
VOL_WIN = 60           # spec sec.4
MAX_W = 0.25           # spec sec.4
COST = 0.0010          # spec sec.5, per side


def load(refresh=False):
    """Dividend-adjusted daily closes. Bond ETFs pay most of their return as
    income, so price-only would misstate the whole exercise."""
    if os.path.exists(CACHE) and not refresh:
        return pd.read_csv(CACHE, index_col=0, parse_dates=True)
    import yfinance as yf
    syms = sorted(UNIVERSE)
    raw = yf.download(syms, start="2004-01-01", end="2026-08-18",
                      auto_adjust=False, progress=False, group_by="ticker",
                      threads=True)
    px = pd.DataFrame({s: raw[s]["Adj Close"] for s in syms}).dropna(how="all")
    if getattr(px.index, "tz", None) is not None:
        px.index = px.index.tz_localize(None)
    px.to_csv(CACHE)
    return px


def backtest(px, start, end, lookback=LOOKBACK, cost=COST):
    """Monthly-rebalanced, vol-weighted trend book. Signals use only data up to
    the rebalance date; the new book is applied from the NEXT trading day."""
    ret = px.pct_change()
    vol = ret.rolling(VOL_WIN).std()
    mom = px / px.shift(lookback) - 1.0

    idx = px.index
    rebal = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last().values
    rebal = pd.DatetimeIndex(rebal)

    weights = pd.DataFrame(0.0, index=idx, columns=px.columns)
    for dt in rebal:
        m, v = mom.loc[dt], vol.loc[dt]
        hold = (m > 0) & v.notna() & (v > 0) & px.loc[dt].notna()
        w = pd.Series(0.0, index=px.columns)
        if hold.any():
            inv = (1.0 / v[hold])
            w[hold] = inv / inv.sum()
            # cap, then renormalise; repeat until stable
            for _ in range(10):
                over = w > MAX_W
                if not over.any():
                    break
                excess = (w[over] - MAX_W).sum()
                w[over] = MAX_W
                room = w[(~over) & (w > 0)]
                if room.empty:
                    break
                w[room.index] += excess * room / room.sum()
        # applied from the next session, never the signal day itself
        nxt = idx.searchsorted(dt, side="right")
        if nxt < len(idx):
            weights.iloc[nxt:] = w.values

    port = (weights.shift(1) * ret).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1)
    port = port - turnover * cost

    sel = (idx >= pd.Timestamp(start)) & (idx <= pd.Timestamp(end))
    return port[sel].dropna(), weights[sel], turnover[sel]


def perf(r, label=""):
    if len(r) < 250:
        return dict(label=label, cagr=np.nan, vol=np.nan, sharpe=np.nan, dd=np.nan)
    eq = (1 + r).cumprod()
    yrs = len(r) / 252.0
    return dict(label=label,
                cagr=eq.iloc[-1] ** (1 / yrs) - 1,
                vol=r.std(ddof=1) * np.sqrt(252),
                sharpe=r.mean() / r.std(ddof=1) * np.sqrt(252),
                dd=float((eq / eq.cummax() - 1).min()))


def bench(px, start, end):
    ret = px.pct_change()
    sel = (px.index >= pd.Timestamp(start)) & (px.index <= pd.Timestamp(end))
    spy = ret["SPY"][sel].dropna()
    sixty = (0.6 * ret["SPY"] + 0.4 * ret["IEF"])[sel].dropna()
    return spy, sixty


def show(px, start, end, title):
    r, w, to = backtest(px, start, end)
    spy, sixty = bench(px, start, end)
    a = perf(r, "trend (12m)")
    b = perf(spy, "SPY")
    c = perf(sixty, "60/40")
    corr = r.corr(spy.reindex(r.index))

    print("\n" + "=" * 72)
    print("  %s   %s to %s" % (title, start, end))
    print("=" * 72)
    print("  %-14s %9s %9s %8s %10s" % ("", "CAGR", "vol", "Sharpe", "max DD"))
    for x in (a, b, c):
        print("  %-14s %+8.2f%% %8.2f%% %8.2f %9.1f%%"
              % (x["label"], 100 * x["cagr"], 100 * x["vol"], x["sharpe"],
                 100 * x["dd"]))
    print("  " + "-" * 68)
    print("  correlation to SPY      %.2f" % corr)
    print("  average assets held     %.1f of %d" % ((w > 0).sum(axis=1).mean(),
                                                    len(UNIVERSE)))
    print("  share of time in cash   %.0f%%" % (100 * (w.sum(axis=1) < 0.01).mean()))
    print("  annual turnover         %.0fx" % (to.sum() / (len(r) / 252)))

    ok = [
        ("Sharpe >= 0.60", a["sharpe"] >= 0.60, "%.2f" % a["sharpe"]),
        ("max DD < half of SPY", a["dd"] > b["dd"] / 2,
         "%.1f%% vs %.1f%% allowed" % (100 * a["dd"], 100 * b["dd"] / 2)),
        ("correlation to SPY < 0.60", corr < 0.60, "%.2f" % corr),
        ("CAGR >= 60/40", a["cagr"] >= c["cagr"],
         "%.2f%% vs %.2f%%" % (100 * a["cagr"], 100 * c["cagr"])),
    ]
    print("\n  PRE-REGISTERED CRITERIA (trend_spec.md section 7)")
    for n, good, det in ok:
        print("    [%s] %-28s %s" % ("PASS" if good else "FAIL", n, det))
    print("    -> %s" % ("PASSES" if all(x[1] for x in ok) else "FAILS"))
    return a, all(x[1] for x in ok), r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    px = load(args.refresh)
    print("loaded %d funds, %s to %s"
          % (px.shape[1], px.index[0].date(), px.index[-1].date()))

    _, d_ok, _ = show(px, *DISCOVERY, title="DISCOVERY")
    _, c_ok, _ = show(px, *CONFIRM, title="CONFIRMATION -- untouched window")

    print("\n" + "=" * 72)
    print("  ROBUSTNESS -- not a menu. The 12-month version is the one judged.")
    print("  These show whether the result depends on one lucky number.")
    print("=" * 72)
    print("  %-12s %10s %9s %9s %10s %9s" %
          ("lookback", "disc CAGR", "Sharpe", "maxDD", "conf CAGR", "Sharpe"))
    for lb, nm in [(63, "3 months"), (126, "6 months"), (252, "12 months"),
                   (378, "18 months")]:
        rd, _, _ = backtest(px, *DISCOVERY, lookback=lb)
        rc, _, _ = backtest(px, *CONFIRM, lookback=lb)
        pd_, pc_ = perf(rd), perf(rc)
        print("  %-12s %+9.2f%% %9.2f %8.1f%% %+9.2f%% %9.2f"
              % (nm, 100 * pd_["cagr"], pd_["sharpe"], 100 * pd_["dd"],
                 100 * pc_["cagr"], pc_["sharpe"]))

    print("\n  overall: %s" %
          ("PASSES both windows" if d_ok and c_ok else
           "FAILS -- per spec section 9 we say so and do not tune it"))
    print("  2026 remains untouched.")


if __name__ == "__main__":
    main()
