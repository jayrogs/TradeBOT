"""
premise_test.py -- is the underlying claim even true in this universe?

    python premise_test.py

The strategy is built on one observation from 169 ChartGuys trades: stocks that
were FALLING short-term at signal time went on to do better than stocks that
were rising. Before engineering anything further, it is worth asking whether
that is true of the S&P 500 at all, separately from any entry, stop or target.

This does not test a strategy. It measures one thing: sort every liquid
S&P 500 name on every day by RSI(14), then look at what the stock did over the
next 30 trading days relative to SPY. If weakness predicts strength, the low-RSI
bucket beats the high-RSI bucket. If it does not, no amount of trade
construction will rescue the idea and the honest move is to stop.

One pre-specified comparison: bottom RSI decile vs top RSI decile. Deciles in
between are printed for shape only, not to be mined.
"""

import numpy as np
import pandas as pd

import data as D
import harness as H
import run_test as R

HORIZON = 30          # trading days forward, matching the spec's time stop
START, END = "2023-01-01", "2025-12-31"


def main():
    feats, sectors, spy, memb = R.load_real(START, END)
    spy_close = spy["Close"].astype(float)
    spy_fwd = spy_close.shift(-HORIZON) / spy_close - 1.0

    rows = []
    lo, hi = pd.Timestamp(START), pd.Timestamp(END)
    for sym, f in feats.items():
        m = memb.get(sym, [])
        if not m:
            continue
        ok = np.zeros(len(f), dtype=bool)
        for a, b in m:
            ok |= (f.index >= a) & (f.index <= b)
        sel = ok & (f.index >= lo) & (f.index <= hi)
        sel &= (f["adv"] >= H.DEFAULTS["min_adv"]).values
        sel &= (f["close"] > H.DEFAULTS["min_price"]).values
        sel &= np.isfinite(f["rsi"]).values
        if not sel.any():
            continue
        sub = f.loc[sel]
        fwd = f["close"].shift(-HORIZON) / f["close"] - 1.0
        rows.append(pd.DataFrame({
            "date": sub.index,
            "sym": sym,
            "rsi": sub["rsi"].values,
            "rngpos": sub["rngpos"].values,
            "fwd": fwd.loc[sub.index].values,
        }))

    d = pd.concat(rows, ignore_index=True).dropna(subset=["fwd"])
    d["spy_fwd"] = d["date"].map(spy_fwd)
    d = d.dropna(subset=["spy_fwd"])
    d["excess"] = d["fwd"] - d["spy_fwd"]

    print("\n%s" % ("=" * 70))
    print("  Forward %d-day return by RSI(14), S&P 500, %s to %s"
          % (HORIZON, START, END))
    print("  %s observations across %d symbols" % (f"{len(d):,}", d.sym.nunique()))
    print("=" * 70)

    d["bucket"] = pd.qcut(d["rsi"], 10, labels=False, duplicates="drop")
    g = d.groupby("bucket").agg(n=("excess", "size"),
                                rsi=("rsi", "mean"),
                                mean_excess=("excess", "mean"),
                                med_excess=("excess", "median"),
                                pct_beat=("excess", lambda x: (x > 0).mean()))
    print("\n  decile  mean RSI       n   mean vs SPY   median vs SPY   %% beating SPY")
    for b, r in g.iterrows():
        print("    %2d      %6.1f   %7d      %+6.2f%%        %+6.2f%%          %5.1f%%"
              % (b + 1, r["rsi"], r["n"], 100 * r["mean_excess"],
                 100 * r["med_excess"], 100 * r["pct_beat"]))

    low = d[d.bucket == g.index.min()]["excess"]
    high = d[d.bucket == g.index.max()]["excess"]
    diff = low.mean() - high.mean()

    # Overlapping windows and same-day cross-sectional correlation both make a
    # plain t-test far too confident. Cluster by date: average the difference
    # within each day, then test the daily series. Still imperfect, but honest
    # about the fact that 200,000 observations are not 200,000 independent facts.
    daily = (d[d.bucket == g.index.min()].groupby("date")["excess"].mean() -
             d[d.bucket == g.index.max()].groupby("date")["excess"].mean()).dropna()
    n_eff = len(daily) / HORIZON        # non-overlapping windows only
    t = daily.mean() / (daily.std(ddof=1) / np.sqrt(max(n_eff, 1)))

    print("\n  PRE-SPECIFIED COMPARISON: lowest RSI decile vs highest")
    print("    lowest  RSI decile  mean vs SPY  %+.2f%%  (n=%s)"
          % (100 * low.mean(), f"{len(low):,}"))
    print("    highest RSI decile  mean vs SPY  %+.2f%%  (n=%s)"
          % (100 * high.mean(), f"{len(high):,}"))
    print("    difference                       %+.2f%%" % (100 * diff))
    print("    t-statistic, clustered by date and de-overlapped:  %+.2f" % t)
    print("    %s" % ("weakness does predict strength here (|t| > 2)"
                      if abs(t) > 2 else
                      "not distinguishable from noise (|t| < 2)"))
    if diff < 0:
        print("\n    NOTE: the sign is BACKWARDS. In this universe over this window,")
        print("    strong names beat weak ones. The premise of strategy_spec_v1")
        print("    does not hold here.")

    # The spec also required the name not be in free-fall. Same split, but only
    # among names in the top 40% of their 252-day range, as the spec demands.
    q = d[d["rngpos"] >= H.DEFAULTS["min_range_pos"]]
    if len(q) > 1000:
        qb = pd.qcut(q["rsi"], 10, labels=False, duplicates="drop")
        ql = q[qb == qb.min()]["excess"]
        qh = q[qb == qb.max()]["excess"]
        print("\n  Same comparison, restricted to names in the top 40%% of their")
        print("  252-day range (spec section 4.2 'not a falling knife'):")
        print("    lowest RSI  %+.2f%%   highest RSI  %+.2f%%   difference %+.2f%%"
              % (100 * ql.mean(), 100 * qh.mean(), 100 * (ql.mean() - qh.mean())))

    d.to_csv("premise_observations.csv", index=False)
    print("\n  wrote premise_observations.csv")


if __name__ == "__main__":
    main()
