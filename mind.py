"""
mind.py -- 1,008 combinations built out of crowd psychology rather than
           indicator levels. The companion to grand.py.

    python mind.py

WHY A SEPARATE GRID
grand.py asks "which indicator threshold and which stop". That is the mechanical
half. It cannot express the things actually described in this project: buying
into a panic rather than at a number, adding while it is still falling, selling
half into the first bounce to get the average back to flat, and refusing to sell
while price is still going down.

So every TRIGGER here is a fear event and every EXIT here is a relief event.

  CONTEXT (6)   unchanged from grand.py -- which higher timeframes must agree
  TRIGGER (8)   capitulation volume, three and five down days, a gap down,
                stretched below the 50-day, a climax down bar, a new 20-day low
                while oversold, and an inside bar right after a drop
  EXIT (7)      the half-out-at-breakeven rule, RSI relief at 50 and 60, three
                green days, a climax up bar, the structural stop, a 3-ATR trail
  MANAGEMENT(3) all-in, three tranches, three tranches halted when RSI cools

  6 x 8 x 7 x 3 = 1,008

SCORED THE SAME WAY as grand.py, which matters more than the grid itself: each
market is compounded across the whole holdout so idle cash is charged for, and
the result is measured against simply OWNING that market. A dip-buying system
that returns +9%/yr on a market that returned +14%/yr has lost, however good the
per-trade statistics look.
"""

import itertools
import os
import time
import warnings

import numpy as np
import pandas as pd

import panel as P

warnings.filterwarnings("ignore")

CACHE = os.path.join("cache", "scan_prices.pkl")
COST = 0.0005
SPLIT = pd.Timestamp("2018-01-01")
MAX_HOLD = 400
MIN_TRADES = 40
DROP_STEP = 0.05


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs)


def atr(h, l, c, n=14):
    pc = np.roll(c, 1)
    pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().values


def first_after(cond, n):
    """First bar at or after i where cond holds; the last bar if it never does."""
    nxt = np.full(n, n - 1, dtype=int)
    last = n - 1
    for i in range(n - 1, -1, -1):
        if cond[i]:
            last = i
        nxt[i] = last
    return nxt


def streak(flag, k):
    s = np.zeros(len(flag), bool)
    run = 0
    for i in range(len(flag)):
        run = run + 1 if flag[i] else 0
        s[i] = run >= k
    return s


def prep(sym, d):
    if len(d) < 600:
        return None
    c = d["Close"].values.astype(float)
    o = d["Open"].values.astype(float)
    hi = d["High"].values.astype(float)
    lo = d["Low"].values.astype(float)
    if not np.all(np.isfinite(c)) or c.min() <= 0:
        return None
    v = d["Volume"].values.astype(float) if "Volume" in d else np.ones(len(c))
    idx, n = d.index, len(c)

    st_d, hl_d, _ = P.trend_state(d)
    wk, mo = P.resample(d, "W-FRI"), P.resample(d, "ME")
    if len(wk) < 60 or len(mo) < 20:
        return None
    st_w, hl_w, _ = P.trend_state(wk)
    st_m, hl_m, _ = P.trend_state(mo)

    def up(src, states):
        return pd.Series(states == "UP", index=src).reindex(
            idx, method="ffill").fillna(False).values

    r = rsi(c)
    a = atr(hi, lo, c)
    ma50 = pd.Series(c).rolling(50).mean().values
    vol20 = pd.Series(v).rolling(20).mean().values
    prev_c = np.roll(c, 1); prev_c[0] = c[0]
    prev_l = np.roll(lo, 1); prev_l[0] = lo[0]
    prev_h = np.roll(hi, 1); prev_h[0] = hi[0]

    down, up_day = c < prev_c, c > prev_c
    low20 = pd.Series(c).rolling(20).min().values
    drop3 = c < np.roll(c, 3)

    trig = {
        # the crowd giving up
        "cap_vol": (v > 2.0 * vol20) & down,
        "down3": streak(down, 3),
        "down5": streak(down, 5),
        "gap_dn": o < prev_l,
        "stretch": (ma50 - c) / np.where(a > 0, a, np.nan) > 1.5,
        "climax_dn": ((hi - lo) > 2.0 * a) & (c < o),
        "newlow_os": (c <= low20) & (r < 35),
        # fear exhausting itself: the range dries up right after the drop
        "quiet_after": (hi < prev_h) & (lo > prev_l) & drop3,
    }
    for k in trig:
        trig[k] = np.nan_to_num(np.asarray(trig[k], dtype=float),
                                nan=0.0).astype(bool)

    ex = {
        "rsi50": first_after(r >= 50, n),
        "rsi60": first_after(r >= 60, n),
        "up3": first_after(streak(up_day, 3), n),
        "climax_up": first_after(((hi - lo) > 2.0 * a) & (c > o) & (r > 55), n),
        "HL_d": first_after(np.isfinite(hl_d) & (c < hl_d), n),
    }

    return dict(sym=sym, idx=idx, c=c, n=n, rsi=r, atr=a,
                ctx={"any": np.ones(n, bool),
                     "W": up(wk.index, st_w),
                     "M": up(mo.index, st_m),
                     "W+M": up(wk.index, st_w) & up(mo.index, st_m),
                     "D+W": (st_d == "UP") & up(wk.index, st_w),
                     "M_notWdn": up(mo.index, st_m) &
                     ~pd.Series(st_w == "DOWN", index=wk.index).reindex(
                         idx, method="ffill").fillna(False).values},
                trig=trig, exits=ex, hl=hl_d)


