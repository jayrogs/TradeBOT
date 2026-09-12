"""tcg_lab.py -- the Chart Guys method broken into switches, measured one at a time (2026-09-11).

His ask: "can you distill junglefunks and the chartguys methodology, and we try to methodologically apply those to see
what helps, because if it counts for eqs it counts for anything really".

So this is not another EQ study. It writes down EVERY entry from their five triggers, stamps each one with the
conditions their method talks about, and runs three of their managements. The analysis then asks one question per
rule: WITH it versus WITHOUT it, everything else the same.

TRIGGERS (the "when", on the small chart)
    eq_break        a small EQ breaks our way
    eq_hl           a higher low confirms inside a live small EQ
    hl              a plain higher low confirms (the trend ride's timing)
    backburner      RSI 14 goes to 30 or under, then back over it
    regain12        price closes back over the small 12 EMA after being under it
CONDITIONS (the "where", stamped at entry, never used to filter the rows)
    big_trend       the idea chart (1h for 5m, 4h for 15m) is in a trend our way
    big_side12      price is on our side of the idea chart's 12 EMA
    at_12           the entry sits AT that 12 EMA (within half a normal idea bar)  -- their "location"
    at_level        the entry sits at the idea chart's last swing low (for longs)   -- previous support
    big_os          the idea chart is oversold (RSI 35 or under) for longs, overbought (65+) for shorts
    stack           how many of the three charts above have price on the right side of their 12 EMA (0-3)
    strong          the name over its benchmark (SPY / BTC / ES) is above that ratio's 12 EMA on the daily
    in_eq           a small EQ was live at the entry
    mover           the name's normal bar is wide for its price (its own history, top half)
MANAGEMENT (the "how")
    out2r           all out at twice the risk
    walk            half at 1x the risk, rest with the stop walked under each new idea-chart higher low
    ema_runner      half at the overhead idea 12 EMA (or 1x the risk, whichever is further), rest until an idea bar
                    closes through the small chart's 12 EMA
Stop for all three: the NEAREST structure that kills the idea (small EQ floor, small higher low, idea higher low),
floored at a quarter of a normal small bar. Costs 0.2% round trip on crypto, 0.05% elsewhere.

    pythonw studies/tcg_lab.py --procs 20 --log logs/tcg_lab.log        (focus list; --all for all 809 names)
Writes validation/tcg_lab.json
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
import panel as P                 # noqa: E402
import structure as ST            # noqa: E402
import trend_ride as R            # noqa: E402
import indicators as IND          # noqa: E402
import exit_managers as XM        # noqa: E402
import eq_coil as EC              # noqa: E402
import eq_freeride as FR          # noqa: E402
import eq_freeride2 as FR2        # noqa: E402

OUT = os.path.join("validation", "tcg_lab.json")
PAIRS = [("5m", "1h", ["15m", "1h", "4h"]), ("15m", "4h", ["1h", "4h", "1d"])]
TRIGGERS = ["eq_break", "eq_hl", "hl", "backburner", "regain12"]
MANAGERS = ["out2r", "walk", "ema_runner"]
CONDS = ["big_trend", "big_side12", "at_12", "at_level", "big_os", "stack2", "strong", "in_eq", "mover"]
COST = {"crypto": 0.20, "stock": 0.05, "etf": 0.05, "futures": 0.05}
MAX_BARS = 480                    # give up after this many small bars
BENCH = {"stock": ("SPY", "etf"), "etf": ("SPY", "etf"), "crypto": ("BTC", "crypto"), "futures": ("ES_F", "futures")}
ERAS = ["before", "first", "second"]
COLS = ["tf", "trig", "side", "era"] + CONDS + MANAGERS


def align_to(small, tf, frames, htf, arr):
    """A bigger chart's series, read on the small chart's clock, with no look-ahead."""
    hdf = frames.get(htf)
    if hdf is None or len(hdf) < 60:
        return np.full(len(small), np.nan)
    al = FR.align(small, tf, hdf, htf, np.asarray(arr, dtype=object))
    return np.array([np.nan if isinstance(x, str) else float(x) for x in al], dtype=float)


def run_trade(kind, o, h, l, c, e, side, stop, risk, big12, big_hl, small12, big_rsi, mode):
    """One trade, array math, no bar-by-bar loop."""
    n = len(c)
    last = min(n - 1, e + MAX_BARS)
    lw, hw, cw = l[e:last + 1], h[e:last + 1], c[e:last + 1]
    entry = o[e]

    def first(mask):
        return int(np.argmax(mask)) if mask.any() else None
    hit_stop = first(lw <= stop) if side > 0 else first(hw >= stop)
    if mode == "out2r":
        tgt = entry + side * 2 * risk
        hit_t = first(hw >= tgt) if side > 0 else first(lw <= tgt)
        s_ = hit_stop if hit_stop is not None else 10 ** 9
        t_ = hit_t if hit_t is not None else 10 ** 9
        if s_ <= t_ and hit_stop is not None:
            return side * (stop - entry) / entry * 100 - COST.get(kind, 0.05)
        if hit_t is not None:
            return side * (tgt - entry) / entry * 100 - COST.get(kind, 0.05)
        return side * (cw[-1] - entry) / entry * 100 - COST.get(kind, 0.05)
    # both managed modes take half off first
    if mode == "walk":
        cut = entry + side * risk
    else:
        ov = big12[e]
        far = entry + side * risk
        cut = ov if (np.isfinite(ov) and ((side > 0 and ov > far) or (side < 0 and ov < far))) else far
    hit_cut = first(hw >= cut) if side > 0 else first(lw <= cut)
    s_ = hit_stop if hit_stop is not None else 10 ** 9
    c_ = hit_cut if hit_cut is not None else 10 ** 9
    cost = COST.get(kind, 0.05)
    if s_ <= c_:
        return side * (stop - entry) / entry * 100 - cost
    got = 0.5 * side * (cut - entry) / entry
    j0 = e + c_
    # the rest
    if mode == "walk":                      # stop walked under each new idea-chart higher low
        stops = np.maximum.accumulate(np.where(np.isfinite(big_hl[j0:last + 1]), big_hl[j0:last + 1], -np.inf)) \
            if side > 0 else -np.minimum.accumulate(-np.where(np.isfinite(big_hl[j0:last + 1]), big_hl[j0:last + 1], np.inf))
        line = np.maximum(stops, stop) if side > 0 else np.minimum(stops, stop)
        out = first(l[j0:last + 1] <= line) if side > 0 else first(h[j0:last + 1] >= line)
        px = line[out] if out is not None else c[last]
    else:                                   # held until a bar closes through the small chart's 12 EMA
        ev = small12[j0:last + 1]
        bad = (c[j0:last + 1] < ev) if side > 0 else (c[j0:last + 1] > ev)
        stopped = (l[j0:last + 1] <= stop) if side > 0 else (h[j0:last + 1] >= stop)
        out = first(bad | stopped)
        px = (stop if (out is not None and stopped[out]) else (c[j0 + out] if out is not None else c[last]))
    got += 0.5 * side * (px - entry) / entry
    return got * 100 - cost * 1.5


def _work(args):
    sym, kind, start, bench = args
    try:
        frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    if kind in ("stock", "etf"):
        frames = FR2.regular_hours(frames)
    mid_t = start + (pd.Timestamp.now() - start) / 2
    rows, errs = [], []
    for tf_i, (tf, big, above) in enumerate(PAIRS):
        df = frames.get(tf)
        bdf = frames.get(big)
        if df is None or bdf is None or len(df) < 500 or len(bdf) < 80:
            continue
        try:
            o = df["Open"].values.astype(float); c = df["Close"].values.astype(float)
            h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
            n = len(c)
            atr = P._atr(df)
            small12 = XM.ema(c, 12)
            rsi = IND.rsi(c, 14)
            states = ST.states(df, causal=True)
            piv = ST.pivots(df)
            # the last confirmed small pivot at every bar, worked out ONCE (2026-09-11: scanning the pivot list per
            # entry was billions of steps on a big name and the run never finished)
            last_lo = np.full(n, np.nan); last_hi = np.full(n, np.nan)
            cl_ = ch_ = np.nan; q = 0
            for k in range(n):
                while q < len(piv) and piv[q][0] <= k:
                    if piv[q][3] == "low":
                        cl_ = float(piv[q][2])
                    else:
                        ch_ = float(piv[q][2])
                    q += 1
                last_lo[k] = cl_; last_hi[k] = ch_
            floor, ceil, cid, recs, _ = EC.coils(df, min_gap=3)
            # the idea chart, read on this chart's clock
            b12 = align_to(df, tf, frames, big, XM.ema(bdf["Close"].values.astype(float), 12))
            batr = align_to(df, tf, frames, big, P._atr(bdf))
            brsi = align_to(df, tf, frames, big, IND.rsi(bdf["Close"].values.astype(float), 14))
            bst = FR.align(df, tf, bdf, big, np.asarray(ST.states(bdf, causal=True), dtype=object))
            bst = np.array([str(x) for x in bst])
            bl = np.full(len(bdf), np.nan); bh = np.full(len(bdf), np.nan)
            cl = ch = np.nan
            p_ = 0
            bp = ST.pivots(bdf)
            for k in range(len(bdf)):
                while p_ < len(bp) and bp[p_][0] <= k:
                    if bp[p_][3] == "low":
                        cl = float(bp[p_][2])
                    else:
                        ch = float(bp[p_][2])
                    p_ += 1
                bl[k] = cl; bh[k] = ch
            big_lo = align_to(df, tf, frames, big, bl)
            big_hi = align_to(df, tf, frames, big, bh)
            # the three charts above, for the 12 EMA stack
            stack_up = np.zeros(n)
            for htf in above:
                hdf = frames.get(htf)
                if hdf is None or len(hdf) < 60:
                    continue
                ev = align_to(df, tf, frames, htf, XM.ema(hdf["Close"].values.astype(float), 12))
                stack_up += np.where(np.isfinite(ev) & (c > ev), 1, 0)
            # relative strength against the benchmark, on the daily
            strong = np.full(n, np.nan)
            d1 = frames.get("1d")
            if bench is not None and d1 is not None and len(d1) > 40:
                bx = bench.reindex(d1.index).ffill()
                ratio = (d1["Close"].values.astype(float) / bx.values.astype(float))
                ok = np.isfinite(ratio)
                if ok.sum() > 40:
                    r12 = XM.ema(np.where(ok, ratio, np.nan), 12)
                    strong = align_to(df, tf, frames, "1d", np.where(ratio > r12, 1.0, 0.0))
            mover = 1.0 if np.nanmedian(atr / c) > 0.004 else 0.0
            # ---- the triggers
            events = []                                    # (bar, trigger index, side)
            live = np.zeros(n, dtype=bool)
            for r in recs:
                if not r["tradeable"]:
                    continue
                live[r["confirm"]:r["end"] + 1] = True
                k = r["end"]
                how = str(r["how"])
                sg = 1 if ("ceiling" in how or "higher high" in how) else -1 if ("floor" in how or "lower low" in how) else 0
                if sg and k + 1 < n and k > r["confirm"]:
                    events.append((k + 1, 0, sg))
                for j_, p_i, kd_, lb_ in r["shape"]:
                    pass
            for ci, j, price, kind_, lab in piv:
                if ci + 1 >= n:
                    continue
                if kind_ == "low" and lab in ("HL", "EL"):
                    events.append((ci + 1, 1 if live[ci] else 2, 1))
                elif kind_ == "high" and lab in ("LH", "EH"):
                    events.append((ci + 1, 1 if live[ci] else 2, -1))
            os_ = (rsi <= 30)
            back = np.where(os_[:-1] & ~os_[1:])[0] + 1
            for k in back:
                if k + 1 < n:
                    events.append((k + 1, 3, 1))
            ob = (rsi >= 70)
            for k in np.where(ob[:-1] & ~ob[1:])[0] + 1:
                if k + 1 < n:
                    events.append((k + 1, 3, -1))
            cross_up = np.where((c[:-1] <= small12[:-1]) & (c[1:] > small12[1:]))[0] + 1
            cross_dn = np.where((c[:-1] >= small12[:-1]) & (c[1:] < small12[1:]))[0] + 1
            for k in cross_up:
                if k + 1 < n:
                    events.append((k + 1, 4, 1))
            for k in cross_dn:
                if k + 1 < n:
                    events.append((k + 1, 4, -1))
            for e, trig, side in events:
                if e < 100 or e + 5 >= n or not np.isfinite(atr[e]) or atr[e] <= 0:
                    continue
                a = atr[e]
                ba = batr[e] if np.isfinite(batr[e]) else a
                entry = o[e]
                # the nearest structure that kills the idea
                cands = []
                if np.isfinite(floor[e - 1] if e else np.nan):
                    cands.append(floor[e - 1] if side > 0 else ceil[e - 1])
                near = last_lo[e - 1] if side > 0 else last_hi[e - 1]
                if np.isfinite(near):
                    cands.append(near)
                bigline = big_lo[e] if side > 0 else big_hi[e]
                if np.isfinite(bigline):
                    cands.append(bigline)
                cands = [x for x in cands if np.isfinite(x) and ((side > 0 and x < entry) or (side < 0 and x > entry))]
                if not cands:
                    continue
                stop = max(cands) if side > 0 else min(cands)
                stop = stop - 0.15 * a if side > 0 else stop + 0.15 * a
                risk = abs(entry - stop)
                if risk < 0.25 * a:
                    risk = 0.25 * a
                    stop = entry - side * risk
                t_ = df.index[e]
                era = 0 if t_ < start else 1 if t_ < mid_t else 2
                flags = [
                    1.0 if bst[e] == ("up" if side > 0 else "down") else 0.0,
                    1.0 if (np.isfinite(b12[e]) and ((side > 0 and c[e] > b12[e]) or (side < 0 and c[e] < b12[e]))) else 0.0,
                    1.0 if (np.isfinite(b12[e]) and abs(entry - b12[e]) <= 0.5 * ba) else 0.0,
                    1.0 if (np.isfinite(bigline) and abs(entry - bigline) <= 0.5 * ba) else 0.0,
                    1.0 if (np.isfinite(brsi[e]) and ((side > 0 and brsi[e] <= 35) or (side < 0 and brsi[e] >= 65))) else 0.0,
                    1.0 if (stack_up[e] >= 2 if side > 0 else stack_up[e] <= 1) else 0.0,
                    (strong[e] if side > 0 else (1.0 - strong[e])) if np.isfinite(strong[e]) else np.nan,
                    1.0 if live[e - 1] else 0.0,
                    mover]
                res = [run_trade(kind, o, h, l, c, e, side, stop, risk, b12, big_lo if side > 0 else big_hi,
                                 small12, brsi, m) for m in MANAGERS]
                rows.append([tf_i, trig, side, era] + flags + res)
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    if not rows:
        return None, errs
    return np.asarray(rows, dtype=np.float32), errs


def stats(v):
    v = v[np.isfinite(v)]
    if len(v) < 60:
        return None
    return dict(n=int(len(v)), avg=float(v.mean()), middle=float(np.median(v)), won=float((v > 0).mean()))


def main():
    procs, log, allnames = max(1, os.cpu_count() or 4), None, False
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--all":
            allnames = True
        if a == "--log" and i + 1 < len(sys.argv):
            log = sys.argv[i + 1]
            sys.stdout = sys.stderr = open(log, "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * B.YEARS)
    if allnames:
        names = R._by_size([(s_, k_) for s_, k_ in B.universe() if k_ != "forex"])
    else:
        import focus
        names = [(s_, k_) for s_, k_ in focus.names() if focus.have(s_, k_)]
    benches = {}
    for kd, (bs, bk) in BENCH.items():
        try:
            benches[kd] = B.frames_for(bs, bk)["1d"]["Close"]
        except Exception:
            benches[kd] = None
    R.quiet_workers()
    jobs = [(s_, k_, start, benches.get(k_)) for s_, k_ in names]
    parts, errs, done = [], [], 0
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for part, err in ex.map(_work, jobs, chunksize=1):
            done += 1
            errs += err or []
            if part is not None:
                parts.append(part)
            if done % 25 == 0 or done == len(jobs):
                print("  %d/%d names  (%.0fs)" % (done, len(jobs), time.time() - t0), flush=True)
    f = pd.DataFrame(np.concatenate(parts), columns=COLS)
    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(jobs),
                         rows=int(len(f)), triggers=TRIGGERS, managers=MANAGERS, conditions=CONDS,
                         all_names=allnames, seconds=int(time.time() - t0)), table={})
    print("\n  THE CHART GUYS METHOD, RULE BY RULE  (%d names, %d entries, %.0fs)" % (len(jobs), len(f), time.time() - t0))
    for m in MANAGERS:
        out["table"][m] = {}
        print("\n  managed: %s" % m)
        print("    %-26s %8s %8s %6s   %8s %8s %6s   what the rule adds" % (
            "rule", "n with", "avg with", "won", "n without", "avg without", "won"))
        for trig_i, trig in enumerate(TRIGGERS):
            g = f[f.trig == trig_i]
            s_all = stats(g[m].values)
            if not s_all:
                continue
            out["table"][m][trig] = dict(all=s_all, rules={})
            print("    %-26s %8d %+7.3f%% %5.0f%%" % ("[" + trig + "] every entry", s_all["n"], s_all["avg"],
                                                      100 * s_all["won"]))
            for cond in CONDS:
                with_ = stats(g[g[cond] > 0][m].values)
                without = stats(g[g[cond] == 0][m].values)
                if not with_ or not without:
                    continue
                out["table"][m][trig]["rules"][cond] = dict(with_rule=with_, without=without,
                                                            adds=with_["avg"] - without["avg"])
                print("      %-24s %8d %+7.3f%% %5.0f%%   %8d %+7.3f%% %5.0f%%   %+7.3f%%" % (
                    cond, with_["n"], with_["avg"], 100 * with_["won"],
                    without["n"], without["avg"], 100 * without["won"], with_["avg"] - without["avg"]))
    json.dump(out, open(OUT, "w"))
    for e_ in errs[:15]:
        print("  ERR " + e_)
    if log:
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
