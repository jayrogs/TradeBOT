"""trend_ride.py -- the trend ride as graded by the owner on 27 charts (2026-09-06).

His corrections, one rule each:
  * "a lower high isn't a death sentence, it's when the HL breaks"  -> the
    only exit is a wick under the last higher low. A lower high is a pause.
  * "HL, HH then catch the next HL, that makes sense" / "only a HH and HL in
    that trend, is that all you needed?"  -> the uptrend must already be open
    (a higher low and a higher high printed) BEFORE the higher low we buy.
    We count which higher low of the trend it is (2nd, 3rd, 4th+) because he
    also said "bought late" on one with many behind it.
  * "the 15m and 1h looked like a bear flag" / "red on the hourly and 4hr" /
    "daily was a mess"  -> the next chart up is recorded (up / flat / down)
    and so is whether it is stretched (many green closes in a row).
  * "ran so much before the buy, one huge single movement"  -> recorded: did
    a single bar in the last 10 move more than 3 normal bars' worth.
  * "the difference is so minuscule" / "that LL looks like an EL" / "we need
    some tolerance for wicking below"  -> the break under the higher low must
    exceed a tolerance, in normal bars' moves; three widths are tested.
  * "15m and 1h looked good, so selling on 5m action wasn't great"  -> a
    second exit is tested: the NEXT chart's last higher low breaking.
  * the partial fired one bar in on JPM because the risk was 22 cents  -> the
    partial target is twice the risk, with the risk floored at one normal
    bar's move.

  Round 3 (28 more charts): "why the 4th higher low? the second worked much
  better" (x8) -> ONLY the second higher low is an entry; "we gotta hold" on
  the 1h -> 1h holds overnight, 5m/15m still close at the bell; "choppy as
  fuck, avoid" (x7) -> a chop measure is recorded; "LL with no follow through
  is a major green flag to try again" (x4) -> the fakeout re-entry is tested.

    pythonw studies/trend_ride.py --procs 16 --log logs/trend_ride.log
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
import panel as PN                # noqa: E402
import structure as ST            # noqa: E402

CHAIN = ["5m", "15m", "1h", "4h", "1d", "1w"]
UP = {"5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d", "1d": "1w"}
BARS_DAY, CLASS_COST = B.BARS_DAY, B.CLASS_COST
CAP_DAYS = 60
MAX_CHASE = 1.0
TOLS = [0.5]                      # how far under the last higher low the wick must go, in normal bars' moves
CHASES = [1.0, 2.0, 3.0]          # how far above the pivot the open may be, in normal bars' moves
PROCS = max(1, os.cpu_count() or 4)      # every core (owner 2026-09-08: "always using all cores possible")
OUT = os.path.join("validation", "trend_ride.json")
VARIANTS = "--variants" in sys.argv     # add the trail-width variants (slower)
EXITS = "--exits" in sys.argv           # twenty exit managers (exit_managers.py), second higher low only, no partial
EXITS2 = "--exits2" in sys.argv         # the second batch (exit_managers2.py)
TOLERANCE = "--tols" in sys.argv        # how far under the last higher low counts as a break (owner 2026-09-08)
TOL_SET = [("a wick under the line at all", 0.0, False), ("a wick a quarter bar under", 0.25, False),
           ("a wick half a bar under (as graded)", 0.5, False), ("a wick a whole bar under", 1.0, False),
           ("a wick one and a half bars under", 1.5, False), ("a wick two bars under", 2.0, False),
           ("a close under the line", 0.0, True), ("a close half a bar under", 0.5, True), ("a close a whole bar under", 1.0, True)]
KEYS = ["exit", "take", "tf", "era", "kind", "nth", "hi", "stretched", "big_bar", "spacing", "chop", "leg"]


# ------------------------------------------------------------------ one frame

def hl_break_exit(c, o, l, h, a14, lows, lcis, e, level, n, cap, tol, day=None, trail_after=None, trail_bars=8.0, trail_mode="raise", by_close=False):
    """Hold from bar e. The line is the last higher low (an equal low counts);
    every later confirmed one raises it. Out when a wick goes under the line
    by more than `tol` normal bars' moves, sold at the next open. Lower highs
    are ignored. `day`: session ids for fast stock charts -> out at the close
    of the day (no overnight). `trail_after`: once up this many R, switch to a
    stop 8 normal bars' moves under the highest close (his SPY note)."""
    p = bisect.bisect_right(lcis, e - 1)
    fill = o[e]
    worst = 0.0
    peak = c[e]
    # the risk is floored at one normal bar's move, same as the charts he graded
    # (pics_ride.walk) and the live tracker (ride_log.live_walk)
    atr0 = a14[e - 1] if e >= 1 and np.isfinite(a14[e - 1]) else 0.0
    R = max(fill - level, atr0) if level is not None else None
    trailing = False
    for k in range(e, n - 1):
        while p < len(lows) and lows[p][0] <= k:
            ci, j, price, lab = lows[p]; p += 1
            if j >= e and lab in ("HL", "EL") and price > level:
                level = price
        worst = min(worst, c[k] / fill - 1)
        peak = max(peak, c[k])
        atr = a14[k] if np.isfinite(a14[k]) else 0.0
        if trail_after is not None and not trailing and R and R > 0 and c[k] >= fill + trail_after * R:
            trailing = True
        if trailing:
            if trail_mode == "raise":
                # the trail only ever RAISES the line; the last higher low still holds under it
                level = max(level, peak - trail_bars * atr)
                if c[k] < level:
                    return k, o[k + 1], "trail hit", worst
            else:
                # "replace": the trail is the only line now (how the study was coded before 2026-09-07)
                if c[k] < peak - trail_bars * atr:
                    return k, o[k + 1], "trail hit", worst
        elif (c[k] if by_close else l[k]) < level - tol * atr:
            return k, o[k + 1], "higher low broke", worst
        if day is not None and k + 1 < n and day[k + 1] != day[k]:
            return k, c[k], "session end", worst
        if k - e >= cap:
            return k, o[k + 1], "time", worst
    return None


