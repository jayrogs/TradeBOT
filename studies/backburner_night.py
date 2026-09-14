"""backburner_night.py -- everything at once on the backburner (2026-09-12 overnight).

His instruction: "throw everything you have at backburners tonight, use all collective knowledge of the best
psychological trend patterns of the market to refine the back burner trade".

HIS TRADE, as he has corrected it into shape over the last two days:
  - a backburner is RSI 14 AT OR UNDER 30, bought AT OR UNDER 30 -- not a bounce, not a cross back over
  - it is SCALED INTO as it falls, so the position is the average of several fills
  - it is only engaged in a name that has a run going on
  - on the high timeframes it is the crash dip that pays: "its those giant winners we are chasing, its when
    markets go from bear to bull, that backburners are back in play"

One skeleton, switches for everything (rule 13d -- nobody trades a single condition):

  SEVEN WAYS IN      how deep the print has to be, how many units, how far apart, and whether the dip has to be
                     the first in a long time
  SIXTEEN READS      recorded per trade, cut at report time. Market health (Murphy's breadth), how wrecked the
                     leader is, how stretched the name is, capitulation volume, a new 1-year low versus a
                     pullback, the retest of a prior low, momentum divergence, a fear gap, how long since the
                     last dip, the name's run, its strength against its own sector leader
  SIX WAYS OUT       the walked stop, chandelier 3, ride it at 8 and 12 with no partial at all, out at 2x, and
                     HIS OWN: sell everything the moment it prints overbought
  THE CONTROL        every one of them also measured entering on any bar at all, same management, same read

    pythonw studies/backburner_night.py --procs 8 --log logs/backburner_night.log
Writes validation/backburner_night.json and _rows.parquet
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
import panel as P                 # noqa: E402
import structure as ST            # noqa: E402
import trend_ride as R            # noqa: E402
import indicators as IND          # noqa: E402
import exit_managers as XM        # noqa: E402
import eq_freeride2 as FR2        # noqa: E402
import tcg_lab as L               # noqa: E402
from scalein_study import describe, SECTOR_MAP, BREADTH, BR_GROUP     # noqa: E402

OUT = os.path.join("validation", "backburner_night.json")
COSTV = L.COST
ERAS = ["before 2022", "first half", "second half"]
PAIRS = [("1d", "1w", []), ("4h", "1d", []), ("1h", "1d", [])]

# (label, how deep the print must be, units, how far apart in normal bars, must be first in N bars)
ENTRIES = [("one unit at 30, no scaling", 30, 1, 0.0, 0),
           ("scale in at 30, 3 units, half a bar apart", 30, 3, 0.5, 0),
           ("scale in at 30, 3 units, a quarter bar apart", 30, 3, 0.25, 0),
           ("scale in at 30, 5 units, a quarter bar apart", 30, 5, 0.25, 0),
           ("scale in at 25, 3 units, half a bar apart", 25, 3, 0.5, 0),
           ("scale in at 20, 3 units, half a bar apart", 20, 3, 0.5, 0),
           ("scale in at 30, first dip in 120+ bars", 30, 3, 0.5, 120)]

# (label, mode, chandelier distance)
MANAGERS = [("stop walked under the idea chart's higher lows, half off at 1x", "walk", 3.0),
            ("chandelier 3, half off at 1x", "chand", 3.0),
            ("RIDE it: chandelier 8, no partial", "ride", 8.0),
            ("RIDE it: chandelier 12, no partial", "ride", 12.0),
            ("all out at 2x", "out2r", 3.0),
            ("HIS exit: sell everything when it prints overbought", "obout", 3.0)]

COND_COLS = ["breadth", "br_turn", "lead_dd", "stretch", "cap_vol", "new_low", "retest",
             "diverge", "gap_down", "fresh", "run60", "on_200", "f_over", "role_rev", "at_low", "wick"]


def _series(sym, kind, frames, tf, df, n):
    """Every read this study can take, on the entry chart's clock, with nothing from the future."""
    out = {c: np.full(n, np.nan) for c in COND_COLS}
    d1 = frames.get("1d")
    if d1 is None or len(d1) < 220:
        return out
    dc = d1["Close"].values.astype(float)
    dl = d1["Low"].values.astype(float)
    dh = d1["High"].values.astype(float)
    dat = P._atr(d1)
    e200 = XM.ema(dc, 200)

    def up(arr):
        return L.align_to(df, tf, frames, "1d", arr)

    # --- market health: Murphy's breadth, and whether that line has turned
    bg = BREADTH.get(BR_GROUP.get(kind, kind))
    if bg is not None:
        bidx = pd.to_datetime(bg["dates"])
        out["breadth"] = up(pd.Series(bg["above200"], index=bidx).reindex(d1.index).ffill().values.astype(float))
        out["br_turn"] = up(pd.Series([np.nan if x is None else float(x) for x in bg["turn20"]],
                                      index=bidx).reindex(d1.index).ffill().values.astype(float))
    # --- how far the name is under its own 200-day, in normal bars: the stretch is the fear
    with np.errstate(invalid="ignore"):
        st = np.where(np.isfinite(e200) & (dat > 0), (dc - e200) / dat, np.nan)
    out["stretch"] = up(st)
    out["on_200"] = up(np.where(np.isfinite(e200), (dc > e200).astype(float), np.nan))
    # --- the name's run, in normal bars over 60 days
    rd = np.full(len(dc), np.nan)
    rd[60:] = (dc[60:] - dc[:-60]) / np.where(dat[60:] > 0, dat[60:], np.nan)
    out["run60"] = up(rd)
    # --- capitulation volume: the day's volume against its own 50-day average
    if "Volume" in d1:
        vol = d1["Volume"].values.astype(float)
        av = pd.Series(vol).rolling(50, min_periods=20).mean().values
        out["cap_vol"] = up(np.where(av > 0, vol / av, np.nan))
    # --- a new 1-year low (the name is broken) versus a pullback inside an uptrend
    lo252 = pd.Series(dl).rolling(252, min_periods=252).min().values
    out["new_low"] = up(np.where(np.isfinite(lo252), (dl <= lo252 + 0.25 * dat).astype(float), np.nan))
    # --- the retest: price back at a low it already held once, within a quarter of a normal bar
    lo60 = pd.Series(dl).rolling(60, min_periods=60).min().values
    prior = np.r_[np.full(20, np.nan), lo60[:-20]]
    out["retest"] = up(np.where(np.isfinite(prior) & (dat > 0),
                                (np.abs(dl - prior) <= 0.25 * dat).astype(float), np.nan))
    out["at_low"] = up(np.where(np.isfinite(lo60) & (dat > 0),
                                (dl <= lo60 + 0.5 * dat).astype(float), np.nan))
    # --- Murphy's divergence: at the low, but momentum is HIGHER than it was at the last one
    drsi = IND.rsi(dc, 14)
    lo40 = pd.Series(dl).rolling(40, min_periods=40).min().values
    dv = np.zeros(len(dc))
    dv[40:] = ((dl[40:] <= lo40[40:] + 0.25 * np.nan_to_num(dat[40:])) & (drsi[40:] > drsi[:-40])).astype(float)
    out["diverge"] = up(dv)
    # --- a fear gap: the day opened below yesterday's low
    do = d1["Open"].values.astype(float)
    gd = np.zeros(len(dc))
    gd[1:] = (do[1:] < dl[:-1]).astype(float)
    out["gap_down"] = up(gd)
    # --- role reversal: the dip lands where an old high was
    hi60 = pd.Series(dh).rolling(60, min_periods=60).max().values
    oldhi = np.r_[np.full(20, np.nan), hi60[:-20]]
    out["role_rev"] = up(np.where(np.isfinite(oldhi) & (dat > 0),
                                  (np.abs(dl - oldhi) <= 0.5 * dat).astype(float), np.nan))
    # --- the tail on the day: a long lower wick is buyers showing up
    wick = np.where((dh - dl) > 0, (np.minimum(do, dc) - dl) / np.maximum(dh - dl, 1e-12), np.nan)
    out["wick"] = up(wick)
    # --- strength against its own sector leader
    lead = SECTOR_MAP.get("%s|%s" % (kind, sym))
    if lead:
        lk, ls = lead[0].split("|")
        try:
            bx = B.frames_for(ls, lk)["1d"]["Close"]
        except Exception:
            bx = None
        if bx is not None and lead[0] != "%s|%s" % (kind, sym):
            bxa = bx.reindex(d1.index).ffill().values.astype(float)
            ratio = dc / bxa
            ok = np.isfinite(ratio)
            if ok.sum() >= 60:
                r12 = XM.ema(np.where(ok, ratio, np.nan), 12)
                out["f_over"] = up(np.where(ratio > r12, 1.0, 0.0))
                b200 = XM.ema(bxa, 200)
                out["lead_dd"] = up((bxa / np.where(b200 > 0, b200, np.nan) - 1.0) * 100.0)
    return out


