"""
rider_select.py -- does picking names that OBEY the 12 EMA make the rider work?

    python rider_select.py                  long and short, crypto
    python rider_select.py --side long

THE CLAIM BEING TESTED
"EMA riders work, it's just about picking names that obey the EMA12. And it
works either way -- EMA12 as resistance too."

Two separate claims, tested separately:

  SELECTION   some names respect the 12 EMA and some do not, and if you only
              trade the ones that do, the edge appears
  SHORT SIDE  the mirror works: in a downtrend, price rides the 12 EMA from
              below and it acts as resistance

WHY THE SPLIT MATTERS MORE THAN THE RESULT
Obedience is measured on the FIRST half of each name's history and the trades
are taken in the SECOND half. Measuring both on the same data would be circular
-- the names that happened to ride well are of course the names that rode well.
The only question worth asking is whether past obedience PREDICTS future
obedience, because that is what you would have to do in real time.

OBEDIENCE is the mean length of an armed ride. A name that holds the EMA for
thirty bars at a time obeys it; one that gets shaken out in three does not.

The rider itself already failed the plain test: entering once per ride and
holding to the EMA break beat random entries by +0.023% against a 0.200%
round-trip cost. If selection is the missing piece, the obedient bucket has to
clear that cost. If it does not, selection is not the answer either.
"""

import argparse
import warnings

import numpy as np
import pandas as pd

import crypto
import panel as P
import rider
import scanner as SC

warnings.filterwarnings("ignore")

COST = 0.001
BARS = 12000


