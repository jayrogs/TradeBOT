"""eq_anticipate.py -- the EQ the way The Chart Guys trade it: ANTICIPATED, not detected (2026-09-21).

From the full read of their videos (TCG_METHOD.md 19e-19i; 58S_UyhOa7Q, zFzDEvWsPk8, rFzRJDCzh7g, EUtyFJ9WRxE):

    a BIG MOVE  ->  a swing back that takes 50% OR MORE of it  ->  an equilibrium is now the most likely thing,
    so scout the HIGHER LOW (after a drop) or the LOWER HIGH (after a run), timed on the chart two sizes down,
    and aim at the other line. Under 38.2% the same picture is a FLAG and playing off the floor gets stopped out.
    Volume should be dropping off while it forms.

Jay's own words for the trade inside it: "the idea is buying the floor and selling the LH ideally to make a risk
free position". My detector (eq_coil) needs TWO confirmed pairs before it says "EQ", by which time about three bars
are left (#26b). This one acts after the FIRST swing back -- when they do.

THE STRUCTURE, on the idea chart (1d, 4h, 1h), from confirmed pivots only:
    long:  A a pivot high, B the pivot low after it, C the next pivot high, C under A (a lower high).
           leg = A-B in normal bars.  retrace = (C-B)/(A-B).
    short: the mirror (A low, B high, C a higher low).
Everything is recorded; "their EQ" (leg 4+, retrace 50%+) is a cut, and "their flag" and small legs are printed
beside it, so the definition's worth is visible (rule 38).

THREE WAYS IN, all after C has CONFIRMED on the idea chart, all dead once price takes out B or C first:
    confirm   the next open after a higher low D confirms on the IDEA chart (how every study here did it; late)
    small     the first higher low that confirms on the TIMING chart once price has given back 38.2%+ of the
              bounce (1d<-1h, 4h<-15m, 1h<-5m).  Stop under the pullback's low.
    touch     the first touch of RSI 30 on the TIMING chart during the pullback -- the backburner, which is
              what they say it is for ("5 minute oversold marks the hourly higher low").  Stop under B.
ONE trade per structure per way in.

OUT: all out just before C (they exit a little BEFORE the level, never at it), or half there and the rest for A
(the start of the big move) with the stop left where it was -- half made 1x, half can lose 1x: risk free by
arithmetic, their definition. Stops fill at the stop or the open if it gaps; a bar that touches both counts as
the stop. Risk band 3x the round-trip cost to 4 idea-chart normal bars.

    pythonw studies/eq_anticipate.py --procs 8 --log logs/eq_anticipate.log
Writes validation/eq_anticipate.json (+ _rows.parquet)
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
import trend_ride as R            # noqa: E402
import panel as P                 # noqa: E402
import structure as ST            # noqa: E402
import indicators as IND          # noqa: E402
import eq_freeride as FR          # noqa: E402
import eq_freeride2 as FR2        # noqa: E402
import backburner_dan as DAN      # noqa: E402

OUT = os.path.join("validation", "eq_anticipate.json")
PAIRS = [("1d", "1h"), ("4h", "15m"), ("1h", "5m")]          # idea chart, timing chart
WAYS = ["confirm", "small", "touch"]
WAIT_X = 3.0                  # how long the higher low may take: this many times the bounce's own length
CAP_X = 60                    # a trade is closed after this many idea-chart bars
NEAR = 0.15                   # exit this share of a normal bar BEFORE the far line
GIVEBACK = 0.382              # the pullback must have taken back this much of the bounce before "small" may fire
DETAIL = None                  # pics_eqanticipate sets this to a list to get every trade's bars and prices back
COLS = ["pair", "side", "way", "leg", "retrace", "fade", "rr", "risk", "tag", "kind", "yr", "era", "t",
        "depth", "r_all", "r_half", "reached", "held"]


def _walk(side, o, h, l, e, fill, stop, tgt, far, last, cost):
    """Bar by bar on the timing chart from the bar AFTER the fill bar's open.
    Returns (all-out %, half %, reached, the all-out exit bar, the all-out exit price)."""
    r_all = r_half = None
    took = False
    xb, xpx = last, o[last]
    for j in range(e, last + 1):
        if side > 0:
            hit_stop = l[j] <= stop
            px_stop = min(o[j], stop) if j > e else stop
            hit_t = h[j] >= tgt
            hit_f = h[j] >= far
        else:
            hit_stop = h[j] >= stop
            px_stop = max(o[j], stop) if j > e else stop
            hit_t = l[j] <= tgt
            hit_f = l[j] <= far
        if hit_stop:                                   # the stop first, whatever else the bar did
            g = side * (px_stop - fill) / fill * 100
            if r_all is None:
                r_all = g - cost
                xb, xpx = j, px_stop
            r_half = (0.5 * side * (tgt - fill) / fill * 100 + 0.5 * g - cost) if took else (g - cost)
            return r_all, r_half, took, xb, xpx
        if hit_t and not took:
            took = True
            if r_all is None:
                r_all = side * (tgt - fill) / fill * 100 - cost
                xb, xpx = j, tgt
        if took and hit_f:
            r_half = 0.5 * side * (tgt - fill) / fill * 100 + 0.5 * side * (far - fill) / fill * 100 - cost
            return r_all, r_half, took, xb, xpx
    g = side * (o[last] - fill) / fill * 100
    if r_all is None:
        r_all = g - cost
    r_half = (0.5 * side * (tgt - fill) / fill * 100 + 0.5 * g - cost) if took else (g - cost)
    return r_all, r_half, took, xb, xpx


def _work(args):
    sym, kind, start = args
    try:
        frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    need = {x for p in PAIRS for x in p} | {"1d", "1w"}
    allf = {k: v for k, v in frames.items() if k in need}
    reg = allf
    if kind in ("stock", "etf"):
        try:
            reg = FR2.regular_hours(allf)              # their rule: an extended-hours print does not count
        except Exception:
            reg = allf
    cost = B.CLASS_COST.get(kind, B.COST) * 100
    mid = start + (pd.Timestamp.now() - start) / 2
    rows, errs = [], []
    for p_i, (T, t) in enumerate(PAIRS):
        D, d = reg.get(T), reg.get(t)
        if D is None or d is None or len(D) < 200 or len(d) < 500:
            continue
        try:
            Dh = D["High"].values.astype(float); Dl = D["Low"].values.astype(float)
            Do = D["Open"].values.astype(float)
            Dv = D["Volume"].values.astype(float) if "Volume" in D else None
            Datr = P._atr(D)
            Dt = D.index.values.astype("int64")
            nD = len(D)
            do = d["Open"].values.astype(float); dh = d["High"].values.astype(float)
            dl = d["Low"].values.astype(float); dc = d["Close"].values.astype(float)
            dt = d.index.values.astype("int64")
            nd = len(d)
            datr = P._atr(d)
            rsi, au, ad = IND.rsi_parts(dc, 14)
            p30 = DAN.rsi_price(dc, au, ad, 30); p70 = DAN.rsi_price(dc, au, ad, 70)
            prev = np.r_[np.nan, rsi[:-1]]
            with np.errstate(invalid="ignore"):
                touch = {1: np.isfinite(p30) & (dl <= p30) & (prev > 30),
                         -1: np.isfinite(p70) & (dh >= p70) & (prev < 70)}
            nxt = {}
            for sd in (1, -1):                          # the next bar at or after k where the touch happens
                arr_ = np.full(nd + 1, nd, dtype=np.int64)
                idx_ = np.flatnonzero(touch[sd])
                arr_[idx_] = idx_
                nxt[sd] = np.minimum.accumulate(arr_[::-1])[::-1]
            piv = ST.pivots(D)                          # (confirm, form, price, kind, label), confirm order
            spiv = ST.pivots(d)
            s_low = [(int(x[0]), int(x[1]), float(x[2]), x[4]) for x in spiv if x[3] == "low"]
            s_high = [(int(x[0]), int(x[1]), float(x[2]), x[4]) for x in spiv if x[3] == "high"]
            s_low_ci = np.array([x[0] for x in s_low]); s_high_ci = np.array([x[0] for x in s_high])
            big = "1d" if T in ("1h", "4h") else "1w"
            e50 = FR.ema_of(D, T, allf, big)
            per_T = max(1, int(round(nd / max(nD, 1))))   # timing bars in one idea bar, roughly
            for i in range(2, len(piv)):
                ciA, jA, pA, kA, _ = piv[i - 2]
                ciB, jB, pB, kB, _ = piv[i - 1]
                ciC, jC, pC, kC, _ = piv[i]
                if not (kA == kC and kA != kB):
                    continue
                side = 1 if kB == "low" else -1
                pA, pB, pC = float(pA), float(pB), float(pC)
                if side > 0 and not (pB < pC < pA):
                    continue                            # C must be a LOWER high: over A is a trend change, not an EQ
                if side < 0 and not (pB > pC > pA):
                    continue
                ciC = int(ciC); jA = int(jA); jB = int(jB); jC = int(jC)
                if ciC + 1 >= nD or jA < 30:
                    continue
                a = Datr[ciC]
                if not (np.isfinite(a) and a > 0):
                    continue
                leg = abs(pA - pB) / a
                retr = abs(pC - pB) / abs(pA - pB)
                fade = np.nan
                if Dv is not None and jC > jB > jA:
                    v1 = np.nanmean(Dv[jA:jB + 1]); v2 = np.nanmean(Dv[jB + 1:ciC + 1])
                    if np.isfinite(v1) and v1 > 0 and np.isfinite(v2):
                        fade = float(v2 / v1)
                wait = int(max(6, WAIT_X * (jC - jB)))
                endT = min(nD - 1, ciC + wait)
                # the structure dies on the idea chart when B or C is taken out
                if side > 0:
                    bad = (Dl[ciC + 1:endT + 1] < pB) | (Dh[ciC + 1:endT + 1] > pC)
                else:
                    bad = (Dh[ciC + 1:endT + 1] > pB) | (Dl[ciC + 1:endT + 1] < pC)
                killed = bool(bad.any())
                deadT = ciC + 1 + int(np.argmax(bad)) if killed else endT
                s0 = int(np.searchsorted(dt, Dt[ciC + 1], side="left"))
                s1 = int(np.searchsorted(dt, Dt[deadT], side="left"))      # timing bars before the bar that killed it
                if s0 >= nd - 5 or s1 <= s0:
                    continue
                tgt = pC - side * NEAR * a
                far = pA - side * NEAR * a
                tolT = P.SAME_LEVEL_ATR * a
                span = abs(pC - pB)
                t_entry = D.index[ciC + 1]
                base = [p_i, side, 0, leg, retr, fade, 0, 0, FR2.TAGS.index(FR.tag("long" if side > 0 else "short", e50[ciC])),
                        FR2.KINDS.index(kind) if kind in FR2.KINDS else 0, float(t_entry.year),
                        0 if t_entry < start else 1 if t_entry < mid else 2, float(t_entry.value)]

                def book(way_i, e, fill, stop):
                    if e >= nd - 2:
                        return False
                    if (side > 0 and not (stop < fill < tgt)) or (side < 0 and not (tgt < fill < stop)):
                        return False
                    risk = abs(fill - stop)
                    rp = risk / fill * 100
                    if rp < 3 * cost or risk > 4 * a:
                        return False
                    last = min(nd - 1, e + CAP_X * per_T)
                    ra, rh, took, xb, xpx = _walk(side, do, dh, dl, e, fill, stop, tgt, far, last, cost)
                    if DETAIL is not None:
                        DETAIL.append(dict(sym=sym, kind=kind, pair=p_i, side=side, way=way_i, jA=jA, jB=jB, jC=jC,
                                           ciC=ciC, pA=pA, pB=pB, pC=pC, e=int(e), fill=float(fill), stop=float(stop),
                                           tgt=float(tgt), far=float(far), xb=int(xb), xpx=float(xpx), leg=float(leg),
                                           retrace=float(retr), fade=float(fade) if np.isfinite(fade) else None,
                                           rr=float(abs(tgt - fill) / risk), risk_pct=float(rp), pct=float(ra),
                                           R=float(ra / rp), t=str(d.index[min(e, nd - 1)]),
                                           tA=str(D.index[jA]), tB=str(D.index[jB]), tC=str(D.index[jC]),
                                           t_e=str(d.index[min(e, nd - 1)]), t_x=str(d.index[min(xb, nd - 1)])))
                    row = list(base)
                    row[2] = way_i; row[6] = abs(tgt - fill) / risk; row[7] = rp
                    rows.append(row + [abs(pC - fill) / span, ra, rh, 1.0 if took else 0.0, 0.0])
                    return True

                # WAY 1: the higher low confirms on the idea chart
                for q in range(i + 1, min(len(piv), i + 4)):
                    ciD, jD, pD, kD, _ = piv[q]
                    if int(ciD) > endT or (killed and int(ciD) >= deadT):
                        break
                    if kD == kB and ((side > 0 and float(pD) > pB) or (side < 0 and float(pD) < pB)) and int(ciD) + 1 < nD:
                        e = int(np.searchsorted(dt, Dt[int(ciD) + 1], side="left"))
                        if e < nd:
                            book(0, e, do[e], float(pD) - side * tolT)
                        break
                # the pullback on the timing chart, bar by bar
                lo = np.minimum.accumulate(dl[s0:s1]) if side > 0 else np.maximum.accumulate(dh[s0:s1])
                # WAY 2: the first small-chart higher low once 38.2% of the bounce is given back
                arr_ci = s_low_ci if side > 0 else s_high_ci
                arr = s_low if side > 0 else s_high
                q0 = int(np.searchsorted(arr_ci, s0, side="left"))
                for q in range(q0, len(arr)):
                    ci_s, j_s, p_s, lab_s = arr[q]
                    if ci_s >= s1 - 1:
                        break
                    if j_s < s0:
                        continue
                    ext = lo[ci_s - s0]
                    if abs(pC - ext) < GIVEBACK * span:
                        continue
                    if lab_s not in (("HL", "EL") if side > 0 else ("LH", "EH")):
                        continue
                    ta = datr[ci_s] if np.isfinite(datr[ci_s]) else 0.0
                    book(1, ci_s + 1, do[ci_s + 1], ext - side * P.SAME_LEVEL_ATR * ta)
                    break
                # WAY 3: the first touch of RSI 30 (70) on the timing chart = the backburner marking the higher low
                pa = p30 if side > 0 else p70
                k = int(nxt[side][max(s0, 1)])
                if k < s1:
                    fill = min(do[k], pa[k]) if side > 0 else max(do[k], pa[k])
                    stop3 = pB - side * tolT
                    if book(2, k + 1, fill, stop3):              # walked from the next bar; the fill bar is checked here
                        if (side > 0 and dl[k] <= stop3) or (side < 0 and dh[k] >= stop3):
                            g = side * (stop3 - fill) / fill * 100 - cost
                            rows[-1][14] = g; rows[-1][15] = g; rows[-1][16] = 0.0
                            if DETAIL is not None:
                                DETAIL[-1].update(xb=int(k), xpx=float(stop3), pct=float(g), R=float(g / rows[-1][7]),
                                                  t_x=str(d.index[k]))
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, T, ex))
    if not rows:
        return None, errs
    return np.asarray(rows, dtype=np.float64), errs


def main():
    procs, log = 8, None
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            log = sys.argv[i + 1]
            sys.stdout = sys.stderr = io.open(log, "w", buffering=1, encoding="utf-8", errors="replace")
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
    for e_ in errs[:15]:
        print("  ERR " + e_)
    f = pd.DataFrame(np.concatenate(parts), columns=COLS)
    f = f.sort_values("t").reset_index(drop=True)

    def st(g, col):
        g = g[np.isfinite(g[col])]
        if len(g) < 40:
            return None
        v = g[col].values
        blocks = [v[i:i + 20].sum() for i in range(0, len(v) - 19, 20)]
        yrs = g.groupby("yr")[col].mean()
        return dict(n=int(len(g)), mean=float(v.mean()), median=float(np.median(v)), won=float((v > 0).mean()),
                    avg_R=float((g[col] / g.risk).mean()), reached=float(g.reached.mean()),
                    blocks_up=int(sum(1 for b in blocks if b > 0)), blocks=int(len(blocks)),
                    years_up=int((yrs > 0).sum()), years=int(len(yrs)),
                    eras=[float(g[g.era == e][col].mean()) if (g.era == e).sum() >= 20 else None for e in range(3)])

    eq = lambda x: (x.leg >= 4) & (x.retrace >= 0.5)                       # noqa: E731
    CUTS = [
        ("every lower-high / higher-low structure", lambda x: x.leg > 0),
        ("NOT one of theirs: a small move first (under 2 normal bars)", lambda x: x.leg < 2),
        ("big move (4+), swing back 38.2% or less   = their FLAG", lambda x: (x.leg >= 4) & (x.retrace <= 0.382)),
        ("big move, swing back 38.2-50%             = their grey zone", lambda x: (x.leg >= 4) & (x.retrace > 0.382) & (x.retrace < 0.5)),
        ("big move, swing back 50% or more          = THEIR EQ", eq),
        ("their EQ, swing back 50-61.8%", lambda x: eq(x) & (x.retrace < 0.618)),
        ("their EQ, swing back 61.8-78.6%", lambda x: eq(x) & (x.retrace >= 0.618) & (x.retrace < 0.786)),
        ("their EQ, swing back 78.6%+", lambda x: eq(x) & (x.retrace >= 0.786)),
        ("their EQ, a VERY big move first (8+)", lambda x: (x.leg >= 8) & (x.retrace >= 0.5)),
        ("their EQ + volume FADING since the low", lambda x: eq(x) & (x.fade < 1.0)),
        ("their EQ + volume RISING since the low", lambda x: eq(x) & (x.fade >= 1.0)),
        ("their EQ + far line 1x+ the risk", lambda x: eq(x) & (x.rr >= 1)),
        ("their EQ + far line 2x+ the risk", lambda x: eq(x) & (x.rr >= 2)),
        ("their EQ + far line 1x+ + fading volume", lambda x: eq(x) & (x.rr >= 1) & (x.fade < 1)),
        ("their EQ + far line 1x+ + WITH the bigger chart's 50 EMA", lambda x: eq(x) & (x.rr >= 1) & (x.tag == 0)),
        ("their EQ + far line 1x+ + AGAINST it", lambda x: eq(x) & (x.rr >= 1) & (x.tag == 1)),
        ("their FLAG + far line 1x+", lambda x: (x.leg >= 4) & (x.retrace <= 0.382) & (x.rr >= 1)),
    ]
    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names), rows=int(len(f)),
                         pairs=["%s idea, %s timing" % p for p in PAIRS], ways=WAYS, seconds=int(time.time() - t0)),
               tables={})
    print("\n  THE ANTICIPATED EQ   %d names, %d trades  (%.0fs)" % (len(names), len(f), time.time() - t0))
    print("  MY VERSION of their trade. avg / middle per trade, R, won, far line reached, blocks of 20 up, years up,")
    print("  then the three eras (before 2022 / first half / second half).\n")
    for p_i, (T, t) in enumerate(PAIRS):
        for side, sname in ((1, "LONG the higher low after a drop"), (-1, "SHORT the lower high after a run")):
            for w_i, way in enumerate(WAYS):
                base = f[(f.pair == p_i) & (f.side == side) & (f.way == w_i)]
                if len(base) < 200:
                    continue
                for col, mlab in (("r_all", "all out just before the far line"),
                                  ("r_half", "half there, rest for the start of the big move, stop left alone")):
                    key = "%s idea / %s timing | %s | in: %s | out: %s" % (T, t, sname, way, mlab)
                    print("  " + key)
                    print("    %-62s %6s %7s %7s %6s %5s %6s %8s %6s  %s" % (
                        "cut", "n", "avg", "middle", "R", "won", "reach", "blocks", "years", "eras"))
                    out["tables"][key] = {}
                    for lab, fn in CUTS:
                        s = st(base[fn(base)], col)
                        if not s:
                            continue
                        out["tables"][key][lab] = s
                        eras = " ".join(("%+.2f" % e) if e is not None else "  -  " for e in s["eras"])
                        print("    %-62s %6d %+6.2f%% %+6.2f%% %+5.2f %4.0f%% %5.0f%% %4d/%-3d %2d/%-2d  %s" % (
                            lab[:62], s["n"], s["mean"], s["median"], s["avg_R"], 100 * s["won"], 100 * s["reached"],
                            s["blocks_up"], s["blocks"], s["years_up"], s["years"], eras))
                    print()
    json.dump(out, io.open(OUT, "w", encoding="utf-8"))
    try:
        f.to_parquet(os.path.splitext(OUT)[0] + "_rows.parquet")
    except Exception:
        pass
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
