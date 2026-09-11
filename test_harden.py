"""test_harden.py -- the exit rules on hand-built candles, and every
re-implementation checked against the canonical one.

    python test_harden.py

Two chart-lying incidents happened because a renderer's copy of the rule
drifted from the scored rule. These tests make that a test failure instead
of a wasted grading round:

  PART 1  run_exit on synthetic arrays: body exit, promotion, stop
          precedence, ratchet floor, targets, grace -- each rule proven on
          candles built to trigger exactly it
  PART 2  entries() gate on synthetic arrays
  PART 3  on real BTC history: trade_pics2.trades_with_marks must produce
          the IDENTICAL trades to rider_lab entries+run_exit, and
          partial_study.walk must produce the identical exit prices
  PART 4  rider_short's inversion must be a true involution
"""

import sys
import warnings

import numpy as np
import pandas as pd

import rider_lab as L

warnings.filterwarnings("ignore")

FAILS = []


def check(name, cond, detail=""):
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("  " + detail if detail and not cond else "")))
    if not cond:
        FAILS.append(name)


def mkv(c, lo=None, hi=None, e=None, hold=None, o=None, atr=None):
    c = np.asarray(c, float)
    n = len(c)
    v = dict(c=c,
             lo=np.asarray(lo, float) if lo is not None else c - 0.1,
             hi=np.asarray(hi, float) if hi is not None else c + 0.1,
             e=np.asarray(e, float) if e is not None else np.full(n, 100.0),
             hold=np.asarray(hold, bool) if hold is not None else np.ones(n, bool),
             o=np.asarray(o, float) if o is not None else c,
             atr=np.asarray(atr, float) if atr is not None else np.ones(n),
             n=n)
    return v


def part1():
    print("\nPART 1 -- exit rules on hand-built candles")

    # body close under the EMA before promotion ends the trade at that close
    v = mkv(c=[100, 100.2, 99.0, 98, 97], hold=[1, 1, 0, 1, 1])
    r = L.run_exit(v, 0, 100.0, "promote1")
    check("body exit fires pre-promotion", r == (2, 99.0, "body"), str(r))

    # OWNER SPEC: a body close only BARELY under the EMA (within 0.25 ATR)
    # does not exit -- "it just baaaaarely didnt hold"
    v = mkv(c=[100, 99.9, 99.85, 99.9, 99.85], hold=[1, 0, 0, 0, 0])
    r = L.run_exit(v, 0, 100.0, "promote1")
    check("barely-under closes are tolerated", r is None, str(r))

    # promoted at +1%: the same body close is ignored, only the trail exits
    v = mkv(c=[100, 101.5, 99.0, 98.5, 96.0],
            lo=[99.9, 101.0, 98.8, 98.3, 96.0],
            hold=[1, 1, 0, 0, 0])
    r = L.run_exit(v, 0, 100.0, "promote1")
    check("promotion ignores body closes, trail exits",
          r == (4, 100.0 * 0.97, "stop"), str(r))

    # stop beats everything else on the same bar
    v = mkv(c=[100, 96.0], lo=[99.9, 96.0], hold=[1, 0])
    r = L.run_exit(v, 0, 100.0, "promote1")
    check("stop precedence on the shared bar", r == (1, 97.0, "stop"), str(r))

    # ratchet: the floor must NOT follow the EMA down
    e = [100, 102, 104, 103, 101, 99.5, 98.5]
    lo = [99, 101, 103, 102.2, 100.2, 98.7, 97.7]     # never 3% under CURRENT e
    c = [100, 102, 104, 102.5, 100.5, 99.0, 98.0]
    v = mkv(c=c, lo=lo, e=e, hold=[1] * 7)
    r1 = L.run_exit(v, 0, 100.0, "promote1")
    r2 = L.run_exit(v, 0, 100.0, "ratchet1")
    check("plain trail never fires on the bleed", r1 is None, str(r1))
    check("ratchet floor holds at the peak (104*0.97=100.88)",
          r2 is not None and r2[2] == "stop" and abs(r2[1] - 104 * 0.97) < 1e-9
          and r2[0] == 4, str(r2))

    # target: resting limit sell at +2%
    v = mkv(c=[100, 101, 101.5], hi=[100.5, 101.9, 102.4])
    r = L.run_exit(v, 0, 100.0, "target2")
    check("target fills at the limit, not the high",
          r == (2, 102.0, "target"), str(r))

    # grace2: one body close under survives, two consecutive do not
    v = mkv(c=[100, 99.8, 100.2, 99.7, 99.6], hold=[1, 0, 1, 0, 0])
    r = L.run_exit(v, 0, 100.0, "grace2")
    check("grace2 survives one, dies on two", r == (4, 99.6, "body"), str(r))

    # redexit: a GREEN candle body-closing under does not exit
    v = mkv(c=[100, 99.5, 99.0], o=[100, 99.0, 99.6], hold=[1, 0, 0])
    r = L.run_exit(v, 0, 100.0, "redexit")
    check("green body-under ignored, red body-under exits",
          r == (2, 99.0, "body"), str(r))


