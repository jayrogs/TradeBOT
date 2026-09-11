"""
rider_v4.py -- require the EMA to have been DEFENDED before calling it a ride.

    python rider_v4.py                 sweep required touches x stop width
    python rider_v4.py --n 40

THE CHANGE
Every previous version gated the entry on the ride's AGE in bars. That is the
wrong measure: a ride can be twenty bars old having never come near the EMA, or
five bars old having been defended three times. What makes it a rider is that
price keeps coming back to the line and the line keeps holding.

So the gate is now TOUCHES. A touch is a bar whose low reached the EMA (or went
under it) while the body still closed above -- the wick-hold. Entry is only
taken on touch number N+1, after N have already been defended.

This is the same object the charts mark with blue triangles, and it is what
"the chart needs a little more time to be considered an EMA rider" means in
code.

REGIME
The claim attached to this is that the edge is conditional: "it works as long as
things are bullish, and the inverse works as long as things are bearish." So
results are also split by whether the name's own DAILY trend was up at the time
of entry. If the edge only exists in the bullish half, that is a real and usable
finding, not a failure -- but it has to show up in the split rather than be
assumed.

THE NULL
Random entries put through the IDENTICAL trailing stop, so their holding periods
are generated the same way. An earlier null gave random entries the same NUMBER
of bars as real trades, which compared survivors against non-survivors and
invented a +6.6% edge out of nothing.
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
ENTRY_MAX_ATR = 0.25
TOUCHES = [0, 1, 2, 3, 4]
STOPS = [0.01, 0.02, 0.03]


def prep(df):
    c = df["Close"].values.astype(float)
    lo = df["Low"].values.astype(float)
    st = P.trend_state(df)
    state = st[0]
    r = rider.read(df, state=st)
    e = r["ema"]
    a = P._atr(df)
    tol = ENTRY_MAX_ATR * np.where(np.isfinite(a), a, 0.0)
    rising = np.concatenate([[False], e[1:] > e[:-1]])
    holding = r["closed_above"]
    # a TOUCH: the low reached the EMA, the body still held it
    touch = holding & (lo <= e + tol)
    # THE ENTRY IS A LIMIT BID RESTING AT THE EMA, filled when price comes down
    # to it. The previous version required the CLOSE to sit within a fraction of
    # an ATR of the line, which rejects every strong touch -- price dips to the
    # EMA and closes well above it -- and only accepts the weak, limp bounces.
    # Those cluster at the END of a ride, so the rule sat out SOL's entire
    # 200 -> 250 run, counted ten touches, then bought 242.62 at the top and
    # stopped out three bars later.
    near = touch
    # THE TREND MUST STILL BE UP AT THE MOMENT OF ENTRY, not merely when the
    # ride armed. rider.armed LATCHES: it checks the trend once, then stays
    # alive until the EMA body-breaks. So a ride armed in an uptrend survived
    # the trend rolling over, and the rule bought dips inside red downtrends --
    # visible on every chart as a green arrow on a red background.
    up_now = state == "UP"
    return (c, lo, e, r["armed"] & up_now, holding, touch, near, rising, up_now)


def trades(df, need_touches, stop_pct, daily_up=None, exit_on_trend=False,
           exit_body=True, fill_mode="bid"):
    """THE FILL IS A RESTING LIMIT BID, AND IT FILLS ON BAD BARS TOO.

    The previous version only entered on bars it already knew were defended
    touches -- the body held the EMA. But you place the bid DURING the bar,
    before the close exists. On the bar where the ride dies -- low reaches the
    EMA and the body closes under -- a real bid is filled and the trade is an
    instant loser. Skipping those bars filters out exactly the immediate
    losses, which is lookahead. Everything gating the bid now comes from the
    PREVIOUS bar: the ride was alive, the touches were already defended, the
    EMA was already rising.
    """
    c, lo, e, armed, holding, touch, near, rising, up_now = prep(df)
    o = df["Open"].values.astype(float)
    n = len(c)
    out = []
    i = 0
    while i < n:
        if not armed[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and armed[j + 1]:
            j += 1
        # the bid may rest on bar k if, AS OF BAR k-1: the ride was alive,
        # need_touches were already defended, and the EMA was rising. Bar j+1
        # is included -- the bid was resting when that bar opened.
        seen = 0
        entry = None
        if fill_mode == "close":
            # WAIT FOR CONFIRMATION, PAY FOR IT: the touch bar closes, the body
            # held, buy at that close. Fully causal -- the decision and the
            # price both come from the same completed bar. The cost is the
            # distance between the close and the EMA, which the lookahead
            # version pocketed for free.
            for k in range(i, j + 1):
                if touch[k]:
                    seen += 1
                    if seen > need_touches and rising[k]:
                        entry = k
                        fill = c[k]
                        break
        else:
            for k in range(i + 1, min(j + 2, n)):
                if touch[k - 1]:
                    seen += 1
                if seen >= need_touches and rising[k - 1]:
                    bid = e[k - 1]
                    if lo[k] <= bid:
                        entry = k
                        # limit order: filled at the bid, or better on a gap
                        fill = min(bid, o[k])
                        break
        if entry is None or entry >= n - 2:
            i = j + 1
            continue
        # THE EXIT IS THE STATED RULE: a candle BODY closing below the EMA12
        # ends the trade at that bar's close -- INCLUDING the entry bar itself,
        # which is precisely the case the old code was hiding. The stop is
        # disaster protection underneath, the trend-exit optional on top.
        px, why = None, None
        start = entry + 1 if fill_mode == "close" else entry
        for k in range(start, n):
            floor = e[k] * (1 - stop_pct)
            if k > entry and lo[k] <= floor:
                px, why = floor, "stop"
                break
            if exit_body and not holding[k]:
                px, why = c[k], "body"
                break
            if exit_on_trend and k > entry and not up_now[k]:
                px, why = c[k], "trend"
                break
        if px is None:
            i = j + 1
            continue
        out.append(dict(bars=int(k - entry), touches=need_touches,
                        stop=stop_pct, fill=float(fill), why=why,
                        trendexit=exit_on_trend,
                        bull=bool(daily_up[entry]) if daily_up is not None else None,
                        net=float(px / fill - 1 - 2 * COST)))
        i = j + 1
    return out


def null_for(df, n_trades, stop_pct, rng, reps=10, exit_body=True):
    """Random entries through the IDENTICAL exit: body close under the EMA,
    or the trailing stop, whichever first. The null must exit the same way
    the strategy does or the comparison is between different games."""
    c = df["Close"].values.astype(float)
    lo = df["Low"].values.astype(float)
    e = rider.ema(c)
    # the SAME body-hold definition the strategy uses (10% body grace),
    # not a stricter homemade one. Cached: the grid calls this 25x per frame
    # and closed_above does not depend on the configuration.
    key = id(df)
    if null_for._hold.get("k") != key:
        null_for._hold = dict(k=key, v=rider.read(df)["closed_above"])
    body_hold = null_for._hold["v"]
    n = len(c)
    means = []
    for _ in range(reps):
        vals = []
        for _ in range(n_trades):
            i = int(rng.integers(0, n - 5))
            for k in range(i + 1, n):
                floor = e[k] * (1 - stop_pct)
                if lo[k] <= floor:
                    vals.append(floor / c[i] - 1 - 2 * COST)
                    break
                if exit_body and not body_hold[k]:
                    vals.append(c[k] / c[i] - 1 - 2 * COST)
                    break
        if vals:
            means.append(float(np.mean(vals)))
    return float(np.mean(means)) if means else np.nan


null_for._hold = {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--tf", default="15m,1h,4h")
    a = ap.parse_args()
    tfs = [t.strip() for t in a.tf.split(",") if t.strip()]

    u = crypto.universe(a.n)
    from concurrent.futures import ThreadPoolExecutor
    pairs = [(x["sym"], x["source"]) for _, x in u.iterrows()]
    jobs = [(s, src, b) for s, src in pairs for b in ("15m", "1h", "1d")]

    def grab(job):
        s, src, b = job
        try:
            return (s, b), crypto.candles(s, b, BARS, source=src)
        except Exception:
            return (s, b), None

    print("fetching %d series..." % len(jobs))
    store = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for key, df in ex.map(grab, jobs):
            store[key] = df

    rng = np.random.default_rng(5)
    rows, nulls = [], []
    for sym, src in pairs:
        raw = {b: store.get((sym, b)) for b in ("15m", "1h", "1d")}
        dd = raw.get("1d")
        dstate = None
        if dd is not None and len(dd) > 80:
            s1, _, _ = P.trend_state(dd)
            dstate = pd.Series(s1 == "UP", index=dd.index)
        for tf in tfs:
            if tf in SC.BASE:
                df = raw.get(SC.BASE[tf])
            else:
                s2, rule = SC.DERIVE[tf]
                df = SC.resample(raw.get(SC.BASE[s2]), rule)
            if df is None or len(df) < 400:
                continue
            dup = (dstate.reindex(df.index, method="ffill").fillna(False).values
                   if dstate is not None else None)
            for nt in TOUCHES:
                for sp in STOPS:
                    for te in (False, True):
                        t = trades(df, nt, sp, dup, exit_on_trend=te)
                        if not t:
                            continue
                        for x in t:
                            x.update(sym=sym, tf=tf)
                        rows += t
            for sp in STOPS:
                nulls.append(dict(stop=sp, tf=tf, null=null_for(df, 60, sp, rng)))
        print("  %-6s" % sym, end="\r")

    R = pd.DataFrame(rows)
    N = pd.DataFrame(nulls)
    if R.empty:
        print("no trades")
        return
    R.to_csv("rider_v4.csv", index=False)

    print("\n" + "=" * 88)
    print("  REQUIRED TOUCHES BEFORE ENTRY -- crypto, %.1f%% round trip"
          % (200 * COST))
    print("=" * 88)
    for sp in STOPS:
        nn = N[N.stop == sp].null.mean()
        print("\n  stop %.0f%% below the EMA   (null %+.3f%%)" % (100 * sp, 100 * nn))
        print("    %-9s %8s %10s %10s %7s %7s %10s"
              % ("touches", "trades", "mean", "median", "win%", "bars", "vs null"))
        for nt in TOUCHES:
            g = R[(R.touches == nt) & (R.stop == sp)]
            if g.empty:
                continue
            print("    %-9d %8d %+9.3f%% %+9.3f%% %6.0f%% %7.0f %+9.3f%%"
                  % (nt, len(g), 100 * g.net.mean(), 100 * g.net.median(),
                     100 * (g.net > 0).mean(), g.bars.median(),
                     100 * (g.net.mean() - nn)))

    print("\n" + "=" * 88)
    print("  IS IT CONDITIONAL ON THE DAILY BEING UP?")
    print("=" * 88)
    B = R.dropna(subset=["bull"])
    print("  %-9s %-6s %9s %10s %9s %10s"
          % ("touches", "stop", "bull n", "bull mean", "bear n", "bear mean"))
    for nt in TOUCHES:
        for sp in STOPS:
            g = B[(B.touches == nt) & (B.stop == sp)]
            if len(g) < 40:
                continue
            bl, br = g[g.bull], g[~g.bull]
            print("  %-9d %-6s %9d %+9.3f%% %9d %+9.3f%%"
                  % (nt, "%.0f%%" % (100 * sp), len(bl), 100 * bl.net.mean(),
                     len(br), 100 * br.net.mean()))
    print("\n  full table: rider_v4.csv")


if __name__ == "__main__":
    main()
