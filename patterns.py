"""
patterns.py -- classic chart setups, defined mechanically.

FROZEN BEFORE TESTING. Every threshold below is a conventional value taken from
how these setups are normally described, not a value chosen because it worked.
If a pattern fails, the honest conclusion is that the pattern fails -- not that
the flag should have been 7 days instead of 10.

Each function returns a boolean matrix (dates x symbols): True on the day the
setup TRIGGERS, meaning the day you would act. Every input uses data up to and
including that day's close; the event study then buys at the NEXT day's close.

Covered, roughly in the order a chart reader would name them:

    trend riding      trend_pullback, three_day_pullback, golden_cross
    moving averages   ema_ride_20, ema_ride_50
    bull flags        bull_flag
    equilibrium       range_breakout, range_breakdown, vcp
    breakouts         new_high_52w, inside_bar_break
    candles           bullish_engulf, hammer, doji_reversal
    volume/psych      pocket_pivot, gap_and_go
"""

import numpy as np
import pandas as pd


# ------------------------------------------------------------ helpers

def _ema(px, n):
    return px.ewm(span=n, adjust=False).mean()


def _atr(d, n=14):
    pc = d["close"].shift(1)
    tr = pd.concat([(d["high"] - d["low"]).stack(),
                    (d["high"] - pc).abs().stack(),
                    (d["low"] - pc).abs().stack()], axis=1).max(axis=1).unstack()
    return tr.ewm(alpha=1.0 / n, adjust=False).mean()


def _uptrend(d):
    """The context nearly every bullish setup assumes: price above the 200-day,
    50-day above the 200-day. Without this filter these are just shapes."""
    px = d["close"]
    return (px > px.rolling(200).mean()) & \
           (px.rolling(50).mean() > px.rolling(200).mean())


def _body(d):
    return (d["close"] - d["open"]).abs()


def _range(d):
    return (d["high"] - d["low"]).replace(0, np.nan)


# ------------------------------------------------------------ trend riding

def trend_pullback(d):
    """Higher low. In an uptrend, price pulls back at least 3 days, makes a low
    above the prior 20-day low, then closes up. The bread-and-butter
    trend-continuation entry."""
    px, lo = d["close"], d["low"]
    pulled = px < px.shift(3)
    higher_low = lo > lo.rolling(20).min().shift(3)
    turn = px > px.shift(1)
    return _uptrend(d) & pulled.shift(1).fillna(False) & higher_low & turn


def three_day_pullback(d):
    """Three consecutive down closes in an uptrend, then an up close.
    The simplest possible pullback rule, included as a baseline."""
    px = d["close"]
    dn = px < px.shift(1)
    three = dn.shift(1) & dn.shift(2) & dn.shift(3)
    return _uptrend(d) & three.fillna(False) & (px > px.shift(1))


def golden_cross(d):
    """50-day average crosses up through the 200-day. The most famous signal in
    technical analysis and the easiest to check."""
    px = d["close"]
    f, s = px.rolling(50).mean(), px.rolling(200).mean()
    return (f > s) & (f.shift(1) <= s.shift(1))


# ------------------------------------------------------------ moving averages

def ema_ride_20(d):
    """Riding the 20-day EMA: in an uptrend price dips to or through the 20 EMA
    intraday and closes back above it."""
    e = _ema(d["close"], 20)
    return _uptrend(d) & (d["low"] <= e) & (d["close"] > e) & \
           (d["close"].shift(1) > e.shift(1))


def ema_ride_50(d):
    """Same idea, slower average, deeper pullback."""
    e = _ema(d["close"], 50)
    return _uptrend(d) & (d["low"] <= e) & (d["close"] > e) & \
           (d["close"].shift(1) > e.shift(1))


# ------------------------------------------------------------ bull flag

def bull_flag(d):
    """
    Pole then flag then break.
      pole  : +15% or more over 10 days, ending 5 to 15 days ago
      flag  : since the pole, price held within 10% of the pole high and the
              daily range tightened to under 70% of what it was during the pole
      break : today closes above the highest high of the flag
    """
    px, hi = d["close"], d["high"]
    pole = (px.shift(5) / px.shift(15) - 1.0) >= 0.15
    pole_high = hi.rolling(10).max().shift(5)
    held = px >= pole_high * 0.90
    rng = _range(d) / px
    tight = rng.rolling(5).mean() < 0.70 * rng.rolling(10).mean().shift(5)
    flag_high = hi.rolling(5).max().shift(1)
    return pole.fillna(False) & held.fillna(False) & tight.fillna(False) & \
           (px > flag_high)


# ------------------------------------------------------------ equilibrium

def range_breakout(d):
    """Balance then expansion. Price coils into a 20-day range narrower than 8%
    of price, then closes above the top of it."""
    px, hi, lo = d["close"], d["high"], d["low"]
    top = hi.rolling(20).max().shift(1)
    bot = lo.rolling(20).min().shift(1)
    tight = (top - bot) / px < 0.08
    return tight.fillna(False) & (px > top)


