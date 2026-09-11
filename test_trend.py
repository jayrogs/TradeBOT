"""
test_trend.py -- the cases the trend classifier MUST get right, all at once.

    python test_trend.py

Written because six successive patches each fixed one chart and broke another.
Every case below came from the user pointing at a chart and saying "that's
wrong". Any change to trend_state has to pass all of them together, not one at
a time.
"""

import os
import sys
import collections

import numpy as np
import pandas as pd

import panel as P

STORE = pd.read_pickle("cache/scan_prices.pkl")
CASES = [
    # symbol, timeframe rule, start, end, requirement, description
    ("SPY", "W-FRI", "2023-10-01", "2024-04-30", "mostly UP",
     "SPY's long weekly advance -- months of higher highs"),
    ("SPY", "W-FRI", "2024-06-01", "2025-01-31", "mostly UP",
     "SPY continues higher through 2024"),
    ("SPY", None, "2023-11-01", "2024-03-31", "mostly UP",
     "same advance read on the daily"),
    ("SOL-USD", "W-FRI", "2022-03-01", "2022-07-01", "mostly DOWN",
     "SOL's 2022 collapse, 100 -> 30"),
    ("SOL-USD", "W-FRI", "2022-04-15", "2022-05-13", "never UP",
     "the 1.5% 'higher low' that faked an uptrend mid-collapse"),
    ("BTC-USD", None, "2026-07-15", "2026-08-19", "never mostly UP",
     "BTC chopping on LH/LL -- structure rotting, must not read green"),
    ("BTC-USD", None, "2026-05-20", "2026-06-25", "mostly DOWN",
     "BTC 78k -> 58k"),
    ("QQQ", "W-FRI", "2023-02-01", "2024-03-31", "mostly UP",
     "QQQ's 2023 advance"),
]


def state_for(sym, rule, a, b):
    d = STORE[sym]
    df = P.resample(d, rule)
    # These cases were written down from a human reading CHARTS, so they are
    # judgments about the shaded picture -- which is display_state, the
    # backdated view. trend_state is the causal one and legitimately shows long
    # unshaded stretches before a trend has confirmed.
    fn = P.display_state if os.environ.get("TT_MODE", "display") == "display"         else P.trend_state
    st, _, _ = fn(df)
    m = (df.index >= pd.Timestamp(a)) & (df.index <= pd.Timestamp(b))
    return st[m]


def check(req, st):
    n = len(st)
    if n == 0:
        return False, "no bars"
    c = collections.Counter(st)
    up = c.get("UP", 0) / n
    dn = c.get("DOWN", 0) / n
    mix = ", ".join("%s %.0f%%" % (k, 100 * v / n) for k, v in sorted(c.items()))
    if req == "mostly UP":
        return up >= 0.60, mix
    if req == "mostly DOWN":
        return dn >= 0.50, mix
    if req == "never UP":
        return c.get("UP", 0) == 0, mix
    if req == "never mostly UP":
        return up < 0.40, mix
    return False, mix


def main():
    print("=" * 84)
    print("  TREND CLASSIFIER TEST SET")
    print("=" * 84)
    fails = 0
    for sym, rule, a, b, req, desc in CASES:
        try:
            st = state_for(sym, rule, a, b)
            ok, mix = check(req, st)
        except Exception as e:
            ok, mix = False, "ERROR %s" % type(e).__name__
        tf = {None: "D", "W-FRI": "W", "ME": "M"}.get(rule, rule)
        print("  [%s] %-8s %-2s %-10s..%-10s  %-16s  %s"
              % ("PASS" if ok else "FAIL", sym, tf, a, b, req, mix))
        print("         %s" % desc)
        if not ok:
            fails += 1
    print("\n  %d of %d passing" % (len(CASES) - fails, len(CASES)))
    return fails


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