def part2():
    print("\nPART 2 -- the entry gate")
    n = 10
    v = mkv(c=[100.0] * n)
    v["armed"] = np.array([0, 1, 1, 1, 1, 1, 1, 1, 0, 0], bool)
    v["touch"] = np.array([0, 0, 1, 0, 1, 0, 1, 0, 0, 0], bool)
    v["rising"] = np.ones(n, bool)
    v["steep"] = np.ones(n, bool)
    v["upage"] = np.full(n, 9)
    ent = L.entries(v, 2, "promote1")
    check("2 defended touches -> entry on the 3rd", ent == [(6, 100.0)], str(ent))
    v["rising"][6] = False
    ent = L.entries(v, 2, "promote1")
    check("falling EMA blocks the entry", ent == [], str(ent))
    # OWNER SPEC: minimum wind -- the trend must have been UP for 5+ bars
    v["rising"][6] = True
    v["upage"] = np.full(n, 3)
    ent = L.entries(v, 2, "promote1")
    check("young trend (3 bars) blocks the entry", ent == [], str(ent))


def part3():
    print("\nPART 3 -- every copy of the rule against the canonical one")
    import trade_pics2 as TP
    import partial_study as PS

    raw = pd.read_csv("history/BTC_1h.csv.gz", index_col=0,
                      parse_dates=True).tail(8000)
    v = L.prep(raw)

    canon = []
    for entry, fill in L.entries(v, 2, "promote1"):
        if entry >= v["n"] - 2:
            continue
        r = L.run_exit(v, entry, fill, "promote1")
        if r:
            canon.append((entry, r[0], round(r[1] / fill - 1 - 2 * L.COST, 12)))

    pics = [(t["entry"], t["exit"], round(t["net"], 12))
            for t in TP.trades_with_marks(raw, 2, 0.03)]
    check("trade_pics2 == canonical (%d trades)" % len(canon),
          pics == canon,
          "canon %d vs pics %d; first diff %s" % (
              len(canon), len(pics),
              next((a for a, b in zip(canon, pics) if a != b), "len")))

    ok = True
    for entry, fill in L.entries(v, 2, "promote1")[:200]:
        if entry >= v["n"] - 2:
            continue
        r = L.run_exit(v, entry, fill, "promote1")
        px, _ = PS.walk(v, entry, fill)
        if (r is None) != (px is None) or (r and abs(r[1] - px) > 1e-9):
            ok = False
            break
    check("partial_study.walk == canonical exit", ok)


def part3b():
    print("\nPART 3b -- the trend engine never peeks at the future")
    import panel as P
    raw = pd.read_csv("history/BTC_1h.csv.gz", index_col=0,
                      parse_dates=True).tail(9000)
    full, _, _ = P.trend_state(raw)
    n = int(len(raw) * 0.7)
    cut, _, _ = P.trend_state(raw.iloc[:n])
    mism = int(np.sum(np.asarray(full[:n]) != np.asarray(cut)))
    check("trend_state is causal (cut vs full: 0 mismatches)", mism == 0,
          "%d bars differ" % mism)