def trend_pivots_before(allp, pos_by_ci, ci):
    """His count: walk back over HL/HH/EH/EL until a LH or LL. Returns
    (pivots including this one, has a higher high, higher lows including this one)."""
    k = pos_by_ci.get(ci)
    if k is None:
        return 0, False, 0
    cnt, has_hh, nhl = 0, False, 0
    for m in range(k, -1, -1):
        lab = allp[m][4]
        if lab in ("LH", "LL", "H", "L"):
            break
        cnt += 1
        has_hh = has_hh or lab == "HH"
        nhl += lab in ("HL", "EL")
    return cnt, has_hh, nhl


def hi_level_series(df, hdf, n, tol):
    """For each bar of this chart: the next chart's last higher low, and
    whether the next chart's wick has gone under it (known from that bar's
    timestamp on). Returns (level array, broke array)."""
    level = np.full(n, np.nan)
    if hdf is None or len(hdf) < 60:
        return level
    piv = ST.pivots(hdf)
    hl_ = [(hdf.index[ci], p) for ci, j, p, k_, lab in piv if k_ == "low" and lab == "HL"]
    pos = df.index.searchsorted([t for t, _ in hl_], side="right")
    cur = np.nan
    j = 0
    for i in range(n):
        while j < len(pos) and pos[j] <= i:
            cur = hl_[j][1]; j += 1
        level[i] = cur
    return level


