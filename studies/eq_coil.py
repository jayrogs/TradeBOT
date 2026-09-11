"""eq_coil.py -- the EQ as he defines it (2026-09-09, his words):

    "eq is a series of HL and LH increasingly tightening"

Higher lows pressing UP into lower highs pressing DOWN, the gap narrowing, until it has to
break. That is a coil. What I built before this (a flat-floor, flat-ceiling box) is a CHANNEL
and is a different thing; it is kept under that name.

The rule, exactly:
    * the pivots alternate low, high, low, high (the engine's: 2 bars each side, a leg of at
      least one normal bar's move, labelled HH/HL/LH/LL/EH/EL)
    * a coil is a run where every low is a higher low and every high is a lower high. An EQUAL
      low or high (within 0.15 of a normal bar) does not break the run -- a double bottom inside
      a coil is still the coil -- but it does not count towards the tightening either.
    * it takes at least two higher lows and two lower highs (his "HL LH HL LH")
    * and it must actually be narrowing: the last pair is closer together than the first
    * the FLOOR is the last higher low, the CEILING is the last lower high. Both step INWARD as
      it goes, which is the point: the trade gets cheaper and the break gets clearer.
    * it dies when a WICK goes through the floor or ceiling by more than the equal-level
      tolerance (0.15 of a normal bar), or when a lower low / higher high pivot breaks the
      sequence. His words 2026-09-09: "a break isnt a close under the floor, a break is a wick
      though the floor, with slight tolerance, basically for it not to be an EL." A poke that
      would still have been labelled an equal low is not a break.

TIMING. A pivot is not knowable until it confirms, two bars after it prints. So a coil has two
dates: `born`, the first pivot of the shape (what the eye draws), and `confirm`, the first bar
you could have known it was there. Between the two, price can already have left -- those are
recorded with tradeable=False, because a break you could not have acted on is not a trade.

`coils(df)` returns floor[], ceil[], cid[] (which coil each bar belongs to, -1 outside) and a
list of records. Each record is a dict so nothing downstream has to unpack by position.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import panel as P                 # noqa: E402
import structure as ST            # noqa: E402

MIN_PAIRS = 2                     # two higher lows AND two lower highs
UP_LAB = ("HL", "EL")             # a low that keeps a coil alive
DN_LAB = ("LH", "EH")             # a high that keeps a coil alive


def coils(df, min_pairs=MIN_PAIRS, need_tighter=True, min_gap=0):
    """Every EQ on this chart, using only what was known at the time."""
    c = df["Close"].values.astype(float)
    h_ = df["High"].values.astype(float)
    l_ = df["Low"].values.astype(float)
    n = len(c)
    atr = P._atr(df)
    piv = ST.pivots(df)                       # (confirm_bar, form_bar, price, kind, label)
    floor = np.full(n, np.nan)
    ceil = np.full(n, np.nan)
    cid = np.full(n, -1)
    out = []

    run = []                                  # the pivots of the coil being built
    i = 0
    while i < len(piv):
        ci, j, price, kind, lab = piv[i]
        good = (lab in UP_LAB) if kind == "low" else (lab in DN_LAB)
        if not good:
            run = [piv[i]]                    # this pivot breaks the run and seeds the next
            i += 1
            continue
        if min_gap and run and j - run[-1][1] < min_gap:
            run = [piv[i]]                    # pivots on top of each other: an anomaly, not an EQ (his rule)
            i += 1
            continue
        run.append(piv[i])
        n_hl = sum(1 for x in run if x[3] == "low" and x[4] == "HL")
        n_lh = sum(1 for x in run if x[3] == "high" and x[4] == "LH")
        if n_hl < min_pairs or n_lh < min_pairs:
            i += 1
            continue
        lows = [x for x in run if x[3] == "low"]
        highs = [x for x in run if x[3] == "high"]
        f = float(lows[-1][2]); ce = float(highs[-1][2])
        first_f = float(lows[0][2]); first_c = float(highs[0][2])
        if ce <= f or (need_tighter and (ce - f) >= (first_c - first_f)):
            i += 1
            continue                          # inverted, or not actually narrowing
        born = min(run[0][1], run[0][0])      # the first pivot of the shape: what the eye draws
        confirm = ci                          # the first bar you could have known
        # The bars between the last pivot PRINTING and CONFIRMING are real bars. If price already broke
        # through the floor or the ceiling there, the EQ was dead before anyone could know it existed.
        # (INJ daily, May 2024: a spike to 28.80 through a 26.37 ceiling, then an EQ was "declared".)
        lo_from = int(lows[-1][1]) + 1
        hi_from = int(highs[-1][1]) + 1
        broke_early = False
        for kk in range(min(lo_from, hi_from), confirm):
            tolk = P.SAME_LEVEL_ATR * (atr[kk] if np.isfinite(atr[kk]) else 0.0)
            if (kk >= hi_from and h_[kk] > ce + tolk) or (kk >= lo_from and l_[kk] < f - tolk):
                broke_early = True
                break
        if broke_early:
            i += 1
            continue
        # walk forward: a later pivot tightens the edges, a close outside ends it
        k = confirm
        nxt = i + 1
        died = None
        painted = 0
        while k < n:
            tol = P.SAME_LEVEL_ATR * (atr[k] if np.isfinite(atr[k]) else 0.0)
            if h_[k] > ce + tol or l_[k] < f - tol:
                died = (k, "a wick through the ceiling" if h_[k] > ce + tol else "a wick through the floor")
                break
            floor[k] = f; ceil[k] = ce; cid[k] = len(out)
            painted += 1
            while nxt < len(piv) and piv[nxt][0] == k:
                ci2, j2, p2, kind2, lab2 = piv[nxt]
                good2 = (lab2 in UP_LAB) if kind2 == "low" else (lab2 in DN_LAB)
                if not good2:
                    died = (k, "a lower low broke it" if kind2 == "low" else "a higher high broke it")
                    break
                if min_gap and j2 - run[-1][1] < min_gap:
                    died = (k, "two pivots too close together")
                    break
                run.append(piv[nxt])
                if kind2 == "low":
                    f = float(p2); n_hl += 1 if lab2 == "HL" else 0
                else:
                    ce = float(p2); n_lh += 1 if lab2 == "LH" else 0
                nxt += 1
            if died:
                break
            k += 1
        end = died[0] if died else n - 1
        a0 = atr[confirm] if np.isfinite(atr[confirm]) and atr[confirm] > 0 else np.nan
        out.append(dict(
            i=len(out), born=born, confirm=confirm, end=end,
            how=died[1] if died else "still open",
            pairs=int(min(n_hl, n_lh)), highs=int(n_lh), lows=int(n_hl),
            floor=f, ceil=ce, first_floor=first_f, first_ceil=first_c,
            bars=int(end - born + 1), live_bars=int(painted),
            # a break inside the two bars before the last pivot confirmed is not a trade
            tradeable=bool(painted > 0),
            wide_at_start=float((first_c - first_f) / a0) if np.isfinite(a0) else None,
            wide_at_end=float((ce - f) / a0) if np.isfinite(a0) else None))
        i = nxt
        run = []
    return floor, ceil, cid, out, atr


if __name__ == "__main__":
    import backburner_study as B
    a = sys.argv[1:]
    sym, kind, tf = (a + ["MSTR", "stock", "1d"])[:3] if a else ("MSTR", "stock", "1d")
    df = B.frames_for(sym, kind)[tf]
    floor, ceil, cid, out, atr = coils(df)
    live = [r for r in out if r["tradeable"]]
    print("%s %s: %d EQs, %d you could have traded" % (sym, tf, len(out), len(live)))
    for r in live[-12:]:
        print("  %s -> %s  %3d bars (%3d live)  %d pairs  %.1f -> %.1f bars wide  %s" % (
            df.index[r["born"]].date(), df.index[r["end"]].date(), r["bars"], r["live_bars"],
            r["pairs"], r["wide_at_start"] or 0, r["wide_at_end"] or 0, r["how"]))
