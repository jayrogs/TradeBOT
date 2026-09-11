"""
test_rider.py -- the EMA 12 Rider charts a human looked at and approved.

    python test_rider.py

Same idea as test_approved.py, separate file because it freezes different
numbers. The trend suite watches the UP/DOWN/BALANCE mix; this one watches what
the rider actually did: how much of the window it was armed for, how many
wick-holds it counted, and how many entries it marked.

Those three together catch the failures that mattered while building it:

    armed share   the latch. Before it latched, `armed` disarmed on every bar
                  with a lower low and this sat at 14-23% instead of 23-50%
    wick holds    the body-vs-close rule. Testing `close > ema` passed candles
                  with most of their body under the line
    entries       the interaction bug. `armed` and `pullback` were mutually
                  exclusive by construction and every chart showed exactly 1
                  entry -- coincidence, not signal

If any of those drift, a rule changed. Go look at the chart before deciding the
new number is fine.
"""

import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

import panel as P
import rider

warnings.filterwarnings("ignore")

APPROVED = os.path.join("validation", "approved_rider.json")
STORE = pd.read_pickle(os.path.join("cache", "scan_prices.pkl"))
TOL_ARMED = 0.08        # armed share may drift this much of the window
TOL_COUNT = 2           # counts may drift by this many bars


def main():
    if not os.path.exists(APPROVED):
        sys.exit("no approved rider charts yet -- grade a batch first")
    items = json.load(open(APPROVED))
    print("=" * 76)
    print("  EMA 12 RIDER -- %d charts graded right by eye" % len(items))
    print("=" * 76)

    bad = 0
    for it in items:
        d = (P.resample(STORE[it["sym"]], "W-FRI") if it["tf"] == "W"
             else STORE[it["sym"]])
        df = d[(d.index >= it["start"]) & (d.index <= it["end"])]
        try:
            r = rider.read(df)
        except Exception as e:
            print("  [ERROR] %-6s %-2s  %s" % (it["sym"], it["tf"], e))
            bad += 1
            continue
        armed = float(np.mean(r["armed"]))
        wicks = int(r["wick_hold"].sum())
        entries = int(np.sum(r["pullback"] & r["armed"]))
        probs = []
        if abs(armed - it["armed"]) > TOL_ARMED:
            probs.append("armed %.0f%% -> %.0f%%" % (100 * it["armed"], 100 * armed))
        if abs(wicks - it["wick_holds"]) > TOL_COUNT:
            probs.append("wick-holds %d -> %d" % (it["wick_holds"], wicks))
        if abs(entries - it["entries"]) > TOL_COUNT:
            probs.append("entries %d -> %d" % (it["entries"], entries))
        bad += bool(probs)
        print("  [%s] %-6s %-2s  %s"
              % ("PASS" if not probs else "FAIL", it["sym"], it["tf"],
                 "stable" if not probs else "; ".join(probs)))

    print()
    print("  %d of %d holding" % (len(items) - bad, len(items)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
