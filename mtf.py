"""
mtf.py -- the multi-timeframe setup, tested at every scale, on 18 years of data.

    python mtf.py

THE IDEA, in the user's words:
    "Oversold lower timeframes to mark higher lows on healthy uptrend higher
     timeframes... it could even be daily candles, if trying to catch a weekly
     or monthly higher low... a daily tightening wedge."

The important part is that it is scale-invariant. So it gets tested at three
timeframe pairs rather than one, using daily bars back to 2007 -- far more
evidence than the 3 years of hourly data available.

    pair            higher timeframe trend      lower timeframe trigger
    daily->weekly   weekly close > 10-wk > 40-wk    daily bars
    daily->monthly  monthly close > 6-mo > 12-mo    daily bars
    weekly->monthly monthly close > 6-mo > 12-mo    weekly bars

At each pair, four conditions, all required, frozen before running:

  1. HEALTHY UPTREND on the higher timeframe, using only completed higher-
     timeframe bars (last week's close, not this week's part-formed one)
  2. OVERSOLD on the lower timeframe: RSI(14) touched 35 or lower within the
     last 10 lower-timeframe bars
  3. HIGHER LOW: the most recent confirmed swing low is above the previous one.
     A swing low needs 3 bars either side, so it is not treated as known until
     3 bars after it printed
  4. TIGHTENING WEDGE: over the last 10 bars the highs are falling and the lows
     are rising -- the range is converging, which is what "tightening" means
     mechanically. Plus a confirmation close above the previous bar's high.

Each condition is added one at a time so it is clear which part, if any, carries
the result. The full four-condition setup is the one being judged; the
decomposition is attribution, not a menu.

Scored against SPY and against an equal-weight book of the same universe, over
identical days. Discovery 2007-2019, confirmation 2020-2025, 2026 sealed.
"""

import os
import warnings

import numpy as np
import pandas as pd

import survey as V

warnings.filterwarnings("ignore")

DISCOVERY = ("2007-01-01", "2019-12-31")
CONFIRM = ("2020-01-01", "2025-12-31")
HOLDS = [10, 21, 63]

RSI_LEN = 14
OVERSOLD = 35
OVERSOLD_WINDOW = 10
PIVOT = 3
WEDGE_WIN = 10

PAIRS = {
    "daily -> weekly":    dict(rule="W", fast=10, slow=40),
    "daily -> monthly":   dict(rule="ME", fast=6, slow=12),
    "weekly -> monthly":  dict(rule="ME", fast=6, slow=12, low_rule="W"),
}


# ---------------------------------------------------------------- helpers

def resample(px, rule, how):
    return getattr(px.resample(rule), how)()


def rsi(close, n=RSI_LEN):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1.0 / n, adjust=False).mean()
    dn = (-d).clip(lower=0).ewm(alpha=1.0 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).where(dn != 0, 100.0)


def higher_tf_uptrend(close, rule, fast, slow, daily_index):
    """Condition 1, computed on completed higher-timeframe bars only.

    The .shift(1) is the whole ballgame: this week's weekly close is not known
    until the week ends, so using it on Tuesday would be lookahead.
    """
    htf = close.resample(rule).last()
    up = (htf > htf.rolling(fast).mean()) & \
         (htf.rolling(fast).mean() > htf.rolling(slow).mean())
    up = up.shift(1)
    return up.reindex(daily_index, method="ffill").fillna(False)


def confirmed_higher_low(low):
    """Condition 3."""
    is_piv = low.rolling(2 * PIVOT + 1, center=True).min().eq(low)
    is_piv = is_piv.shift(PIVOT).fillna(False)
    piv = low.shift(PIVOT).where(is_piv)
    last = piv.ffill()
    prev = piv.apply(lambda c: c.dropna().shift(1).reindex(c.index).ffill())
    return (last > prev) & last.notna() & prev.notna()


