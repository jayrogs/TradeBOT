"""trend_trail.py -- how loose should the trailing stop be, and what does a partial really save you?

    python studies/trend_partials.py       # writes validation/trend_partials.json

The owner, 2026-09-06: "yeah always want to sell partial and let the other shit
run as long as we can". The trend ride's problem was never the entry, it was
that one stop under the last higher low sold the whole position on the first
pullback -- on average the name traded 4% higher within 60 bars of the sale
(11% on the 4h, 16% on the daily).

ENTRY, fixed at the best one from studies/trend_variants.py: a confirmed higher
low, bought at the next bar's open, SKIPPED if that open is already more than
one normal bar's move (14-bar ATR) above the pivot. Risk R = fill - pivot.

TAKE THE PARTIAL
  none                 sell nothing early (the old behaviour)
  at 1R / at 2R        a resting limit sell at fill + 1 or 2 x the risk; it
                       fills off the bar's high, so it can fill on a bar that
                       later closes red -- that is honest for a limit order
  at a new high        when a new higher high confirms, sell at the next open
  sizes: a third or a half of the position

THEN LET THE REST RUN, until
  higher low           a close under the last higher low, the line raised by
                       each new one (the old exit)
  one behind           a close under the PREVIOUS higher low, so a fresh pivot
                       cannot become the stop straight away
  clear break          one behind, and the close must be more than half a
                       normal bar's move under the line
  12 EMA               the first close under the 12 EMA by more than half a
                       normal bar's move
  higher timeframe     a close under the last higher low ON THE NEXT CHART UP
                       (15m -> 1h, 1h -> 4h, 4h -> 1d, 1d -> 1w): the slowest
                       leash, closest to "as long as we can"
  nothing              no stop at all, out at the 30-day cap: the ceiling on
                       what any trailing rule could have made

Reported per variant: money return per trade (the partial and the runner
blended, one round-trip cost), how often the partial filled, how long the
runner lived, and how much the name went on to make in the 60 bars AFTER the
final exit -- the number that says whether the leash is still too short.
"""

import bisect
import concurrent.futures as cf
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "studies"))
import backburner_study as B      # noqa: E402
import structure as ST            # noqa: E402
import rider                      # noqa: E402

CHAIN = ["15m", "1h", "4h", "1d"]
UP = {"15m": "1h", "1h": "4h", "4h": "1d", "1d": "1w"}
BARS_DAY, CLASS_COST = B.BARS_DAY, B.CLASS_COST
CAP_DAYS = 30
MAX_CHASE = 1.0
BUF = 0.5
PROCS = max(1, (os.cpu_count() or 4) - 4)      # leave a few cores for the machine
OUT = os.path.join("validation", "trend_trail.json")
BARS_DAY_TF = 24

TAKES = [("no partial", None, 0.0), ("a third at 2R", "2R", 1 / 3), ("half at 2R", "2R", 0.5)]
RUNS = ["higher low"] + ["trail %g bars under the high" % t for t in (3, 4, 5, 6, 8, 10, 14)] + ["hold 14 days"]
HOLD_DAYS = {"hold 14 days": 14}
TRAIL = {"trail %g bars under the high" % t: float(t) for t in (3, 4, 5, 6, 8, 10, 14)}


def run_exit(c, o, ema, a14, lows, lcis, highs, hcis, e, level, n, cap, mode, hi_stop):
    """Where the runner gets out, plus the worst it got underwater on the way.
    Returns (bar, price, why, worst)."""
    p = bisect.bisect_right(lcis, e - 1)
    pending = None
    fill = o[e]
    peak = c[e]
    worst = 0.0
    stop_days = HOLD_DAYS.get(mode)
    bars = int(stop_days * BARS_DAY_TF) if stop_days else cap
    trail = TRAIL.get(mode)
    for k in range(e, n - 1):
        worst = min(worst, c[k] / fill - 1)
        peak = max(peak, c[k])
        if mode in ("higher low", "clear break"):
            while p < len(lows) and lows[p][0] <= k:
                ci, j, price, lab = lows[p]; p += 1
                if j < e or price <= level:
                    continue
                if mode == "higher low":
                    level = price
                else:
                    if pending is not None and pending > level:
                        level = pending
                    pending = price
            buf = (BUF * a14[k] if mode == "clear break" and np.isfinite(a14[k]) else 0.0)
            if c[k] < level - buf:
                return k, o[k + 1], "stopped", worst
        elif trail is not None:
            if np.isfinite(a14[k]) and c[k] < peak - trail * a14[k]:
                return k, o[k + 1], "trail hit", worst
        if k - e >= bars:
            return k, o[k + 1], "time", worst
    return None