def study_frame(sym, kind, tf, frames, start):
    df = frames[tf]
    if len(df) < 300:
        return []
    c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    cap = CAP_DAYS * BARS_DAY[tf]
    cost = CLASS_COST.get(kind, B.COST)
    a14 = B.atr(h, l, c)
    piv = ST.pivots(df)
    lows = [(ci, j, p, lab) for ci, j, p, k_, lab in piv if k_ == "low"]
    lcis = [x[0] for x in lows]
    if EXITS or EXITS2:
        import exit_managers as XM
        highs = [(ci, j, p, lab) for ci, j, p, k_, lab in piv if k_ == "high"]
        hcis = [x[0] for x in highs]
        ind = XM.indicators(c, o, h, l, a14)
    if EXITS2:
        import exit_managers2 as XM2
        vol = df["Volume"].values.astype(float) if "Volume" in df else None
        ind2 = XM2.prep(c, o, h, l, vol, a14, XM.ema)
    # the live uptrend, bar by bar: is it open, and how many higher lows has it made
    up_start = np.full(n, -1)
    for kind_, s0, s1 in ST.spans(df, causal=True):
        if kind_ == "UP":
            up_start[s0:s1 + 1] = s0
    # the next chart: state, its last higher low, and whether it is stretched
    ci_ = CHAIN.index(tf)
    hdf = frames.get(UP.get(tf))
    t1 = B.higher_view(df, tf, hdf, UP[tf])[0] if hdf is not None else None
    hi_lvl = hi_level_series(df, hdf, n, 0.0) if hdf is not None else np.full(n, np.nan)
    streak = np.zeros(n)
    if hdf is not None and len(hdf) > 30:
        hc = hdf["Close"].values.astype(float)
        run = np.zeros(len(hc))
        for i in range(1, len(hc)):
            run[i] = run[i - 1] + 1 if hc[i] > hc[i - 1] else 0
        pos = np.clip(hdf.index.searchsorted(df.index, side="right") - 1, 0, len(hc) - 1)
        streak = run[pos]
    lr = np.diff(np.log(c), prepend=np.log(c[0]))
    drift = float(np.nanmean(lr[np.isfinite(lr)]))
    mid = start + (pd.Timestamp.now() - start) / 2
    rows = []
    pos_by_ci = {pv[0]: i for i, pv in enumerate(piv)}
    day = None
    if kind in ("stock", "etf") and tf in ("5m", "15m"):          # the 1h holds overnight now ("we gotta hold")
        day = df.index.normalize().values
    # chop: how many times the live trend flipped in the last 60 bars
    state = np.array(["FLAT"] * n, dtype=object)
    for kind_, s0, s1 in ST.spans(df, causal=True):
        state[s0:s1 + 1] = kind_
    flips = np.zeros(n)
    chg = np.r_[0, (state[1:] != state[:-1]).astype(int)]
    cs = np.cumsum(chg)
    flips[60:] = cs[60:] - cs[:-60]
    for idx, (ci, j, price, lab) in enumerate(lows):
        if lab not in ("HL", "EL") or ci < 60 or ci + 2 >= n - 1:
            continue
        e = ci + 1
        cnt, has_hh, nhl = trend_pivots_before(piv, pos_by_ci, ci)
        if cnt < 3 or not has_hh:
            continue                       # a higher low AND a higher high must already exist
        nth_b = "2nd higher low" if nhl <= 2 else "3rd" if nhl == 3 else "4th or later"
        atr = a14[ci] if np.isfinite(a14[ci]) and a14[ci] > 0 else np.nan
        if not np.isfinite(atr):
            continue
        fill = o[e]
        if fill < price:
            continue                       # opened under the higher low: already broken
        chase = (fill - price) / atr
        max_chase = 1.0 if tf in ("5m", "15m", "1h") else 3.0
        if chase > max_chase:
            continue
        risk = max(fill - price, atr)
        big = float(np.max(h[ci - 10:ci + 1] - l[ci - 10:ci + 1]) / atr) if ci >= 10 else 0.0
        big_b = "a giant bar just before" if big > 3 else "smooth climb"
        hi_b = ("higher chart up" if t1 is not None and str(t1[ci]) == "UP" else
                "higher chart down" if t1 is not None and str(t1[ci]) == "DOWN" else "higher chart flat")
        st_b = "higher chart stretched (6+ green closes)" if streak[ci] >= 6 else "higher chart not stretched"
        prev_hl = next((x for x in reversed(lows[:idx]) if x[3] in ("HL", "EL")), None)
        spacing = (price - prev_hl[2]) / atr if prev_hl is not None else np.nan
        sp_b = ("no earlier higher low" if not np.isfinite(spacing) else
                "close to the last higher low (<3 bars' moves)" if spacing < 3 else
                "3-6 bars' moves above it" if spacing < 6 else "far above the last higher low (6+)")
        f = flips[ci]
        chop_b = "calm (0-2 trend flips in 60 bars)" if f <= 2 else "some chop (3-4 flips)" if f <= 4 else "choppy (5+ flips in 60 bars)"
        t = df.index[e]
        era = "before" if t < start else "first" if t < mid else "second"
        tgt = fill + 2 * risk
        pbar = next((k for k in range(e, min(n - 1, e + cap)) if h[k] >= tgt), None)
        base = dict(tf=tf, era=era, kind=kind, nth=nth_b, hi=hi_b, stretched=st_b, big_bar=big_b,
                    spacing=sp_b, chop=chop_b, t=str(t))
        if EXITS or EXITS2:
            if nhl > 2:
                continue                   # second higher low only, to keep the run short
            exits = {"higher low breaks, trail once up 3R": hl_break_exit(c, o, l, h, a14, lows, lcis, e, price, n, cap, 0.5, day=day, trail_after=3.0)}
            if EXITS:
                exits.update(XM.run_all(c, o, l, h, a14, ind, lows, lcis, highs, hcis, e, price, n, cap, day))
            else:
                exits.update(XM2.run_all2(c, o, l, h, vol, a14, ind2, hi_lvl, lows, lcis, highs, hcis, e, price, n, cap, day))
            for ex_label, res in exits.items():
                if res is None:
                    continue
                xb, xpx, why, worst = res
                after = min(n - 1, xb + 60)
                rows.append(dict(base, exit=ex_label, take="no partial", leg="first try",
                                 ret=float(xpx / fill - 1 - cost), held=int(xb + 1 - e), why=why, took=False,
                                 worst=float(worst), best_after=float(np.max(c[xb:after + 1]) / fill - 1),
                                 drift=float(np.exp(drift * (xb + 1 - e)) - 1 - cost)))
            continue
        exits = {"higher low breaks, trail once up 3R": hl_break_exit(c, o, l, h, a14, lows, lcis, e, price, n, cap, 0.5, day=day, trail_after=3.0),
                 "higher low breaks": hl_break_exit(c, o, l, h, a14, lows, lcis, e, price, n, cap, 0.5, day=day)}
        if TOLERANCE:
            exits = {}
            for lab_, tol_, cl_ in TOL_SET:
                exits[lab_] = hl_break_exit(c, o, l, h, a14, lows, lcis, e, price, n, cap, tol_, day=day, trail_after=3.0, by_close=cl_)
        if VARIANTS:
            # his sentence read the other way: once up 3x the risk, the trail REPLACES the higher-low line
            for tb in (8.0, 4.0, 2.0):
                exits["trail replaces the line once up 3R, %g bars under the high" % tb] = hl_break_exit(
                    c, o, l, h, a14, lows, lcis, e, price, n, cap, 0.5, day=day, trail_after=3.0, trail_bars=tb, trail_mode="replace")
        for ex_label, res in exits.items():
            if res is None:
                continue
            xb, xpx, why, worst = res
            for take_label, sz in (("no partial", 0.0), ("a third at 2x risk", 1 / 3)):
                took = sz > 0 and pbar is not None and pbar <= xb
                s_ = sz if took else 0.0
                ret = s_ * (tgt / fill - 1) + (1 - s_) * (xpx / fill - 1) - cost
                after = min(n - 1, xb + 60)
                rows.append(dict(base, exit=ex_label, take=take_label, leg="first try",
                                 ret=float(ret), held=int(xb + 1 - e), why=why, took=bool(took),
                                 worst=float(worst), best_after=float(np.max(c[xb:after + 1]) / fill - 1),
                                 drift=float(np.exp(drift * (xb + 1 - e)) - 1 - cost)))
            # the fakeout re-entry: stopped by a wick under the line, and within 5
            # bars a close is back above that line -> buy the next open, same rules
            if why == "higher low broke" and nhl <= 2:
                broken = min(price, float(l[xb]) + 0.5 * (a14[xb] if np.isfinite(a14[xb]) else 0))   # the line at the break
                line = None
                # recover the exact line: the last HL/EL price at xb
                line = price
                p2 = bisect.bisect_right(lcis, e - 1)
                while p2 < len(lows) and lows[p2][0] <= xb:
                    ci2, j2, pr2, lab2 = lows[p2]; p2 += 1
                    if j2 >= e and lab2 in ("HL", "EL") and pr2 > line:
                        line = pr2
                rb = next((k for k in range(xb + 1, min(n - 2, xb + 6)) if c[k] > line), None)
                if rb is not None:
                    e2 = rb + 1
                    fill2 = o[e2]
                    res2 = hl_break_exit(c, o, l, h, a14, lows, lcis, e2, line, n, cap, 0.5, day=day, trail_after=3.0)
                    if res2 is not None:
                        xb2, xpx2, why2, worst2 = res2
                        after2 = min(n - 1, xb2 + 60)
                        rows.append(dict(base, exit=ex_label, take="no partial", leg="fakeout re-entry",
                                         ret=float(xpx2 / fill2 - 1 - cost), held=int(xb2 + 1 - e2), why=why2,
                                         took=False, worst=float(worst2),
                                         best_after=float(np.max(c[xb2:after2 + 1]) / fill2 - 1),
                                         drift=float(np.exp(drift * (xb2 + 1 - e2)) - 1 - cost)))
    return rows


