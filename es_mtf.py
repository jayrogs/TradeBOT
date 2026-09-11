"""
es_mtf.py -- timeframe alignment on ES futures.

    python es_mtf.py

THE HYPOTHESIS, in the user's words:
    "we don't play when there aren't uptrends on enough time frames. because
     then the wind would be going against us... using smaller time frame trend
     changes into getting into larger timeframe higher lows."

So the pre-specified question is not "does this make money" but something
sharper and much harder to fake:

    DOES REQUIRING MORE TIMEFRAMES TO AGREE MONOTONICALLY IMPROVE THE RESULT?

If alignment matters, results should climb steadily as the requirement goes from
0 to 3 timeframes. A single good number at one threshold is noise; a clean
gradient across four thresholds is structure. That gradient is very hard to
produce by luck, which is why it is the right thing to test.

SETUP
    entry timeframe   1 hour (the smallest with usable history -- see below)
    macro timeframes  4-hour, daily, weekly, each built from the hourly bars
    uptrend on a TF   close > fast EMA > slow EMA, on COMPLETED bars only
    alignment         how many of the three macro timeframes are in uptrend
    trigger           a confirmed hourly swing low printing above the previous
                      one, i.e. a higher low, while alignment >= threshold
    stop              at that higher low, trailed up on each new higher low
    exit              price trades through the stop. No time limit.

COSTS -- and this is the point of using ES
    1 tick slippage + $4 round-turn commission on ~$386,000 notional
    = 0.0043% per round trip, versus 0.20% charged to stocks in this project.
    47x cheaper. Several ideas that died to stock costs are viable here.

DATA LIMIT, stated plainly
    Sub-hour history is 60 days from this source, which cannot validate
    anything, so 1 hour is the floor. ES hourly covers ~29 months. That is ONE
    instrument over a short window: this test can show a gradient or fail to,
    but it cannot establish a tradeable edge on its own.

LEVERAGE
    Not modelled, deliberately. Leverage multiplies return and drawdown by the
    same factor. It cannot create an edge, and reporting a levered curve would
    only make a weak result look strong.
"""

import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

COST = 0.000043            # round trip, as a fraction of notional
PIVOTS = [3, 5, 10]
FAST, SLOW = 10, 30        # EMA lengths on each macro timeframe
MACRO = {"4h": 4, "daily": 24, "weekly": 120}   # in hourly bars


def load():
    import yfinance as yf
    d = yf.download("ES=F", interval="1h", period="730d", progress=False,
                    auto_adjust=False).dropna()
    d.columns = [c[0] if isinstance(c, tuple) else c for c in d.columns]
    return d[["Open", "High", "Low", "Close"]]


def macro_uptrend(close, span):
    """Uptrend on a coarser timeframe, built by taking every `span`-th hourly
    bar. Shifted one coarse bar so the current, incomplete bar is never used."""
    coarse = close.iloc[::span]
    f = coarse.ewm(span=FAST, adjust=False).mean()
    s = coarse.ewm(span=SLOW, adjust=False).mean()
    up = ((coarse > f) & (f > s)).shift(1)
    return up.reindex(close.index, method="ffill").fillna(False)


def pivot_lows(low, P):
    n = len(low)
    conf = np.full(n, -1, dtype=int)
    for i in range(P, n - P):
        if low[i] == np.nanmin(low[i - P:i + P + 1]) and i + P < n:
            conf[i + P] = i
    return conf


def ride(o, h, l, c, align, need, P):
    n = len(c)
    conf = pivot_lows(l, P)
    trades, pos = [], np.zeros(n)
    in_pos = False
    entry_i = entry_px = stop = np.nan
    prev = np.nan
    for i in range(n - 1):
        pi = conf[i]
        v = l[pi] if pi >= 0 else np.nan
        if in_pos:
            if l[i] <= stop:
                px = o[i] if o[i] < stop else stop
                trades.append((entry_i, i, entry_px, px))
                in_pos = False
            else:
                pos[i] = 1
                if pi >= 0 and v > stop:
                    stop = v
        if not in_pos and pi >= 0 and np.isfinite(v):
            if np.isfinite(prev) and v > prev and align[i] >= need:
                in_pos, entry_i, entry_px, stop = True, i + 1, o[i + 1], v
        if pi >= 0 and np.isfinite(v):
            prev = v
    if in_pos:
        trades.append((entry_i, n - 1, entry_px, c[n - 1]))
        pos[entry_i:] = 1
    return trades, pos