def hi_stop_series(df, hdf, n):
    """For each bar of this chart, the last confirmed higher low on the chart
    above it (nan until one exists). Causal: a pivot only counts from its
    confirm bar's timestamp on."""
    out = np.full(n, np.nan)
    if hdf is None or len(hdf) < 40:
        return out
    piv = [(ci, p) for ci, j, p, k_, lab in ST.pivots(hdf) if k_ == "low"]
    if not piv:
        return out
    times = [hdf.index[ci] for ci, _ in piv]
    pos = df.index.searchsorted(times, side="right")      # first bar that knows
    level = np.nan
    j = 0
    for i in range(n):
        while j < len(pos) and pos[j] <= i:
            price = piv[j][1]
            if not np.isfinite(level) or price > level:
                level = price
            j += 1
        out[i] = level
    return out


def study_frame(sym, kind, tf, frames, start):
    df = frames[tf]
    if len(df) < 300:
        return []
    c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    global BARS_DAY_TF
    BARS_DAY_TF = BARS_DAY[tf]
    cap = CAP_DAYS * BARS_DAY[tf]
    cost = CLASS_COST.get(kind, B.COST)
    a14 = B.atr(h, l, c)
    ema = rider.ema(c)
    piv = ST.pivots(df)
    lows = [(ci, j, p, lab) for ci, j, p, k_, lab in piv if k_ == "low"]
    highs = [(ci, j, p, lab) for ci, j, p, k_, lab in piv if k_ == "high"]
    lcis = [x[0] for x in lows]; hcis = [x[0] for x in highs]
    hi = hi_stop_series(df, frames.get(UP.get(tf)), n)
    lr = np.diff(np.log(c), prepend=np.log(c[0]))
    drift = float(np.nanmean(lr[np.isfinite(lr)]))
    mid = start + (pd.Timestamp.now() - start) / 2
    rows = []
    for ci, j, price, lab in lows:
        if lab != "HL" or ci < 30 or ci + 2 >= n - 1:
            continue
        e = ci + 1
        atr = a14[ci] if np.isfinite(a14[ci]) and a14[ci] > 0 else np.nan
        if not np.isfinite(atr) or (o[e] - price) / atr > MAX_CHASE:
            continue                                   # don't chase
        fill = o[e]
        R = fill - price
        if R <= 0:
            continue
        t = df.index[e]
        era = "before" if t < start else "first" if t < mid else "second"
        # where each runner rule would get out (computed once, shared by the takes)
        outs = {}
        for mode in RUNS:
            outs[mode] = run_exit(c, o, ema, a14, lows, lcis, highs, hcis, e, price, n, cap, mode, hi)
        for take_label, trig, size in TAKES:
            # when the partial fills, and at what price
            if trig is None:
                pbar, ppx = None, None
            elif trig in ("1R", "2R"):
                tgt = fill + (1 if trig == "1R" else 2) * R
                pbar = next((k for k in range(e, n - 1) if h[k] >= tgt), None)
                ppx = tgt
            else:
                hh = next(((ci2, j2) for ci2, j2, p2, lab2 in highs if j2 >= e and lab2 == "HH"), None)
                pbar = hh[0] if hh else None
                ppx = o[pbar + 1] if pbar is not None and pbar + 1 < n else None
            for mode in RUNS:
                res = outs[mode]
                if res is None:
                    continue
                xb, xpx, why, worst_price = res
                took = pbar is not None and ppx is not None and pbar <= xb
                sz = size if took else 0.0
                part_ret = (ppx / fill - 1) if took else 0.0
                ret = (sz * part_ret + (1 - sz) * (xpx / fill - 1)) - cost
                if took and sz > 0:
                    pre = float(np.min(c[e:pbar + 1])) / fill - 1 if pbar >= e else 0.0
                    post = float(np.min(c[pbar + 1:xb + 1])) / fill - 1 if xb > pbar else part_ret
                    worst = min(min(pre, 0.0), sz * part_ret + (1 - sz) * post)
                else:
                    worst = worst_price
                after = min(n - 1, xb + 60)
                rows.append(dict(sym=sym, kind=kind, tf=tf, t=str(t), era=era, null=0,
                                 variant="%s, then run to %s" % (take_label, mode),
                                 take=take_label, run=mode, ret=float(ret), took=bool(took),
                                 held=int(xb + 1 - e), why=why, worst=float(worst),
                                 best_after=float(np.max(c[xb:after + 1]) / fill - 1),
                                 drift=float(np.exp(drift * (xb + 1 - e)) - 1 - cost)))
    return rows