def rides(df, side="long"):
    """One trade per ride. Returns (entries, exits, obedience)."""
    if df is None or len(df) < 200:
        return [], np.nan
    c = df["Close"].values.astype(float)
    o = df["Open"].values.astype(float)
    hi = df["High"].values.astype(float)
    lo = df["Low"].values.astype(float)
    n = len(c)
    e = rider.ema(c)
    a = P._atr(df)
    st, _, lh = P.trend_state(df)
    tol = rider.TOUCH_ATR * np.where(np.isfinite(a), a, 0.0)

    body_lo = np.minimum(o, c)
    body_hi = np.maximum(o, c)
    body = body_hi - body_lo
    tiny = body < 0.05 * np.where(np.isfinite(a), a, 1.0)

    if side == "long":
        under = np.clip(e - body_lo, 0.0, None)
        share = np.where(tiny, np.where(c < e, 1.0, 0.0),
                         np.where(body > 0, under / np.where(body > 0, body, 1.0), 0.0))
        holding = (body_hi > e) & (share <= rider.BODY_GRACE)
        trend_ok = st == "UP"
        near = holding & (lo - e <= tol)
        hl_run = np.zeros(n, int)
        for i in range(1, n):
            hl_run[i] = hl_run[i - 1] + 1 if lo[i] > lo[i - 1] else 0
        stack = hl_run >= rider.MIN_HL
    else:
        # the mirror: the body stays BELOW the EMA and it caps every bounce
        over = np.clip(body_hi - e, 0.0, None)
        share = np.where(tiny, np.where(c > e, 1.0, 0.0),
                         np.where(body > 0, over / np.where(body > 0, body, 1.0), 0.0))
        holding = (body_lo < e) & (share <= rider.BODY_GRACE)
        trend_ok = st == "DOWN"
        near = holding & (e - hi <= tol)
        lh_run = np.zeros(n, int)
        for i in range(1, n):
            lh_run[i] = lh_run[i - 1] + 1 if hi[i] < hi[i - 1] else 0
        stack = lh_run >= rider.MIN_HL

    armed = np.zeros(n, bool)
    live = False
    for i in range(n):
        if live:
            if not holding[i]:
                live = False
        elif trend_ok[i] and holding[i] and stack[i]:
            live = True
        armed[i] = live

    out, lens = [], []
    i = 0
    while i < n:
        if not armed[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and armed[j + 1]:
            j += 1
        lens.append(j - i + 1)
        entry = next((k for k in range(i, j + 1) if near[k]), None)
        x = min(j + 1, n - 1)               # exit the bar AFTER it breaks
        if entry is not None and x > entry:
            g = c[x] / c[entry] - 1
            if side == "short":
                g = -g
            out.append(dict(i=int(entry), j=int(x), bars=int(x - entry),
                            net=float(g - 2 * COST)))
        i = j + 1
    return out, (float(np.mean(lens)) if lens else np.nan)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--tf", default="15m,1h,4h,1d")
    ap.add_argument("--side", default="both", choices=("long", "short", "both"))
    a = ap.parse_args()
    tfs = [t.strip() for t in a.tf.split(",") if t.strip()]
    sides = ["long", "short"] if a.side == "both" else [a.side]

    u = crypto.universe(a.n)
    print("universe: %d names" % len(u))

    from concurrent.futures import ThreadPoolExecutor
    pairs = [(x["sym"], x["source"]) for _, x in u.iterrows()]
    jobs = [(s, src, b) for s, src in pairs for b in ("15m", "1h", "1d")]

    def grab(job):
        s, src, b = job
        try:
            return (s, b), crypto.candles(s, b, BARS, source=src)
        except Exception:
            return (s, b), None

    store = {}
    print("fetching %d series..." % len(jobs))
    with ThreadPoolExecutor(max_workers=8) as ex:
        for key, df in ex.map(grab, jobs):
            store[key] = df

    rows = []
    for sym, src in pairs:
        raw = {b: store.get((sym, b)) for b in ("15m", "1h", "1d")}
        for tf in tfs:
            if tf in SC.BASE:
                df = raw.get(SC.BASE[tf])
            elif tf in SC.DERIVE:
                s2, rule = SC.DERIVE[tf]
                df = SC.resample(raw.get(SC.BASE[s2]), rule)
            else:
                df = None
            if df is None or len(df) < 600:
                continue
            half = len(df) // 2
            for side in sides:
                _, obey = rides(df.iloc[:half], side)       # measured on the past
                tr, _ = rides(df.iloc[half:], side)         # traded on the future
                if not np.isfinite(obey) or len(tr) < 3:
                    continue
                rows.append(dict(sym=sym, tf=tf, side=side, obey=obey,
                                 n=len(tr),
                                 mean=float(np.mean([t["net"] for t in tr])),
                                 med=float(np.median([t["net"] for t in tr])),
                                 win=float(np.mean([t["net"] > 0 for t in tr]))))
        print("  %-6s" % sym, end="\r")

    R = pd.DataFrame(rows)
    if R.empty:
        print("no data")
        return
    R.to_csv("rider_select.csv", index=False)

    print("\n" + "=" * 82)
    print("  DOES PAST OBEDIENCE PREDICT FUTURE RIDES?")
    print("=" * 82)
    print("  obedience measured on the first half, trades taken on the second")
    print("  costs %.1f%% round trip" % (200 * COST))
    for side in sides:
        S = R[R.side == side]
        if len(S) < 8:
            continue
        print("\n  %s side -- %d name/timeframe combinations, %d trades"
              % (side.upper(), len(S), int(S.n.sum())))
        q = pd.qcut(S.obey, min(4, S.obey.nunique()),
                    labels=["least obedient", "", " ", "most obedient"][:min(4, S.obey.nunique())],
                    duplicates="drop")
        print("    %-16s %6s %8s %10s %9s %8s"
              % ("bucket", "combos", "trades", "avg ride", "mean/trade", "win%"))
        for k, g in S.groupby(q, observed=True):
            print("    %-16s %6d %8d %9.1f %+10.3f%% %7.0f%%"
                  % (k, len(g), int(g.n.sum()), g.obey.mean(),
                     100 * g["mean"].mean(), 100 * g.win.mean()))
        c = S.obey.corr(S["mean"])
        print("    correlation between past obedience and future return: %+.3f" % c)
        best = S.nlargest(max(len(S) // 4, 1), "obey")
        print("    top quartile by obedience: %+.3f%% per trade vs %.3f%% cost"
              % (100 * best["mean"].mean(), 200 * COST))
    print("\n  full table: rider_select.csv")


if __name__ == "__main__":
    main()
