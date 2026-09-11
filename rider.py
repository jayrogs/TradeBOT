"""
rider.py -- the EMA 12 Rider playbook.

    python rider.py MRNA D              read one name on one timeframe
    python rider.py --charts 6          render a blind batch to grade

THE PLAYBOOK, as described
    "On strong trend days the 12 EMA acts as a dynamic floor. Buy pullbacks that
    hold the EMA with multiple higher lows, entering on the next dip."

THE RULES, as pinned down

    holding     Judged on the candle BODY, not the close price. A wick below
                the EMA is a hold -- price was bought back up before the close.
                Up to BODY_GRACE of the body may also sit under the EMA; beyond
                that the candle is trading below the line and the ride is over.

                An earlier version tested `close > ema`, which passed candles
                with most of their body underneath it so long as the closing
                tick squeaked over the line.

    armed       LATCHED. Arms when the trend reads UP, the body is holding the
                EMA and MIN_HL higher lows have stacked up. Stays armed through
                the dips until it dies -- the higher lows start the ride, they
                do not have to keep printing during it

    pullback    price has come back to within TOUCH_ATR of the EMA while still
                closing above it -- the dip you are meant to buy

    dead        a close below the 12 EMA, or a close below the last higher low,
                whichever happens first

    Every timeframe uses ITS OWN 12 EMA -- 5m rides the 5m EMA, weekly rides the
    weekly one. This is not the Oversold Bounce, which watches the next higher
    timeframe's EMA instead.

WHAT IS MEASURED AND WHY
    wick holds  bars that dipped under the EMA and closed back above it. The
                signature of the setup: a floor being defended, not just price
                drifting above a line
    ride length how many consecutive closes have held the EMA
    room        distance from price down to the EMA -- how much of a dip is
                available before the next entry
    the EMA     the actual number, which is where the bid goes

UNVALIDATED. These rules are one reading of a one-line description. Nothing here
has been tested for profitability and the trend engine underneath it was wrong
in eleven different ways before it was graded right 24 times. Chart it, grade
it, then argue about it.
"""

import argparse
import json
import os
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import panel as P

warnings.filterwarnings("ignore")

EMA_N = 12
MIN_HL = 2              # consecutive higher lows before the ride is armed
BODY_GRACE = 0.10       # this much of the candle BODY may sit under the EMA
TOUCH_ATR = 0.35        # this close to the EMA counts as a pullback into it
OUT = "validation"


def ema(c, n=EMA_N):
    return pd.Series(c).ewm(span=n, adjust=False).mean().values


def read(df, state=None):
    """Evaluate the rider on one OHLC frame. Returns a per-bar record.

    `state` is an optional (state, hl, lh) triple from P.trend_state. Pass it in
    when the caller already has one: the scanner computed trend_state and then
    called this, which computed it AGAIN, so every (name, timeframe) paid 5.6ms
    twice out of a 13.5ms total.
    """
    c = df["Close"].values.astype(float)
    lo = df["Low"].values.astype(float)
    n = len(c)
    e = ema(c)
    a = P._atr(df)
    st, hl, _ = state if state is not None else P.trend_state(df)

    o = df["Open"].values.astype(float)
    body_lo = np.minimum(o, c)
    body_hi = np.maximum(o, c)
    body = body_hi - body_lo
    # what share of the body is under the EMA
    under = np.clip(e - body_lo, 0.0, None)
    with np.errstate(divide="ignore", invalid="ignore"):
        share = np.where(body > 0, under / np.where(body > 0, body, 1.0),
                         np.where(c < e, 1.0, 0.0))
    # a doji has no body to measure, so fall back to the close
    tiny = body < 0.05 * np.where(np.isfinite(a), a, 1.0)
    share = np.where(tiny, np.where(c < e, 1.0, 0.0), share)
    closed_above = (body_hi > e) & (share <= BODY_GRACE)
    wick_hold = (lo < e) & closed_above

    # consecutive closes holding the EMA, ending at each bar
    ride = np.zeros(n, dtype=int)
    for i in range(n):
        ride[i] = ride[i - 1] + 1 if (i and closed_above[i]) else int(closed_above[i])

    # consecutive higher lows ending at each bar
    hls = np.zeros(n, dtype=int)
    for i in range(1, n):
        hls[i] = hls[i - 1] + 1 if lo[i] > lo[i - 1] else 0

    # The ride LATCHES. It arms when the trend is up, the body is holding the
    # EMA and the higher lows have stacked up -- then it STAYS armed until it
    # dies, regardless of what any single bar's low does.
    #
    # Testing all three conditions bar-by-bar made `armed` and `pullback`
    # mutually exclusive: two consecutive higher lows means price is bouncing
    # AWAY from the EMA, while a pullback means price has come back TO it, which
    # breaks the streak. Across six charts that produced exactly one overlap
    # each -- coincidence, not signal -- and chopped every clean advance into
    # six or seven fragments. The playbook is "higher lows establish the ride,
    # buy the NEXT dip", so the streak is an entry condition, not a live one.
    dead = (~closed_above) | (np.isfinite(hl) & (c < hl))
    armed = np.zeros(n, dtype=bool)
    live = False
    for i in range(n):
        if live:
            if dead[i]:
                live = False
        elif st[i] == "UP" and closed_above[i] and hls[i] >= MIN_HL:
            live = True
        armed[i] = live

    # "enter whenever it gets NEAR the 12 EMA once the rider is engaged."
    # Measured on the bar's LOW, not its close. Testing the close missed 61% of
    # the touches: a candle that dips to the EMA and closes strongly back up --
    # the best version of the setup, and the one the wick-hold triangles mark --
    # was rejected because its CLOSE ended up too far above the line.
    tol = TOUCH_ATR * np.where(np.isfinite(a), a, 0.0)
    pullback = closed_above & (lo - e <= tol)

    return dict(idx=df.index, close=c, ema=e, atr=a, state=st, hl=hl,
                closed_above=closed_above, wick_hold=wick_hold, ride=ride,
                hls=hls, armed=armed, pullback=pullback, dead=dead)