# ------------------------------------------------------------------ counting

KEYS = ["variant", "take", "run", "tf", "era", "kind"]


def fold(rows):
    """Squash a worker's rows down to per-group sums, so the parent process
    never holds tens of millions of trades in memory."""
    if not rows:
        return None
    d = pd.DataFrame(rows)
    d = d[np.isfinite(d.ret) & (d.ret.abs() < 5)]
    if d.empty:
        return None
    d["wins"] = (d.ret > 0.005).astype(int)
    d["losses"] = (d.ret < -0.005).astype(int)
    d["win_ret"] = d.ret.where(d.ret > 0.005, 0.0)
    d["loss_ret"] = d.ret.where(d.ret < -0.005, 0.0)
    d["left"] = d.best_after - d.ret
    d["took_n"] = d["took"].astype(int)
    d["deep"] = (d.worst < -0.10).astype(int)
    d["capped"] = (d.why == "time").astype(int)
    g = d.groupby(KEYS, observed=True)
    out = g.agg(n=("ret", "size"), sum_ret=("ret", "sum"), sum_drift=("drift", "sum"),
                wins=("wins", "sum"), losses=("losses", "sum"),
                sum_win=("win_ret", "sum"), sum_loss=("loss_ret", "sum"),
                sum_held=("held", "sum"), sum_left=("left", "sum"), sum_worst=("worst", "sum"),
                deep=("deep", "sum"),
                took=("took_n", "sum"), capped=("capped", "sum")).reset_index()
    return out


def block(g):
    """One results line from folded sums."""
    n = float(g["n"].sum())
    if not n:
        return None
    return dict(n=int(n), ret=float(g.sum_ret.sum() / n), drift=float(g.sum_drift.sum() / n),
                edge=float((g.sum_ret.sum() - g.sum_drift.sum()) / n),
                win=float(g.wins.sum() / n),
                avg_win=float(g.sum_win.sum() / g.wins.sum()) if g.wins.sum() else None,
                avg_loss=float(g.sum_loss.sum() / g.losses.sum()) if g.losses.sum() else None,
                took=float(g.took.sum() / n), held=float(g.sum_held.sum() / n),
                left=float(g.sum_left.sum() / n), capped=float(g.capped.sum() / n),
                worst=float(g.sum_worst.sum() / n), deep=float(g.deep.sum() / n))


def by(folded, cols):
    return {(k if isinstance(k, str) else " | ".join(k)): block(g)
            for k, g in folded.groupby(cols, observed=True)}


def quiet_workers():
    """Windows spawns a console window per worker unless they run under
    pythonw.exe. The owner sees them as empty cmd windows popping up."""
    if sys.platform == "win32":
        exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if os.path.exists(exe):
            mp.set_executable(exe)


def _work(args):
    """One name, every timeframe: returns folded sums, not rows."""
    sym, kind, start = args
    errs = []
    try:
        fr = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    rows = []
    for tf in CHAIN:
        if tf not in fr:
            continue
        try:
            rows += study_frame(sym, kind, tf, fr, start)
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    return fold(rows), errs



