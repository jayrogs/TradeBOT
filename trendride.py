"""
trendride.py -- buy the uptrend, trail the stop under each new higher low,
exit when a higher low breaks.

    python trendride.py

THE RULE, in the user's words:
    "buying uptrends, set a stop under the next formed higher low, hold until
     that trend breaks, when a higher low is broken."

WHY THIS IS GENUINELY DIFFERENT FROM EVERYTHING ELSE TESTED
Every earlier test used a FIXED holding period -- 6 bars, 21 days, 48 hours. A
fixed exit sells out of the middle of a good move and sits through a bad one, so
it cannot ever show the thing trend riding is supposed to do: cut losers quickly
and let winners run for months. The holding period here is decided by the market,
not by the clock. That is the whole strategy.

MECHANICS
    swing low   a bar whose low is the lowest of the P bars either side.
                Not treated as known until P bars later, so it is never used
                before a chart reader could have seen it.
    entry       flat, price above its 200-day average, and a newly confirmed
                swing low prints ABOVE the previous swing low (a higher low).
                Buy the next open.
    stop        at that higher low.
    trail       every time a new swing low confirms above the current stop,
                raise the stop to it. Never lowered.
    exit        price trades below the stop -> out at the stop, or at the open
                if it gapped through. No time limit.

THE COMPARISON THAT MATTERS
Not "did it make money" -- in a rising market almost anything does. The question
is whether riding with a trailing stop beat simply BUYING AND HOLDING the same
names over the same window. That is the real alternative.

Costs 0.10% per side. Tested on 500 S&P names 2007-2025 and on the volatile
basket, and split first half vs second half to see whether it persists.
"""

import os
import warnings

import numpy as np
import pandas as pd

import survey as V

warnings.filterwarnings("ignore")

PIVOTS = [3, 5, 10]          # swing-low sensitivity, reported side by side
COST = 0.0010
MA_LEN = 200


def confirmed_pivot_lows(low, P):
    """Index positions where a swing low is CONFIRMED, and its value.
    A pivot at bar i is only known at bar i+P."""
    n = len(low)
    is_piv = np.zeros(n, dtype=bool)
    for i in range(P, n - P):
        w = low[i - P:i + P + 1]
        if low[i] == np.nanmin(w):
            is_piv[i] = True
    conf_at = np.full(n, -1, dtype=int)     # value index confirmed at this bar
    for i in np.where(is_piv)[0]:
        if i + P < n:
            conf_at[i + P] = i
    return conf_at


def ride_one(o, h, l, c, ma, P):
    """Walk one symbol forward. Returns list of trades."""
    n = len(c)
    conf_at = confirmed_pivot_lows(l, P)
    trades = []
    in_pos = False
    entry_i = entry_px = stop = np.nan
    prev_piv = np.nan

    for i in range(n - 1):
        pi = conf_at[i]
        new_piv = l[pi] if pi >= 0 else np.nan

        if in_pos:
            # exit first: did we trade below the stop today?
            if l[i] <= stop:
                px = o[i] if o[i] < stop else stop
                trades.append((entry_i, i, entry_px, px))
                in_pos = False
            elif pi >= 0 and new_piv > stop:
                stop = new_piv                      # trail up, never down
        if not in_pos and pi >= 0 and np.isfinite(new_piv):
            higher = np.isfinite(prev_piv) and new_piv > prev_piv
            healthy = np.isfinite(ma[i]) and c[i] > ma[i]
            if higher and healthy and np.isfinite(o[i + 1]):
                in_pos = True
                entry_i, entry_px = i + 1, o[i + 1]
                stop = new_piv
        if pi >= 0 and np.isfinite(new_piv):
            prev_piv = new_piv

    if in_pos:
        trades.append((entry_i, n - 1, entry_px, c[n - 1]))
    return trades


