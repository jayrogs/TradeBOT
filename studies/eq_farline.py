"""eq_farline.py -- skip the EQ trade when the far line is too close (2026-09-10).

From his grading: "wtf 91% sold? ... the wins are meaningless if you only have 9% position size" (TSM 15m,
far line 0.09x the risk). eq_freeride2 showed the partial trades earn about nothing when the far line is under
1x the risk, and are positive on both the average and the middle trade at 1-2x and 2x+ on the 1h and 4h.
This tests that as a FILTER: take the trade only when the far line is at least N times the risk away,
N = 0 (every trade), 0.5, 1, 1.5, 2, in all three eras, against the chart's own drift.
Same trade as eq_freeride2 (daily 50 EMA direction, buy the next open after the higher low confirms inside the
EQ, stop a wick through it). All hours, every market.

    pythonw studies/eq_farline.py --procs 20 --log logs/eq_farline.log
Writes validation/eq_farline.json
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

OUT = os.path.join("validation", "eq_farline.json")
TFS = FR2.TFS
GAPS = [0, 3]
VARIANTS = [FR2.MODES[1][0], FR2.MODES[2][0], FR2.MODES[0][0]]    # half, all out, a third
MINS = [0.0, 0.5, 1.0, 1.5, 2.0]
ERAS = FR2.ERAS
KINDS = FR2.KINDS


def _work(args):
    sym, kind, start = args
    try:
        frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    cols = {k: [] for k in ("gap", "var", "tf", "kind", "era", "rr", "ret", "drift", "took", "held")}
    errs = []
    for g_i, gap in enumerate(GAPS):
        for tf in TFS:
            try:
                for x in FR2.trades(kind, tf, frames.get(tf), frames, start, gap, modes=VARIANTS):
                    if x["tag1"] != 0:                 # only trades WITH the daily 50 EMA
                        continue
                    cols["gap"].append(g_i); cols["var"].append(VARIANTS.index(x["variant"]))
                    cols["tf"].append(x["tf_i"]); cols["kind"].append(x["kind_i"]); cols["era"].append(x["era_i"])
                    cols["rr"].append(x["rr"]); cols["ret"].append(x["ret"]); cols["drift"].append(x["drift"])
                    cols["took"].append(1 if x["took"] else 0); cols["held"].append(x["held"])
            except Exception as ex:
                errs.append("%s %s %s gap%d: %s" % (kind, sym, tf, gap, ex))
    if not cols["ret"]:
        return None, errs
    return {k: np.asarray(v, dtype=np.float32 if k in ("rr", "ret", "drift") else np.int32) for k, v in cols.items()}, errs


def main():
    procs, log = max(1, os.cpu_count() or 4), None
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
    f = pd.DataFrame({k: np.concatenate([p[k] for p in parts]) for k in parts[0]})
    f["ret"] = f["ret"].astype(float); f["drift"] = f["drift"].astype(float)

    def st(g):
        if len(g) < 20:
            return None
        return dict(n=int(len(g)), mean=float(g.ret.mean()), median=float(g.ret.median()),
                    edge=float((g.ret - g.drift).mean()), won=float((g.ret > 0).mean()),
                    reached=float(g.took.mean()), held=float(g.held.mean()))

    out = {}
    for g_i, gap in enumerate(GAPS):
        for v_i, v in enumerate(VARIANTS):
            for t_i, tf in enumerate(TFS):
                sub = f[(f.gap == g_i) & (f["var"] == v_i) & (f.tf == t_i)]
                for m in MINS:
                    s2 = sub[sub.rr >= m]
                    key = "%d | %s | %s | %.1f" % (gap, v, tf, m)
                    out[key + " | all"] = st(s2)
                    for e_i, era in enumerate(ERAS):
                        out[key + " | " + era] = st(s2[s2.era == e_i])
                    for k_i, kd in enumerate(KINDS):
                        out[key + " | " + kd] = st(s2[s2.kind == k_i])
    out = {k: v for k, v in out.items() if v}
    res = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names), tfs=TFS,
                         gaps=[str(g) for g in GAPS], variants=VARIANTS, mins=MINS, eras=ERAS, kinds=KINDS,
                         rows=int(len(f)), seconds=int(time.time() - t0)), table=out)
    json.dump(res, open(OUT, "w"))
    print("\n  FAR LINE FILTER  %d names, %d trades with the daily 50 EMA  (%.0fs)" % (len(names), len(f), time.time() - t0))
    print("  average / middle / edge over drift  n   then the three eras (average / middle)")
    for gap in GAPS:
        for v in VARIANTS:
            print("  pivots %d+ apart | %s" % (gap, v))
            for tf in ("1h", "4h", "1d"):
                for m in MINS:
                    a = out.get("%d | %s | %s | %.1f | all" % (gap, v, tf, m))
                    if not a:
                        continue
                    eras = "  ".join("%+.2f/%+.2f" % (100 * e["mean"], 100 * e["median"]) if e else "   -   "
                                     for e in (out.get("%d | %s | %s | %.1f | %s" % (gap, v, tf, m, er)) for er in ERAS))
                    print("    %-3s far line >= %.1fx  %+6.2f / %+6.2f / %+6.2f  n%-6d  eras %s" % (
                        tf, m, 100 * a["mean"], 100 * a["median"], 100 * a["edge"], a["n"], eras))
    if log:
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
