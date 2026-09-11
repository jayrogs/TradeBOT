"""trend_v2_score.py -- v2 grammar on trial. Three scoreboards, no mercy.

    python trend_v2_score.py

  A. the user's 1,636 painted bars across 12 windows: agreement, silence,
     conflict -- v1 vs v2 side by side
  B. the 24 approved charts (display form, share-drift <= 10%): v2 must not
     break what the eye already blessed
  C. causality: v2 on a cut series must match itself on the full series
  D. how often each state fires overall (BALANCE must exist now, and FLAT
     should shrink without vanishing)
"""

import json
import warnings

import numpy as np
import pandas as pd

import panel as P
import panel_v2 as V2
import scanner as SC

warnings.filterwarnings("ignore")

LAB = {"U": "UP", "D": "DOWN", "B": "BALANCE"}
RULES = {"1h": None, "4h": "4h", "1d": "1D"}


def part_a():
    print("=" * 78)
    print("  A. THE 1,636 PAINTED BARS -- v1 vs v2")
    print("=" * 78)
    W = {w["n"]: w for w in json.load(open("validation/fixture_windows.json"))}
    M = json.load(open("validation/fixture_marks.json"))
    meta = {w["n"]: (w["sym"], w["tf"]) for w in W.values()}

    # regenerate each window's v2 states from the FULL series, then slice --
    # windows were cut from history files at known date ranges
    tots = {"v1": [0, 0, 0], "v2": [0, 0, 0]}   # agree, silent, conflict
    painted = 0
    for n_str, marks in sorted(M.items(), key=lambda kv: int(kv[0])):
        n = int(n_str)
        w = W[n]
        sym, tf = meta[n]
        raw = pd.read_csv("history/%s_1h.csv.gz" % sym, index_col=0,
                          parse_dates=True)
        df = SC.resample(raw, RULES[tf]) if RULES[tf] else raw
        st2_full, _, _ = V2.trend_state_v2(df)
        pos = df.index.get_indexer([pd.Timestamp(w["dates"][0])])[0]
        assert pos >= 0 and str(df.index[pos]) == w["dates"][0], (n, pos)
        st2 = list(st2_full[pos:pos + len(marks)])
        st1 = w["state"]
        for i, m in enumerate(marks):
            if not m:
                continue
            painted += 1
            for tag, st in (("v1", st1), ("v2", st2)):
                got = st[i]
                if got == LAB[m]:
                    tots[tag][0] += 1
                elif got == "FLAT":
                    tots[tag][1] += 1
                else:
                    tots[tag][2] += 1
    for tag in ("v1", "v2"):
        a, s, x = tots[tag]
        print("  %s: agree %4.0f%%   silent %4.0f%%   conflict %4.0f%%   (%d bars)"
              % (tag, 100 * a / painted, 100 * s / painted,
                 100 * x / painted, painted))
    return tots, painted


def part_b():
    print("\n" + "=" * 78)
    print("  B. THE 24 APPROVED CHARTS (display form, drift <= 10%)")
    print("=" * 78)
    import os
    items = json.load(open("validation/approved.json"))
    STORE = pd.read_pickle(os.path.join("cache", "scan_prices.pkl"))
    bad = []
    for it in items:
        d = STORE[it["sym"]]
        df = P.resample(d, "W-FRI") if it["tf"] == "W" else d
        df = df[(df.index >= it["start"]) & (df.index <= it["end"])]
        st, _, _ = V2.display_state_v2(df)
        now = {k: float(np.mean(st == k))
               for k in ("UP", "DOWN", "BALANCE", "FLAT")}
        was = {"UP": it["up"], "DOWN": it["down"],
               "BALANCE": it["bal"], "FLAT": it["flat"]}
        drift = {k: now[k] - was[k] for k in was}
        worst = max(drift, key=lambda k: abs(drift[k]))
        if abs(drift[worst]) > 0.10:
            bad.append("%s %s: %s %+.0f pts (was %.0f%%, now %.0f%%)"
                       % (it["sym"], it["tf"], worst, 100 * drift[worst],
                          100 * was[worst], 100 * now[worst]))
    print("  %d of %d holding" % (len(items) - len(bad), len(items)))
    for b in bad:
        print("    FAIL " + b)
    return len(items) - len(bad), len(items)


def part_c():
    print("\n" + "=" * 78)
    print("  C. CAUSALITY")
    print("=" * 78)
    raw = pd.read_csv("history/BTC_1h.csv.gz", index_col=0,
                      parse_dates=True).tail(12000)
    full, _, _ = V2.trend_state_v2(raw)
    n = int(len(raw) * 0.7)
    cut, _, _ = V2.trend_state_v2(raw.iloc[:n])
    mism = int(np.sum(np.asarray(full[:n]) != np.asarray(cut)))
    print("  cut vs full: %d mismatches -> %s"
          % (mism, "CAUSAL" if mism == 0 else "LOOKAHEAD, DO NOT SHIP"))
    return mism


def part_d():
    print("\n" + "=" * 78)
    print("  D. STATE MIX ACROSS 6 NAMES, 1h + 1d, v1 vs v2")
    print("=" * 78)
    mix = {"v1": {}, "v2": {}}
    tot = 0
    for sym in ("BTC", "ETH", "SOL", "LTC", "LINK", "DOGE"):
        raw = pd.read_csv("history/%s_1h.csv.gz" % sym, index_col=0,
                          parse_dates=True)
        for rule in (None, "1D"):
            df = SC.resample(raw, rule) if rule else raw
            s1, _, _ = P.trend_state(df)
            s2, _, _ = V2.trend_state_v2(df)
            tot += len(df)
            for tag, st in (("v1", s1), ("v2", s2)):
                for kk in ("UP", "DOWN", "BALANCE", "FLAT"):
                    mix[tag][kk] = mix[tag].get(kk, 0) + int(np.sum(st == kk))
    for tag in ("v1", "v2"):
        print("  %s:  " % tag + "   ".join(
            "%s %.1f%%" % (kk, 100 * mix[tag][kk] / tot)
            for kk in ("UP", "DOWN", "BALANCE", "FLAT")))


if __name__ == "__main__":
    part_a()
    part_b()
    part_c()
    part_d()