def _work(args):
    sym, kind, start = args
    try:
        frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    need = {"1d"}
    for q in PAIRS:
        need.add(q[0])
        need.add(q[1])
    frames = {k: v for k, v in frames.items() if k in need}
    if kind in ("stock", "etf"):
        frames = FR2.regular_hours(frames)
    mid_t = start + (pd.Timestamp.now() - start) / 2
    rows, errs = [], []
    for tf_i, (tf, big, _a) in enumerate(PAIRS):
        df, bdf = frames.get(tf), frames.get(big)
        if df is None or bdf is None or len(df) < 300 or len(bdf) < 80:
            continue
        try:
            o = df["Open"].values.astype(float); c = df["Close"].values.astype(float)
            h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
            n = len(c)
            atr = P._atr(df)
            rsi = IND.rsi(c, 14)
            small12 = XM.ema(c, 12)
            piv = ST.pivots(df)
            last_lo = np.full(n, np.nan); last_hi = np.full(n, np.nan)
            cl = ch = np.nan; q = 0
            for k in range(n):
                while q < len(piv) and piv[q][0] <= k:
                    if piv[q][3] == "low":
                        cl = float(piv[q][2])
                    else:
                        ch = float(piv[q][2])
                    q += 1
                last_lo[k] = cl; last_hi[k] = ch
            bp = ST.pivots(bdf)
            bl = np.full(len(bdf), np.nan); bh = np.full(len(bdf), np.nan)
            cl2 = ch2 = np.nan; p2 = 0
            for k in range(len(bdf)):
                while p2 < len(bp) and bp[p2][0] <= k:
                    if bp[p2][3] == "low":
                        cl2 = float(bp[p2][2])
                    else:
                        ch2 = float(bp[p2][2])
                    p2 += 1
                bl[k] = cl2; bh[k] = ch2
            big_lo = L.align_to(df, tf, frames, big, bl)
            big_hi = L.align_to(df, tf, frames, big, bh)
            b12 = L.align_to(df, tf, frames, big, XM.ema(bdf["Close"].values.astype(float), 12))
            reads = _series(sym, kind, frames, tf, df, n)
            bells = None
            if kind in ("stock", "etf") and tf in ("5m", "15m"):
                day = df.index.normalize().values
                bells = np.searchsorted(day, day, side="right") - 1
            cost = COSTV.get(kind, 0.05)
            for ev, (_lab, lvl, adds, gap_bars, need_fresh) in enumerate(ENTRIES):
                os_ = rsi <= lvl
                ob = rsi >= (100 - lvl)
                since = {}
                for nm, flag in (("long", os_), ("short", ob)):
                    g = np.zeros(n); seen = -10 ** 6
                    for k in range(n):
                        g[k] = k - seen
                        if flag[k]:
                            seen = k
                    since[nm] = g
                ups = np.where(os_[1:] & ~os_[:-1])[0] + 1
                dns = np.where(ob[1:] & ~ob[:-1])[0] + 1
                stepc = max(60, n // 2500)
                groups = ((1, ups, 0), (-1, dns, 0),
                          (1, np.arange(120, n - 8, stepc), 1), (-1, np.arange(140, n - 8, stepc), 1))
                for side, ks, is_ctrl in groups:
                    for k in ks:
                        e = k + 1
                        m_ = e - 1
                        if e < 120 or e + 6 >= n or not np.isfinite(atr[m_]) or atr[m_] <= 0:
                            continue
                        fresh = since["long" if side > 0 else "short"][max(0, k - 1)]
                        if need_fresh and not is_ctrl and fresh < need_fresh:
                            continue
                        a = atr[m_]
                        fills = [o[e]]; fill_bars = [e]; j = e
                        while len(fills) < adds and j + 1 < n:
                            j += 1
                            inside = (rsi[j - 1] <= lvl) if side > 0 else (rsi[j - 1] >= (100 - lvl))
                            if not inside:
                                break
                            step = gap_bars * a
                            low_enough = (o[j] <= fills[-1] - step) if side > 0 else (o[j] >= fills[-1] + step)
                            if low_enough:
                                fills.append(o[j]); fill_bars.append(j)
                        entry = float(np.mean(fills))
                        e_last = fill_bars[-1]
                        worst = min(fills) if side > 0 else max(fills)
                        cands = []
                        for x in (last_lo[e_last] if side > 0 else last_hi[e_last],
                                  big_lo[e_last] if side > 0 else big_hi[e_last]):
                            if np.isfinite(x) and ((side > 0 and x < worst) or (side < 0 and x > worst)):
                                cands.append(x)
                        if cands:
                            stop = max(cands) if side > 0 else min(cands)
                            stop = stop - 0.15 * a if side > 0 else stop + 0.15 * a
                        else:
                            # NO STRUCTURE LEFT UNDER THE POSITION. Discarding these threw away the dips that
                            # crashed through every level -- the losers -- and it threw away MORE of them from
                            # the scaling rules than the one-unit rule, because scaling reaches lower. That is
                            # what made averaging down look free (2026-09-13). A stop still has to go somewhere.
                            stop = worst - a if side > 0 else worst + a
                        risk = abs(entry - stop)
                        if risk < 0.25 * a:
                            risk = 0.25 * a
                            stop = entry - side * risk
                        rp = risk / entry * 100
                        if rp < 3 * cost or risk > 4.0 * a or rp > 25.0:
                            continue
                        t_ = df.index[e]
                        era = 0 if t_ < start else 1 if t_ < mid_t else 2
                        res = []
                        for _n2, mode, chd in MANAGERS:
                            trail = big_lo if side > 0 else big_hi
                            res.append(L.run_trade(kind, o, h, l, c, e_last, side, stop, risk, b12, trail,
                                                   small12, rsi, mode,
                                                   None if bells is None else bells[e_last], atr,
                                                   chand=chd, entry_px=entry))
                        cond = []
                        for cname in COND_COLS:
                            v = reads[cname][m_]
                            if cname == "fresh":
                                v = fresh
                            elif cname == "f_over" and np.isfinite(v):
                                v = v if side > 0 else (1.0 - v)
                            elif cname in ("run60", "stretch") and np.isfinite(v):
                                v = v if side > 0 else -v
                            cond.append(float(v) if np.isfinite(v) else np.nan)
                        rows.append([tf_i, ev, side, era, len(fills), rp, float(t_.value), is_ctrl]
                                    + cond + res)
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    if not rows:
        return None, errs
    return (np.asarray(rows, dtype=np.float64), kind), errs


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
    parts, kinds, errs, done = [], [], [], 0
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got, err in ex.map(_work, [(s_, k_, start) for s_, k_ in names], chunksize=1):
            done += 1
            errs += err or []
            if got is not None:
                parts.append(got[0])
                kinds += [got[1]] * len(got[0])
            if done % 100 == 0 or done == len(names):
                print("  %d/%d names  (%.0fs)" % (done, len(names), time.time() - t0), flush=True)
    f = np.concatenate(parts)
    cols = ["tf", "ev", "side", "era", "units", "risk_pct", "t", "ctrl"] + COND_COLS + \
        ["r%d" % i for i in range(len(MANAGERS))]
    d = pd.DataFrame(f, columns=cols)
    d["kind"] = np.array(kinds)
    d = d.sort_values("t")
    d["yr"] = pd.to_datetime(d.t).dt.year
    TFN = [q[0] for q in PAIRS]
    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names),
                         rows=int(len(d)), seconds=int(time.time() - t0),
                         entries=[e[0] for e in ENTRIES], managers=[m[0] for m in MANAGERS],
                         charts=TFN))
    print("\n  EVERYTHING AT THE BACKBURNER  (%d names, %d rows, %.0fs)\n" % (
        len(names), len(d), time.time() - t0), flush=True)

    def stat(g, col):
        g = g[np.isfinite(g[col])]
        if len(g) < 60:
            return None
        return describe(g[col].values, (g[col] / g.risk_pct).values)

    def years_up(g, col):
        if not len(g):
            return 0, 0
        y = g.groupby("yr").apply(lambda x: (x[col] / x.risk_pct).mean(), include_groups=False)
        return int((y > 0).sum()), int(len(y))

    # ---- 1. the way in, held against every way out, per chart
    out["entries"] = {}
    for tf_i, tfn in enumerate(TFN):
        print("  THE WAY IN -- %s chart (avg R, then the control in brackets)" % tfn)
        print("    %-44s %8s %s" % ("", "n", "  ".join("%-16s" % m[0][:16] for m in MANAGERS)))
        for ev, (elab, _lv, _ad, _gp, _fr) in enumerate(ENTRIES):
            g = d[(d.tf == tf_i) & (d.ev == ev) & (d.ctrl == 0)]
            cc = d[(d.tf == tf_i) & (d.ev == ev) & (d.ctrl == 1)]
            if len(g) < 200:
                continue
            cells = []
            for mi in range(len(MANAGERS)):
                col = "r%d" % mi
                s1 = stat(g, col)
                s2 = stat(cc, col)
                cells.append("%+6.2fR (%+5.2f)" % ((s1["avg_R"] or 0) if s1 else 0,
                                                   (s2["avg_R"] or 0) if s2 else 0))
                out["entries"].setdefault(tfn, {}).setdefault(elab, {})[MANAGERS[mi][0]] = \
                    dict(setup=s1, control=s2)
            print("    %-44s %8d %s" % (elab[:44], len(g), "  ".join(cells)))
        print()

    # ---- 2. the psychology, on the best way in, per chart
    READS = [
        ("market washed out: breadth under 20%", lambda x: x.breadth < 0.20),
        ("breadth under 30 and STILL falling", lambda x: (x.breadth < 0.30) & (x.br_turn == 0)),
        ("breadth under 30 and turning up", lambda x: (x.breadth < 0.30) & (x.br_turn > 0.5)),
        ("the leader itself is 10%+ under its 200-day", lambda x: x.lead_dd <= -10),
        ("the name is 3+ normal bars under its own 200-day", lambda x: x.stretch <= -3),
        ("the name is 6+ normal bars under it (real fear)", lambda x: x.stretch <= -6),
        ("capitulation volume: 2x its own average", lambda x: x.cap_vol >= 2.0),
        ("capitulation volume: 3x", lambda x: x.cap_vol >= 3.0),
        ("at a NEW 1-year low (the name is broken)", lambda x: x.new_low > 0.5),
        ("NOT at a new low: a pullback in an uptrend", lambda x: (x.new_low == 0) & (x.on_200 > 0.5)),
        ("the retest of a low it already held", lambda x: x.retest > 0.5),
        ("momentum divergence at the low", lambda x: x.diverge > 0.5),
        ("a fear gap: opened under yesterday's low", lambda x: x.gap_down > 0.5),
        ("a long lower wick on the day", lambda x: x.wick >= 0.5),
        ("role reversal: the dip lands on an old high", lambda x: x.role_rev > 0.5),
        ("first dip in 120+ bars", lambda x: x.fresh >= 120),
        ("the name ran 4+ daily bars in 60 days", lambda x: x.run60 >= 4),
        ("strong against its own sector leader", lambda x: x.f_over > 0.5),
        ("washed out AND a pullback, not a new low",
         lambda x: (x.breadth < 0.30) & (x.new_low == 0)),
        ("washed out AND capitulation volume",
         lambda x: (x.breadth < 0.30) & (x.cap_vol >= 2.0)),
        ("washed out AND divergence", lambda x: (x.breadth < 0.30) & (x.diverge > 0.5)),
        ("washed out AND a long lower wick", lambda x: (x.breadth < 0.30) & (x.wick >= 0.5)),
    ]
    out["reads"] = {}
    for tf_i, tfn in enumerate(TFN):
        for mi, (mlab, _md, _cd) in enumerate(MANAGERS):
            col = "r%d" % mi
            base = d[(d.tf == tf_i) & (d.ev == 1)]
            g0 = base[base.ctrl == 0]
            s0 = stat(g0, col)
            if not s0:
                continue
            print("  THE PSYCHOLOGY -- %s chart, %s" % (tfn, mlab))
            print("    %-48s %7s %8s %8s %6s %7s %7s %7s" % (
                "read", "n", "avg", "middle", "won", "avg R", "ctrl R", "yrs up"))
            yu, yt = years_up(g0, col)
            print("    %-48s %7d %+7.3f%% %+7.3f%% %5.0f%% %+6.2fR %+6.2fR %4d/%-2d" % (
                "every dip (nothing asked of the market)", s0["n"], s0["avg"], s0["middle"],
                100 * s0["won"], s0["avg_R"] or 0,
                (stat(base[base.ctrl == 1], col) or {}).get("avg_R") or 0, yu, yt))
            got = []
            for rlab, fn in READS:
                gg = g0[fn(g0)]
                cc = base[(base.ctrl == 1) & fn(base)]
                s1 = stat(gg, col)
                if not s1:
                    continue
                s2 = stat(cc, col)
                yu, yt = years_up(gg, col)
                got.append((s1["avg_R"] or 0, rlab, s1, s2, yu, yt))
                out["reads"].setdefault(tfn, {}).setdefault(mlab, {})[rlab] = dict(setup=s1, control=s2,
                                                                                   years_up=yu, years=yt)
            for r_, rlab, s1, s2, yu, yt in sorted(got, key=lambda x: -x[0]):
                print("    %-48s %7d %+7.3f%% %+7.3f%% %5.0f%% %+6.2fR %+6.2fR %4d/%-2d" % (
                    rlab, s1["n"], s1["avg"], s1["middle"], 100 * s1["won"], r_,
                    (s2["avg_R"] or 0) if s2 else 0, yu, yt))
            print()
    json.dump(out, io.open(OUT, "w", encoding="utf-8"))
    try:
        d.to_parquet(os.path.splitext(OUT)[0] + "_rows.parquet")
    except Exception:
        pass
    for e_ in errs[:10]:
        print("  ERR " + e_)
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