def main():
    for i, a in enumerate(sys.argv):
        if a == "--log" and i + 1 < len(sys.argv):
            sys.stdout = sys.stderr = open(sys.argv[i + 1], "w", buffering=1,
                                           encoding="utf-8", errors="replace")
    procs = PROCS
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
    t0 = time.time()
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * B.YEARS)
    names = B.universe()
    quiet_workers()
    parts, done, errs = [], 0, []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for out, err in ex.map(_work, [(s_, k_, start) for s_, k_ in names], chunksize=1):
            done += 1
            errs += err or []
            if out is not None:
                parts.append(out)
            if done % 25 == 0 or done == len(names):
                print("  %d/%d names  (%.0fs)" % (done, len(names), time.time() - t0), flush=True)
    for e in errs[:40]:
        print("  " + e, flush=True)
    folded = pd.concat(parts, ignore_index=True)
    res = {"by_variant": by(folded, ["variant"]),
           "by_variant_tf": by(folded, ["variant", "tf"]),
           "by_variant_era": by(folded, ["variant", "era"]),
           "by_variant_asset": by(folded, ["variant", "kind"]),
           "by_run": by(folded, ["run"]),
           "by_take": by(folded, ["take"]),
           "by_run_tf": by(folded, ["run", "tf"]),
           "by_take_tf": by(folded, ["take", "tf"]),
           "meta": dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names),
                        trades=int(folded.n.sum()), tfs=CHAIN, cap_days=CAP_DAYS,
                        max_chase=MAX_CHASE, procs=procs, seconds=int(time.time() - t0))}
    json.dump(res, open(OUT, "w"))
    print()
    print("  PARTIALS  %d names, %d trade-variants, %d workers  (%.0fs)" % (
        len(names), int(folded.n.sum()), procs, time.time() - t0))
    print()
    print("  %-52s %9s %9s %9s %6s %7s %10s %9s %7s" % ("variant", "n", "per trade", "vs drift", "win", "held", "left after", "worst dip", "dip>10%"))
    for v, b in sorted(res["by_variant"].items(), key=lambda kv: -kv[1]["ret"]):
        print("  %-52s %9d %+8.2f%% %+8.2f%% %5.0f%% %6.0f %+9.2f%% %+8.2f%% %6.0f%%" % (
            v, b["n"], 100 * b["ret"], 100 * b["edge"], 100 * b["win"], b["held"], 100 * b["left"],
            100 * b["worst"], 100 * b["deep"]))
    print()
    print("  by how long the runner is held:")
    for v, b in sorted(res["by_run"].items(), key=lambda kv: -kv[1]["ret"]):
        print("    %-30s n=%9d %+7.2f%%  held %6.0f bars  worst dip %+.1f%%  left after %+.2f%%" % (
            v, b["n"], 100 * b["ret"], b["held"], 100 * b["worst"], 100 * b["left"]))
    print()
    print("  by what gets sold early:")
    for v, b in sorted(res["by_take"].items(), key=lambda kv: -kv[1]["ret"]):
        print("    %-24s n=%9d %+7.2f%%  filled %3.0f%%" % (v, b["n"], 100 * b["ret"], 100 * b["took"]))
    print()
    print("  best per timeframe:")
    for tf in CHAIN:
        rowsx = [(k, b) for k, b in res["by_variant_tf"].items() if k.endswith(" | " + tf)]
        for k, b in sorted(rowsx, key=lambda kv: -kv[1]["ret"])[:4]:
            print("    %-64s n=%8d %+7.2f%% vs drift %+6.2f%% left after %+.1f%%" % (
                k, b["n"], 100 * b["ret"], 100 * b["edge"], 100 * b["left"]))
    for i, a in enumerate(sys.argv):
        if a == "--log" and i + 1 < len(sys.argv):
            done = os.path.splitext(sys.argv[i + 1])[0] + ".done"
            sys.stdout.flush()
            open(done, "w").write("done")


if __name__ == "__main__":
    main()
