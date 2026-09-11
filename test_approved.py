"""
test_approved.py -- the charts a human looked at and approved.

    python test_approved.py

WHY THIS EXISTS
audit_chart.py checks the shading against the labels, but both come out of
panel.py -- my code checking my code. It passed clean on three consecutive
engines that were plainly broken, because internal consistency is not
correctness. The only real test is a person looking at a chart and saying yes.

That has now happened for the charts listed in validation/approved.json, graded
blind from a random sample. This file freezes the engine's reading of each one.
If a later change shifts any of them by more than TOL, that is a regression
against a human verdict, not a style difference -- go look at the chart.

Every earlier version of the trend engine would fail this file. That is the
point.

    test_trend.py      8 hand-written cases, each from a specific complaint
    test_approved.py   charts approved wholesale, frozen by their state mix
"""

import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

import panel as P

warnings.filterwarnings("ignore")

APPROVED = os.path.join("validation", "approved.json")
STORE = pd.read_pickle(os.path.join("cache", "scan_prices.pkl"))
TOL = 0.10          # a state may drift this much of the window before failing


def window(item):
    d = STORE[item["sym"]]
    df = P.resample(d, "W-FRI") if item["tf"] == "W" else d
    return df[(df.index >= item["start"]) & (df.index <= item["end"])]


def main():
    if not os.path.exists(APPROVED):
        sys.exit("no approved charts yet -- grade a batch first")
    items = json.load(open(APPROVED))
    print("=" * 78)
    print("  APPROVED CHARTS -- %d graded right by eye" % len(items))
    print("=" * 78)

    bad = 0
    for it in items:
        try:
            df = window(it)
            st, _, _ = P.display_state(df)
        except Exception as e:
            print("  [ERROR] %-9s %-2s  %s" % (it["sym"], it["tf"], e))
            bad += 1
            continue
        n = max(len(st), 1)
        now = {k: float(np.mean(st == k))
               for k in ("UP", "DOWN", "BALANCE", "FLAT")}
        was = {"UP": it["up"], "DOWN": it["down"],
               "BALANCE": it["bal"], "FLAT": it["flat"]}
        drift = {k: now[k] - was[k] for k in was}
        worst = max(drift, key=lambda k: abs(drift[k]))
        ok = abs(drift[worst]) <= TOL
        bad += not ok
        print("  [%s] %-9s %-2s  %s  %s"
              % ("PASS" if ok else "FAIL", it["sym"], it["tf"], it["start"],
                 "stable" if ok else
                 "%s %+.0f pts (was %.0f%%, now %.0f%%)"
                 % (worst, 100 * drift[worst], 100 * was[worst],
                    100 * now[worst])))

    print()
    print("  %d of %d holding" % (len(items) - bad, len(items)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