def summarize(trades, pos, c, bars_per_year):
    if len(trades) < 15:
        return None
    r = np.array([(b / a - 1) - COST for (_, _, a, b) in trades])

    # Build the return series FROM THE TRADES, not from a position mask.
    # A position mask credits the move from the prior close to the entry open,
    # which was never captured -- entries here follow a bounce off a higher low,
    # so that phantom gap is positive on average and badly inflates the result.
    strat = np.zeros(len(c))
    for (i_in, i_out, px_in, px_out) in trades:
        if i_in >= len(c) or i_out >= len(c) or i_in > i_out:
            continue
        if i_out == i_in:
            strat[i_in] = px_out / px_in - 1 - COST
            continue
        strat[i_in] = c[i_in] / px_in - 1 - COST      # entry bar: from fill
        for k in range(i_in + 1, i_out):
            strat[k] = c[k] / c[k - 1] - 1
        strat[i_out] = px_out / c[i_out - 1] - 1      # exit bar: to the stop
    eq = np.cumprod(1 + strat)
    yrs = len(c) / bars_per_year
    ann = eq[-1] ** (1 / yrs) - 1
    sd = strat.std(ddof=1) * np.sqrt(bars_per_year)
    dd = float((eq / np.maximum.accumulate(eq) - 1).min())
    wins = r[r > 0]
    return dict(n=len(r), win=len(wins) / len(r), expect=r.mean(),
                avg_win=wins.mean() if len(wins) else np.nan,
                avg_loss=r[r <= 0].mean() if (r <= 0).any() else np.nan,
                ann=ann, sharpe=(strat.mean() / strat.std(ddof=1) * np.sqrt(bars_per_year))
                if strat.std(ddof=1) > 0 else np.nan,
                dd=dd, inmkt=pos.mean())


def main():
    d = load()
    o, h, l, c = (d["Open"].values, d["High"].values,
                  d["Low"].values, d["Close"].values)
    close = d["Close"]
    print("ES hourly: %d bars, %s -> %s"
          % (len(d), d.index[0].date(), d.index[-1].date()))

    ups = {k: macro_uptrend(close, v).values.astype(int) for k, v in MACRO.items()}
    align = sum(ups.values())
    for k, v in ups.items():
        print("  %-7s in uptrend %.0f%% of bars" % (k, 100 * v.mean()))
    print("  alignment distribution: " +
          "  ".join("%d TF: %.0f%%" % (i, 100 * (align == i).mean())
                    for i in range(4)))

    bpy = len(d) / ((d.index[-1] - d.index[0]).days / 365.25)
    bh = (c[-1] / c[0]) ** (1 / ((d.index[-1] - d.index[0]).days / 365.25)) - 1
    print("  buy & hold ES over this window: %+.2f%%/yr" % (100 * bh))

    for P in PIVOTS:
        print("\n" + "=" * 74)
        print("  swing low = %d bars either side" % P)
        print("=" * 74)
        print("  %-14s %6s %6s %9s %9s %9s %8s %8s %7s"
              % ("require", "trades", "win%", "avg win", "avg loss", "expect",
                 "CAGR", "Sharpe", "in mkt"))
        for need in [0, 1, 2, 3]:
            tr, pos = ride(o, h, l, c, align, need, P)
            s = summarize(tr, pos, c, bpy)
            if s is None:
                print("  %-14s too few trades" % ("%d timeframes" % need))
                continue
            print("  %-14s %6d %5.1f%% %+8.2f%% %+8.2f%% %+8.3f%% %+7.2f%% %8.2f %6.0f%%"
                  % ("%d timeframes" % need, s["n"], 100 * s["win"],
                     100 * s["avg_win"], 100 * s["avg_loss"], 100 * s["expect"],
                     100 * s["ann"], s["sharpe"], 100 * s["inmkt"]))

    print("\n  THE QUESTION: does expectancy climb steadily from 0 to 3 timeframes?")
    print("  A gradient is structure. One good row is noise.")
    print("\n  Reminder: one instrument, 29 months. This can falsify the idea or")
    print("  support it, but it cannot establish it.")


if __name__ == "__main__":
    main()
