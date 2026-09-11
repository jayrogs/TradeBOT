"""eq_direction.py -- which reads call a 5m / 15m / 1h EQ's direction, scored on the first poke AND the follow-through
(2026-09-11). His words: "why not both? and we can compare to see which were fakeouts".

Fixes the weak points of eq_fastread.py:
  1. FIRST POKE ONLY  -> every break is scored two ways:
       the poke     which line the first wick went through (up = ceiling, down = floor)
       what next    real      ran 2+ normal bars past the line before a close back inside (or never came back)
                    fakeout   a close back inside within 5 bars, without running even 1 normal bar
                    reversal  the OTHER line broke within 20 bars
                    weak      none of those
                    and where price is 20 bars after the break, measured from the EQ's middle, in normal bars
  2. THE 12 EMA'S FREE PASS -> every read is taken at TWO moments: the bar the EQ becomes knowable, and the last bar
     before the break. "Which pivot confirmed last" is its own read so the bounce effect is visible. The 12 EMA's slope
     across the whole EQ (first pivot to the moment) is added next to price-vs-12-EMA (which sits mid-EQ, his point).
  3. THE EQ READ'S LOOK-AHEAD -> touches are counted against the lines AS THEY STOOD at that moment.
  4. DIRECTION VS TRADE -> this study scores direction only. Trades come after, with the reads that hold.
Reads: the daily 50 EMA; this chart's price vs 12 EMA; this chart's 12 EMA slope across the EQ; the next chart up's
12 EMA; the next chart up's pivot trend; the next chart up's swing shape (last high and last low); which EQ line is
pressed against a bigger chart's 12 EMA; the EQ's own read (line tested more holds + against the move it came from);
the last pivot. Control: every EQ called "up". Three eras. EQ pivots 3+ bars apart (his rule); stocks on regular hours.

    pythonw studies/eq_direction.py --procs 20 --log logs/eq_direction.log
Writes validation/eq_direction.json
"""
import bisect
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
import panel as P                 # noqa: E402
import structure as ST            # noqa: E402
import trend_ride as R            # noqa: E402
import exit_managers as XM        # noqa: E402
import eq_coil as EC              # noqa: E402
import eq_freeride as FR          # noqa: E402
import eq_freeride2 as FR2        # noqa: E402
import eq_fastread as EF          # noqa: E402
import eq_riders as ER            # noqa: E402

OUT = os.path.join("validation", "eq_direction.json")
TFS = ["5m", "15m", "1h"]
ABOVE = {"5m": ["15m", "1h", "4h"], "15m": ["1h", "4h", "1d"], "1h": ["4h", "1d"]}
N_AFTER = 20
FAKE_BARS = 5
REAL_RUN = 2.0
NEAR = 0.5
TOUCH = 0.25
MOMENTS = ["when the EQ became knowable", "last bar before the break"]
READS = [("control", "every EQ called up (the control)"),
         ("daily50", "the daily 50 EMA"),
         ("price_vs_12", "this chart: price over a rising / under a falling 12 EMA"),
         ("slope12_eq", "this chart: the 12 EMA's slope across the EQ"),
         ("next12", "next chart up: price over a rising / under a falling 12 EMA"),
         ("next_trend", "next chart up: uptrend / downtrend (pivots)"),
         ("next_swings", "next chart up: last high and last low both higher / both lower"),
         ("pressed_line", "the EQ line pressed against a bigger chart's 12 EMA (ceiling -> up, floor -> down)"),
         ("eq_read", "the EQ's own read: line tested more holds + against the move it came from"),
         ("eq_lean", "the EQ's own read, either half"),
         ("last_pivot", "the last pivot: a higher low -> up, a lower high -> down")]
READ_KEYS = [k for k, _ in READS]
OUTCOMES = ["real", "fakeout", "reversal", "weak"]
ERAS = ["before", "first", "second"]


def code(v):
    v = str(v)
    return 1 if v in ("up", "UP") else 2 if v in ("down", "DOWN") else 0


def outcome(sgn, k, line, other, h, l, c, a, n):
    run_before_back = 0.0
    back = None
    for j in range(k, min(n, k + N_AFTER + 1)):
        if sgn > 0 and l[j] < other or sgn < 0 and h[j] > other:
            return 2, run_before_back                    # the other line broke: a reversal
        fav = ((h[j] - line) if sgn > 0 else (line - l[j])) / a
        if back is None:
            run_before_back = max(run_before_back, fav)
            if j > k and ((sgn > 0 and c[j] < line) or (sgn < 0 and c[j] > line)):
                back = j
    if run_before_back >= REAL_RUN:
        return 0, run_before_back
    if back is not None and back - k <= FAKE_BARS and run_before_back < 1.0:
        return 1, run_before_back
    return 3, run_before_back


