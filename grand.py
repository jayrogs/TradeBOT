"""
grand.py -- 1,008 combinations of trend-riding and dip-buying, run as a
            distribution study rather than a search for a winner.

    python grand.py

WHY IT IS BUILT THIS WAY
Four times in this project a large sweep produced a spectacular winner that then
reversed out of sample. The failure is not the search, it is the reporting: the
best of N is spectacular even when nothing is there. So this reports the whole
distribution, runs the identical sweep on broken data at the same scale, and
judges only on a window the search never touches.

THE GRID -- every component comes from something already tested here

  CONTEXT (6)      which higher timeframes must agree, using the trend engine
                   that passes test_trend.py 8/8
  TRIGGER (8)      the dip: RSI thresholds, EQ resolution, EMA12 reclaim,
                   a confirmed higher low, weekly oversold
  EXIT (7)         daily / weekly / monthly higher-low break, EMA12 close,
                   +20% target, 20% trail, 60-day time stop
  MANAGEMENT (3)   all-in, three tranches, three tranches with the user's
                   "RSI cooled off" rule halting adds

  6 x 8 x 7 x 3 = 1,008

THE THREE THINGS REPORTED

  1. DISTRIBUTION   all 1,008 in the holdout, not the best one
  2. NULL           the same 1,008 on phase-shifted returns. If the best real
                    combo cannot beat the best broken combo, there is nothing
                    here and the number is just the tail of 1,008 tries.
  3. COMPONENTS     the marginal effect of each choice averaged over every
                    combination containing it. Far more robust than picking a
                    single winner: it asks "does requiring weekly-up help, on
                    average, across 168 different systems" rather than "which
                    of 1,008 looked best".

SPLIT   search 2005-2017, holdout 2018-2026. Nothing is tuned on the holdout.
COSTS   0.05% per side throughout.
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
DROP_STEP = 0.05        # each extra tranche after another 5% down


# ---------------------------------------------------------------- indicators

def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs)


def prep(sym, d):
    """Everything a combination might need, computed once per market."""
    if len(d) < 600:
        return None
    c = d["Close"].values.astype(float)
    l = d["Low"].values.astype(float)
    if not np.all(np.isfinite(c)) or c.min() <= 0:
        return None
    idx = d.index
    n = len(c)

    st_d, hl_d, _ = P.trend_state(d)
    wk, mo = P.resample(d, "W-FRI"), P.resample(d, "ME")
    if len(wk) < 60 or len(mo) < 20:
        return None
    st_w, hl_w, _ = P.trend_state(wk)
    st_m, hl_m, _ = P.trend_state(mo)

    def up(idx_src, states):
        return pd.Series(states == "UP", index=idx_src).reindex(idx, method="ffill").fillna(False).values

    def lvl(idx_src, arr):
        return pd.Series(arr, index=idx_src).reindex(idx, method="ffill").values

    r_d = rsi(c)
    r_w = lvl(wk.index, rsi(wk["Close"].values.astype(float)))
    ema12 = pd.Series(c).ewm(span=12, adjust=False).mean().values
    ma50 = pd.Series(c).rolling(50).mean().values
    _, _, _, _, _, res_d = P.compression(d)

    seq = P.zigzag(d)
    hl_confirm = np.zeros(n, bool)
    lows = []
    for conf, j, price, kind in seq:
        if kind == "low":
            if lows and price > lows[-1]:
                hl_confirm[conf] = True
            lows.append(price)

    return dict(
        sym=sym, idx=idx, c=c, l=l, n=n,
        ctx={"any": np.ones(n, bool),
             "W": up(wk.index, st_w),
             "M": up(mo.index, st_m),
             "W+M": up(wk.index, st_w) & up(mo.index, st_m),
             "D+W": (st_d == "UP") & up(wk.index, st_w),
             "M_notWdn": up(mo.index, st_m) &
                         ~pd.Series(st_w == "DOWN", index=wk.index).reindex(idx, method="ffill").fillna(False).values},
        trig={"rsi30": r_d < 30, "rsi35": r_d < 35, "rsi40": r_d < 40,
              "wrsi40": r_w < 40,
              "eq_up": res_d > 0,
              "ema12_reclaim": (c > ema12) & (np.roll(c, 1) < np.roll(ema12, 1)),
              "hl_confirm": hl_confirm,
              "ma50_dip": (c < ma50) & (np.roll(c, 1) >= np.roll(ma50, 1))},
        exits=build_exits(c, l, hl_d, lvl(wk.index, hl_w), lvl(mo.index, hl_m),
                          ema12, n),
        lvls={"HL_d": hl_d, "HL_w": lvl(wk.index, hl_w),
              "HL_m": lvl(mo.index, hl_m)},
        rsi=r_d)


def build_exits(c, l, hl_d, hl_w, hl_m, ema12, n):
    """For each bar, the first bar at or after it that each rule would exit on.
    Computed once with backward passes so every combination is a lookup."""
    out = {}

    def first_after(cond):
        nxt = np.full(n, n - 1, dtype=int)
        last = n - 1
        for i in range(n - 1, -1, -1):
            if cond[i]:
                last = i
            nxt[i] = last
        return nxt

    out["HL_d"] = first_after(np.isfinite(hl_d) & (c < hl_d))
    out["HL_w"] = first_after(np.isfinite(hl_w) & (c < hl_w))
    out["HL_m"] = first_after(np.isfinite(hl_m) & (c < hl_m))

    # EMA12 is a RIDE rule, not a stop. You enter oversold, which is BELOW the
    # EMA, so "first close below EMA12" fires on bar one and the whole thing
    # degenerates into a one-day trade. It has to arm first: wait for price to
    # reclaim the EMA, THEN exit on the first close back below it.
    above = first_after(c > ema12)
    below = first_after(c < ema12)
    armed = np.empty(n, dtype=int)
    for i in range(n):
        a = above[i]
        armed[i] = below[min(a + 1, n - 1)]
    out["ema12"] = armed
    return out


# ---------------------------------------------------------------- simulation

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
    """One combination on one market. Returns per-trade net returns."""
    c, l, n = m["c"], m["l"], m["n"]
    entry_ok = m["ctx"][ctx_k] & m["trig"][trig_k] & mask
    idxs = np.where(entry_ok)[0]
    if len(idxs) == 0:
        return np.empty(0), np.empty(0)
    r = m["rsi"]
    rets, holds = [], []
    i_prev = -1
    lv = m["lvls"].get(exit_k)
    for i0 in idxs:
        if i0 <= i_prev or i0 >= n - 2:
            continue
        # A stop that is ALREADY violated at entry is not a stop. Taking the
        # trade anyway books a same-bar exit and floods the sample with noise;
        # 18 of 36 SPY entries did exactly this the last time it went unchecked.
        if lv is not None and np.isfinite(lv[i0]) and c[i0] < lv[i0]:
            continue
        # ---- exit bar
        if exit_k in m["exits"]:
            j = m["exits"][exit_k][i0]
            j = max(j, i0 + 1)
        elif exit_k == "target20":
            hit = np.where(c[i0 + 1:min(i0 + MAX_HOLD, n)] >= c[i0] * 1.20)[0]
            j = i0 + 1 + hit[0] if len(hit) else min(i0 + MAX_HOLD, n - 1)
        elif exit_k == "trail20":
            j = min(i0 + MAX_HOLD, n - 1)
            peak = c[i0]
            for k in range(i0 + 1, j + 1):
                peak = max(peak, c[k])
                if c[k] <= peak * 0.80:
                    j = k
                    break
        else:                                   # time60
            j = min(i0 + 60, n - 1)
        j = min(j, i0 + MAX_HOLD, n - 1)

        # ---- position build, on a fixed budget for every style
        ret, _, _ = position_return(c, r, i0, j, mgmt_k, c[j] * (1 - COST / 2))
        rets.append(ret)
        holds.append(j - i0)
        i_prev = j
    return np.array(rets), np.array(holds, dtype=float)


def score(rets, holds):
    """mean return per trade, plus return per day HELD.

    A +20% target that takes 300 days is worse than a +4% exit that takes 20.
    Mean-per-trade cannot tell them apart; per-day can, and per-day is what
    competes with buy-and-hold SPY (~0.045%/day since 2018)."""
    if len(rets) < 5:
        return None
    tot_days = float(np.sum(holds))
    return dict(n=len(rets), mean=float(np.mean(rets)),
                med=float(np.median(rets)), win=float(np.mean(rets > 0)),
                hold=float(np.mean(holds)),
                perday=(float(np.sum(rets)) / tot_days) if tot_days > 0 else 0.0)


# ---------------------------------------------------------------- main

def main():
    store = pd.read_pickle(CACHE)
    syms = [s for s, d in store.items() if len(d) > 2500]
    syms = sorted(syms)[:int(os.environ.get("GRAND_N", 260))]
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
        # NULL: same bars, returns reversed -- identical drift and volatility,
        # causality destroyed
        ch = m["c"][m["m_hold"]]
        m["bh_hold"] = ((ch[-1] / ch[0]) ** (252.0 / max(len(ch), 1)) - 1
                        if len(ch) > 60 else np.nan)
        cc = m["c"]
        rr = np.diff(np.log(cc))
        m["c_null"] = cc[0] * np.exp(np.concatenate([[0], np.cumsum(rr[::-1])]))

    ctxs = list(mk[0]["ctx"])
    trigs = list(mk[0]["trig"])
    exits = ["HL_d", "HL_w", "HL_m", "ema12", "target20", "trail20", "time60"]
    mgmts = ["allin", "scale", "scale_rsi"]
    combos = list(itertools.product(ctxs, trigs, exits, mgmts))
    print("grid: %d x %d x %d x %d = %d combinations"
          % (len(ctxs), len(trigs), len(exits), len(mgmts), len(combos)))

    rows = []
    t0 = time.time()
    for k, (cx, tg, ex, mg) in enumerate(combos):
        sr, sh, hr, hh = [], [], [], []
        anns, excs = [], []
        for m in mk:
            a, ah = run_combo(m, cx, tg, ex, mg, m["m_search"])
            b, bh = run_combo(m, cx, tg, ex, mg, m["m_hold"])
            if len(a):
                sr.append(a); sh.append(ah)
            if len(b):
                hr.append(b); hh.append(bh)
                # Compound this market's trades over the whole holdout, so the
                # days sitting in cash between signals count against it. This is
                # the only figure directly comparable to owning the thing.
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
            rows.append(dict(ctx=cx, trig=tg, exit=ex, mgmt=mg,
                             s_n=s["n"], s_mean=s["mean"], s_med=s["med"],
                             s_perday=s["perday"],
                             h_n=h["n"], h_mean=h["mean"], h_med=h["med"],
                             h_win=h["win"], h_hold=h["hold"],
                             h_perday=h["perday"],
                             h_ann=float(np.median(anns)) if anns else np.nan,
                             h_exc=float(np.median(excs)) if excs else np.nan,
                             h_beat=float(np.mean(np.array(excs) > 0)) if excs else np.nan,
                             h_mkts=len(anns)))
        if (k + 1) % 100 == 0:
            print("  %d/%d combos  (%.0fs)" % (k + 1, len(combos), time.time() - t0))
    R = pd.DataFrame(rows)
    R.to_csv("grand_results.csv", index=False)
    print("\n%d combinations produced enough trades in both windows" % len(R))

    # ---- null at the same scale
    print("\nrunning the null (same grid, broken data)...")
    for m in mk:
        m["c_real"] = m["c"]
        m["c"] = m["c_null"]
    nrows = []
    t0 = time.time()
    for k, (cx, tg, ex, mg) in enumerate(combos):
        hr, hh = [], []
        for m in mk:
            b, bh = run_combo(m, cx, tg, ex, mg, m["m_hold"])
            if len(b):
                hr.append(b); hh.append(bh)
        h = score(np.concatenate(hr), np.concatenate(hh)) if hr else None
        if h and h["n"] >= MIN_TRADES:
            nrows.append((h["mean"], h["perday"]))
        if (k + 1) % 200 == 0:
            print("  %d/%d  (%.0fs)" % (k + 1, len(combos), time.time() - t0))
    for m in mk:
        m["c"] = m["c_real"]
    N = np.array([x[0] for x in nrows])
    NPD = np.array([x[1] for x in nrows])

    # what buy-and-hold SPY did per bar over the identical window
    spy = store.get("SPY")
    sp = spy[spy.index >= SPLIT]["Close"].values.astype(float)
    spy_pd = (sp[-1] / sp[0]) ** (1.0 / len(sp)) - 1

    print("\n" + "=" * 80)
    print("  1. THE DISTRIBUTION -- all %d combinations, holdout 2018-2026" % len(R))
    print("=" * 80)
    q = R.h_mean.quantile([0.05, 0.25, 0.5, 0.75, 0.95]).values
    print("  mean return per trade:  5th %+.2f%%  25th %+.2f%%  median %+.2f%%"
          "  75th %+.2f%%  95th %+.2f%%"
          % tuple(100 * x for x in q))
    print("  best %+.2f%%   worst %+.2f%%   share profitable %.0f%%"
          % (100 * R.h_mean.max(), 100 * R.h_mean.min(), 100 * (R.h_mean > 0).mean()))
    qd = R.h_perday.quantile([0.05, 0.5, 0.95]).values
    print()
    print("  THE NUMBER THAT MATTERS -- return per DAY the money was at risk")
    print("  (mean-per-trade rewards holding longer; per-day does not)")
    print("    SPY buy-and-hold, same window:  %+.4f%%/day" % (100 * spy_pd))
    print("    combos:  5th %+.4f%%   median %+.4f%%   95th %+.4f%%   best %+.4f%%"
          % (100 * qd[0], 100 * qd[1], 100 * qd[2], 100 * R.h_perday.max()))
    beat = (R.h_perday > spy_pd).mean()
    print("    share of the %d combinations that beat SPY per day: %.0f%% (%d)"
          % (len(R), 100 * beat, int((R.h_perday > spy_pd).sum())))

    V = R.dropna(subset=["h_exc"])
    print()
    print("  THE HARDER TEST -- compounded per market, cash charged for idle days,")
    print("  measured against simply OWNING each market over the same window.")
    print("    combos with enough markets to judge: %d" % len(V))
    print("    median annual return of the system:  %+.1f%%/yr"
          % (100 * V.h_ann.median()))
    print("    median EXCESS over buy-and-hold:     %+.1f%%/yr"
          % (100 * V.h_exc.median()))
    print("    best combo's excess:                 %+.1f%%/yr"
          % (100 * V.h_exc.max()))
    print("    combos beating buy-and-hold at all:  %d of %d (%.0f%%)"
          % (int((V.h_exc > 0).sum()), len(V), 100 * (V.h_exc > 0).mean()))
    print("    within the best combo, share of individual markets beaten: %.0f%%"
          % (100 * V.loc[V.h_exc.idxmax(), "h_beat"]))

    print("\n" + "=" * 80)
    print("  2. THE NULL -- same grid on broken data (%d combos)" % len(N))
    print("=" * 80)
    print("  best REAL combo, holdout   %+.2f%%" % (100 * R.h_mean.max()))
    print("  best NULL combo            %+.2f%%" % (100 * N.max()))
    print("  median real %+.2f%%   median null %+.2f%%"
          % (100 * R.h_mean.median(), 100 * np.median(N)))
    print()
    print("  per-day, which is the fair comparison:")
    print("    best real %+.4f%%/day    best null %+.4f%%/day    SPY %+.4f%%/day"
          % (100 * R.h_perday.max(), 100 * NPD.max(), 100 * spy_pd))
    print("    median real %+.4f%%/day  median null %+.4f%%/day"
          % (100 * R.h_perday.median(), 100 * np.median(NPD)))
    pct = float((NPD >= R.h_perday.max()).mean())
    print("    %.1f%% of NULL combos matched or beat the BEST real one"
          % (100 * pct))
    verdict = ("REAL WINS" if R.h_perday.max() > NPD.max()
               else "NULL WINS -- the best real result is inside the noise")
    print("  -> %s" % verdict)

    print("\n" + "=" * 80)
    print("  3. DOES THE SEARCH PREDICT THE HOLDOUT?")
    print("=" * 80)
    print("  This is the whole question. If picking the best in 2005-2017 tells")
    print("  you nothing about 2018-2026, then no amount of searching helps.")
    print()
    print("  correlation, mean per trade:   %+.3f" % R.s_mean.corr(R.h_mean))
    print("  correlation, return per day:   %+.3f" % R.s_perday.corr(R.h_perday))
    top = R.nlargest(50, "s_perday")
    print()
    print("  top 50 chosen by SEARCH per-day:")
    print("    search  %+.4f%%/day  ->  holdout %+.4f%%/day"
          % (100 * top.s_perday.mean(), 100 * top.h_perday.mean()))
    print("    all %d combos average holdout: %+.4f%%/day"
          % (len(R), 100 * R.h_perday.mean()))
    print("    of those 50, beat SPY in holdout: %d of 50"
          % int((top.h_perday > spy_pd).sum()))

    print("\n" + "=" * 80)
    print("  4. COMPONENT EFFECTS -- averaged over every combo containing them")
    print("=" * 80)
    for col, label in [("ctx", "CONTEXT"), ("trig", "TRIGGER"),
                       ("exit", "EXIT"), ("mgmt", "MANAGEMENT")]:
        print("\n  %s" % label)
        g = V.groupby(col).agg(n=("h_mean", "size"), hold=("h_mean", "mean"),
                               win=("h_win", "mean"), pd_=("h_perday", "mean"),
                               days=("h_hold", "mean"), exc=("h_exc", "median"),
                               ann=("h_ann", "median"))
        for k, x in g.sort_values("exc", ascending=False).iterrows():
            print("    %-14s %4d combos  %+6.1f%%/yr  vs own %+6.1f%%/yr  "
                  "%+7.2f%%/trade  %4.0f days  win %3.0f%%"
                  % (k, x.n, 100 * x.ann, 100 * x.exc, 100 * x.hold,
                     x.days, 100 * x.win))

    print("\n" + "=" * 80)
    print("  5. TOP 15 BY HOLDOUT  (for information -- NOT a recommendation)")
    print("=" * 80)
    print("  %-10s %-13s %-9s %-10s %6s %9s %9s %6s %5s"
          % ("context", "trigger", "exit", "mgmt", "trades", "ann/yr",
             "vs own", "days", "win"))
    for _, x in V.nlargest(15, "h_exc").iterrows():
        print("  %-10s %-13s %-9s %-10s %6d %+8.1f%% %+8.1f%% %6.0f %4.0f%%"
              % (x.ctx, x.trig, x["exit"], x.mgmt, x.h_n, 100 * x.h_ann,
                 100 * x.h_exc, x.h_hold, 100 * x.h_win))
    print("\n  These are the best of %d tries. Compare them to the null above"
          % len(R))
    print("  before believing any of them.")


if __name__ == "__main__":
    main()