def range_breakdown(d):
    """The same coil breaking the other way. Included as the mirror case: if
    breakouts work, breakdowns should hurt, and if neither does anything the
    pattern is decoration."""
    px, hi, lo = d["close"], d["high"], d["low"]
    top = hi.rolling(20).max().shift(1)
    bot = lo.rolling(20).min().shift(1)
    tight = (top - bot) / px < 0.08
    return tight.fillna(False) & (px < bot)


def vcp(d):
    """Volatility contraction: recent range compressed to under 70% of its
    50-day norm, price within 10% of its 52-week high, then a 20-day breakout."""
    px, hi = d["close"], d["high"]
    a = _atr(d, 10)
    contracted = a / a.rolling(50).mean() < 0.70
    near_high = px / hi.rolling(252).max() > 0.90
    brk = px > hi.rolling(20).max().shift(1)
    return contracted.fillna(False) & near_high.fillna(False) & brk


# ------------------------------------------------------------ breakouts

def new_high_52w(d):
    """A fresh 52-week high after at least 20 quiet days. Breakout to new highs,
    the setup ChartGuys wrote about more than any other."""
    px, hi = d["close"], d["high"]
    h = hi.rolling(252).max().shift(1)
    fresh = px > h
    return fresh & (~fresh.rolling(20).max().shift(1).fillna(0).astype(bool))


def inside_bar_break(d):
    """An inside day -- a full day contained within the previous day's range --
    then a close above its high. Compression on the smallest scale."""
    hi, lo, px = d["high"], d["low"], d["close"]
    inside = (hi.shift(1) < hi.shift(2)) & (lo.shift(1) > lo.shift(2))
    return _uptrend(d) & inside.fillna(False) & (px > hi.shift(1))


# ------------------------------------------------------------ candles

def bullish_engulf(d):
    """Yesterday down, today up and today's body swallows yesterday's, in an
    uptrend. The most cited bullish candle."""
    o, c = d["open"], d["close"]
    prev_dn = c.shift(1) < o.shift(1)
    today_up = c > o
    engulf = (c > o.shift(1)) & (o < c.shift(1))
    return _uptrend(d) & prev_dn.fillna(False) & today_up & engulf.fillna(False)


def hammer(d):
    """Long lower wick, small body, at a 10-day low, in an uptrend. Sellers
    pushed it down and got rejected -- the psychology story in one bar."""
    o, c, h, l = d["open"], d["close"], d["high"], d["low"]
    body = _body(d)
    lower = pd.concat([o.stack(), c.stack()], axis=1).min(axis=1).unstack() - l
    upper = h - pd.concat([o.stack(), c.stack()], axis=1).max(axis=1).unstack()
    at_low = l <= l.rolling(10).min()
    return _uptrend(d) & at_low & (lower > 2 * body) & (upper < body)


def doji_reversal(d):
    """A doji -- open and close nearly equal, indecision -- at the bottom of a
    pullback in an uptrend, followed by an up close."""
    o, c = d["open"], d["close"]
    doji = _body(d) < 0.1 * _range(d)
    at_low = d["low"].shift(1) <= d["low"].rolling(10).min().shift(1)
    return _uptrend(d) & doji.shift(1).fillna(False) & at_low.fillna(False) & \
           (c > c.shift(1))


# ------------------------------------------------------------ volume / psych

def pocket_pivot(d):
    """An up day on heavier volume than any down day in the last 10. Buying
    showing up louder than the selling did."""
    px, v = d["close"], d["volume"]
    up = px > px.shift(1)
    dn_vol = v.where(px < px.shift(1))
    return _uptrend(d) & up & (v > dn_vol.rolling(10).max())


def gap_and_go(d):
    """Opens more than 2% above yesterday's close and closes above the open --
    the gap holds instead of filling."""
    o, c = d["open"], d["close"]
    gap = o / c.shift(1) - 1.0
    return _uptrend(d) & (gap > 0.02) & (c > o)


PATTERNS = {
    "trend_pullback":     (trend_pullback,     "higher low in an uptrend"),
    "three_day_pullback": (three_day_pullback, "3 down days then an up close"),
    "golden_cross":       (golden_cross,       "50-day crosses above 200-day"),
    "ema_ride_20":        (ema_ride_20,        "dip to the 20 EMA and recover"),
    "ema_ride_50":        (ema_ride_50,        "dip to the 50 EMA and recover"),
    "bull_flag":          (bull_flag,          "pole, tight flag, breakout"),
    "range_breakout":     (range_breakout,     "tight 20-day coil breaks up"),
    "range_breakdown":    (range_breakdown,    "tight 20-day coil breaks down"),
    "vcp":                (vcp,                "volatility contraction near highs"),
    "new_high_52w":       (new_high_52w,       "fresh 52-week high"),
    "inside_bar_break":   (inside_bar_break,   "inside day then break of its high"),
    "bullish_engulf":     (bullish_engulf,     "bullish engulfing candle"),
    "hammer":             (hammer,             "hammer at a 10-day low"),
    "doji_reversal":      (doji_reversal,      "doji at a pullback low"),
    "pocket_pivot":       (pocket_pivot,       "up day on above-average buy volume"),
    "gap_and_go":         (gap_and_go,         "gap up that holds"),
}