# ------------------------------------------------------------------ counting

def fold(rows):
    if not rows:
        return None
    d = pd.DataFrame(rows)
    d = d[np.isfinite(d.ret) & (d.ret.abs() < 5)]
    if d.empty:
        return None
    d = d.drop(columns=["t"], errors="ignore")
    d["wins"] = (d.ret > 0.005).astype(int)
    d["losses"] = (d.ret < -0.005).astype(int)
    d["win_ret"] = d.ret.where(d.ret > 0.005, 0.0)
    d["loss_ret"] = d.ret.where(d.ret < -0.005, 0.0)
    d["left"] = d.best_after - d.ret
    d["took_n"] = d["took"].astype(int)
    d["timed"] = (d.why == "time").astype(int)
    g = d.groupby(KEYS, observed=True)
    return g.agg(n=("ret", "size"), sum_ret=("ret", "sum"), sum_drift=("drift", "sum"),
                 wins=("wins", "sum"), losses=("losses", "sum"), sum_win=("win_ret", "sum"),
                 sum_loss=("loss_ret", "sum"), sum_held=("held", "sum"), sum_left=("left", "sum"),
                 sum_worst=("worst", "sum"), took=("took_n", "sum"), timed=("timed", "sum")).reset_index()


def block(g):
    n = float(g["n"].sum())
    if not n:
        return None
    return dict(n=int(n), ret=float(g.sum_ret.sum() / n), drift=float(g.sum_drift.sum() / n),
                edge=float((g.sum_ret.sum() - g.sum_drift.sum()) / n), win=float(g.wins.sum() / n),
                avg_win=float(g.sum_win.sum() / g.wins.sum()) if g.wins.sum() else None,
                avg_loss=float(g.sum_loss.sum() / g.losses.sum()) if g.losses.sum() else None,
                took=float(g.took.sum() / n), held=float(g.sum_held.sum() / n),
                left=float(g.sum_left.sum() / n), worst=float(g.sum_worst.sum() / n),
                timed=float(g.timed.sum() / n))