def tightening_wedge(high, low):
    """Condition 4a. Highs falling and lows rising over the window -- the two
    boundaries converging. Measured by the slope of the rolling max and min."""
    hh = high.rolling(WEDGE_WIN).max()
    ll = low.rolling(WEDGE_WIN).min()
    highs_falling = hh < hh.shift(WEDGE_WIN // 2)
    lows_rising = ll > ll.shift(WEDGE_WIN // 2)
    return highs_falling & lows_rising


# ---------------------------------------------------------------- study

def study(trig, close, spy_ret, elig, hold, start, end):
    ret = close.pct_change()
    fired = (trig & elig).fillna(False)
    book = fired.shift(1).fillna(False).astype(float) \
                .rolling(hold, min_periods=1).max()
    w = book.div(book.sum(axis=1).replace(0, np.nan), axis=0)
    uw = elig.astype(float)
    uw = uw.div(uw.sum(axis=1).replace(0, np.nan), axis=0)

    idx = close.index
    sel = (idx >= pd.Timestamp(start)) & (idx <= pd.Timestamp(end))
    port = (w * ret).sum(axis=1).where(book.sum(axis=1) > 0)
    uni = (uw * ret).sum(axis=1)
    df = pd.DataFrame({"port": port, "spy": spy_ret, "uni": uni})[sel].dropna()
    df["vs_spy"] = df["port"] - df["spy"]
    df["vs_uni"] = df["port"] - df["uni"]
    return df, int(fired[sel].sum().sum())


def run_pair(name, cfg, d, start, end):
    close, high, low = d["close"], d["high"], d["low"]
    elig = d["elig"]

    lr = cfg.get("low_rule")
    if lr:                                   # weekly triggers
        c = close.resample(lr).last()
        h = high.resample(lr).max()
        l = low.resample(lr).min()
    else:
        c, h, l = close, high, low

    up = higher_tf_uptrend(c, cfg["rule"], cfg["fast"], cfg["slow"], c.index)
    os_ = (rsi(c) <= OVERSOLD).rolling(OVERSOLD_WINDOW, min_periods=1).max().astype(bool)
    hl = confirmed_higher_low(l)
    wedge = tightening_wedge(h, l) & (c > h.shift(1))

    cond = {"uptrend": up, "oversold": os_, "higher_low": hl, "wedge": wedge}
    if lr:                                   # map weekly triggers back to daily
        cond = {k: v.reindex(close.index, method="ffill").fillna(False)
                for k, v in cond.items()}
        # only act on the first daily bar after a new weekly signal
        for k in cond:
            cond[k] = cond[k] & (~cond[k].shift(1).fillna(False))

    steps = [("1 uptrend only", ["uptrend"]),
             ("2 + oversold", ["uptrend", "oversold"]),
             ("3 + higher low", ["uptrend", "oversold", "higher_low"]),
             ("4 + wedge  <-- SETUP", ["uptrend", "oversold", "higher_low", "wedge"])]

    rows = []
    print("\n  %s" % name)
    print("  %-24s %8s %5s %11s %7s %11s %7s"
          % ("conditions", "events", "hold", "vs SPY/yr", "t", "vs univ/yr", "t"))
    print("  " + "-" * 70)
    for label, keys in steps:
        trig = cond[keys[0]]
        for k in keys[1:]:
            trig = trig & cond[k]
        first = True
        for hold in HOLDS:
            df, n_ev = study(trig, close, d["spy_ret"], elig, hold, start, end)
            if len(df) < 250 or n_ev < 50:
                continue
            a, b = V.stats(df["vs_spy"]), V.stats(df["vs_uni"])
            rows.append(dict(pair=name, step=label, hold=hold, events=n_ev,
                             spy=a["ann"], t_spy=a["t"],
                             uni=b["ann"], t_uni=b["t"], p_uni=b["p"]))
            print("  %-24s %8d %5d %+10.2f%% %7.2f %+10.2f%% %7.2f"
                  % (label if first else "", n_ev, hold,
                     100 * a["ann"], a["t"], 100 * b["ann"], b["t"]))
            first = False
    return pd.DataFrame(rows)


def main():
    d = V.load_panel("2009-01-01", "2026-12-31")
    d["spy_ret"] = d["spy_close"].pct_change()

    allrows = []
    for win, title in [(DISCOVERY, "DISCOVERY 2007-2019"),
                       (CONFIRM, "CONFIRMATION 2020-2025 -- untouched")]:
        print("\n" + "=" * 76)
        print("  %s" % title)
        print("=" * 76)
        for name, cfg in PAIRS.items():
            r = run_pair(name, cfg, d, *win)
            r["window"] = title.split()[0]
            allrows.append(r)

    res = pd.concat(allrows, ignore_index=True)
    res.to_csv("mtf_results.csv", index=False)

    disc = res[res.window == "DISCOVERY"].copy()
    conf = res[res.window == "CONFIRMATION"].copy()
    disc["survives"] = V.benjamini_hochberg(disc["p_uni"].values)

    print("\n" + "=" * 76)
    print("  THE FULL SETUP, both windows, scored against the equal-weight universe")
    print("=" * 76)
    m = disc[disc.step.str.startswith("4")].merge(
        conf[conf.step.str.startswith("4")], on=["pair", "hold"],
        suffixes=("_d", "_c"))
    print("  %-20s %5s %9s %11s %8s %11s %8s"
          % ("pair", "hold", "events", "2007-19", "t", "2020-25", "t"))
    for _, r in m.iterrows():
        print("  %-20s %5d %9d %+10.2f%% %8.2f %+10.2f%% %8.2f"
              % (r["pair"], r.hold, r.events_d, 100 * r.uni_d, r.t_uni_d,
                 100 * r.uni_c, r.t_uni_c))
    n_sur = int(disc.survives.sum())
    print("\n  Surviving multiple-testing correction in discovery: %d of %d"
          % (n_sur, len(disc)))
    if n_sur:
        for _, r in disc[disc.survives].iterrows():
            print("    %-20s %-24s hold %2d  %+6.2f%%/yr  t=%+.2f"
                  % (r["pair"], r["step"], r.hold, 100 * r.uni, r.t_uni))
    print("\n  2026 remains untouched.")


if __name__ == "__main__":
    main()
