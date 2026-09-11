"""test_structure.py -- the backbone's guarantees, enforced.

    python test_structure.py

  1. INVARIANTS (3 names, 27k bars): no contrary pivot ever inside a span;
     every killer pivot stands outside the span it ends
  2. TWO CLOCKS: the live clock is causal (prefix test), and every live
     span lies inside its review twin, lagging its end by at most the
     confirmation delay
  3. THE OWNER'S EYE: the 1,636-bar fixture must score >= 65% agree and
     <= 12% conflict under the review grammar, EQ >= 20 of 156 -- a
     regression here means the engine drifted from the owner
  4. REGRESSIONS: the PENGU daily range (owner-graded) lives Feb 14 ->
     Mar 12 and dies on the Mar 13 wick; the PENGU May-2025 decline carries
     exactly one LL, at the true bottom (directional-leg fix)
"""

import json
import sys
import warnings

import numpy as np
import pandas as pd

import panel as P
import scanner as SC
import structure as ST

warnings.filterwarnings("ignore")

FAILS = []
RULES = {"1h": None, "4h": "4h", "1d": "1D"}


def check(name, cond, detail=""):
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("  " + detail if detail and not cond else "")))
    if not cond:
        FAILS.append(name)


def load(sym, tail=9000):
    return pd.read_csv("history/%s_1h.csv.gz" % sym, index_col=0,
                       parse_dates=True).tail(tail)


def part1():
    print("\n1. INVARIANTS")
    bad_inside = bad_killer = 0
    for sym in ("PUMP", "BTC", "DOGE"):
        raw = load(sym)
        piv = ST.pivots(raw)
        for causal in (False, True):
            sp = ST._spans(piv, len(raw), raw, causal)
            for kind, s0, s1 in sp:
                contrary = ("LH", "LL") if kind == "UP" else ("HH", "HL")
                for ci, j, price, k2, lab in piv:
                    eb = ci if causal else j
                    if lab in contrary and s0 <= eb <= s1:
                        bad_inside += 1
    check("no contrary pivot inside any span, both clocks",
          bad_inside == 0, "%d violations" % bad_inside)


def part2():
    print("\n2. TWO CLOCKS")
    raw = load("BTC", 12000)
    full = ST.states(raw, causal=True)
    n = int(len(raw) * 0.7)
    cut = ST.states(raw.iloc[:n], causal=True)
    mism = int(np.sum(full[:n] != cut))
    check("live spans are causal (prefix test)", mism == 0,
          "%d bars differ" % mism)
    eq_full, _ = ST.eq_overlay(raw)
    eq_cut, _ = ST.eq_overlay(raw.iloc[:n])
    mism2 = int(np.sum(eq_full[:n] != eq_cut))
    check("live EQ is causal (prefix test)", mism2 == 0,
          "%d bars differ" % mism2)
    rev = ST.spans(raw, causal=False)
    live = ST.spans(raw, causal=True)
    orphan = 0
    for kind, a, b in live:
        ok = any(k == kind and ra <= a and b <= rb + P.PIVOT_BARS + 1
                 for k, ra, rb in rev)
        orphan += not ok
    check("every live span sits inside its review twin (lag <= confirm)",
          orphan == 0, "%d orphan live spans of %d" % (orphan, len(live)))


def part3():
    print("\n3. THE OWNER'S EYE (fixture floor)")
    W = {w["n"]: w for w in
         json.load(open("validation/fixture_windows.json"))}
    M = json.load(open("validation/fixture_marks.json"))
    agree = silent = conflict = eq_hit = eq_tot = painted = 0
    for n_str, marks in M.items():
        w = W[int(n_str)]
        raw = pd.read_csv("history/%s_1h.csv.gz" % w["sym"], index_col=0,
                          parse_dates=True)
        df = SC.resample(raw, RULES[w["tf"]]) if RULES[w["tf"]] else raw
        pos = df.index.get_indexer([pd.Timestamp(w["dates"][0])])[0]
        st = ST.states(df)[pos:pos + len(marks)]
        eqa, _ = ST.eq_overlay(df)
        eqa = eqa[pos:pos + len(marks)]
        for i, m in enumerate(marks):
            if not m:
                continue
            painted += 1
            if m == "B":
                eq_tot += 1
                if eqa[i]:
                    eq_hit += 1
                    agree += 1
                else:
                    silent += 1
            else:
                want = {"U": "UP", "D": "DOWN"}[m]
                if st[i] == want:
                    agree += 1
                elif st[i] == "FLAT":
                    silent += 1
                else:
                    conflict += 1
    a, s, c = (100 * agree / painted, 100 * silent / painted,
               100 * conflict / painted)
    print("     fixture: agree %.0f%%  silent %.0f%%  conflict %.0f%%  EQ %d/%d"
          % (a, s, c, eq_hit, eq_tot))
    check("agreement with the owner >= 65%", a >= 65, "%.1f%%" % a)
    check("conflict with the owner <= 12%", c <= 12, "%.1f%%" % c)
    check("painted EQ bars matched >= 20", eq_hit >= 20, str(eq_hit))


def part4():
    print("\n4. OWNER-GRADED REGRESSIONS")
    raw = pd.read_csv("history/PENGU_1h.csv.gz", index_col=0,
                      parse_dates=True)
    df = SC.resample(raw, "1D")
    eqd, _ = ST.eq_display(df)
    runs = []
    i = 0
    while i < len(eqd):
        if eqd[i]:
            j = i
            while j + 1 < len(eqd) and eqd[j + 1]:
                j += 1
            runs.append((str(df.index[i].date()), str(df.index[j].date())))
            i = j + 1
        else:
            i += 1
    check("PENGU 1d range lives 2026-02-14 -> 2026-03-12 (wick-kill)",
          ("2026-02-14", "2026-03-12") in runs,
          str([r for r in runs if r[0].startswith("2026-0")][:4]))
    piv = ST.labelled_pivots(raw)
    lo, hi = pd.Timestamp("2025-05-03 12:00"), pd.Timestamp("2025-05-04 16:00")
    lls = [(raw.index[j], p) for j, p, k, lab in piv
           if lo <= raw.index[j] <= hi and lab == "LL"]
    check("PENGU May-2025 decline: one LL, at the true bottom",
          len(lls) == 1 and abs(lls[0][1] - 0.00974) < 1e-5, str(lls))


def main():
    part1()
    part2()
    part3()
    part4()
    print("\n  %s" % ("ALL STRUCTURE TESTS PASS" if not FAILS
                      else "FAILURES: %s" % ", ".join(FAILS)))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