def by(folded, cols):
    return {(k if isinstance(k, str) else " | ".join(k)): block(g) for k, g in folded.groupby(cols, observed=True)}


def _work(args):
    sym, kind, start = args
    errs, rows = [], []
    try:
        fr = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    for tf in CHAIN:
        if tf not in fr:
            continue
        try:
            rows += study_frame(sym, kind, tf, fr, start)
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    return fold(rows), errs


def _by_size(names):
    """Biggest files first, so the slow names start early and the cores stay full to the end."""
    import glob as _g
    def sz(sk):
        s_, k_ = sk
        folder = {"crypto": "history", "stock": "history/stocks", "etf": "history/stocks", "futures": "history/futures"}.get(k_, "history")
        return sum(os.path.getsize(p) for p in _g.glob(os.path.join(folder, "%s_*.csv.gz" % s_)))
    return sorted(names, key=sz, reverse=True)


def quiet_workers():
    if sys.platform == "win32":
        exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if os.path.exists(exe):
            mp.set_executable(exe)


def main():
    procs = PROCS
    log = None
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            log = sys.argv[i + 1]
            sys.stdout = sys.stderr = open(log, "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * B.YEARS)
    names = [(s_, k_) for s_, k_ in B.universe() if k_ != "forex"]     # forex intraday is not real yet
    global OUT
    if "--focus" in sys.argv:
        import focus
        names = [(s_, k_) for s_, k_ in focus.names() if focus.have(s_, k_)]
        OUT = os.path.join("validation", "trend_ride_focus.json")
    if VARIANTS:
        OUT = OUT.replace(".json", "_trail.json")
    if EXITS:
        OUT = OUT.replace(".json", "_exits.json")
    if EXITS2:
        OUT = OUT.replace(".json", "_exits2.json")
    if TOLERANCE:
        OUT = OUT.replace(".json", "_tol.json")
    names = _by_size(names)
    quiet_workers()
    parts, done, errs = [], 0, []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for out, err in ex.map(_work, [(s_, k_, start) for s_, k_ in names], chunksize=1):
            done += 1
            errs += err or []
            if out is not None:
                parts.append(out)
            if done % 50 == 0 or done == len(names):
                print("  %d/%d names  (%.0fs)" % (done, len(names), time.time() - t0), flush=True)
    for e in errs[:30]:
        print("  " + e)
    f = pd.concat(parts, ignore_index=True)
    first = f[(f.leg == "first try")]
    second = first[first.nth == "2nd higher low"]
    res = {"by_exit": by(second, ["exit", "take"]),
           "by_exit_tf": by(second, ["exit", "tf"]), "by_exit_era": by(second, ["exit", "era"]),
           "by_exit_kind": by(second, ["exit", "kind"]),
           "by_nth": by(first, ["exit", "nth"]), "by_nth_tf": by(first, ["exit", "nth", "tf"]),
           "by_hi": by(second, ["exit", "hi"]), "by_hi_tf": by(second, ["exit", "hi", "tf"]),
           "by_stretched": by(second, ["exit", "stretched"]), "by_big": by(second, ["exit", "big_bar"]),
           "by_spacing": by(second, ["exit", "spacing"]),
           "by_chop": by(second, ["exit", "chop"]), "by_chop_tf": by(second, ["exit", "chop", "tf"]),
           "by_leg": by(f[f.nth == "2nd higher low"], ["exit", "leg"]),
           "by_leg_tf": by(f[f.nth == "2nd higher low"], ["exit", "leg", "tf"]),
           "meta": dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names),
                        trades=int(f.n.sum()), tfs=CHAIN, cap_days=CAP_DAYS, procs=procs, seconds=int(time.time() - t0))}
    json.dump(res, open(OUT, "w"))
    print()
    print("  TREND RIDE, his rules, round 3  %d names  (%.0fs)" % (len(names), time.time() - t0))
    hdr = "  %-58s %9s %9s %9s %5s %6s %8s %9s" % ("", "n", "per trade", "vs drift", "win", "held", "worst", "left after")
    def line(k, b):
        return "  %-58s %9d %+8.2f%% %+8.2f%% %4.0f%% %6.0f %+7.2f%% %+8.2f%%" % (
            k[:58], b["n"], 100 * b["ret"], 100 * b["edge"], 100 * b["win"], b["held"], 100 * b["worst"], 100 * b["left"])
    print("\n  SECOND HIGHER LOW ONLY"); print(hdr)
    for k, b in sorted(res["by_exit"].items(), key=lambda kv: -kv[1]["ret"]):
        print(line(k, b))
    for title, key in (("which higher low (all entries)", "by_nth"), ("the next chart up", "by_hi"),
                       ("chop", "by_chop"), ("spacing", "by_spacing"), ("stretched", "by_stretched"),
                       ("giant bar", "by_big"), ("first try vs the fakeout re-entry", "by_leg")):
        print("\n  %s:" % title); print(hdr)
        for k, b in sorted(res[key].items()):
            if k.startswith("higher low breaks, trail once up 3R"):
                print(line(k.split(" | ", 1)[1], b))
    print("\n  per timeframe (second higher low, trail once up 3R):"); print(hdr)
    for k, b in sorted(res["by_exit_tf"].items()):
        if k.startswith("higher low breaks, trail once up 3R"):
            print(line(k.split(" | ", 1)[1], b))
    print("\n  per timeframe, the fakeout re-entry:"); print(hdr)
    for k, b in sorted(res["by_leg_tf"].items()):
        if k.startswith("higher low breaks, trail once up 3R | fakeout"):
            print(line(k.split(" | ", 2)[2], b))
    print("\n  per timeframe, chop:"); print(hdr)
    for k, b in sorted(res["by_chop_tf"].items()):
        if k.startswith("higher low breaks, trail once up 3R"):
            print(line(" | ".join(k.split(" | ")[1:]), b))
    if log:
        sys.stdout.flush()
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