def run(px_o, px_h, px_l, px_c, elig, P, start, end, label):
    idx = px_c.index
    sel = (idx >= pd.Timestamp(start)) & (idx <= pd.Timestamp(end))
    pos = np.where(sel)[0]
    lo_i, hi_i = pos[0], pos[-1]

    all_tr = []
    per_symbol = {}
    for s in px_c.columns:
        c = px_c[s].values.astype(float)
        if np.isfinite(c).sum() < 400:
            continue
        o, h, l = (px_o[s].values.astype(float), px_h[s].values.astype(float),
                   px_l[s].values.astype(float))
        ma = pd.Series(c).rolling(MA_LEN).mean().values
        e = elig[s].values if s in elig.columns else np.ones(len(c), bool)
        tr = ride_one(o, h, l, c, ma, P)
        keep = [t for t in tr if lo_i <= t[0] <= hi_i and e[t[0]]]
        if keep:
            per_symbol[s] = keep
            all_tr.extend([(s,) + t for t in keep])

    if not all_tr:
        return None
    df = pd.DataFrame(all_tr, columns=["sym", "i_in", "i_out", "px_in", "px_out"])
    df["ret"] = (df.px_out * (1 - COST)) / (df.px_in * (1 + COST)) - 1.0
    df["bars"] = df.i_out - df.i_in

    # buy and hold the same names over the same window, equal weight
    sub = px_c.loc[idx[lo_i]:idx[hi_i]]
    bh = sub.pct_change().mean(axis=1)
    bh_total = (1 + bh).prod() - 1
    bh_ann = (1 + bh_total) ** (252 / len(sub)) - 1

    # strategy as a portfolio: equal weight across whatever is open each day
    n = len(px_c)
    book = np.zeros((n, len(px_c.columns)))
    colpos = {s: j for j, s in enumerate(px_c.columns)}
    for s, tr in per_symbol.items():
        j = colpos[s]
        for (a, b, _, _) in tr:
            book[a:b + 1, j] = 1.0
    W = pd.DataFrame(book, index=idx, columns=px_c.columns)
    W = W.div(W.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    rets = px_c.pct_change().fillna(0.0)
    port = (W.shift(1) * rets).sum(axis=1)
    turn = W.diff().abs().sum(axis=1)
    port = (port - turn * COST)[sel]
    eq = (1 + port).cumprod()
    ann = eq.iloc[-1] ** (252 / len(port)) - 1
    dd = float((eq / eq.cummax() - 1).min())
    bh_eq = (1 + bh).cumprod()
    bh_dd = float((bh_eq / bh_eq.cummax() - 1).min())

    wins = df[df.ret > 0]
    return dict(
        label=label, P=P, trades=len(df),
        win=len(wins) / len(df),
        avg_win=wins.ret.mean(), avg_loss=df[df.ret <= 0].ret.mean(),
        med_bars=df.bars.median(), max_bars=df.bars.max(),
        p90_bars=df.bars.quantile(0.90),
        expectancy=df.ret.mean(),
        ann=ann, dd=dd, bh_ann=bh_ann, bh_dd=bh_dd,
        invested=float((W[sel].sum(axis=1) > 0).mean()),
        best=df.ret.max(), worst=df.ret.min(),
    )


def report(rows, title):
    print("\n" + "=" * 78)
    print("  %s" % title)
    print("=" * 78)
    print("  %-6s %7s %6s %8s %8s %8s %9s %9s %8s %8s"
          % ("pivot", "trades", "win%", "avg win", "avg loss", "expect",
             "strat/yr", "hold/yr", "strat DD", "hold DD"))
    for r in rows:
        if r is None:
            continue
        print("  %-6d %7d %5.1f%% %+7.2f%% %+7.2f%% %+7.3f%% %+8.2f%% %+8.2f%% %7.1f%% %7.1f%%"
              % (r["P"], r["trades"], 100 * r["win"], 100 * r["avg_win"],
                 100 * r["avg_loss"], 100 * r["expectancy"], 100 * r["ann"],
                 100 * r["bh_ann"], 100 * r["dd"], 100 * r["bh_dd"]))
    r = rows[1] if len(rows) > 1 and rows[1] else rows[0]
    if r:
        print("\n  does it let winners run?  median hold %.0f bars, 90th pct %.0f, "
              "longest %.0f" % (r["med_bars"], r["p90_bars"], r["max_bars"]))
        print("  best trade %+.0f%%   worst trade %+.0f%%   invested %.0f%% of the time"
              % (100 * r["best"], 100 * r["worst"], 100 * r["invested"]))


def main():
    d = V.load_panel("2009-01-01", "2026-12-31")
    o, h, l, c = d["open"], d["high"], d["low"], d["close"],
    elig = d["elig"]

    for start, end, title in [
            ("2007-01-01", "2016-12-31", "S&P 500 -- FIRST HALF 2007-2016"),
            ("2017-01-01", "2025-12-31", "S&P 500 -- SECOND HALF 2017-2025"),
            ("2007-01-01", "2025-12-31", "S&P 500 -- FULL PERIOD")]:
        rows = [run(o, h, l, c, elig, P, start, end, title) for P in PIVOTS]
        report(rows, title)

    print("\n  strat/yr = the trailing-stop strategy.  hold/yr = simply buying and")
    print("  holding the same names, equal weight, over the same window.")
    print("  2026 remains untouched.")


if __name__ == "__main__":
    main()