def part3c():
    print("\nPART 3c -- the range overlay (owner-verified 2026-08-31)")
    import panel_v3 as V3
    raw = pd.read_csv("history/BTC_1h.csv.gz", index_col=0,
                      parse_dates=True).tail(9000)
    full, _ = V3.eq_overlay(raw)
    n = int(len(raw) * 0.7)
    cut, _ = V3.eq_overlay(raw.iloc[:n])
    mism = int(np.sum(full[:n] != cut))
    check("eq_overlay is causal", mism == 0, "%d bars differ" % mism)
    disp, _ = V3.eq_display(raw, min_span=4)
    spans = []
    i = 0
    while i < len(disp):
        if disp[i]:
            j = i
            while j + 1 < len(disp) and disp[j + 1]:
                j += 1
            spans.append(j - i + 1)
            i = j + 1
        else:
            i += 1
    check("display suppresses sub-4-bar blips",
          all(x >= 4 for x in spans), str(sorted(spans)[:5]))
    import panel as P
    st, _, _ = P.trend_state(raw)
    check("the overlay leaves v1's states untouched",
          "panel_v3" not in open("panel.py").read())


def part3d():
    print("\nPART 3d -- chart bundles carry EVERY layer (the PENGU miss)")
    import scanner as SC
    import chartkit as CK
    raw = pd.read_csv("history/PENGU_1h.csv.gz", index_col=0,
                      parse_dates=True)
    df = SC.resample(raw, "1D")
    pos = df.index.get_indexer([pd.Timestamp("2025-11-06")])[0]
    b = CK.bundle(df, pos, 200)
    check("bundle has the required layers",
          all(k in b for k in ("spans", "eq", "pivots", "ema", "d")))
    check("spans present", len(b["spans"]) > 0, str(len(b["spans"])))
    check("pivots present", len(b["pivots"]) > 10, str(len(b["pivots"])))
    # the regression itself: the owner's circled EQ (born 2026-02-28 off
    # LH HL LH HL) must be IN the bundle -- a renderer that draws bundles
    # cannot hide it again
    idx = b["d"].index
    m = [(i, v) for i, v in enumerate(b["eq"])
         if v and pd.Timestamp("2026-02-14") <= idx[i]
         <= pd.Timestamp("2026-03-15")]
    check("the circled PENGU EQ is in the bundle", len(m) >= 10,
          "%d eq bars in the window" % len(m))


def part3e():
    print("\nPART 3e -- span invariants: no contrary pivot inside a span")
    import pics_spans as PSp
    bad = 0
    for sym in ("PUMP", "BTC", "DOGE"):
        raw = pd.read_csv("history/%s_1h.csv.gz" % sym, index_col=0,
                          parse_dates=True).tail(9000)
        piv = PSp.labelled_pivots(raw)
        spans = PSp.spans_from_pivots(piv, len(raw), raw)
        for kind, s0, s1 in spans:
            contrary = ("LH", "LL") if kind == "UP" else ("HH", "HL")
            for j, price, k2, lab in piv:
                if lab in contrary and s0 <= j <= s1:
                    bad += 1
    check("no LL/LH inside green, no HH/HL inside red (3 names, 27k bars)",
          bad == 0, "%d violations" % bad)


def part4():
    print("\nPART 4 -- the short-side inversion")
    from studies import rider_short as RS
    raw = pd.read_csv("history/BTC_1h.csv.gz", index_col=0,
                      parse_dates=True).tail(3000)
    back = RS.invert(RS.invert(raw))
    err = max(float((back[k] - raw[k]).abs().max()) for k in
              ("Open", "High", "Low", "Close"))
    check("invert(invert(x)) == x", err < 1e-9, "max err %g" % err)
    inv = RS.invert(raw)
    check("inversion swaps High and Low ordering",
          bool((inv["High"] >= inv["Low"]).all()))


def main():
    part1()
    part2()
    part3()
    part3b()
    part3c()
    part3d()
    part3e()
    part4()
    print("\n  %s" % ("ALL HARDENING TESTS PASS" if not FAILS
                      else "FAILURES: %s" % ", ".join(FAILS)))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
