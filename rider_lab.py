"""rider_lab.py -- my own attempt at maximizing profit from EMA12 riders.

    python rider_lab.py

The surviving rule (close-confirmed touch entry, body-close exit, 3% disaster
stop) makes +0.32%/trade over random out of sample -- but it punches out on the
first body close, which surrenders the long rides that make this playbook
worth anything. This script does two things:

OBSERVE first: what do riders actually do after a body-close shakeout, does a
defended touch predict more defense, and how concentrated is the profit?

THEN TEST exits and filters, every one with the honest close-confirmed fill
and a null pushed through the identical exit:

  base       body close under the EMA ends it (the current rule)
  grace2     two CONSECUTIVE body closes under end it -- one is a shakeout
  promote1/2/5   once the trade is up 1/2/5%, it has proven itself: stop
             honoring body closes, trail the 3% stop under the EMA instead.
             Cut unproven trades fast, let proven ones run
  target2/5  resting limit sell at +2%/+5%, body-close exit otherwise
  steep      base exit, but only enter when the EMA is actually climbing
             (e[k] - e[k-3] >= 0.10 ATR) -- flat EMAs are chop
  reenter    after a body-close exit, the ride often resumes: re-enter on the
             first body re-close above a rising EMA within 6 bars (rinse and
             repeat), without demanding a fresh set of touches

Chosen on the first half of every series, scored on the second. The judge is
the OOS edge per trade AND the total OOS profit, because a config that trades
three times as often can earn more money with a thinner edge.
"""

import warnings

import numpy as np
import pandas as pd

import crypto
import panel as P
import rider
import rider_v4 as V4
import scanner as SC

warnings.filterwarnings("ignore")

COST = V4.COST
BARS = 12000
STOP = 0.03
# OWNER SPEC 2026-08-29, measured in wind_study.py on BOTH eras before
# adoption (mined +0.32->+0.67, frozen +0.07->+0.36):
EXIT_TOL_ATR = 0.25   # the body may close under the EMA by up to this much
                      # ATR before the unproven exit fires ("it just barely
                      # didnt hold")
MIN_WIND = 5          # the live trend must have been UP this many bars
                      # ("we need the wind at our backs")
TOUCHES = [2, 3]
# ROUND 3 -- the graded objections, each as a testable tweak on the champion
# (promote1: body-close exit while unproven, only the 3% trail once up 1%):
#   redexit   chart 2: a GREEN candle body-closing under the EMA is buying,
#             not failure -- only RED body closes exit
#   near      chart 9: only enter if the close is within 0.5 ATR of the EMA
#   fresh     charts 4/7/10/13/17: skip freshly-flipped trends -- the live
#             trend must have been UP for 5+ bars
#   liquid    charts 16/20: skip names too thin to trust the candles
#             (median dollar volume under $1M/hour)
#   all5      everything at once
#   all4      round-3 confirm: liquid + fresh + redexit, WITHOUT near --
#             the close-distance cap hurt in every cell of two rounds
MODES = ["promote1", "liquid", "all4"]


def prep(df):
    c = df["Close"].values.astype(float)
    o = df["Open"].values.astype(float)
    hi = df["High"].values.astype(float)
    lo = df["Low"].values.astype(float)
    st = P.trend_state(df)
    r = rider.read(df, state=st)
    e = r["ema"]
    a = P._atr(df)
    up = st[0] == "UP"
    armed = r["armed"] & up
    hold = r["closed_above"]
    tol = V4.ENTRY_MAX_ATR * np.where(np.isfinite(a), a, 0.0)
    touch = hold & (lo <= e + tol)
    rising = np.concatenate([[False], e[1:] > e[:-1]])
    steep = np.zeros(len(c), bool)
    aa = np.where(np.isfinite(a), a, np.inf)
    steep[3:] = (e[3:] - e[:-3]) >= 0.10 * aa[3:]
    upage = np.zeros(len(c), dtype=int)
    for i in range(1, len(c)):
        upage[i] = upage[i - 1] + 1 if up[i] else 0
    return dict(c=c, o=o, hi=hi, lo=lo, e=e, up=up, armed=armed, hold=hold,
                touch=touch, rising=rising, steep=steep, upage=upage,
                atr=np.where(np.isfinite(a), a, np.inf), n=len(c))


THR = dict(promote1=1.01, promote2=1.02, promote5=1.05,
           ratchet1=1.01, ratchet2=1.02,
           redexit=1.01, near=1.01, fresh=1.01, liquid=1.01, all5=1.01,
           all4=1.01)
TGT = dict(target2=1.02, target5=1.05)


