"""
audit_chart.py -- verify the shading agrees with the labels, before anyone looks.

    python audit_chart.py

The labels on the chart (HH / HL / LH / LL) already state what the structure is
doing. So a green region should contain mostly HH and HL, and a red region
mostly LH and LL. Any region where the colour contradicts its own labels is a
bug, and this finds it without a human having to squint at a picture.

Written after shipping several charts where a red block was full of HH/HL and a
green block was full of LH/LL.
"""

import sys

import numpy as np
import pandas as pd

import chart
import panel as P

STORE = pd.read_pickle("cache/scan_prices.pkl")
TARGETS = [
    ("SPY", "W-FRI", "W"), ("SPY", None, "D"),
    ("QQQ", "W-FRI", "W"),
    ("BTC-USD", None, "D"), ("BTC-USD", "W-FRI", "W"),
    ("GC=F", None, "D"), ("GC=F", "W-FRI", "W"),
    ("SOL-USD", "W-FRI", "W"), ("SLV", None, "D"),
]
MIN_LABELS = 4          # ignore regions too short to judge


def audit(sym, rule, tf, bars=150):
    d = STORE[sym]
    df = P.resample(d, rule).tail(bars)
    st, _, _ = P.trend_state(df)
    marks = chart.pivot_labels(df)

    regions = []
    i = 0
    while i < len(st):
        j = i
        while j + 1 < len(st) and st[j + 1] == st[i]:
            j += 1
        regions.append((i, j, st[i]))
        i = j + 1

    bad = []
    for a, b, state in regions:
        tags = [t for idx, price, t, kind in marks if a <= idx <= b]
        if len(tags) < MIN_LABELS:
            continue
        bull = sum(1 for t in tags if t in ("HH", "HL"))
        bear = sum(1 for t in tags if t in ("LH", "LL"))
        tags = [t for t in tags if t not in ("EH", "EL")]
        if state == "UP" and bear > bull:
            bad.append((a, b, state, bull, bear, tags))
        elif state == "DOWN" and bull > bear:
            bad.append((a, b, state, bull, bear, tags))
    return df, regions, bad


def main():
    total_bad = 0
    print("=" * 80)
    print("  CHART AUDIT -- does the shading agree with its own labels?")
    print("=" * 80)
    for sym, rule, tf in TARGETS:
        if sym not in STORE:
            continue
        try:
            df, regions, bad = audit(sym, rule, tf)
        except Exception as e:
            print("  %-9s %-2s  ERROR %s" % (sym, tf, type(e).__name__))
            total_bad += 1
            continue
        n_reg = len([r for r in regions if r[2] in ("UP", "DOWN")])
        if not bad:
            print("  [ok]   %-9s %-2s  %d trend regions, all consistent"
                  % (sym, tf, n_reg))
        else:
            total_bad += len(bad)
            print("  [BAD]  %-9s %-2s  %d of %d trend regions contradict their labels"
                  % (sym, tf, len(bad), n_reg))
            for a, b, state, bull, bear, tags in bad[:3]:
                print("           %s..%s  %-5s  bull %d / bear %d   %s"
                      % (df.index[a].date(), df.index[b].date(), state,
                         bull, bear, " ".join(tags[:10])))
    print("\n  %d contradictory regions total" % total_bad)
    return total_bad


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