def _work(args):
    sym, kind, start = args
    try:
        all_frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    frames = FR2.regular_hours(all_frames) if kind in ("stock", "etf") else all_frames
    mid_t = start + (pd.Timestamp.now() - start) / 2
    rows = []
    errs = []
    for tf_i, tf in enumerate(TFS):
        df = frames.get(tf)
        if df is None or len(df) < 300:
            continue
        try:
            c = df["Close"].values.astype(float); h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
            n = len(c)
            floor, ceil, cid, recs, atr = EC.coils(df, min_gap=3)
            if not recs:
                continue
            e12 = XM.ema(c, 12)
            e12s = e12 - np.r_[np.full(3, np.nan), e12[:-3]]
            d50 = FR.ema_of(df, tf, all_frames, "1d")
            up1 = ABOVE[tf][0]
            next12 = ER.above12(df, tf, frames, up1)[0]
            next_trend = EF.higher_state(df, tf, frames, up1)
            next_sw = FR.swings_of(df, tf, frames, up1)
            above_ev = [ER.above12(df, tf, frames, htf)[1] for htf in ABOVE[tf]]
            states = ST.states(df, causal=True)
            piv = ST.pivots(df)
            pcis = [pv[0] for pv in piv]
            for r in recs:
                if not r["tradeable"] or r["born"] < 60:
                    continue
                how = str(r["how"])
                k = r["end"]
                if "ceiling" in how or "higher high" in how:
                    sgn = 1
                elif "floor" in how or "lower low" in how:
                    sgn = -1
                else:
                    continue
                if k - 1 < r["confirm"] or k + 1 >= n:
                    continue
                kb = k - 1                                        # the last bar the EQ was alive
                fl_b, ce_b = floor[kb], ceil[kb]
                a = atr[k] if np.isfinite(atr[k]) and atr[k] > 0 else np.nan
                if not (np.isfinite(fl_b) and np.isfinite(ce_b) and np.isfinite(a)):
                    continue
                line = ce_b if sgn > 0 else fl_b
                other = fl_b if sgn > 0 else ce_b
                cls, run = outcome(sgn, k, line, other, h, l, c, a, n)
                j20 = min(n - 1, k + N_AFTER)
                move20 = (c[j20] - (fl_b + ce_b) / 2) / a            # from the EQ's middle, in normal bars (+ = up)
                t = df.index[k]
                era_i = 0 if t < start else 1 if t < mid_t else 2
                born = r["born"]
                vals = []
                for m in (r["confirm"], kb):
                    fl_m = floor[m] if np.isfinite(floor[m]) else fl_b
                    ce_m = ceil[m] if np.isfinite(ceil[m]) else ce_b
                    am = atr[m] if np.isfinite(atr[m]) and atr[m] > 0 else a
                    pre = str(states[born - 1]) if born > 0 else "FLAT"
                    t_fl = int(np.sum(l[born:m + 1] <= fl_m + TOUCH * am))
                    t_ce = int(np.sum(h[born:m + 1] >= ce_m - TOUCH * am))
                    sc = (1 if t_fl > t_ce else -1 if t_ce > t_fl else 0) + (1 if pre == "DOWN" else -1 if pre == "UP" else 0)
                    near_fl = any(np.isfinite(ev[m]) and abs(fl_m - ev[m]) <= NEAR * am for ev in above_ev)
                    near_ce = any(np.isfinite(ev[m]) and abs(ce_m - ev[m]) <= NEAR * am for ev in above_ev)
                    last = None
                    for ci_, j_, p_, kd_, lab_ in piv[bisect.bisect_left(pcis, born):bisect.bisect_right(pcis, m)]:
                        if born <= j_ and ((kd_ == "low" and lab_ in EC.UP_LAB) or (kd_ == "high" and lab_ in EC.DN_LAB)):
                            last = kd_
                    slope = e12[m] - e12[born] if np.isfinite(e12[m]) and np.isfinite(e12[born]) else np.nan
                    vals += [1,
                             code(d50[m]),
                             1 if (c[m] > e12[m] and e12s[m] > 0) else 2 if (c[m] < e12[m] and e12s[m] < 0) else 0,
                             0 if not np.isfinite(slope) else (1 if slope > 0.5 * am else 2 if slope < -0.5 * am else 0),
                             code(next12[m]), code(next_trend[m]), code(next_sw[m]),
                             1 if (near_ce and not near_fl) else 2 if (near_fl and not near_ce) else 0,
                             1 if sc >= 2 else 2 if sc <= -2 else 0,
                             1 if sc >= 1 else 2 if sc <= -1 else 0,
                             1 if last == "low" else 2 if last == "high" else 0]
                rows.append([tf_i, sgn, cls, float(run), float(move20), era_i] + vals)
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    if not rows:
        return None, errs
    return np.asarray(rows, dtype=np.float32), errs


