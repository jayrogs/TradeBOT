"""eq_retrace.py -- The Chart Guys' number for telling a FLAG from an EQ, put on Jay's EQ trade (2026-09-21).

From the full read of their videos (TCG_METHOD.md 19g; zFzDEvWsPk8 and four others): a pullback that takes back
38.2% OR LESS of the move before it is a FLAG, continuation favoured; 50% OR MORE means an EQUILIBRIUM is the most
likely thing to form; between the two is the grey zone. And, in Dan's words paraphrased: if a flag is likely and
you play off support you get stopped out; if an equilibrium is likely, playing off support has the odds.

Every EQ study on this desk (#26b-#26n) bought the higher low inside the shape without ever asking how deep the
first swing back was. This asks. SAME TRADE as eq_farline (the next open after a higher low / lower high confirms
inside a live EQ, stop a wick through it, half or all out at the far line) -- only the split is new:

    retrace    the shape's first swing back, as a share of the move INTO the shape   (eq_coil: `retrace`)
    leg        how big that move was, in normal bars                                  (`leg_bars`)
    fade       volume in the second half of the shape against the first half          (`vol_fade`; they want it falling)
    began      did the shape start from a LOW (a drop, then a 50% bounce: their example) or from a HIGH

1h, 4h and daily only (the fast charts have never paid after cost, #24-#26h). Frames are trimmed to the charts
used and it runs on 8 cores (#36).

    pythonw studies/eq_retrace.py --procs 8 --log logs/eq_retrace.log
Writes validation/eq_retrace.json
"""
import concurrent.futures as cf
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
import eq_freeride2 as FR2        # noqa: E402

import functools                  # noqa: E402
import eq_coil as EC              # noqa: E402

# HIS POINT, 2026-09-21: Dan acts after ONE pair (high, low, lower high, higher low); my detector waits for two.
# EQ_PAIRS=1 in the environment runs the SAME trade with the detector firing after one pair. Workers re-import this
# module, so the switch is read here, at import.
PAIRS_NEEDED = int(os.environ.get("EQ_PAIRS", "2"))
if PAIRS_NEEDED != 2:
    EC.coils = functools.partial(EC.coils, min_pairs=PAIRS_NEEDED)
OUT = os.path.join("validation", "eq_retrace.json" if PAIRS_NEEDED == 2 else "eq_retrace_pairs%d.json" % PAIRS_NEEDED)
TFS = ["1h", "4h", "1d"]
KEEP = {"1h", "4h", "1d", "1w"}
VARIANTS = [FR2.MODES[1][0], FR2.MODES[2][0]]          # half at the far line; all out at the far line
ERAS = FR2.ERAS
KINDS = FR2.KINDS
COLS = ("var", "tf", "side", "tag", "kind", "era", "rr", "ret", "drift", "took", "held", "risk", "retrace", "leg",
        "fade", "began", "yr")


