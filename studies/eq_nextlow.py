"""eq_nextlow.py -- after high -> low -> lower high, is the next low a HIGHER low? (2026-09-21)

His words: "that's after a larger move, if it has 3 of those pivots, high low lower high, you can expect a higher
low, I think". No trade, no money: just the count. For every three confirmed pivots A (a high), B (the low after it),
C (the next high, UNDER A), what is the next pivot low D -- higher than B (equal counts) or lower? And when it IS a
higher low, is the high after it another lower high (the EQ keeps forming) or a higher high (it left upward)?
Split by how big the move A->B was (in normal bars) and how much of it C took back. The mirror (low, high, higher
low -> is the next high a LOWER high) is counted too. "Every low" is the base rate to beat: how often ANY pivot low
is higher than the one before it.

    pythonw studies/eq_nextlow.py --procs 8 --log logs/eq_nextlow.log
Writes validation/eq_nextlow.json
"""
import concurrent.futures as cf
import io
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as B      # noqa: E402
import trend_ride as R            # noqa: E402
import panel as P                 # noqa: E402
import structure as ST            # noqa: E402
import eq_freeride2 as FR2        # noqa: E402

OUT = os.path.join("validation", "eq_nextlow.json")
TFS = ["1h", "4h", "1d"]
COLS = ["tf", "side", "leg", "retrace", "held", "then", "yr", "kind"]      # then: 1 = EQ kept forming, 2 = left our way


def _work(args):
    sym, kind = args
    try:
        frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    frames = {k: v for k, v in frames.items() if k in TFS}
    if kind in ("stock", "etf"):
        try:
            frames = FR2.regular_hours(frames)
        except Exception:
            pass
    rows, errs = [], []
    for t_i, tf in enumerate(TFS):
        df = frames.get(tf)
        if df is None or len(df) < 200:
            continue
        try:
            atr = P._atr(df)
            piv = ST.pivots(df)
            yrs = df.index.year.values
            k_i = FR2.KINDS.index(kind) if kind in FR2.KINDS else 0
            for i in range(2, len(piv) - 1):
                ciA, jA, pA, kA, _ = piv[i - 2]
                ciB, jB, pB, kB, _ = piv[i - 1]
                ciC, jC, pC, kC, _ = piv[i]
                ciD, jD, pD, kD, _ = piv[i + 1]
                if not (kA == kC and kA != kB and kD == kB):
                    continue
                side = 1 if kB == "low" else -1
                pA, pB, pC, pD = float(pA), float(pB), float(pC), float(pD)
                a = atr[int(ciC)]
                if not (np.isfinite(a) and a > 0):
                    continue
                inside = (pB < pC < pA) if side > 0 else (pB > pC > pA)
                leg = abs(pA - pB) / a
                retr = abs(pC - pB) / abs(pA - pB) if pA != pB else np.nan
                tol = P.SAME_LEVEL_ATR * a
                held = (pD >= pB - tol) if side > 0 else (pD <= pB + tol)
                then = 0.0
                if held and i + 2 < len(piv):
                    pE = float(piv[i + 2][2])
                    then = 1.0 if ((pE <= pC + tol) if side > 0 else (pE >= pC - tol)) else 2.0
                # side 1/-1 = the three-pivot shape; 2/-2 = the same count with C NOT inside A (a higher high first)
                rows.append([t_i, side if inside else 2 * side, leg, retr, 1.0 if held else 0.0, then,
                             float(yrs[int(ciC)]), k_i])
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    if not rows:
        return None, errs
    return np.asarray(rows, dtype=np.float64), errs


def main():
    procs, log = 8, None
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            log = sys.argv[i + 1]
            sys.stdout = sys.stderr = io.open(log, "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    names = R._by_size([(s_, k_) for s_, k_ in B.universe() if k_ != "forex"])
    R.quiet_workers()
    parts, errs = [], []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for part, err in ex.map(_work, names, chunksize=2):
            errs += err or []
            if part is not None:
                parts.append(part)
    f = pd.DataFrame(np.concatenate(parts), columns=COLS)
    try:
        f.to_parquet(os.path.splitext(OUT)[0] + "_rows.parquet")
    except Exception:
        pass
    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names), rows=int(len(f)),
                         seconds=int(time.time() - t0)), table={})
    LEGS = [("any size move first", 0, 1e9), ("a small move first (under 2 normal bars)", 0, 2),
            ("2 to 4 normal bars", 2, 4), ("a LARGER move first (4 to 8)", 4, 8), ("a VERY large move first (8+)", 8, 1e9)]
    RETS = [("any swing back", 0, 1e9), ("swing back 38% or less", 0, 0.382), ("38 to 50%", 0.382, 0.5),
            ("50 to 62%", 0.5, 0.618), ("62 to 79%", 0.618, 0.786), ("79% or more", 0.786, 1e9)]
    print("\n  AFTER high -> low -> lower high, IS THE NEXT LOW A HIGHER LOW?   %d names, %d shapes  (%.0fs)\n" % (
        len(names), len(f), time.time() - t0))
    for t_i, tf in enumerate(TFS):
        for side, sname, word in ((1, "high, low, LOWER HIGH -> the next low", "higher low"),
                                  (-1, "low, high, HIGHER LOW -> the next high", "lower high")):
            g = f[(f.tf == t_i)]
            base = g[g.side.isin([side, 2 * side])]
            shape = g[g.side == side]
            other = g[g.side == 2 * side]
            key = "%s | %s" % (tf, sname)
            out["table"][key] = {}
            print("  %s   %s" % (tf, sname))
            print("    base rate, every such pivot: %s %.0f%% (n %d)   |   when the middle high/low was NOT inside the first: %.0f%% (n %d)" % (
                word, 100 * base.held.mean(), len(base), 100 * other.held.mean() if len(other) else 0, len(other)))
            out["table"][key]["base"] = dict(n=int(len(base)), held=float(base.held.mean()))
            out["table"][key]["not_inside"] = dict(n=int(len(other)), held=float(other.held.mean()) if len(other) else None)
            print("    %-44s %-24s %7s %9s %14s %12s %8s" % ("the move first", "the swing back", "n", word, "then EQ forms", "then leaves", "yrs>base"))
            for ll, l0, l1 in LEGS:
                for rl, r0, r1 in RETS:
                    if ll.startswith("any") != rl.startswith("any") and not (ll.startswith("any") or rl.startswith("any")):
                        pass
                    s = shape[(shape.leg >= l0) & (shape.leg < l1) & (shape.retrace > r0) & (shape.retrace <= r1)]
                    if len(s) < 100:
                        continue
                    h = s[s.held > 0]
                    by = s.groupby("yr").held.mean(); bb = base.groupby("yr").held.mean()
                    yu = int((by > bb.reindex(by.index)).sum())
                    row = dict(n=int(len(s)), held=float(s.held.mean()),
                               then_eq=float((h.then == 1).mean()) if len(h) else None,
                               then_left=float((h.then == 2).mean()) if len(h) else None, years_over_base=yu, years=int(len(by)))
                    out["table"][key]["%s | %s" % (ll, rl)] = row
                    if ll.startswith("any") or rl.startswith("any") or l0 >= 4:
                        print("    %-44s %-24s %7d %8.0f%% %13.0f%% %11.0f%% %5d/%-2d" % (
                            ll, rl, row["n"], 100 * row["held"], 100 * (row["then_eq"] or 0), 100 * (row["then_left"] or 0),
                            yu, row["years"]))
            print()
    json.dump(out, io.open(OUT, "w", encoding="utf-8"))
    for e_ in errs[:8]:
        print("  ERR " + e_)
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