def run_exit(v, entry, fill, mode):
    c, lo, hi, e, hold = v["c"], v["lo"], v["hi"], v["e"], v["hold"]
    thr, tgt = THR.get(mode), TGT.get(mode)
    promoted = False
    graced = 0
    # THE PLAIN "3% UNDER THE EMA" STOP IS NOT A FLOOR. In a decline the EMA
    # falls with price, so the stop falls too, and an orderly bleed never gets
    # 3% away from its own average -- that is how a "3% stop" lost 16.7% on an
    # XRP chart. The ratchet modes fix it: the floor only moves UP.
    ratchet = mode.startswith("ratchet")
    floor = 0.0
    for k in range(entry + 1, v["n"]):
        f = e[k] * (1 - STOP)
        floor = max(floor, f) if ratchet else f
        if lo[k] <= floor:                       # disaster stop, always on
            return k, floor, "stop"
        if tgt and hi[k] >= fill * tgt:          # resting limit sell
            return k, fill * tgt, "target"
        if thr and not promoted and c[k] >= fill * thr:
            promoted = True
        if mode == "grace2":
            graced = graced + 1 if not hold[k] else 0
            if graced >= 2:
                return k, c[k], "body"
        elif promoted:
            pass                                 # proven: only the stop exits
        elif mode in ("redexit", "all5", "all4"):
            if not hold[k] and c[k] < v["o"][k]:
                return k, c[k], "body"
        else:
            # tolerant body exit: under the EMA by more than the buffer
            buf = EXIT_TOL_ATR * (v["atr"][k] if np.isfinite(v["atr"][k])
                                  else 0.0)
            if c[k] < e[k] - buf:
                return k, c[k], "body"
    return None


def entries(v, need, mode):
    out = []
    n = v["n"]
    i = 0
    while i < n:
        if not v["armed"][i]:
            i += 1
            continue
        j = i
        while j + 1 < n and v["armed"][j + 1]:
            j += 1
        seen = 0
        for k in range(i, j + 1):
            if v["touch"][k]:
                seen += 1
                if seen > need and v["rising"][k]:
                    # THIS touch is the ride's one entry candidate. The wind
                    # gate SKIPS the ride rather than waiting for a later
                    # touch -- the waiting variant was measured worse in both
                    # eras (mined +0.59 vs +0.67, frozen +0.21 vs +0.36).
                    ok = v["upage"][k] >= MIN_WIND
                    if mode == "steep":
                        ok = ok and v["steep"][k]
                    if mode in ("near", "all5"):
                        ok = ok and (v["c"][k] - v["e"][k]) <= 0.5 * v["atr"][k]
                    if ok:
                        out.append((k, v["c"][k]))
                    break
        i = j + 1
    return out


def trades(v, need, mode):
    if mode in ("liquid", "all5", "all4") and not v.get("liquid", True):
        return []
    ts = []
    for entry, fill in entries(v, need, mode):
        if entry >= v["n"] - 2:
            continue
        r = run_exit(v, entry, fill, mode)
        if r is None:
            continue
        k, px, why = r
        ts.append(dict(entry=entry, exit=k, bars=k - entry, why=why,
                       net=px / fill - 1 - 2 * COST))
    if mode == "reenter":
        extra = []
        for t in list(ts):
            x, why = t["exit"], t["why"]
            while why == "body":
                nxt = next((k for k in range(x + 1, min(x + 7, v["n"] - 2))
                            if v["hold"][k] and v["up"][k] and v["rising"][k]),
                           None)
                if nxt is None:
                    break
                r = run_exit(v, nxt, v["c"][nxt], "base")
                if r is None:
                    break
                k2, px, why = r
                extra.append(dict(entry=nxt, exit=k2, bars=k2 - nxt, why=why,
                                  net=px / v["c"][nxt] - 1 - 2 * COST))
                x = k2
        ts += extra
    return ts


def null_for(v, n_trades, mode, rng, reps=6):
    m = "base" if mode == "reenter" else mode
    means = []
    for _ in range(reps):
        vals = []
        for _ in range(n_trades):
            i = int(rng.integers(1, v["n"] - 5))
            r = run_exit(v, i, v["c"][i], m)
            if r:
                vals.append(r[1] / v["c"][i] - 1 - 2 * COST)
        if vals:
            means.append(np.mean(vals))
    return float(np.mean(means)) if means else np.nan


def score(frames, need, mode, rng):
    nets, nulls = [], []
    for v in frames:
        t = trades(v, need, mode)
        if not t:
            continue
        nets += [x["net"] for x in t]
        nulls.append(null_for(v, min(len(t), 40), mode, rng))
    if not nets:
        return None
    nn = float(np.nanmean(nulls)) if nulls else np.nan
    a = np.array(nets)
    return dict(n=len(a), mean=float(a.mean()), tot=float(a.sum()),
                win=float((a > 0).mean()), null=nn,
                edge=float(a.mean() - nn))