def _work(args):
    sym, kind, start = args
    try:
        frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    frames = {k: v for k, v in frames.items() if k in KEEP}
    rows, errs = [], []
    for tf in TFS:
        try:
            for x in FR2.trades(kind, tf, frames.get(tf), frames, start, 0, modes=VARIANTS):
                if x.get("retrace") is None:
                    continue
                rows.append([VARIANTS.index(x["variant"]), TFS.index(tf), x["side_i"], x["tag1"], x["kind_i"],
                             x["era_i"], x["rr"], x["ret"], x["drift"], 1.0 if x["took"] else 0.0, x["held"],
                             abs(x["fill"] - x["stop"]) / x["fill"], x["retrace"],
                             x["leg_bars"] if x["leg_bars"] is not None else np.nan,
                             x["vol_fade"] if x["vol_fade"] is not None else np.nan,
                             0.0 if x["first_kind"] == "low" else 1.0, float(pd.Timestamp(x["t"]).year)])
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
            sys.stdout = sys.stderr = open(log, "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * B.YEARS)
    names = R._by_size([(s_, k_) for s_, k_ in B.universe() if k_ != "forex"])
    R.quiet_workers()
    parts, errs, done = [], [], 0
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for part, err in ex.map(_work, [(s_, k_, start) for s_, k_ in names], chunksize=1):
            done += 1
            errs += err or []
            if part is not None:
                parts.append(part)
            if done % 100 == 0 or done == len(names):
                print("  %d/%d names  (%.0fs)" % (done, len(names), time.time() - t0), flush=True)
    for e_ in errs[:20]:
        print("  ERR " + e_)
    f = pd.DataFrame(np.concatenate(parts), columns=COLS)
    f["R"] = f.ret / f.risk.where(f.risk > 0)

    def st(g):
        if len(g) < 40:
            return None
        blocks = [g.ret.values[i:i + 20].sum() for i in range(0, len(g) - 19, 20)]
        yrs = g.groupby("yr").ret.mean()
        return dict(n=int(len(g)), mean=float(g.ret.mean()), median=float(g.ret.median()),
                    edge=float((g.ret - g.drift).mean()), won=float((g.ret > 0).mean()),
                    avg_R=float(g.R.mean()), reached=float(g.took.mean()), held=float(g.held.mean()),
                    blocks_up=int(sum(1 for b in blocks if b > 0)), blocks=int(len(blocks)),
                    years_up=int((yrs > 0).sum()), years=int(len(yrs)),
                    eras=[float(g[g.era == e].ret.mean()) if (g.era == e).sum() >= 20 else None for e in range(3)])

    flag = lambda x: x.retrace <= 0.382                         # noqa: E731
    grey = lambda x: (x.retrace > 0.382) & (x.retrace < 0.5)    # noqa: E731
    eq = lambda x: x.retrace >= 0.5                             # noqa: E731
    CUTS = [
        ("every EQ trade", lambda x: x.ret == x.ret),
        ("first swing back 38.2% or less  (their FLAG)", flag),
        ("first swing back 38.2-50%       (their grey zone)", grey),
        ("first swing back 50% or more    (their EQ)", eq),
        ("first swing back 50-100%", lambda x: eq(x) & (x.retrace <= 1.0)),
        ("first swing back over 100%      (took out the start of the move)", lambda x: x.retrace > 1.0),
        ("their EQ + a BIG move first (4+ normal bars)", lambda x: eq(x) & (x.leg >= 4)),
        ("their EQ + big move + volume FADING through the shape", lambda x: eq(x) & (x.leg >= 4) & (x.fade < 1.0)),
        ("their EQ + big move + volume RISING through the shape", lambda x: eq(x) & (x.leg >= 4) & (x.fade >= 1.0)),
        ("their FLAG + a big move first", lambda x: flag(x) & (x.leg >= 4)),
        ("far line 1x+ the risk, every trade", lambda x: x.rr >= 1),
        ("far line 1x+, their EQ", lambda x: (x.rr >= 1) & eq(x)),
        ("far line 1x+, their FLAG", lambda x: (x.rr >= 1) & flag(x)),
        ("far line 1x+, their EQ, WITH the daily 50 EMA", lambda x: (x.rr >= 1) & eq(x) & (x.tag == 0)),
        ("far line 1x+, their FLAG, WITH the daily 50 EMA", lambda x: (x.rr >= 1) & flag(x) & (x.tag == 0)),
        ("far line 1x+, their EQ + big move + fading volume", lambda x: (x.rr >= 1) & eq(x) & (x.leg >= 4) & (x.fade < 1)),
        ("LONG, shape began from a LOW  (drop, then the bounce: their example)", lambda x: (x.side == 0) & (x.began == 0)),
        ("LONG, shape began from a HIGH", lambda x: (x.side == 0) & (x.began == 1)),
        ("LONG, began from a low, their EQ, big move first", lambda x: (x.side == 0) & (x.began == 0) & eq(x) & (x.leg >= 4)),
        ("SHORT, began from a high, their EQ, big move first", lambda x: (x.side == 1) & (x.began == 1) & eq(x) & (x.leg >= 4)),
    ]
    out = {}
    print("\n  THE FLAG / EQ NUMBER ON THE EQ TRADE   %d names, %d trade rows  (%.0fs)" % (
        len(names), len(f), time.time() - t0))
    print("  MY VERSION of their rule on MY detector's EQs. avg / middle per trade, then R, won, far line reached,")
    print("  blocks of 20 that made money, years up, and the three eras (before 2022 / first half / second half).\n")
    for v_i, v in enumerate(VARIANTS):
        for t_i, tf in enumerate(TFS):
            base = f[(f["var"] == v_i) & (f.tf == t_i)]
            if len(base) < 100:
                continue
            print("  %s  --  %s" % (tf, v))
            print("    %-64s %6s %7s %7s %6s %5s %6s %8s %6s  %s" % (
                "cut", "n", "avg", "middle", "R", "won", "reach", "blocks", "years", "eras"))
            for lab, fn in CUTS:
                s = st(base[fn(base)])
                if not s:
                    continue
                out["%s | %s | %s" % (tf, v, lab)] = s
                eras = " ".join(("%+.2f" % (100 * e)) if e is not None else "  -  " for e in s["eras"])
                print("    %-64s %6d %+6.2f%% %+6.2f%% %+5.2f %4.0f%% %5.0f%% %4d/%-3d %2d/%-2d  %s" % (
                    lab[:64], s["n"], 100 * s["mean"], 100 * s["median"], s["avg_R"], 100 * s["won"],
                    100 * s["reached"], s["blocks_up"], s["blocks"], s["years_up"], s["years"], eras))
            print()
    res = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names), tfs=TFS,
                         variants=VARIANTS, rows=int(len(f)), seconds=int(time.time() - t0),
                         cuts=[c[0] for c in CUTS]), table=out)
    json.dump(res, open(OUT, "w"))
    try:
        f.to_parquet(os.path.splitext(OUT)[0] + "_rows.parquet")
    except Exception:
        pass
    if log:
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
