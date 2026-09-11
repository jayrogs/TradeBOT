"""trend_v3_score.py -- the overlay architecture against every fixture.

    python trend_v3_score.py

  A. the 1,636 painted bars: trend paint scores against v1's untouched
     states; EQ paint scores against (overlay OR v1 BALANCE); a live range
     under trend paint counts as silence, never conflict
  B. overlap census -- the owner's phenomenon, quantified
  C. approved charts: v1 untouched -> identical by construction
  D. causality prefix test over state + overlay
"""

import json
import warnings

import numpy as np
import pandas as pd

import panel_v3 as V3
import scanner as SC

warnings.filterwarnings("ignore")

RULES = {"1h": None, "4h": "4h", "1d": "1D"}


def part_a():
    print("=" * 78)
    print("  A. THE 1,636 PAINTED BARS -- v1 vs the overlay architecture")
    print("=" * 78)
    W = {w["n"]: w for w in json.load(open("validation/fixture_windows.json"))}
    M = json.load(open("validation/fixture_marks.json"))
    v1 = [0, 0, 0]
    v3 = [0, 0, 0]
    eq_match = eq_tot = 0
    painted = 0
    for n_str, marks in sorted(M.items(), key=lambda kv: int(kv[0])):
        w = W[int(n_str)]
        raw = pd.read_csv("history/%s_1h.csv.gz" % w["sym"], index_col=0,
                          parse_dates=True)
        df = SC.resample(raw, RULES[w["tf"]]) if RULES[w["tf"]] else raw
        S = V3.structures(df)
        pos = df.index.get_indexer([pd.Timestamp(w["dates"][0])])[0]
        st = list(S["state"][pos:pos + len(marks)])
        eqa = S["eq"][pos:pos + len(marks)]
        st1 = w["state"]
        for i, m in enumerate(marks):
            if not m:
                continue
            painted += 1
            want = {"U": "UP", "D": "DOWN", "B": "BALANCE"}[m]
            got1 = st1[i]
            if got1 == want:
                v1[0] += 1
            elif got1 == "FLAT":
                v1[1] += 1
            else:
                v1[2] += 1
            if m == "B":
                eq_tot += 1
                ok = bool(eqa[i]) or st[i] == "BALANCE"
                eq_match += ok
                v3[0 if ok else 1] += 1
            else:
                if st[i] == want:
                    v3[0] += 1
                elif st[i] in ("FLAT", "BALANCE"):
                    v3[1] += 1
                else:
                    v3[2] += 1
    for tag, t in (("v1", v1), ("v3", v3)):
        print("  %s: agree %4.0f%%   silent %4.0f%%   conflict %4.0f%%"
              % (tag, 100 * t[0] / painted, 100 * t[1] / painted,
                 100 * t[2] / painted))
    print("  painted EQ bars matched: %d of %d (v1: 2)" % (eq_match, eq_tot))


def part_b():
    print("")
    print("=" * 78)
    print("  B. OVERLAP CENSUS (6 names, 1h + 1d, 11 years)")
    print("=" * 78)
    tot = both = eqonly = 0
    for sym in ("BTC", "ETH", "SOL", "LTC", "LINK", "DOGE"):
        raw = pd.read_csv("history/%s_1h.csv.gz" % sym, index_col=0,
                          parse_dates=True)
        for rule in (None, "1D"):
            df = SC.resample(raw, rule) if rule else raw
            S = V3.structures(df)
            tot += len(df)
            both += int(S["both"].sum())
            eqonly += int((S["eq"] & ~S["both"]).sum())
    print("  trend + range overlapping: %.2f%% of bars" % (100 * both / tot))
    print("  range alone (no trend):    %.2f%%" % (100 * eqonly / tot))


def part_c():
    print("")
    print("=" * 78)
    print("  C. THE 24 APPROVED CHARTS")
    print("=" * 78)
    print("  v1 is untouched by the overlay -> identical by construction")
    print("  (test_approved.py is the live proof; it runs in run_tests.py)")


def part_d():
    print("")
    print("=" * 78)
    print("  D. CAUSALITY")
    print("=" * 78)
    raw = pd.read_csv("history/BTC_1h.csv.gz", index_col=0,
                      parse_dates=True).tail(12000)
    F = V3.structures(raw)
    n = int(len(raw) * 0.7)
    C = V3.structures(raw.iloc[:n])
    mism = int(np.sum(F["eq"][:n] != C["eq"]))
    mism += int(np.sum(np.asarray(F["state"][:n]) != np.asarray(C["state"])))
    print("  cut vs full, state + overlay: %d mismatches -> %s"
          % (mism, "CAUSAL" if mism == 0 else "LOOKAHEAD"))


if __name__ == "__main__":
    part_a()
    part_b()
    part_c()
    part_d()
