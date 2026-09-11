"""
indicators.py -- the shared maths, defined once.

WHY THIS FILE EXISTS
Wilder's RSI, the reverse-RSI price and the session VWAP were copy-pasted into
desk.py, backburner.py and scanner.py. All three agreed exactly when checked --
but only by luck, and the project has already been bitten twice by the same
calculation living in two places:

  * panel.py had TWO definitions of `zigzag`; a patch went into the first and
    the second silently overrode it, so an ATR filter never ran
  * panel.py carried duplicate `compression` and `balance_zones` bodies for
    weeks, byte-identical, waiting for someone to edit one of them

The RSI in particular is not a detail here. It was verified bar-for-bar against
20,000 bars of TradingView's own export, max error 0.000000, and that agreement
is worth protecting from a well-meaning edit to one of three copies.
"""

import numpy as np
import pandas as pd

RSI_N = 14


def rsi_parts(c, n=RSI_N):
    """Wilder's RSI plus the smoothed up/down averages it is built from.

    The averages are returned because reverse_rsi needs them: to say what price
    would print a given RSI on the next bar, you need the current state of the
    smoothing, not just the RSI value.

    Verified identical to TradingView's rsi() across 20,030 bars of ES 5m and
    20,048 of GC 5m -- max absolute error 0.000000.
    """
    d = np.diff(c, prepend=c[0])
    au = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    ad = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(au, ad, out=np.full_like(au, np.inf), where=ad > 0)
    return 100 - 100 / (1 + rs), au, ad


def rsi(c, n=RSI_N):
    """Just the line, for callers that do not need the internals."""
    return rsi_parts(c, n)[0]


def reverse_rsi(close, au, ad, target, n=RSI_N):
    """The price on the NEXT bar that would print exactly `target` RSI.

    Wilder's smoothing, one bar forward. If price falls by x:
        avgU' = avgU*(n-1)/n            (no upward move)
        avgD' = (avgD*(n-1) + x)/n
    Set RS' = target/(100-target) and solve for x.

    Returns None when x <= 0, which means price would have to RISE to reach
    that reading -- i.e. it is already below the target. That is the honest
    answer and the caller should print "above", not a number.
    """
    if target >= 100:
        return None
    rs_t = target / (100.0 - target)
    if rs_t <= 0:
        return None
    x = au * (n - 1) / rs_t - ad * (n - 1)
    if x <= 0:
        return None
    px = close - x
    return float(px) if px > 0 else None


def session_vwap(df):
    """Volume-weighted average price, reset each session."""
    day = df.index.normalize()
    tp = (df["High"] + df["Low"] + df["Close"]) / 3.0
    pv = (tp * df["Volume"]).groupby(day).cumsum()
    vv = df["Volume"].groupby(day).cumsum()
    return (pv / vv.replace(0, np.nan)).values


def atr(df, n=RSI_N):
    h = df["High"].values.astype(float)
    l = df["Low"].values.astype(float)
    c = df["Close"].values.astype(float)
    pc = np.roll(c, 1)
    pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().values
