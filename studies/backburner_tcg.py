"""backburner_tcg.py -- the BackBurner as THE CHART GUYS define it, which this desk had never tested (2026-09-20).

His words: "this technique is so good but you keep jumping to conclusions". He was right. Every fast-chart test
here was "RSI at or under 30" on any name at any time. It came out flat, and I moved to the daily. TCG's own
definition (chartguys.com/educational-videos/backburner-trade-strategy, and their indicator page) is narrower in
every way that matters:

    THE RUN FIRST      "the first five-minute or first hourly oversold conditions following a substantial bull
                       run". You see a name skyrocketing, you do not chase it, you put it on the back burner.
    THE FIRST PRINT    the FIRST oversold after the high is the trade. Later prints are lower odds: that is the
                       trend weakening, not a dip in it.
    WHAT IT MARKS      "the first 5 min oversold conditions will mark an hourly higher low"; hourly oversold
                       marks a DAILY higher low. It is a way to buy the bigger chart's higher low.
    THE TREND INTACT   the long-term uptrend has to still be there.
    TECHNICAL ONLY     no news, no earnings behind the drop. (No earnings calendar on this machine yet: NOT
                       filtered here, said plainly.)
    LIQUID NAMES       Tesla-type names.
    30 THEN 20         first entry at RSI 30, a second if it reaches 20.
    BOTH WAYS          first overbought after a big drop marks a lower high.

So each oversold run on the entry chart is recorded with: which print it is since the bigger chart's last new
high (1st, 2nd, 3rd...), how long ago that high was, how big the run into it was, and whether the chart above
that is still in an uptrend. Every cut gets its own control (any bar carrying the same reads).

    pythonw studies/backburner_tcg.py --procs 8 --log logs/backburner_tcg.log
Writes validation/backburner_tcg.json and _rows.parquet
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
from scalein_study import describe        # noqa: E402

OUT = os.path.join("validation", "backburner_tcg.json")
# (entry chart, the chart whose higher low it marks, the chart that says the long-term trend is intact)
PAIRS = [("5m", "1h", "1d"), ("1h", "1d", "1w")]
HIGH_LOOK = 50          # "a new high" = the structure chart's highest high of its last 50 bars
RUN_LOOK = 20           # the run into it: travel over the structure chart's last 20 bars, in its normal bars
_SUS = os.path.join("validation", "suspect_names.json")
SUSPECT = {r["sym"] for r in json.load(io.open(_SUS, encoding="utf-8"))} if os.path.exists(_SUS) else set()

# (label, mode, chandelier, close 5m stock trades at the bell)
MANAGERS = [("all out at 2x the risk", "out2r", 3.0, True),
            ("sell everything when it prints overbought", "obout", 3.0, True),
            ("half off at 1x, rest on a chandelier 3", "chand1r", 3.0, True),
            ("HOLD for the bigger chart: half at 1x, stop walked under ITS higher lows", "walk", 3.0, False)]


def _last_extreme_time(sdf, side):
    """For each structure bar: the CLOSE time of the most recent bar that made a new 50-bar high (low for
    shorts), as int64 ns. Known only once that bar has closed."""
    h = sdf["High"].values.astype(float)
    l = sdf["Low"].values.astype(float)
    n = len(h)
    out = np.full(n, np.nan)
    last = np.nan
    ends = sdf.index.values.astype("int64")
    step = int(np.median(np.diff(ends))) if n > 2 else 0
    for i in range(n):
        if i >= HIGH_LOOK:
            if side > 0 and h[i] >= np.max(h[i - HIGH_LOOK:i]):
                last = float(ends[i] + step)
            if side < 0 and l[i] <= np.min(l[i - HIGH_LOOK:i]):
                last = float(ends[i] + step)
        out[i] = last
    return out, step


def _work(args):
    sym, kind, start = args
    try:
        frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    need = {x for p in PAIRS for x in p}
    frames = {k: v for k, v in frames.items() if k in need}
    if kind in ("stock", "etf"):
        frames = FR2.regular_hours(frames)
    rows, errs = [], []
    for tf_i, (tf, sf, tt) in enumerate(PAIRS):
        df, sdf, tdf = frames.get(tf), frames.get(sf), frames.get(tt)
        if df is None or sdf is None or tdf is None or len(df) < 500 or len(sdf) < 120 or len(tdf) < 60:
            continue
        try:
            o = df["Open"].values.astype(float); c = df["Close"].values.astype(float)
            h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
            n = len(c)
            tns = df.index.values.astype("int64")
            atr = P._atr(df)
            rsi = IND.rsi(c, 14)
            small12 = XM.ema(c, 12)
            # --- the structure chart: its pivots (the higher low this is meant to mark), its run, its last high
            sp = ST.pivots(sdf)
            slo = np.full(len(sdf), np.nan); shi = np.full(len(sdf), np.nan)
            a_ = b_ = np.nan; q = 0
            for k in range(len(sdf)):
                while q < len(sp) and sp[q][0] <= k:
                    if sp[q][3] == "low":
                        a_ = float(sp[q][2])
                    else:
                        b_ = float(sp[q][2])
                    q += 1
                slo[k] = a_; shi[k] = b_
            s_lo = L.align_to(df, tf, frames, sf, slo)
            s_hi = L.align_to(df, tf, frames, sf, shi)
            sc = sdf["Close"].values.astype(float)
            satr = P._atr(sdf)
            run = np.full(len(sc), np.nan)
            run[RUN_LOOK:] = (sc[RUN_LOOK:] - sc[:-RUN_LOOK]) / np.where(satr[RUN_LOOK:] > 0, satr[RUN_LOOK:], np.nan)
            s_run = L.align_to(df, tf, frames, sf, run)
            s_atr = L.align_to(df, tf, frames, sf, satr)
            s12 = L.align_to(df, tf, frames, sf, XM.ema(sc, 12))
            ext = {}
            for side in (1, -1):
                tarr, step = _last_extreme_time(sdf, side)
                ext[side] = (L.align_to(df, tf, frames, sf, tarr), step)
            # --- the trend chart: is the long-term trend intact
            tc = tdf["Close"].values.astype(float)
            e50 = XM.ema(tc, 50)
            up = np.zeros(len(tc)); dn = np.zeros(len(tc))
            up[5:] = ((tc[5:] > e50[5:]) & (e50[5:] > e50[:-5])).astype(float)
            dn[5:] = ((tc[5:] < e50[5:]) & (e50[5:] < e50[:-5])).astype(float)
            t_up = L.align_to(df, tf, frames, tt, up)
            t_dn = L.align_to(df, tf, frames, tt, dn)
            # --- liquidity, from the name's own bars: median dollars traded per entry bar
            dollars = float(np.nanmedian(c * df["Volume"].values.astype(float))) if "Volume" in df else 0.0
            bells = None
            if kind in ("stock", "etf") and tf in ("5m", "15m"):
                day = df.index.normalize().values
                bells = np.searchsorted(day, day, side="right") - 1
            cost = L.COST.get(kind, 0.05)
            os_ = rsi <= 30
            ob = rsi >= 70
            starts = {1: np.where(os_[1:] & ~os_[:-1])[0] + 1, -1: np.where(ob[1:] & ~ob[:-1])[0] + 1}
            stepc = max(80, n // 1500)
            for side in (1, -1):
                ext_t, sstep = ext[side]
                # WHICH PRINT IS THIS since the bigger chart's last new high: count oversold runs after it
                ordinal = {}
                cnt = 0
                cur = None
                for k in starts[side]:
                    t_ext = ext_t[k]
                    if not np.isfinite(t_ext):
                        ordinal[k] = 0
                        continue
                    if cur is None or t_ext != cur:
                        cur = t_ext
                        cnt = 0
                    cnt += 1
                    ordinal[k] = cnt
                ctrl_ks = np.arange(150 if side > 0 else 190, n - 8, stepc)
                for ks, is_ctrl in ((starts[side], 0), (ctrl_ks, 1)):
                    for k in ks:
                        e = k + 1
                        m_ = e - 1
                        if e < 150 or e + 6 >= n or not np.isfinite(atr[m_]) or atr[m_] <= 0:
                            continue
                        a = atr[m_]
                        # 30 THEN 20: a second unit if the print reaches 20 while it is still oversold
                        fills = [o[e]]; fill_bars = [e]; j = e
                        if not is_ctrl:
                            while j + 1 < n and len(fills) < 2:
                                j += 1
                                inside = (rsi[j - 1] <= 30) if side > 0 else (rsi[j - 1] >= 70)
                                if not inside:
                                    break
                                deep = (rsi[j - 1] <= 20) if side > 0 else (rsi[j - 1] >= 80)
                                if deep:
                                    fills.append(o[j]); fill_bars.append(j)
                        entry = float(np.mean(fills))
                        e_last = fill_bars[-1]
                        worst = min(fills) if side > 0 else max(fills)
                        # THE STOP IS THE BIGGER CHART'S STRUCTURE: if this marks its higher low, the last one
                        # must hold. No level under the position -> one of ITS normal bars under the fill.
                        lvl = s_lo[e_last] if side > 0 else s_hi[e_last]
                        sa = s_atr[e_last] if np.isfinite(s_atr[e_last]) else a
                        if np.isfinite(lvl) and ((side > 0 and lvl < worst) or (side < 0 and lvl > worst)):
                            stop = lvl - 0.15 * a if side > 0 else lvl + 0.15 * a
                        else:
                            stop = worst - sa if side > 0 else worst + sa
                        risk = abs(entry - stop)
                        if risk < 0.25 * a:
                            risk = 0.25 * a
                            stop = entry - side * risk
                        rp = risk / entry * 100
                        if rp < 3 * cost or rp > 25.0:
                            continue
                        t_ext = ext_t[m_]
                        since = (tns[m_] - t_ext) / sstep if (np.isfinite(t_ext) and sstep > 0) else np.nan
                        rn = s_run[m_]
                        rn = (rn if side > 0 else -rn) if np.isfinite(rn) else np.nan
                        intact = (t_up[m_] if side > 0 else t_dn[m_])
                        over12 = np.nan
                        if np.isfinite(s12[m_]):
                            over12 = 1.0 if ((side > 0 and c[m_] > s12[m_]) or (side < 0 and c[m_] < s12[m_])) else 0.0
                        res = []
                        for _lab, mode, chd, use_bell in MANAGERS:
                            bell = None if (bells is None or not use_bell) else bells[e_last]
                            trail = s_lo if side > 0 else s_hi
                            res.append(L.run_trade(kind, o, h, l, c, e_last, side, stop, risk, s12, trail, small12,
                                                   rsi, mode, bell, atr, chand=chd, entry_px=entry))
                        t_ = df.index[e]
                        rows.append([tf_i, side, float(ordinal.get(k, 0)) if not is_ctrl else -1.0,
                                     since if np.isfinite(since) else -1.0,
                                     rn if np.isfinite(rn) else np.nan,
                                     float(intact) if np.isfinite(intact) else np.nan,
                                     over12, float(len(fills)), rp, dollars, float(t_.value), is_ctrl] + res)
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    if not rows:
        return None, errs
    return (np.asarray(rows, dtype=np.float64), kind, sym), errs


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
    names = R._by_size([(s_, k_) for s_, k_ in B.universe() if k_ != "forex" and s_ not in SUSPECT])
    if "--focus" in sys.argv:
        import focus
        names = [(s_, k_) for s_, k_ in focus.names() if focus.have(s_, k_)]
    R.quiet_workers()
    parts, kinds, syms, errs, done = [], [], [], [], 0
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got, err in ex.map(_work, [(s_, k_, start) for s_, k_ in names], chunksize=1):
            done += 1
            errs += err or []
            if got is not None:
                parts.append(got[0])
                kinds += [got[1]] * len(got[0])
                syms += [got[2]] * len(got[0])
            if done % 100 == 0 or done == len(names):
                print("  %d/%d names  (%.0fs)" % (done, len(names), time.time() - t0), flush=True)
    cols = ["tf", "side", "ordinal", "since", "run", "intact", "over12", "units", "risk_pct", "dollars", "t",
            "ctrl"] + ["r%d" % i for i in range(len(MANAGERS))]
    d = pd.DataFrame(np.concatenate(parts), columns=cols)
    d["kind"] = np.array(kinds)
    d["sym"] = np.array(syms)
    d = d.sort_values("t")
    d["yr"] = pd.to_datetime(d.t).dt.year
    # liquid = the top third of names by dollars traded, within each market
    liq = d.groupby(["kind", "sym"]).dollars.first().reset_index()
    liq["liquid"] = liq.groupby("kind").dollars.transform(lambda x: x >= x.quantile(2 / 3)).astype(float)
    d = d.merge(liq[["kind", "sym", "liquid"]], on=["kind", "sym"], how="left")
    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names),
                         rows=int(len(d)), seconds=int(time.time() - t0),
                         managers=[m[0] for m in MANAGERS], pairs=["%s marks the %s" % (p[0], p[1]) for p in PAIRS]),
               tables={})
    print("\n  THE BACKBURNER, THE CHART GUYS' WAY  (%d names, %d rows, %.0fs)\n" % (
        len(names), len(d), time.time() - t0), flush=True)

    def stat(g, col):
        g = g[np.isfinite(g[col])]
        if len(g) < 80:
            return None
        return describe(g[col].values, (g[col] / g.risk_pct).values)

    def yrs(g, col):
        if not len(g):
            return 0, 0
        y = g.groupby("yr").apply(lambda x: (x[col] / x.risk_pct).mean(), include_groups=False)
        return int((y > 0).sum()), int(len(y))

    CUTS = [
        ("every oversold print (what I tested before)", lambda x, c: x.ctrl == c),
        ("the FIRST print since the bigger chart's new high", lambda x, c: (x.ctrl == c) & ((x.ordinal == 1) | (c == 1))),
        ("the SECOND print", lambda x, c: (x.ctrl == c) & ((x.ordinal == 2) | (c == 1))),
        ("the THIRD or later", lambda x, c: (x.ctrl == c) & ((x.ordinal >= 3) | (c == 1))),
        ("first print, the high under 12 bigger bars ago", lambda x, c: (x.ctrl == c) & ((x.ordinal == 1) | (c == 1)) & (x.since >= 0) & (x.since <= 12)),
        ("first print, AFTER A RUN of 4+ of its normal bars", lambda x, c: (x.ctrl == c) & ((x.ordinal == 1) | (c == 1)) & (x.run >= 4)),
        ("first print, a run of 8+", lambda x, c: (x.ctrl == c) & ((x.ordinal == 1) | (c == 1)) & (x.run >= 8)),
        ("first print, run 4+, long-term trend INTACT", lambda x, c: (x.ctrl == c) & ((x.ordinal == 1) | (c == 1)) & (x.run >= 4) & (x.intact > 0.5)),
        ("first print, run 4+, trend intact, LIQUID name", lambda x, c: (x.ctrl == c) & ((x.ordinal == 1) | (c == 1)) & (x.run >= 4) & (x.intact > 0.5) & (x.liquid > 0.5)),
        ("THE FULL TCG SETUP, high under 12 bars ago too", lambda x, c: (x.ctrl == c) & ((x.ordinal == 1) | (c == 1)) & (x.run >= 4) & (x.intact > 0.5) & (x.liquid > 0.5) & (x.since >= 0) & (x.since <= 12)),
        ("NOT a backburner: no run (under 1), trend not intact", lambda x, c: (x.ctrl == c) & (x.run < 1) & (x.intact < 0.5)),
    ]
    for tf_i, (tf, sf, tt) in enumerate(PAIRS):
        for side, sname in ((1, "LONG: first oversold after a run up"), (-1, "SHORT: first overbought after a run down")):
            base = d[(d.tf == tf_i) & (d.side == side)]
            for mi, (mlab, _m, _c, _b) in enumerate(MANAGERS):
                col = "r%d" % mi
                key = "%s -> %s | %s | %s" % (tf, sf, "long" if side > 0 else "short", mlab)
                print("  %s chart marking the %s's %s -- %s\n    %s" % (
                    tf, sf, "higher low" if side > 0 else "lower high", sname, mlab))
                print("    %-52s %7s %8s %8s %5s %7s %7s %7s" % (
                    "cut", "n", "avg", "middle", "won", "avg R", "ctrl R", "yrs up"))
                out["tables"][key] = {}
                for lab, fn in CUTS:
                    g = base[fn(base, 0)]
                    cc = base[fn(base, 1)]
                    s1, s2 = stat(g, col), stat(cc, col)
                    if not s1:
                        continue
                    yu, yt = yrs(g[np.isfinite(g[col])], col)
                    print("    %-52s %7d %+7.3f%% %+7.3f%% %4.0f%% %+6.2fR %+6.2fR %4d/%-2d" % (
                        lab[:52], s1["n"], s1["avg"], s1["middle"], 100 * s1["won"], s1["avg_R"] or 0,
                        (s2["avg_R"] or 0) if s2 else 0, yu, yt))
                    out["tables"][key][lab] = dict(setup=s1, control=s2, years_up=yu, years=yt)
                    for kd in ("stock", "crypto"):
                        sk = stat(g[g.kind == kd], col)
                        ck = stat(cc[cc.kind == kd], col)
                        if sk and lab.startswith(("THE FULL", "the FIRST", "every")):
                            print("        %-48s %7d %+7.3f%% %+7.3f%% %4.0f%% %+6.2fR %+6.2fR" % (
                                kd, sk["n"], sk["avg"], sk["middle"], 100 * sk["won"], sk["avg_R"] or 0,
                                (ck["avg_R"] or 0) if ck else 0))
                            out["tables"][key][lab][kd] = dict(setup=sk, control=ck)
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