def score(g, col):
    """For EQs where the read gave a call: how often the poke and the real break went the called way, how often the
    called way faked out or reversed, and where price sat 20 bars later, in the called direction."""
    called = g[g[col] > 0]
    if len(called) < 50:
        return None
    call = np.where(called[col] == 1, 1, -1)
    poke = called["sgn"].values == call
    cls = called["cls"].values
    move = called["move20"].values * call
    return dict(n=int(len(called)), share_called=float(len(called) / len(g)),
                poke_right=float(poke.mean()),
                real_right=float((poke & (cls == 0)).mean()),
                real_wrong=float((~poke & (cls == 0)).mean()),
                fakeout_on_call=float((poke & (cls == 1)).mean()),
                reversal_on_call=float((poke & (cls == 2)).mean()),
                fakeout_share_of_right_pokes=float((cls[poke] == 1).mean()) if poke.any() else None,
                ended_right=float((move > 0).mean()),
                avg_move=float(move.mean()),
                median_move=float(np.median(move)))


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
            if done % 50 == 0 or done == len(names):
                print("  %d/%d names  (%.0fs)" % (done, len(names), time.time() - t0), flush=True)
    for e_ in errs[:20]:
        print("  ERR " + e_)
    cols = ["tf", "sgn", "cls", "run", "move20", "era"] + ["%s|%s" % (m_i, rk) for m_i in range(2) for rk in READ_KEYS]
    f = pd.DataFrame(np.concatenate(parts), columns=cols)
    print("  %d EQ breaks, scoring  (%.0fs)" % (len(f), time.time() - t0), flush=True)
    table = {}
    for tf_i, tf in enumerate(TFS):
        g = f[f.tf == tf_i]
        base = dict(n=int(len(g)), broke_up=float((g.sgn > 0).mean()) if len(g) else None,
                    outcomes={o: float((g.cls == o_i).mean()) for o_i, o in enumerate(OUTCOMES)} if len(g) else {})
        table[tf] = dict(all=base, moments={})
        for m_i, moment in enumerate(MOMENTS):
            table[tf]["moments"][moment] = {}
            for rk in READ_KEYS:
                col = "%s|%s" % (m_i, rk)
                st = score(g, col)
                if not st:
                    continue
                st["eras"] = {ERAS[e_i]: score(g[g.era == e_i], col) for e_i in range(3)}
                table[tf]["moments"][moment][rk] = st
    res = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names), tfs=TFS,
                         moments=MOMENTS, reads=READ_KEYS, read_names=dict(READS), outcomes=OUTCOMES,
                         real_run=REAL_RUN, fake_bars=FAKE_BARS, after_bars=N_AFTER, near=NEAR, min_gap=3,
                         hours="stocks and ETFs on regular-hours bars; crypto and futures all hours",
                         rows=int(len(f)), seconds=int(time.time() - t0)),
               table=table)
    json.dump(res, open(OUT, "w"))
    print("\n  EQ DIRECTION: FIRST POKE AND FOLLOW-THROUGH  %d names  (%.0fs)" % (len(names), time.time() - t0))
    for tf in TFS:
        b = table[tf]["all"]
        print("\n  %s: %d EQ breaks, %.0f%% up | real %.0f%%  fakeout %.0f%%  reversal %.0f%%  weak %.0f%%" % (
            tf, b["n"], 100 * (b["broke_up"] or 0), *[100 * b["outcomes"].get(o, 0) for o in OUTCOMES]))
        for moment in MOMENTS:
            print("   %s" % moment)
            print("     %-14s %6s %6s %6s %6s %6s %6s %6s   eras poke/real" % (
                "read", "calls", "poke", "real", "fake", "rev", "ended", "move"))
            for rk in READ_KEYS:
                s = table[tf]["moments"][moment].get(rk)
                if not s:
                    continue
                eras = "  ".join(("%2.0f/%2.0f" % (100 * e["poke_right"], 100 * e["real_right"])) if e else " -/- "
                                 for e in (s["eras"].get(er) for er in ERAS))
                print("     %-14s %5.0f%% %5.0f%% %5.0f%% %5.0f%% %5.0f%% %5.0f%% %+5.2f   %s" % (
                    rk, 100 * s["share_called"], 100 * s["poke_right"], 100 * s["real_right"],
                    100 * s["fakeout_on_call"], 100 * s["reversal_on_call"], 100 * s["ended_right"], s["avg_move"], eras))
    if log:
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