def summarise(r):
    i = len(r["close"]) - 1
    room = (r["close"][i] / r["ema"][i] - 1) if r["ema"][i] > 0 else np.nan
    return dict(
        state=r["state"][i], close=r["close"][i], ema=r["ema"][i],
        holding=bool(r["closed_above"][i]), ride=int(r["ride"][i]),
        higher_lows=int(r["hls"][i]),
        wick_holds=int(np.sum(r["wick_hold"][max(0, i - 40):i + 1])),
        armed=bool(r["armed"][i]), pullback=bool(r["pullback"][i]),
        room=room, stop=r["hl"][i])


# ------------------------------------------------------------------ chart

def draw(df, sym, tf, path):
    r = read(df)
    c, e, lo = r["close"], r["ema"], df["Low"].values.astype(float)
    hi = df["High"].values.astype(float)
    o = df["Open"].values.astype(float)
    x = np.arange(len(df))

    fig, ax = plt.subplots(figsize=(13, 5.6), dpi=110)
    fig.patch.set_facecolor("#0d0f12")
    ax.set_facecolor("#0d0f12")

    # THE BACKGROUND BELONGS TO THE TREND ENGINE, not to this playbook.
    # Green background already means "uptrend" everywhere else in the project,
    # so shading the rider green too would make the two unreadable on one chart
    # -- and the rider only makes sense INSIDE a trend, so both have to show at
    # once. The rider is expressed as a property of the EMA line instead.
    tstate, _, _ = P.display_state(df)
    trend_col = {"UP": "#12351f", "DOWN": "#3a1720", "BALANCE": "#14263d"}
    i = 0
    while i < len(df):
        j = i
        while j + 1 < len(df) and tstate[j + 1] == tstate[i]:
            j += 1
        col = trend_col.get(tstate[i])
        if col:
            ax.axvspan(i - 0.5, j + 0.5, color=col, lw=0, zorder=0)
        i = j + 1

    for k in range(len(df)):
        up = c[k] >= o[k]
        col = "#3ddc97" if up else "#ff5c72"
        ax.plot([k, k], [lo[k], hi[k]], color=col, lw=0.8, zorder=2)
        ax.plot([k, k], [min(o[k], c[k]), max(o[k], c[k])], color=col,
                lw=3.4, zorder=2, solid_capstyle="butt")

    # the EMA carries the rider state: dim and thin when the ride is off,
    # bright and thick with the channel filled in while it is live
    ax.plot(x, e, color="#6b5636", lw=1.2, zorder=3, label="12 EMA")
    live = r["armed"]
    i = 0
    while i < len(df):
        if not live[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(df) and live[j + 1]:
            j += 1
        seg = slice(i, j + 1)
        ax.plot(x[seg], e[seg], color="#ffb84d", lw=3.0, zorder=4,
                solid_capstyle="round")
        ax.fill_between(x[seg], e[seg], c[seg], where=c[seg] >= e[seg],
                        color="#ffb84d", alpha=0.13, lw=0, zorder=1)
        i = j + 1
    ax.plot([], [], color="#ffb84d", lw=3.0, label="rider ARMED")

    # the signature: wicked below, closed above
    w = np.where(r["wick_hold"])[0]
    if len(w):
        ax.scatter(w, lo[w], marker="^", s=42, color="#5aa9ff", zorder=5,
                   label="wick below, closed above (hold)")
    # the dip you are meant to buy
    p = np.where(r["pullback"] & r["armed"])[0]
    if len(p):
        ax.scatter(p, c[p], marker="o", s=30, facecolors="none",
                   edgecolors="#3ddc97", linewidths=1.4, zorder=5,
                   label="pullback into the EMA while armed")
    # where the ride died
    d = np.where(r["dead"] & np.concatenate([[False], r["armed"][:-1]]))[0]
    if len(d):
        ax.scatter(d, c[d], marker="x", s=48, color="#ff5c72", zorder=5,
                   label="ride dead (closed below)")

    ax.set_xlim(-1, len(df))
    ax.tick_params(colors="#8b93a1", labelsize=8)
    for s in ax.spines.values():
        s.set_color("#252a33")
    ax.grid(color="#1b1f26", lw=0.6)
    step = max(len(df) // 9, 1)
    ax.set_xticks(x[::step])
    ax.set_xticklabels([d.strftime("%Y-%m-%d") for d in df.index[::step]],
                       fontsize=7.5)
    ax.set_title("%s  %s   EMA 12 RIDER    %s to %s" %
                 (sym, tf, df.index[0].date(), df.index[-1].date()),
                 color="#e7ebf0", fontsize=11, loc="left", pad=10)
    leg = ax.legend(loc="upper left", fontsize=8, framealpha=.3,
                    facecolor="#15181d", edgecolor="#252a33")
    for t in leg.get_texts():
        t.set_color("#8b93a1")
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return float(np.mean(r["armed"])), int(np.sum(r["wick_hold"]))


def batch(n, seed):
    store = pd.read_pickle(os.path.join("cache", "scan_prices.pkl"))
    syms = sorted([s for s, d in store.items() if len(d) > 900])
    rng = np.random.default_rng(seed)
    items, tries = [], 0
    os.makedirs(OUT, exist_ok=True)
    while len(items) < n and tries < n * 3000:
        tries += 1
        sym = syms[int(rng.integers(len(syms)))]
        tf = ["D", "W"][int(rng.integers(2))]
        d = P.resample(store[sym], "W-FRI") if tf == "W" else store[sym]
        if len(d) < 130:
            continue
        end = int(rng.integers(110, len(d)))
        df = d.iloc[end - 90:end]
        if len(df) < 90 or not np.all(np.isfinite(df["Close"].values)):
            continue
        if any(it["sym"] == sym for it in items):
            continue
        r = read(df)
        # only useful to grade if the playbook actually engages here
        if float(np.mean(r["armed"])) < 0.12:
            continue
        idx = len(items) + 1
        name = "rider_%02d.png" % idx
        try:
            share, wicks = draw(df, sym, tf, os.path.join(OUT, name))
        except Exception as ex:
            print("  skip %s: %s" % (sym, ex))
            continue
        items.append(dict(id=idx, file=name, sym=sym, tf=tf,
                          start=str(df.index[0].date()),
                          end=str(df.index[-1].date()),
                          up=round(share, 3), down=0.0, bal=0.0,
                          flat=round(1 - share, 3)))
        print("  %2d  %-9s %-2s  %s -> %s   armed %3.0f%%  wick-holds %d"
              % (idx, sym, tf, df.index[0].date(), df.index[-1].date(),
                 100 * share, wicks))
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(dict(seed=seed, items=items), f, indent=1)
    print("\n  %d charts -- grade at http://127.0.0.1:5001/validate" % len(items))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol", nargs="?")
    ap.add_argument("tf", nargs="?", default="D")
    ap.add_argument("--charts", type=int, default=0)
    ap.add_argument("--seed", type=int, default=41)
    a = ap.parse_args()

    if a.charts:
        batch(a.charts, a.seed)
        return
    if not a.symbol:
        ap.error("give a symbol, or --charts N")

    store = pd.read_pickle(os.path.join("cache", "scan_prices.pkl"))
    d = store[a.symbol.upper()]
    df = P.resample(d, "W-FRI") if a.tf.upper() == "W" else d
    s = summarise(read(df.tail(200)))
    print("=" * 66)
    print("  %s %s   EMA 12 RIDER" % (a.symbol.upper(), a.tf.upper()))
    print("=" * 66)
    print("  trend            %s" % s["state"])
    print("  close            %.2f" % s["close"])
    print("  12 EMA           %.2f   (%+.1f%% away)"
          % (s["ema"], 100 * s["room"]))
    print("  holding the EMA  %s" % ("yes" if s["holding"] else "NO"))
    print("  ride length      %d closes" % s["ride"])
    print("  higher lows      %d consecutive" % s["higher_lows"])
    print("  wick-holds       %d in the last 40 bars" % s["wick_holds"])
    print()
    print("  ARMED            %s" % ("yes" if s["armed"] else "no"))
    print("  pullback now     %s" % ("YES -- price is at the EMA"
                                     if s["pullback"] else "no"))
    if np.isfinite(s["stop"]):
        print("  dies below       %.2f (last higher low) or a close under the EMA"
              % s["stop"])


if __name__ == "__main__":
    main()
