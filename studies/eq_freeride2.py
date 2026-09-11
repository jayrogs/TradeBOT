"""eq_freeride2.py -- the EQ free ride after his grading of /eqfree (2026-09-10).

What his notes said, and what changed here:
  * "wtf 91% sold? what? who is deciding this? the wins are meaningless if you only have 9% position size"
      -> the partial is a FIXED size at the far line (a third, or half) and the rest's stop moves to the
         entry. The old sizing (sell whatever share makes the rest free) is kept for comparison. Every
         trade is also bucketed by how far the far line is, in units of the risk.
  * "a HL then an LH in the next candle immediately after ... thats an anomaly, not an eq"
      -> measured two ways: any spacing (the old rule) and pivots at least 3 bars apart.
  * "the candle bodies look so weird ... must not be much volume ... was this after hours?" (V 4h: 13 of 17
    bars outside regular hours), "tons of gaps between candles" (ORCL 1h: 18 of 31), "hideous" (NVDA 5m:
    23 of 23, volume 6% of normal)
      -> stocks and ETFs also run on REGULAR-HOURS bars only (5m/15m 09:30-16:00; the 09:00 hourly bar kept;
         4h rebuilt from those hours). He asked to trade all hours (#17), so both are measured.
  * "did this buy, after a HH?" (INJ daily) -> fixed in eq_coil.py: an EQ that broke in the two bars before
    its last pivot confirmed is no longer declared.
Direction: the daily chart against its 50 EMA (8 of 8 on the obvious trends), and 50 + 200 agreeing.
Entry: the next open after a higher low (or lower high) confirms inside the live EQ. Stop a wick through it.

    pythonw studies/eq_freeride2.py --procs 20 --log logs/eq_freeride2.log
Writes validation/eq_freeride2.json. pics_eqfree.py draws trades from trades() below.
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
import eq_coil as EC              # noqa: E402
import eq_freeride as FR          # noqa: E402

TFS = ["5m", "15m", "1h", "4h", "1d"]
CAP_DAYS = 30
TRAIL = 5.0
OUT = os.path.join("validation", "eq_freeride2.json")
HOURS = ["all hours", "regular hours"]
GAPS = [0, 3]
GAP_NAMES = {"0": "any spacing (the old rule)", "3": "pivots at least 3 bars apart"}
MODES = [("a third at the far line, rest to breakeven", "third"),
         ("half at the far line, rest to breakeven", "half"),
         ("all out at the far line", "all"),
         ("hold for the break, no partial", "hold"),
         ("old sizing: sell what makes the rest free", "old")]
SIDES = ["long", "short"]
TAGS = ["with", "against", "no trend"]
RRB = ["far line under 1x the risk", "far line 1-2x the risk", "far line 2x the risk or more"]
ERAS = ["before", "first", "second"]
KINDS = ["stock", "etf", "crypto", "futures"]
DIMS = [("hours", HOURS), ("gap", [str(g) for g in GAPS]), ("variant", [m[0] for m in MODES]), ("tf", TFS),
        ("side", SIDES), ("h_ema_daily", TAGS), ("h_ema_both", TAGS), ("rr", RRB), ("era", ERAS), ("kind", KINDS)]
SIZES = [len(v) for _, v in DIMS]


def encode(vals):
    code = 0
    for v, size in zip(vals, SIZES):
        code = code * size + v
    return code


def regular_hours(frames):
    """Stock frames with only regular-hours bars: 5m/15m 09:30-16:00, the 1h bars stamped 09:00-15:00
    (the 09:00 bar is mostly the open), and the 4h rebuilt from those hourly bars (09:00-13:00, 13:00-16:00)."""
    out = dict(frames)
    for tf in ("5m", "15m"):
        d = frames.get(tf)
        if d is not None and len(d):
            m = d.index.hour * 60 + d.index.minute
            out[tf] = d[(m >= 570) & (m < 960)]
    d = frames.get("1h")
    if d is not None and len(d):
        hh = d.index.hour
        r1 = d[(hh >= 9) & (hh <= 15)]
        out["1h"] = r1
        out["4h"] = r1.resample("4h", offset="1h").agg(
            {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
    return out


def share_of(mode, risk, gain):
    return {"third": 1.0 / 3, "half": 0.5, "all": 1.0, "old": risk / (risk + gain)}.get(mode, 0.0)


def walk2(sgn, c, o, h, l, atr, e, fill, stop, target, n, cap, day, mode):
    """From the fill at bar e. The stop is checked before the far line on every bar (the careful reading).
    third / half / old: sell that share at the far line and move the rest's stop to the entry.
    all: everything off at the far line. hold: no partial. Past the far line our way, trail 5 bars.
    Returns (exit bar, exit price for the whole position, reached the far line, bar it was reached, why)."""
    risk = abs(fill - stop)
    gain = abs(target - fill)
    if risk <= 0 or gain <= 0:
        return None
    share = share_of(mode, risk, gain) if mode != "all" else 0.0
    took = False
    took_bar = None
    broke = False
    stop_now = stop
    best = c[e]
    for k in range(e, n - 1):
        a = atr[k] if np.isfinite(atr[k]) else 0.0
        if (sgn > 0 and l[k] < stop_now) or (sgn < 0 and h[k] > stop_now):
            px = o[k + 1]
            why = "the rest stopped at breakeven" if took else "stopped: a wick through the signal pivot"
            return k, (share * target + (1 - share) * px) if took else px, took, took_bar, why
        if not took and ((sgn > 0 and h[k] >= target) or (sgn < 0 and l[k] <= target)):
            if mode == "all":
                return k, target, True, k, "all out at the far line"
            if share > 0:
                took = True
                took_bar = k
                stop_now = fill
        if not broke:
            tol = P.SAME_LEVEL_ATR * a
            if (sgn > 0 and h[k] > target + tol) or (sgn < 0 and l[k] < target - tol):
                broke = True
                best = c[k]
        if broke:
            best = max(best, c[k]) if sgn > 0 else min(best, c[k])
            if (sgn > 0 and c[k] < best - TRAIL * a) or (sgn < 0 and c[k] > best + TRAIL * a):
                px = o[k + 1]
                return k, (share * target + (1 - share) * px) if took else px, took, took_bar, "trailed out after the EQ broke our way"
        if day is not None and k + 1 < n and day[k + 1] != day[k]:
            return k, (share * target + (1 - share) * c[k]) if took else c[k], took, took_bar, "closed at the bell"
        if k - e >= cap:
            px = o[k + 1]
            return k, (share * target + (1 - share) * px) if took else px, took, took_bar, "out at the 30-day limit"
    return None


def trades(kind, tf, df, frames, start, gap, modes=None):
    """Every trade on one chart, one dict per trade per exit variant. `frames` supplies the daily/weekly
    chart for the direction read (always the all-hours frames: a daily bar is the whole session)."""
    if df is None or len(df) < 300:
        return
    c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    floor, ceil, cid, rs, atr = EC.coils(df, min_gap=gap)
    if not rs:
        return
    piv = ST.pivots(df)
    pcis = [pv[0] for pv in piv]
    big = "1d" if tf in ("5m", "15m", "1h", "4h") else "1w"
    e50 = FR.ema_of(df, tf, frames, big)
    e200 = FR.ema_of(df, tf, frames, big, span=200, slope=False)
    agree = (e50 == e200) & np.isin(e50.astype(str), ["up", "down"])
    both = np.where(agree, e50, "none").astype(object)
    cost = B.CLASS_COST.get(kind, B.COST)
    cap = CAP_DAYS * B.BARS_DAY[tf]
    lr = np.diff(np.log(c), prepend=np.log(c[0]))
    drift = float(np.nanmean(lr[np.isfinite(lr)]))
    mid = start + (pd.Timestamp.now() - start) / 2
    day = df.index.normalize().values if kind in ("stock", "etf") and tf in ("5m", "15m") else None
    kind_i = KINDS.index(kind) if kind in KINDS else 0
    tf_i = TFS.index(tf)
    gap_i = GAPS.index(gap)
    for r in rs:
        if not r["tradeable"] or r["born"] < 60:
            continue
        i, end = r["confirm"], r["end"]
        k0 = bisect.bisect_left(pcis, i)
        k1 = bisect.bisect_left(pcis, end)
        long_pv = next((pv for pv in piv[k0:k1] if pv[3] == "low" and pv[4] in ("HL", "EL")), None)
        short_pv = next((pv for pv in piv[k0:k1] if pv[3] == "high" and pv[4] in ("LH", "EH")), None)
        for side_i, pv in ((0, long_pv), (1, short_pv)):
            if pv is None:
                continue
            ci, j, p, kd, lab = pv
            e = ci + 1
            if e >= n - 1:
                continue
            a = atr[ci] if np.isfinite(atr[ci]) and atr[ci] > 0 else np.nan
            if not np.isfinite(a):
                continue
            tol = P.SAME_LEVEL_ATR * a
            sgn = 1 if side_i == 0 else -1
            fill = o[e]
            if side_i == 0:
                stop = p - tol
                target = ceil[ci]
                if not np.isfinite(target) or not (stop < fill < target):
                    continue
            else:
                stop = p + tol
                target = floor[ci]
                if not np.isfinite(target) or not (target < fill < stop):
                    continue
            side = SIDES[side_i]
            t = df.index[e]
            risk = abs(fill - stop); gain = abs(target - fill)
            rr_ = gain / risk
            base = dict(side=side, side_i=side_i, tf_i=tf_i, gap_i=gap_i, kind_i=kind_i,
                        era_i=0 if t < start else 1 if t < mid else 2,
                        tag1=TAGS.index(FR.tag(side, e50[ci])), tag2=TAGS.index(FR.tag(side, both[ci])),
                        rr=rr_, rr_i=0 if rr_ < 1 else 1 if rr_ < 2 else 2,
                        born=int(r["born"]), end=int(end), e=int(e), pj=int(j), pivot=lab, t=str(t),
                        fill=float(fill), stop=float(stop), target=float(target),
                        e50=str(e50[ci]), e200=str(e200[ci]),
                        eq_lo=float(np.min(l[r["born"]:end + 1])), eq_hi=float(np.max(h[r["born"]:end + 1])))
            for mode_i, (vname, mode) in enumerate(MODES):
                if modes is not None and vname not in modes:
                    continue
                res = walk2(sgn, c, o, h, l, atr, e, fill, stop, target, n, cap, day, mode)
                if res is None:
                    continue
                xb, xpx, took, took_bar, why = res
                held = xb + 1 - e
                yield dict(base, mode_i=mode_i, variant=vname, mode=mode, share=share_of(mode, risk, gain),
                           xb=int(xb), took=took, took_bar=took_bar, why=why, held=int(held),
                           ret=float(sgn * (xpx / fill - 1) - cost),
                           drift=float(sgn * (np.exp(drift * held) - 1) - cost))


def _work(args):
    sym, kind, start = args
    try:
        frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    codes, rets, drifts, tooks, helds = [], [], [], [], []
    errs = []
    sets = [(0, frames)]
    if kind in ("stock", "etf"):
        try:
            sets.append((1, regular_hours(frames)))
        except Exception as ex:
            errs.append("%s %s regular hours: %s" % (kind, sym, ex))
    for hours_i, fr in sets:
        for gap in GAPS:
            for tf in TFS:
                if hours_i == 1 and tf == "1d":
                    continue                       # a daily bar is the whole session either way
                try:
                    for x in trades(kind, tf, fr.get(tf), frames, start, gap):
                        codes.append(encode([hours_i, x["gap_i"], x["mode_i"], x["tf_i"], x["side_i"], x["tag1"],
                                             x["tag2"], x["rr_i"], x["era_i"], x["kind_i"]]))
                        rets.append(x["ret"]); drifts.append(x["drift"])
                        tooks.append(1 if x["took"] else 0); helds.append(x["held"])
                except Exception as ex:
                    errs.append("%s %s %s %s gap%d: %s" % (kind, sym, tf, HOURS[hours_i], gap, ex))
    if not codes:
        return None, errs
    return (np.asarray(codes, dtype=np.int32), np.asarray(rets, dtype=np.float32),
            np.asarray(drifts, dtype=np.float32), np.asarray(tooks, dtype=np.int8),
            np.asarray(helds, dtype=np.int32)), errs


def stats(ret, drift, took, held):
    if len(ret) < 20:
        return None
    s = np.sort(ret)
    cut = s[:max(1, len(s) - max(1, len(s) // 50))]
    return dict(n=int(len(ret)), mean=float(ret.mean()), median=float(np.median(ret)), trimmed=float(cut.mean()),
                edge=float((ret - drift).mean()), won=float((ret > 0).mean()), reached=float(took.mean()),
                held=float(held.mean()))


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
    names = [(s_, k_) for s_, k_ in B.universe() if k_ != "forex"]
    names = R._by_size(names)
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
    code = np.concatenate([p_[0] for p_ in parts]); ret = np.concatenate([p_[1] for p_ in parts]).astype(float)
    drift = np.concatenate([p_[2] for p_ in parts]).astype(float); took = np.concatenate([p_[3] for p_ in parts])
    held = np.concatenate([p_[4] for p_ in parts])
    print("  %d trade rows, folding  (%.0fs)" % (len(ret), time.time() - t0), flush=True)
    rem = code.astype(np.int64)
    cols = {}
    for (name, vals), size in reversed(list(zip(DIMS, SIZES))):
        cols[name] = (rem % size).astype(np.int16)
        rem = rem // size
    f = pd.DataFrame(cols)
    f["ret"] = ret; f["drift"] = drift; f["took"] = took; f["held"] = held
    names_of = dict(DIMS)

    def table(sub, keys):
        out = {}
        for k, g in sub.groupby(keys, sort=False):
            k = k if isinstance(k, tuple) else (k,)
            st = stats(g["ret"].values, g["drift"].values, g["took"].values, g["held"].values)
            if st:
                out[" | ".join(names_of[c_][int(v)] for c_, v in zip(keys, k))] = st
        return out

    base = ["hours", "gap", "variant", "tf"]
    w = f[f.h_ema_daily == 0]
    res = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names), tfs=TFS,
                         hours=HOURS, gaps=[str(g) for g in GAPS], gap_names=GAP_NAMES,
                         variants=[m[0] for m in MODES], tags=TAGS, rr=RRB, eras=ERAS, rows=int(len(f)),
                         seconds=int(time.time() - t0)),
               base=table(f, base),
               by_h_ema_daily=table(f, base + ["h_ema_daily"]),
               by_h_ema_both=table(f, base + ["h_ema_both"]),
               rr_with=table(w, base + ["rr"]),
               era_with=table(w, base + ["era"]),
               kind_with=table(w, base + ["kind"]),
               side_with=table(w, base + ["side"]))
    json.dump(res, open(OUT, "w"))
    print()
    print("  EQ FREE RIDE, AFTER HIS GRADING  %d names, %d rows  (%.0fs)" % (len(names), len(f), time.time() - t0))
    print("  trades WITH the daily 50 EMA:  average / middle / far line reached / n")
    for tf in TFS:
        print("   %s" % tf)
        for hrs in HOURS:
            for g in GAPS:
                for vname, _ in MODES[:4]:
                    v = res["by_h_ema_daily"].get("%s | %s | %s | %s | with" % (hrs, g, vname, tf))
                    if v:
                        print("     %-13s %-30s %-44s avg %+6.2f%%  mid %+6.2f%%  %3.0f%%  n%-7d" % (
                            hrs, GAP_NAMES[str(g)], vname, 100 * v["mean"], 100 * v["median"], 100 * v["reached"], v["n"]))
    if log:
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
