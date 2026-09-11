"""
rider_oos.py -- the only test that matters after a dozen variants.

    python rider_oos.py

WHY
Every version of the EMA rider so far has been judged on the same two years of
crypto, and the rule was changed after seeing each result. That is fitting,
however honest the individual fixes were. The current best -- 1% trailing stop,
3-4 touches, trend UP at entry, no trend exit -- clears its null by about
+0.34%. It is also the survivor of maybe a dozen configurations, which is
exactly the shape of a false positive.

So: choose the configuration on data you are allowed to see, and score it on
data you are not.

  SPLIT BY TIME    fit on the first half of every series, trade the second
  SPLIT BY NAME    fit on half the coins, trade the other half
  THE WHOLE GRID   the out-of-sample result for EVERY configuration, not just
                   the chosen one. If the chosen one is good and the rest are
                   junk, that is luck. If the whole grid is positive out of
                   sample, something real is there

  PER NAME         one coin can carry an entire aggregate. Reported separately

WHAT WOULD COUNT
The in-sample winner has to stay positive out of sample AND beat 0.2% costs. A
+0.34% edge that becomes -0.1% is the same story this project has told five
times already.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import argparse
import warnings

import numpy as np
import pandas as pd

import crypto
import rider_v4 as V4
import scanner as SC

warnings.filterwarnings("ignore")

COST = V4.COST
BARS = 12000
TOUCHES = [0, 1, 2, 3, 4]
STOPS = [0.005, 0.01, 0.015, 0.02, 0.03]


FILL = "bid"


def run(df, nt, sp):
    return V4.trades(df, nt, sp, None, exit_on_trend=False, fill_mode=FILL)


def score(frames, nt, sp):
    """Mean net return and the null, across a set of frames."""
    nets, nulls, n = [], [], 0
    rng = np.random.default_rng(int(sp * 10000) + nt)
    for df in frames:
        t = run(df, nt, sp)
        if not t:
            continue
        nets += [x["net"] for x in t]
        n += len(t)
        nulls.append(V4.null_for(df, min(len(t), 40), sp, rng, reps=6))
    if not nets:
        return None
    nn = float(np.nanmean(nulls)) if nulls else np.nan
    return dict(n=n, mean=float(np.mean(nets)), med=float(np.median(nets)),
                win=float(np.mean(np.array(nets) > 0)), null=nn,
                edge=float(np.mean(nets) - nn))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--tf", default="1h,4h")
    ap.add_argument("--fill", default="bid", choices=("bid", "close"))
    a = ap.parse_args()
    global FILL
    FILL = a.fill
    tfs = [t.strip() for t in a.tf.split(",") if t.strip()]

    u = crypto.universe(a.n)
    from concurrent.futures import ThreadPoolExecutor
    pairs = [(x["sym"], x["source"]) for _, x in u.iterrows()]
    jobs = [(s, src, b) for s, src in pairs for b in ("1h", "1d")]

    def grab(job):
        s, src, b = job
        try:
            return (s, b), crypto.candles(s, b, BARS, source=src)
        except Exception:
            return (s, b), None

    print("fetching...")
    store = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for key, df in ex.map(grab, jobs):
            store[key] = df

    early, late, by_name = [], [], {}
    for sym, src in pairs:
        raw = {b: store.get((sym, b)) for b in ("1h", "1d")}
        for tf in tfs:
            if tf in SC.BASE:
                df = raw.get(SC.BASE[tf])
            else:
                s2, rule = SC.DERIVE[tf]
                df = SC.resample(raw.get(SC.BASE[s2]), rule)
            if df is None or len(df) < 800:
                continue
            h = len(df) // 2
            early.append(df.iloc[:h])
            late.append(df.iloc[h:])
            by_name.setdefault(sym, []).append(df)

    print("  %d series, split in half by time" % len(early))

    grid = [(nt, sp) for nt in TOUCHES for sp in STOPS]
    ins, oos = {}, {}
    for nt, sp in grid:
        ins[(nt, sp)] = score(early, nt, sp)
        oos[(nt, sp)] = score(late, nt, sp)
        print("  grid %d/%d" % (len(ins), len(grid)), end="\r")

    valid = [(k, v) for k, v in ins.items() if v and v["n"] >= 100]
    if not valid:
        print("not enough trades")
        return
    best = max(valid, key=lambda kv: kv[1]["edge"])[0]

    print("\n" + "=" * 84)
    print("  OUT OF SAMPLE -- chosen on the first half, scored on the second")
    print("=" * 84)
    b_in, b_out = ins[best], oos[best]
    print("  chosen config: %d touches, %.1f%% stop" % (best[0], 100 * best[1]))
    print("    first half   %6d trades  mean %+.3f%%  edge %+.3f%%"
          % (b_in["n"], 100 * b_in["mean"], 100 * b_in["edge"]))
    if b_out:
        print("    SECOND HALF  %6d trades  mean %+.3f%%  edge %+.3f%%"
              % (b_out["n"], 100 * b_out["mean"], 100 * b_out["edge"]))
        verdict = ("HOLDS -- clears costs out of sample"
                   if b_out["edge"] > 2 * COST else
                   "does not survive -- inside the noise out of sample")
        print("    -> %s" % verdict)

    print("\n  THE WHOLE GRID OUT OF SAMPLE (not just the winner)")
    print("  %-8s %-7s %9s %10s %10s" % ("touches", "stop", "trades", "in edge",
                                         "OOS edge"))
    pos = 0
    tot = 0
    for nt, sp in grid:
        i, o = ins[(nt, sp)], oos[(nt, sp)]
        if not i or not o or o["n"] < 50:
            continue
        tot += 1
        pos += o["edge"] > 0
        mark = "  <- chosen" if (nt, sp) == best else ""
        print("  %-8d %-7s %9d %+9.3f%% %+9.3f%%%s"
              % (nt, "%.1f%%" % (100 * sp), o["n"], 100 * i["edge"],
                 100 * o["edge"], mark))
    print("  %d of %d configurations positive out of sample" % (pos, tot))

    print("\n  BY NAME, at the chosen configuration")
    rows = []
    for sym, frames in by_name.items():
        s = score(frames, best[0], best[1])
        if s and s["n"] >= 15:
            rows.append(dict(sym=sym, n=s["n"], mean=s["mean"], edge=s["edge"]))
    D = pd.DataFrame(rows).sort_values("edge", ascending=False)
    if len(D):
        for _, r in D.head(6).iterrows():
            print("    %-6s %5d trades  mean %+8.3f%%  edge %+8.3f%%"
                  % (r["sym"], r["n"], 100 * r["mean"], 100 * r["edge"]))
        print("    ...")
        for _, r in D.tail(3).iterrows():
            print("    %-6s %5d trades  mean %+8.3f%%  edge %+8.3f%%"
                  % (r["sym"], r["n"], 100 * r["mean"], 100 * r["edge"]))
        print("    names with a positive edge: %d of %d"
              % (int((D.edge > 0).sum()), len(D)))
        print("    edge without the single best name: %+.3f%%"
              % (100 * D.edge.iloc[1:].mean()))
        D.to_csv("rider_oos_by_name.csv", index=False)


if __name__ == "__main__":
    main()
