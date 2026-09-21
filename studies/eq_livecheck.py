"""eq_livecheck.py -- THE PHANTOM-PIVOT CHECK on the EQ higher-low entry (2026-09-21, his third "r u sure").

panel.zigzag REPLACES a confirmed low when a lower low arrives before a high has qualified, and the replaced low
never appears in the list the studies read (#28). But in real time that first low DID confirm, the rule DID buy it,
and price then went under it: a stopped-out loser the study never sees. Every "buy the higher low after it confirms"
number on this desk is flattered by that, and the random-bar control is not, so the comparison was tilted.

This replays the pivots AS THEY WERE KNOWN: every confirmation is an event, including the ones later replaced.
THE TRADE, the same for both lists (a plain emulation of the one-pair EQ entry, so the two are comparable to EACH
OTHER -- it is not eq_coil, no strict-wick test):
    long:  a low D confirms, D is a higher (or equal) low against the low before it, and the high between them, C,
           is a lower (or equal) high against the high before it.  Buy the next open, stop a wick under D, the sell
           line is C, only when C is at least 1x the risk away.  Half at C, rest to breakeven then trailed (FR2.walk2).
    short: the mirror.
Printed: the FINAL-LIST version (what the studies see), the phantoms alone, and the LIVE version (both together).

    pythonw studies/eq_livecheck.py --procs 8 --log logs/eq_livecheck.log
Writes validation/eq_livecheck.json
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
import exit_managers as XM        # noqa: E402
import eq_freeride2 as FR2        # noqa: E402

OUT = os.path.join("validation", "eq_livecheck.json")
TFS = ["1h", "4h", "1d"]
MODE = FR2.MODES[1][1]            # half at the far line, rest to breakeven
COLS = ["tf", "side", "phantom", "ret", "risk", "rr", "kind", "yr"]


def live_events(df, PB=P.PIVOT_BARS, min_atr=P.MIN_PIVOT_ATR):
    """panel.zigzag, bar for bar, but every confirmation is kept: (confirm, form, price, kind, replaced_later,
    C, B, A) where C is the opposite pivot before it, B the same-kind pivot before that, A the one before B --
    all as the list stood at that moment."""
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    a = P._atr(df); n = len(h)
    win = 2 * PB + 1
    lmin = pd.Series(l).rolling(win, center=True, min_periods=1).min().values
    hmax = pd.Series(h).rolling(win, center=True, min_periods=1).max().values
    cand = np.nonzero(((l == lmin) | (h == hmax)) & (np.arange(n) >= PB) & (np.arange(n) + PB < n))[0]
    seq, ev, slot = [], [], []                 # slot[k] = index in ev of the event currently holding seq[k]
    for j in cand:
        j = int(j); i = j + PB
        is_low = l[j] == lmin[j]; is_high = h[j] == hmax[j]
        if is_low and is_high:
            is_high = False
        kind = "low" if is_low else "high"
        price = l[j] if is_low else h[j]
        thresh = min_atr * (a[j] if np.isfinite(a[j]) and a[j] > 0 else 0.0)
        if seq and seq[-1][3] == kind:
            if (kind == "low" and price < seq[-1][2]) or (kind == "high" and price > seq[-1][2]):
                ev[slot[-1]][4] = True                                   # the one it replaces was a phantom
                ctx = (seq[-2] if len(seq) >= 2 else None, seq[-3] if len(seq) >= 3 else None,
                       seq[-4] if len(seq) >= 4 else None)
                seq[-1] = (i, j, price, kind)
                ev.append([i, j, price, kind, False, ctx]); slot[-1] = len(ev) - 1
            continue
        if seq:
            leg = (price - seq[-1][2]) if kind == "high" else (seq[-1][2] - price)
            if leg < thresh:
                continue
        ctx = (seq[-1] if len(seq) >= 1 else None, seq[-2] if len(seq) >= 2 else None,
               seq[-3] if len(seq) >= 3 else None)
        seq.append((i, j, price, kind))
        ev.append([i, j, price, kind, False, ctx]); slot.append(len(ev) - 1)
    return ev, a


def _work(args):
    sym, kind = args
    try:
        frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    frames = {k: v for k, v in frames.items() if k in TFS}
    rows, errs = [], []
    cost = B.CLASS_COST.get(kind, B.COST)
    k_i = FR2.KINDS.index(kind) if kind in FR2.KINDS else 0
    for t_i, tf in enumerate(TFS):
        df = frames.get(tf)
        if df is None or len(df) < 300:
            continue
        try:
            c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
            h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
            n = len(c)
            ev, atr = live_events(df)
            piv = ST.pivots(df)
            lows_at, highs_at = {}, {}
            for ci_, j_, p_, kd_, lab_ in piv:
                if kd_ == "low" and lab_ in ("HL", "EL"):
                    lows_at.setdefault(ci_, []).append(float(p_))
                elif kd_ == "high" and lab_ in ("LH", "EH"):
                    highs_at.setdefault(ci_, []).append(float(p_))
            extra = dict(rsi=IND.rsi_parts(c)[0], e12=XM.ema(c, 12), lows_at=lows_at, highs_at=highs_at)
            cap = FR2.CAP_DAYS * B.BARS_DAY[tf]
            yrs = df.index.year.values
            for i, j, price, kd, phantom, (C, Bp, A) in ev:
                if C is None or Bp is None or A is None or i + 2 >= n or i < 60:
                    continue
                a0 = atr[j] if np.isfinite(atr[j]) and atr[j] > 0 else np.nan
                if not np.isfinite(a0):
                    continue
                tol = P.SAME_LEVEL_ATR * a0
                sgn = 1 if kd == "low" else -1
                if sgn > 0:
                    ok = (price >= Bp[2] - tol) and (C[2] <= A[2] + tol)      # a higher low, after a lower high
                else:
                    ok = (price <= Bp[2] + tol) and (C[2] >= A[2] - tol)
                if not ok:
                    continue
                e = i + 1
                fill = o[e]; stop = price - sgn * tol; target = float(C[2])
                if not ((stop < fill < target) if sgn > 0 else (target < fill < stop)):
                    continue
                risk = abs(fill - stop); rr_ = abs(target - fill) / risk
                if rr_ < 1.0 or risk / fill < 3 * cost:
                    continue
                res = FR2.walk2(sgn, c, o, h, l, atr, e, fill, stop, target, n, cap, None, MODE, extra)
                if res is None:
                    continue
                xb, xpx = res[0], res[1]
                rows.append([t_i, sgn, 1.0 if phantom else 0.0, float(sgn * (xpx / fill - 1) - cost), risk / fill,
                             rr_, k_i, float(yrs[e])])
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
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
    names = R._by_size([(s_, k_) for s_, k_ in B.universe() if k_ != "forex"])
    R.quiet_workers()
    parts, errs = [], []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for part, err in ex.map(_work, names, chunksize=2):
            errs += err or []
            if part is not None:
                parts.append(part)
    f = pd.DataFrame(np.concatenate(parts), columns=COLS)
    f.to_parquet(os.path.splitext(OUT)[0] + "_rows.parquet")

    def st(g):
        if len(g) < 40:
            return None
        return dict(n=int(len(g)), mean=float(g.ret.mean()), median=float(g.ret.median()),
                    won=float((g.ret > 0).mean()), avg_R=float((g.ret / g.risk).mean()))

    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names), rows=int(len(f)),
                         seconds=int(time.time() - t0)), table={})
    print("\n  THE PHANTOM-PIVOT CHECK   %d names, %d trades  (%.0fs)" % (len(names), len(f), time.time() - t0))
    print("  the EQ higher-low / lower-high entry, sell line 1x+ the risk away, half there, rest to breakeven\n")
    for t_i, tf in enumerate(TFS):
        for lab, sel in (("everything", lambda g: g.ret == g.ret), ("stocks + ETFs, long", lambda g: (g.kind <= 1) & (g.side == 1)),
                         ("crypto, long", lambda g: (g.kind == 2) & (g.side == 1)), ("all shorts", lambda g: g.side == -1)):
            g = f[f.tf == t_i]; g = g[sel(g)]
            if len(g) < 200:
                continue
            print("  %s | %s" % (tf, lab))
            for nm, x in (("FINAL list only (what the studies see)", g[g.phantom == 0]),
                          ("the phantoms alone", g[g.phantom == 1]), ("LIVE: both, as it would have traded", g)):
                s = st(x)
                if not s:
                    continue
                out["table"]["%s | %s | %s" % (tf, lab, nm)] = s
                print("     %-40s n%7d  avg %+.2f%%  middle %+.2f%%  won %2.0f%%  R %+.2f" % (
                    nm, s["n"], 100 * s["mean"], 100 * s["median"], 100 * s["won"], s["avg_R"]))
            print("     phantoms are %.0f%% of the live trades" % (100 * g.phantom.mean()))
    json.dump(out, io.open(OUT, "w", encoding="utf-8"))
    for e_ in errs[:8]:
        print("  ERR " + e_)
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