def position_return(c, r, i0, j, mgmt, exit_price):
    """Return on a FIXED budget, identical for every management style.

    Scaling in is not free. If you plan three tranches and only one fills, the
    other two sat in cash and earned nothing. Scoring the trade on the average
    cost of the lots that did fill hides that, and makes averaging down look
    like a free improvement. Here every style risks the same maximum: all-in
    commits it at entry, the scalers commit a third at a time, and unfilled
    tranches simply contribute nothing.
    """
    if mgmt == "allin":
        lots, w = [c[i0]], 1.0
    else:
        lots, w = [c[i0]], 1.0 / 3.0
        nxt, rlow = c[i0] * (1 - DROP_STEP), r[i0]
        for k in range(i0 + 1, j + 1):
            if len(lots) >= 3:
                break
            if mgmt == "scale_rsi" and r[k] > rlow + 5:
                break                   # RSI cooled off, so stop adding
            if c[k] <= nxt:
                lots.append(c[k])
                nxt = c[k] * (1 - DROP_STEP)
                rlow = min(rlow, r[k])
    buy = 1 + COST / 2
    return (float(sum(w * (exit_price / (p * buy) - 1) for p in lots)),
            lots, w)


def run_combo(m, ctx_k, trig_k, exit_k, mgmt_k, mask):
    c, n, a, hl, r = m["c"], m["n"], m["atr"], m["hl"], m["rsi"]
    ok = m["ctx"][ctx_k] & m["trig"][trig_k] & mask
    idxs = np.where(ok)[0]
    if len(idxs) == 0:
        return np.empty(0), np.empty(0)
    struct = m["exits"]["HL_d"]
    rets, holds = [], []
    i_prev = -1
    for i0 in idxs:
        if i0 <= i_prev or i0 >= n - 2:
            continue
        if exit_k == "HL_d" and np.isfinite(hl[i0]) and c[i0] < hl[i0]:
            continue                    # the stop is already gone: not a trade

        if exit_k in m["exits"]:
            j = min(max(m["exits"][exit_k][i0], i0 + 1), i0 + MAX_HOLD, n - 1)
            ret, _, _ = position_return(c, r, i0, j, mgmt_k,
                                        c[j] * (1 - COST / 2))

        elif exit_k == "atr3":
            j, peak = min(i0 + MAX_HOLD, n - 1), c[i0]
            for k in range(i0 + 1, j + 1):
                peak = max(peak, c[k])
                if c[k] <= peak - 3.0 * a[k]:
                    j = k
                    break
            ret, _, _ = position_return(c, r, i0, j, mgmt_k,
                                        c[j] * (1 - COST / 2))

        else:                           # be_half: half out once flat, rest rides
            jmax = min(i0 + MAX_HOLD, n - 1)
            jstruct = min(max(struct[i0], i0 + 1), jmax)
            _, lots, w = position_return(c, r, i0, jstruct, mgmt_k, c[jstruct])
            avg = float(np.mean(lots))
            jhalf = jstruct
            for k in range(i0 + 1, jstruct + 1):
                if c[k] >= avg:
                    jhalf = k
                    break
            buy = 1 + COST / 2

            def at(px):
                p_out = px * (1 - COST / 2)
                return float(sum(w * (p_out / (p * buy) - 1) for p in lots))

            ret = 0.5 * at(c[jhalf]) + 0.5 * at(c[jstruct])
            j = jstruct

        rets.append(ret)
        holds.append(j - i0)
        i_prev = j
    return np.array(rets), np.array(holds, dtype=float)


