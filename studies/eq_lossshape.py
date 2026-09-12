"""eq_lossshape.py -- why are the losers so big? (2026-09-11, his question)

Takes the plan that won 59% of its trades (hourly-sized stop, half at 1x the risk, sell the rest at the hourly's last
swing high) on EQs lined up with the hourly, and prints the SHAPE of the trade rather than the average:

    how far the stop sits from the entry, in percent
    how far the target sits, in percent, and the reward-to-risk that implies
    the average win, the average loss, and how the losses end (stopped out, time ran out, gapped past the stop)

Focus list only: enough trades to see the shape without a 17-minute run.

    python studies/eq_lossshape.py --procs 20
Writes validation/eq_lossshape.json
"""
import concurrent.futures as cf
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as B      # noqa: E402
import panel as P                 # noqa: E402
import eq_coil as EC              # noqa: E402
import eq_freeride as FR          # noqa: E402
import eq_freeride2 as FR2        # noqa: E402
import eq_direction as ED         # noqa: E402
import eq_fastread as EF          # noqa: E402
import eq_riders as ER            # noqa: E402
import eq_managed as MG           # noqa: E402

OUT = os.path.join("validation", "eq_lossshape.json")
TFS = ["5m", "15m"]


def _work(args):
    sym, kind = args
    try:
        frames = B.frames_for(sym, kind)
    except Exception as ex:
        return [], ["%s %s: %s" % (kind, sym, ex)]
    if kind in ("stock", "etf"):
        frames = FR2.regular_hours(frames)
    rows, errs = [], []
    for tf in TFS:
        df = frames.get(tf)
        hdf = frames.get("1h")
        if df is None or len(df) < 300 or hdf is None or len(hdf) < 60:
            continue
        try:
            o = df["Open"].values.astype(float); c = df["Close"].values.astype(float)
            h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
            n = len(c)
            recs = EC.coils(df, min_gap=3)[3]
            h1lo, h1hi = ED.last_swings(df, tf, frames, "1h")
            al = FR.align(df, tf, hdf, "1h", P._atr(hdf).astype(object))
            h1atr = np.array([np.nan if isinstance(x, str) else float(x) for x in al], dtype=float)
            state = EF.higher_state(df, tf, frames, "1h")
            ev = ER.above12(df, tf, frames, "1h")[1]
            for r in recs:
                if not r["tradeable"] or r["born"] < 60 or r["confirm"] + 2 >= n:
                    continue
                e = r["confirm"] + 1
                up = str(state[e]) == "up" or (np.isfinite(ev[e]) and c[e] > ev[e])
                down = str(state[e]) == "down" or (np.isfinite(ev[e]) and c[e] < ev[e])
                if up == down:
                    continue
                side = 1 if up else -1
                lows_ = [p for j_, p, kd_, lb_ in r["shape"] if kd_ == "low"]
                highs_ = [p for j_, p, kd_, lb_ in r["shape"] if kd_ == "high"]
                ha = h1atr[e]
                if not (np.isfinite(ha) and ha > 0):
                    continue
                line = lows_[-1] if side > 0 else highs_[-1]
                sw_near = h1lo[e] if side > 0 else h1hi[e]
                lined = (np.isfinite(ev[e]) and abs(line - ev[e]) <= 0.5 * ha) or \
                        (np.isfinite(sw_near) and ((side > 0 and sw_near < line <= sw_near + ha) or
                                                   (side < 0 and sw_near - ha <= line < sw_near)))
                if not lined:
                    continue
                t = MG.one_trade("h1", "1r", "h1", tf, kind, df, r, side, h1lo, h1hi, h1atr)
                if t is None or t["pct"] is None:
                    continue
                entry = o[e]
                hl = h1lo[e] if side > 0 else h1hi[e]
                if not np.isfinite(hl):
                    continue
                stop = hl - 0.15 * ha if side > 0 else hl + 0.15 * ha
                risk = abs(entry - stop)
                sw = h1hi[e] if side > 0 else h1lo[e]
                target = sw if (np.isfinite(sw) and ((side > 0 and sw > entry) or (side < 0 and sw < entry))) \
                    else entry + side * 2 * risk
                # did it blow through the stop rather than touch it?
                j_end = min(n - 1, e + 48 * MG.BPH[tf])
                past = 0.0
                for j in range(e, j_end + 1):
                    if side > 0 and l[j] <= stop:
                        past = (stop - l[j]) / risk
                        break
                    if side < 0 and h[j] >= stop:
                        past = (h[j] - stop) / risk
                        break
                rows.append([1 if tf == "15m" else 0, t["pct"], risk / entry * 100,
                             abs(target - entry) / entry * 100, abs(target - entry) / risk, past, t["bars"],
                             1.0 if "stopped" in t["how"] else 0.0, 1.0 if "time" in t["how"] else 0.0])
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    return rows, errs


def main():
    procs = 20
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
    t0 = time.time()
    import focus
    names = [(s_, k_) for s_, k_ in focus.names() if focus.have(s_, k_)]
    rows, errs = [], []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got, err in ex.map(_work, names, chunksize=1):
            rows += got
            errs += err
    f = np.asarray(rows, dtype=float)
    pct, risk, tgt, rr, past, bars, stopped, timed = (f[:, k] for k in range(1, 9))
    wins, losses = pct[pct > 0], pct[pct <= 0]
    res = dict(n=int(len(f)), avg=float(pct.mean()), middle=float(np.median(pct)), won=float((pct > 0).mean()),
               avg_win=float(wins.mean()), avg_loss=float(losses.mean()),
               biggest_loss=float(pct.min()), worst_20=float(np.percentile(pct, 5)),
               stop_away_pct=float(np.median(risk)), target_away_pct=float(np.median(tgt)),
               reward_to_risk=float(np.median(rr)), share_rr_under_1=float((rr < 1).mean()),
               share_stopped=float(stopped.mean()), share_time_ran_out=float(timed.mean()),
               past_the_stop_median=float(np.median(past[past > 0])) if (past > 0).any() else None,
               past_the_stop_worst=float(np.percentile(past[past > 0], 95)) if (past > 0).any() else None,
               loss_from_stops=float(np.mean(pct[(pct <= 0) & (stopped > 0)])) if ((pct <= 0) & (stopped > 0)).any() else None,
               loss_from_time=float(np.mean(pct[(pct <= 0) & (timed > 0)])) if ((pct <= 0) & (timed > 0)).any() else None,
               share_of_losses_from_time=float(np.mean(timed[pct <= 0])))
    json.dump(res, open(OUT, "w"), indent=1)
    print("\n  WHY THE LOSERS ARE BIG  (focus list, %d trades, %.0fs)\n" % (len(f), time.time() - t0))
    for k, v in res.items():
        if k == "n":
            continue
        print("    %-28s %s" % (k, "-" if v is None else ("%+.3f" % v if abs(v) < 10 else "%+.1f" % v)))
    for e in errs[:8]:
        print("  " + e)


if __name__ == "__main__":
    main()