def observe(frames):
    print("=" * 84)
    print("  OBSERVATIONS FIRST (first halves only)")
    print("=" * 84)

    # 1. after a body close ends a ride: shakeout or real death?
    res_r, dead_r = [], []
    for v in frames:
        hold, up, rising, c, n = v["hold"], v["up"], v["rising"], v["c"], v["n"]
        armed = v["armed"]
        for i in range(1, n - 20):
            if armed[i - 1] and not hold[i]:          # the ride just body-broke
                back = next((k for k in range(i + 1, min(i + 7, n))
                             if hold[k] and up[k] and rising[k]), None)
                fwd = c[i + 12] / c[i] - 1
                (res_r if back is not None else dead_r).append(fwd)
    tot = len(res_r) + len(dead_r)
    if tot:
        print("\n  1. When a ride body-breaks (%d cases):" % tot)
        print("     resumes within 6 bars: %.0f%%  -> next 12 bars run %+.2f%%"
              % (100 * len(res_r) / tot, 100 * np.mean(res_r)))
        print("     stays dead:            %.0f%%  -> next 12 bars run %+.2f%%"
              % (100 * len(dead_r) / tot, 100 * np.mean(dead_r)))

    # 2. does defense predict defense?
    counts = {}
    for v in frames:
        n = v["n"]
        i = 0
        while i < n:
            if not v["armed"][i]:
                i += 1
                continue
            j = i
            while j + 1 < n and v["armed"][j + 1]:
                j += 1
            k = int(v["touch"][i:j + 1].sum())
            for m in range(1, min(k, 8) + 1):
                a, b = counts.get(m, (0, 0))
                counts[m] = (a + 1, b + (1 if k > m else 0))
            i = j + 1
    print("\n  2. Given m defended touches, odds the ride defends another:")
    for m in sorted(counts):
        a, b = counts[m]
        print("     after %d: %5.0f%%   (%d rides)" % (m, 100 * b / a, a))

    # 3. where does the money live?
    nets = []
    for v in frames:
        nets += [t["net"] for t in trades(v, 2, "promote2")]
    a = np.array(sorted(nets))
    if len(a) > 50:
        pos = a[a > 0]
        top = a[int(0.9 * len(a)):]
        print("\n  3. Profit concentration (promote2, 2 touches, %d trades):"
              % len(a))
        print("     top 10%% of trades = %.0f%% of all gross profit"
              % (100 * top[top > 0].sum() / pos.sum()))
        print("     median trade %+.2f%%, mean %+.2f%%"
              % (100 * np.median(a), 100 * a.mean()))
    print()


def main():
    u = crypto.universe(30)
    from concurrent.futures import ThreadPoolExecutor
    pairs = [(x["sym"], x["source"]) for _, x in u.iterrows()]

    def grab(job):
        s, src = job
        try:
            return s, crypto.candles(s, "1h", BARS, source=src)
        except Exception:
            return s, None

    print("fetching...")
    early, late = [], []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for sym, raw in ex.map(grab, pairs):
            for tf, df in (("1h", raw),
                           ("4h", SC.resample(raw, "4h") if raw is not None else None)):
                if df is None or len(df) < 800:
                    continue
                mult = 4 if tf == "4h" else 1
                dv = float((df["Close"] * df["Volume"]).median())                     if "Volume" in df else 0.0
                h = len(df) // 2
                for half, bag in ((df.iloc[:h], early), (df.iloc[h:], late)):
                    v = prep(half)
                    v["sym"], v["tf"] = sym, tf
                    v["liquid"] = dv >= 1e6 * mult
                    bag.append(v)
    print("  %d series halves prepared" % (len(early) + len(late)))


    rng = np.random.default_rng(11)
    grid = [(m, t) for m in MODES for t in TOUCHES]
    ins, oos = {}, {}
    for m, t in grid:
        ins[(m, t)] = score(early, t, m, rng)
        oos[(m, t)] = score(late, t, m, rng)
        print("  grid %d/%d" % (len(ins), len(grid)), end="\r")

    valid = [(k, s) for k, s in ins.items() if s and s["n"] >= 100]
    best = max(valid, key=lambda kv: kv[1]["edge"])[0]

    print("\n" + "=" * 84)
    print("  THE LAB, OUT OF SAMPLE -- chosen on the first half, scored on the second")
    print("  (base = the current rule. tot = summed OOS return, the profit view)")
    print("=" * 84)
    print("  %-10s %-8s %7s %10s %10s %10s %9s"
          % ("mode", "touches", "trades", "in edge", "OOS edge", "OOS mean",
             "OOS tot"))
    rows = sorted(grid, key=lambda k: -(oos[k]["edge"] if oos[k] else -9))
    for key in rows:
        i, o = ins[key], oos[key]
        if not i or not o or o["n"] < 50:
            continue
        mark = "  <- chosen in-sample" if key == best else ""
        print("  %-10s %-8d %7d %+9.3f%% %+9.3f%% %+9.3f%% %+8.1f%%%s"
              % (key[0], key[1], o["n"], 100 * i["edge"], 100 * o["edge"],
                 100 * o["mean"], 100 * o["tot"], mark))

    o = oos.get(best)
    if o:
        print("\n  chosen: %s, %d touches -> OOS %d trades, edge %+.3f%%, "
              "total %+.1f%%"
              % (best[0], best[1], o["n"], 100 * o["edge"], 100 * o["tot"]))


if __name__ == "__main__":
    main()