def score(rets, holds):
    if len(rets) < 5:
        return None
    td = float(np.sum(holds))
    return dict(n=len(rets), mean=float(np.mean(rets)),
                med=float(np.median(rets)), win=float(np.mean(rets > 0)),
                hold=float(np.mean(holds)),
                perday=(float(np.sum(rets)) / td) if td > 0 else 0.0,
                p05=float(np.percentile(rets, 5)))


def main():
    store = pd.read_pickle(CACHE)
    syms = sorted([s for s, d in store.items() if len(d) > 2500])
    syms = syms[:int(os.environ.get("MIND_N", 260))]
    print("preparing %d markets..." % len(syms))
    mk, t0 = [], time.time()
    for s in syms:
        try:
            m = prep(s, store[s])
        except Exception:
            continue
        if m:
            mk.append(m)
    print("  %d ready in %.0fs" % (len(mk), time.time() - t0))

    for m in mk:
        m["m_search"] = np.asarray(m["idx"] < SPLIT)
        m["m_hold"] = np.asarray(m["idx"] >= SPLIT)
        ch = m["c"][m["m_hold"]]
        m["bh_hold"] = ((ch[-1] / ch[0]) ** (252.0 / max(len(ch), 1)) - 1
                        if len(ch) > 60 else np.nan)
        rr = np.diff(np.log(m["c"]))
        m["c_null"] = m["c"][0] * np.exp(
            np.concatenate([[0], np.cumsum(rr[::-1])]))

    ctxs = list(mk[0]["ctx"])
    trigs = list(mk[0]["trig"])
    exits = ["be_half", "rsi50", "rsi60", "up3", "climax_up", "HL_d", "atr3"]
    mgmts = ["allin", "scale", "scale_rsi"]
    combos = list(itertools.product(ctxs, trigs, exits, mgmts))
    print("grid: %d x %d x %d x %d = %d combinations"
          % (len(ctxs), len(trigs), len(exits), len(mgmts), len(combos)))

    rows, t0 = [], time.time()
    for k, (cx, tg, ex, mg) in enumerate(combos):
        sr, sh, hr, hh, anns, excs = [], [], [], [], [], []
        for m in mk:
            a, ah = run_combo(m, cx, tg, ex, mg, m["m_search"])
            b, bh = run_combo(m, cx, tg, ex, mg, m["m_hold"])
            if len(a):
                sr.append(a)
                sh.append(ah)
            if len(b):
                hr.append(b)
                hh.append(bh)
                nb = int(m["m_hold"].sum())
                if len(b) >= 3 and nb > 250 and np.isfinite(m["bh_hold"]):
                    grow = float(np.prod(1.0 + b))
                    if grow > 0:
                        ann = grow ** (252.0 / nb) - 1
                        anns.append(ann)
                        excs.append(ann - m["bh_hold"])
        s = score(np.concatenate(sr), np.concatenate(sh)) if sr else None
        h = score(np.concatenate(hr), np.concatenate(hh)) if hr else None
        if s and h and s["n"] >= MIN_TRADES and h["n"] >= MIN_TRADES:
            rows.append(dict(
                ctx=cx, trig=tg, exit=ex, mgmt=mg,
                s_n=s["n"], s_mean=s["mean"], s_perday=s["perday"],
                h_n=h["n"], h_mean=h["mean"], h_med=h["med"], h_win=h["win"],
                h_hold=h["hold"], h_perday=h["perday"], h_p05=h["p05"],
                h_ann=float(np.median(anns)) if anns else np.nan,
                h_exc=float(np.median(excs)) if excs else np.nan,
                h_beat=float(np.mean(np.array(excs) > 0)) if excs else np.nan,
                h_mkts=len(anns)))
        if (k + 1) % 100 == 0:
            print("  %d/%d  (%.0fs)" % (k + 1, len(combos), time.time() - t0))

    R = pd.DataFrame(rows)
    R.to_csv("mind_results.csv", index=False)
    V = R.dropna(subset=["h_exc"])
    print("\n%d of %d combinations produced enough trades in both windows"
          % (len(R), len(combos)))

    print("\nrunning the null (same grid, causality reversed)...")
    for m in mk:
        m["c_real"], m["c"] = m["c"], m["c_null"]
    nex, t0 = [], time.time()
    for k, (cx, tg, ex, mg) in enumerate(combos):
        excs, cnt = [], 0
        for m in mk:
            b, _ = run_combo(m, cx, tg, ex, mg, m["m_hold"])
            cnt += len(b)
            nb = int(m["m_hold"].sum())
            if len(b) >= 3 and nb > 250:
                cn = m["c"][m["m_hold"]]
                bhn = (cn[-1] / cn[0]) ** (252.0 / len(cn)) - 1
                grow = float(np.prod(1.0 + b))
                if grow > 0:
                    excs.append(grow ** (252.0 / nb) - 1 - bhn)
        if cnt >= MIN_TRADES and excs:
            nex.append(float(np.median(excs)))
        if (k + 1) % 300 == 0:
            print("  %d/%d  (%.0fs)" % (k + 1, len(combos), time.time() - t0))
    for m in mk:
        m["c"] = m["c_real"]
    NE = np.array(nex)

    spy = store["SPY"]
    sp = spy[spy.index >= SPLIT]["Close"].values.astype(float)
    spy_ann = (sp[-1] / sp[0]) ** (252.0 / len(sp)) - 1

    print("\n" + "=" * 88)
    print("  PSYCHOLOGICAL GRID -- %d combinations, holdout 2018-2026" % len(V))
    print("=" * 88)
    print("  SPY buy-and-hold over the same window: %+.1f%%/yr" % (100 * spy_ann))
    q = list(V.h_exc.quantile([0.05, 0.5, 0.95]).values) + [V.h_exc.max()]
    print("  excess over OWNING the same market, per year:")
    print("    5th %+.1f%%   median %+.1f%%   95th %+.1f%%   best %+.1f%%"
          % tuple(100 * x for x in q))
    print("    beat buy-and-hold: %d of %d (%.0f%%)"
          % (int((V.h_exc > 0).sum()), len(V), 100 * (V.h_exc > 0).mean()))

    print("\n  NULL -- same grid on reversed returns (%d combos)" % len(NE))
    if len(NE):
        print("    best real excess %+.1f%%/yr    best null excess %+.1f%%/yr"
              % (100 * V.h_exc.max(), 100 * NE.max()))
        print("    median real %+.1f%%   median null %+.1f%%"
              % (100 * V.h_exc.median(), 100 * np.median(NE)))
        print("    share of null combos matching the best real one: %.1f%%"
              % (100 * float((NE >= V.h_exc.max()).mean())))

    print("\n  DOES THE SEARCH PREDICT THE HOLDOUT?")
    print("    correlation search vs holdout, per day: %+.3f"
          % V.s_perday.corr(V.h_perday))
    top = V.nlargest(50, "s_perday")
    print("    top 50 by search -> holdout excess %+.1f%%/yr, %d of 50 positive"
          % (100 * top.h_exc.mean(), int((top.h_exc > 0).sum())))

    for col, label in [("ctx", "CONTEXT"), ("trig", "TRIGGER (the fear event)"),
                       ("exit", "EXIT (the relief event)"),
                       ("mgmt", "MANAGEMENT")]:
        print("\n  %s" % label)
        g = V.groupby(col).agg(n=("h_exc", "size"), exc=("h_exc", "median"),
                               ann=("h_ann", "median"), win=("h_win", "mean"),
                               days=("h_hold", "mean"), worst=("h_p05", "mean"),
                               tr=("h_mean", "mean"))
        for k, x in g.sort_values("exc", ascending=False).iterrows():
            print("    %-12s %4d  %+6.1f%%/yr  vs own %+6.1f%%  %+6.2f%%/trade"
                  "  %4.0f days  win %3.0f%%  worst 5%% %+6.1f%%"
                  % (k, x.n, 100 * x.ann, 100 * x.exc, 100 * x.tr, x.days,
                     100 * x.win, 100 * x.worst))

    print("\n  TOP 15 BY EXCESS  (best of %d tries -- read the null first)" % len(V))
    print("  %-10s %-11s %-10s %-10s %6s %8s %8s %6s"
          % ("context", "trigger", "exit", "mgmt", "trades", "ann/yr",
             "vs own", "days"))
    for _, x in V.nlargest(15, "h_exc").iterrows():
        print("  %-10s %-11s %-10s %-10s %6d %+7.1f%% %+7.1f%% %6.0f"
              % (x.ctx, x.trig, x["exit"], x.mgmt, x.h_n, 100 * x.h_ann,
                 100 * x.h_exc, x.h_hold))
    print("\n  full table: mind_results.csv")


if __name__ == "__main__":
    main()
