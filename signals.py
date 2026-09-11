"""
signals.py -- the pre-specified list of candidate predictors.

THIS LIST IS FROZEN BEFORE ANY OF IT IS TESTED. That is the whole point. If the
list can grow after seeing results, the statistics below are meaningless, because
the correction for "how many things did we look at" needs an honest count.

Each entry states a direction taken from the published literature, so that a
POSITIVE spread always means "the effect showed up in the direction claimed" and
a negative spread means it showed up backwards. Every signal is oriented so that
a HIGHER value is the one predicted to earn MORE.

Nothing here is inherited from the ChartGuys work except entry 12, which is kept
in only so their claim gets measured on the same footing as everything else.

Each function takes a dict of wide DataFrames (dates x symbols) and returns one
wide DataFrame of the same shape.
"""

import numpy as np
import pandas as pd


def _ret(px, n):
    return px / px.shift(n) - 1.0


# ---------------------------------------------------------------- the list

def mom_12_1(d):
    """1. Momentum, 12 months skipping the most recent one (Jegadeesh-Titman).
    Winners keep winning. The single most replicated effect in the literature."""
    px = d["close"]
    return px.shift(21) / px.shift(252) - 1.0


def mom_6_1(d):
    """2. Same thing over 6 months. Included to see whether the horizon matters
    or whether we are just measuring one effect twice."""
    px = d["close"]
    return px.shift(21) / px.shift(126) - 1.0


def rev_1m(d):
    """3. Short-term reversal (Jegadeesh 1990). Last month's losers bounce.
    Note this is the OPPOSITE sign to momentum over a different horizon."""
    return -_ret(d["close"], 21)


def rev_1w(d):
    """4. One-week reversal. Faster version of the same idea."""
    return -_ret(d["close"], 5)


def prox_52w(d):
    """5. Nearness to the 52-week high (George & Hwang). Stocks near their highs
    keep going. Directly contradicts buy-the-dip."""
    px = d["close"]
    return px / px.rolling(252).max()


def low_vol(d):
    """6. Low-volatility anomaly. Boring stocks have historically beaten
    exciting ones on a risk-adjusted basis, and often outright."""
    r = d["close"].pct_change()
    return -r.rolling(126).std()


def low_beta(d):
    """7. Low-beta anomaly (Frazzini-Pedersen 'betting against beta')."""
    r = d["close"].pct_change()
    m = d["spy_ret"]
    cov = r.rolling(252).cov(m)
    var = m.rolling(252).var()
    return -(cov.div(var, axis=0))


def low_ivol(d):
    """8. Idiosyncratic volatility (Ang et al). Stock-specific noise, with the
    market's influence stripped out. High-ivol names underperform."""
    r = d["close"].pct_change()
    m = d["spy_ret"]
    beta = r.rolling(252).cov(m).div(m.rolling(252).var(), axis=0)
    resid = r.sub(beta.mul(m, axis=0))
    return -resid.rolling(126).std()


def low_max(d):
    """9. MAX effect (Bali, Cakici, Whitelaw). Stocks with a big single-day
    jackpot in the last month underperform -- lottery-ticket demand."""
    r = d["close"].pct_change()
    return -r.rolling(21).max()


def trend_50_200(d):
    """10. Classic trend filter: 50-day average above the 200-day."""
    px = d["close"]
    return px.rolling(50).mean() / px.rolling(200).mean() - 1.0


def dist_200(d):
    """11. Distance above the 200-day average. Trend, measured on price rather
    than on two averages."""
    px = d["close"]
    return px / px.rolling(200).mean() - 1.0


def low_rsi(d):
    """12. THE CHARTGUYS CLAIM. Beaten-down names bounce. Oriented so positive
    means their claim held. Already failed once on 2023-2025; included so it is
    measured on the same 13 years and the same statistics as everything else."""
    px = d["close"]
    delta = px.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-delta).clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return -(100 - 100 / (1 + rs))


def vol_shock(d):
    """13. Volume shock. Recent dollar volume against its own baseline. High
    attention tends to precede underperformance."""
    dv = d["close"] * d["volume"]
    return -(dv.rolling(21).mean() / dv.rolling(252).mean())


def neg_skew(d):
    """14. Skewness preference. Investors overpay for right-tailed lottery
    payoffs, so negatively skewed stocks earn more."""
    r = d["close"].pct_change()
    return -r.rolling(126).skew()


def illiquidity(d):
    """15. Amihud illiquidity: price impact per dollar traded. Expected to be
    weak inside the S&P 500, where everything is liquid. Included as a
    half-control: if this lights up, be suspicious of the whole exercise."""
    r = d["close"].pct_change().abs()
    dv = d["close"] * d["volume"]
    return (r / dv.replace(0, np.nan)).rolling(63).mean() * 1e9


def gap_rev(d):
    """16. Overnight gap reversal. Sum of overnight moves over a month; stocks
    that keep gapping up give it back."""
    overnight = d["open"] / d["close"].shift(1) - 1.0
    return -overnight.rolling(21).sum()


SIGNALS = {
    "mom_12_1":     (mom_12_1,     "12-month momentum, skipping last month"),
    "mom_6_1":      (mom_6_1,      "6-month momentum, skipping last month"),
    "rev_1m":       (rev_1m,       "1-month reversal (buy last month's losers)"),
    "rev_1w":       (rev_1w,       "1-week reversal"),
    "prox_52w":     (prox_52w,     "closeness to the 52-week high"),
    "low_vol":      (low_vol,      "low volatility"),
    "low_beta":     (low_beta,     "low beta"),
    "low_ivol":     (low_ivol,     "low stock-specific volatility"),
    "low_max":      (low_max,      "no big single-day jackpot last month"),
    "trend_50_200": (trend_50_200, "50-day average above the 200-day"),
    "dist_200":     (dist_200,     "price above its 200-day average"),
    "low_rsi":      (low_rsi,      "beaten-down on RSI  [the ChartGuys claim]"),
    "vol_shock":    (vol_shock,    "no recent volume surge"),
    "neg_skew":     (neg_skew,     "negatively skewed returns"),
    "illiquidity":  (illiquidity,  "less liquid  [near-control, expect nothing]"),
    "gap_rev":      (gap_rev,      "overnight gap reversal"),
}
