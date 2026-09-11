"""
es_hourly.py -- broad systematic search for hourly ES systems.

    python es_hourly.py

TEN FAMILIES of system, each swept across its parameters, several thousand
configurations in total. Reported as distributions, never as a winner.

    time_of_day     hold long during a fixed window of the 24-hour session
    day_hour        day-of-week combined with session window
    ma_cross        fast EMA over slow EMA
    donchian        break of an N-bar high, exit on an M-bar low
    rsi_mr          buy oversold, exit on recovery or timeout
    zscore_mr       buy N standard deviations below a moving average
    orb             opening-range breakout after the 09:30 open
    gap             follow or fade the overnight gap into the RTH session
    prior_levels    break or hold of the prior session's high / low
    vol_expansion   trade when volatility expands against its own baseline

THREE CHECKS, applied identically to every family
    1. NULL       the same config run on a phase-shifted return series, which
                  keeps all volatility structure but breaks the link between
                  signal and outcome
    2. TIME SPLIT first 60% of bars to search, last 40% held back. The headline
                  number is what the held-back period says, never the search
                  period.
    3. PERSISTENCE correlation between first-half and second-half results across
                  the whole family. This is the statistic that exposed the last
                  sweep -- winners there had a NEGATIVE correlation, meaning the
                  best performers actively reversed.

Positions are decided at a bar's close and earn the NEXT bar's return, so no
configuration can trade on a price it used to decide. Costs 0.0043% per round
trip, ES realistic (1 tick + $4 on ~$386k notional).
"""

import itertools
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

COST = 0.000043
BARS_PER_YEAR = 24 * 252
MIN_TRADES = 30
SPLIT = 0.60


def load():
    import yfinance as yf
    d = yf.download("ES=F", interval="1h", period="730d", progress=False,
                    auto_adjust=False).dropna()
    d.columns = [c[0] if isinstance(c, tuple) else c for c in d.columns]
    d.index = d.index.tz_convert("America/New_York")
    return d


# ---------------------------------------------------------------- helpers

def ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().values


def rsi_np(c, n):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs)


def evaluate(pos, ret, mask=None, min_trades=None):
    """pos decided at bar i earns ret[i+1]. Costs on position changes."""
    p = np.nan_to_num(pos)
    r = np.zeros(len(p))
    r[1:] = p[:-1] * ret[1:]
    turn = np.abs(np.diff(p, prepend=0.0))
    r = r - turn * (COST / 2)
    if mask is not None:
        r = r[mask]
        turn = turn[mask]
    n_tr = int((turn > 0).sum())
    if n_tr < (MIN_TRADES if min_trades is None else min_trades) or r.std(ddof=1) == 0:
        return None
    eq = np.cumprod(1 + r)
    yrs = len(r) / BARS_PER_YEAR
    return dict(cagr=eq[-1] ** (1 / yrs) - 1,
                sharpe=r.mean() / r.std(ddof=1) * np.sqrt(BARS_PER_YEAR),
                dd=float((eq / np.maximum.accumulate(eq) - 1).min()),
                trades=n_tr, exposure=float(np.abs(p[mask] if mask is not None else p).mean()))


# ---------------------------------------------------------------- families

def build_all(d):
    c = d["Close"].values
    o = d["Open"].values
    h = d["High"].values
    l = d["Low"].values
    hr = d.index.hour.values
    dow = d.index.dayofweek.values
    day = pd.factorize(d.index.date)[0]
    n = len(c)
    out = []

    # --- 1. time of day: long during [a, b) ------------------------------
    for a in range(24):
        for span in [1, 2, 3, 4, 6, 8, 12, 17]:
            b = (a + span) % 24
            win = ((hr >= a) & (hr < a + span)) if a + span <= 24 else \
                  ((hr >= a) | (hr < b))
            out.append(("time_of_day", "%02d:00 for %dh" % (a, span),
                        win.astype(float)))

    # --- 2. day of week x session ---------------------------------------
    for dw in range(5):
        for a, span in [(18, 15), (9, 7), (3, 6), (0, 9)]:
            b = (a + span) % 24
            win = ((hr >= a) & (hr < a + span)) if a + span <= 24 else \
                  ((hr >= a) | (hr < b))
            out.append(("day_hour", "dow%d %02d:00+%dh" % (dw, a, span),
                        (win & (dow == dw)).astype(float)))

    # --- 3. moving average cross ----------------------------------------
    for f, s in itertools.product([4, 8, 12, 24, 48], [24, 48, 96, 168, 336]):
        if f >= s:
            continue
        out.append(("ma_cross", "ema%d>ema%d" % (f, s),
                    (ema(c, f) > ema(c, s)).astype(float)))

    # --- 4. donchian breakout -------------------------------------------
    sc = pd.Series(c)
    for up, dn in itertools.product([12, 24, 48, 96, 168], [6, 12, 24, 48, 96]):
        hi = sc.rolling(up).max().shift(1).values
        lo = sc.rolling(dn).min().shift(1).values
        pos = np.zeros(n)
        state = 0.0
        for i in range(n):
            if np.isfinite(hi[i]) and c[i] > hi[i]:
                state = 1.0
            elif np.isfinite(lo[i]) and c[i] < lo[i]:
                state = 0.0
            pos[i] = state
        out.append(("donchian", "hi%d/lo%d" % (up, dn), pos))

    # --- 5. RSI mean reversion ------------------------------------------
    for ln, lo_th, hold in itertools.product([6, 12, 24], [20, 25, 30, 35], [4, 8, 24, 48]):
        r = rsi_np(c, ln)
        sig = r < lo_th
        pos = pd.Series(sig.astype(float)).rolling(hold, min_periods=1).max().values
        out.append(("rsi_mr", "rsi%d<%d hold%d" % (ln, lo_th, hold), pos))

    # --- 6. z-score mean reversion --------------------------------------
    for ln, z in itertools.product([24, 48, 96, 168], [1.0, 1.5, 2.0, 2.5]):
        m = sc.rolling(ln).mean().values
        sd = sc.rolling(ln).std().values
        zz = (c - m) / np.where(sd > 0, sd, np.nan)
        for hold in [8, 24, 48]:
            sig = zz < -z
            pos = pd.Series(np.nan_to_num(sig).astype(float)).rolling(
                hold, min_periods=1).max().values
            out.append(("zscore_mr", "z%d<-%.1f hold%d" % (ln, z, hold), pos))

    # --- 7. opening range breakout --------------------------------------
    df = pd.DataFrame({"c": c, "h": h, "l": l, "hr": hr, "day": day})
    for k in [1, 2, 3]:
        for direction in [1, -1]:
            pos = np.zeros(n)
            for _, g in df.groupby("day"):
                idx = g.index.values
                rth = g[(g.hr >= 9) & (g.hr < 16)]
                if len(rth) < k + 2:
                    continue
                oh = rth.h.iloc[:k].max()
                ol = rth.l.iloc[:k].min()
                rest = rth.index.values[k:]
                for i in rest:
                    if direction == 1 and c[i] > oh:
                        pos[i:rest[-1] + 1] = 1.0
                        break
                    if direction == -1 and c[i] < ol:
                        pos[i:rest[-1] + 1] = -1.0
                        break
            out.append(("orb", "%dh range %s" % (k, "up" if direction == 1 else "dn"), pos))

    # --- 8. overnight gap follow / fade ---------------------------------
    for thr in [0.0, 0.002, 0.004, 0.008]:
        for sign in [1, -1]:
            pos = np.zeros(n)
            for _, g in df.groupby("day"):
                rth = g[(g.hr >= 9) & (g.hr < 16)]
                if len(rth) < 3:
                    continue
                i0 = rth.index.values[0]
                if i0 == 0:
                    continue
                gap = c[i0] / c[i0 - 1] - 1
                if abs(gap) >= thr:
                    pos[rth.index.values] = sign * np.sign(gap)
            out.append(("gap", "%s gap>%.1f%%" % ("follow" if sign == 1 else "fade",
                                                  100 * thr), pos))

    # --- 9. prior day levels --------------------------------------------
    dayhi = df.groupby("day")["h"].max().shift(1)
    daylo = df.groupby("day")["l"].min().shift(1)
    ph = df["day"].map(dayhi).values
    pl = df["day"].map(daylo).values
    for mode in ["break_high", "buy_low", "hold_above"]:
        for hold in [6, 12, 24]:
            if mode == "break_high":
                sig = c > ph
            elif mode == "buy_low":
                sig = c < pl
            else:
                sig = (c > ph) & (np.roll(c, 1) > ph)
            pos = pd.Series(np.nan_to_num(sig).astype(float)).rolling(
                hold, min_periods=1).max().values
            out.append(("prior_levels", "%s hold%d" % (mode, hold), pos))

    # --- 10. volatility expansion ---------------------------------------
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c, 1)),
                                      np.abs(l - np.roll(c, 1))))
    st = pd.Series(tr)
    for fast, slow, thr in itertools.product([6, 12, 24], [72, 168], [1.2, 1.5, 2.0]):
        ratio = (st.rolling(fast).mean() / st.rolling(slow).mean()).values
        up = c > ema(c, slow)
        out.append(("vol_expansion", "atr%d/%d>%.1f" % (fast, slow, thr),
                    ((ratio > thr) & up).astype(float)))

    return out


def main():
    d = load()
    c = d["Close"].values
    ret = np.zeros(len(c))
    ret[1:] = c[1:] / c[:-1] - 1
    n = len(c)
    cut = int(n * SPLIT)
    m1 = np.zeros(n, bool); m1[:cut] = True
    m2 = np.zeros(n, bool); m2[cut:] = True

    print("ES hourly: %d bars  %s -> %s" % (n, d.index[0].date(), d.index[-1].date()))
    print("  search on bars 0-%d (%s to %s)" % (cut, d.index[0].date(), d.index[cut].date()))
    print("  HELD BACK bars %d-%d (%s to %s)"
          % (cut, n, d.index[cut].date(), d.index[-1].date()))
    bh_all = evaluate(np.ones(n), ret, min_trades=0)
    bh2 = evaluate(np.ones(n), ret, m2, min_trades=0)
    print("  buy & hold: %+.2f%%/yr Sharpe %.2f | held-back period %+.2f%%/yr Sharpe %.2f"
          % (100 * bh_all["cagr"], bh_all["sharpe"], 100 * bh2["cagr"], bh2["sharpe"]))

    # null series: reversed returns preserve volatility structure, break causality
    ret_null = np.concatenate([[0.0], ret[1:][::-1]])

    systems = build_all(d)
    print("\nbuilt %d configurations across %d families"
          % (len(systems), len(set(s[0] for s in systems))))

    rows = []
    for fam, name, pos in systems:
        a = evaluate(pos, ret, m1)
        b = evaluate(pos, ret, m2)
        nl = evaluate(pos, ret_null, m1)
        if a is None or b is None:
            continue
        rows.append(dict(family=fam, name=name,
                         s1=a["sharpe"], c1=a["cagr"],
                         s2=b["sharpe"], c2=b["cagr"], dd2=b["dd"],
                         snull=nl["sharpe"] if nl else np.nan,
                         trades=a["trades"], exp=a["exposure"]))
    r = pd.DataFrame(rows)
    r.to_csv("es_hourly_results.csv", index=False)

    print("\n" + "=" * 82)
    print("  BY FAMILY: best in the search period, and what it did held back")
    print("=" * 82)
    print("  %-14s %6s %26s %8s %9s %9s"
          % ("family", "n", "best config (search)", "Sharpe1", "Sharpe2", "corr"))
    for fam, g in r.groupby("family"):
        best = g.loc[g.s1.idxmax()]
        corr = g.s1.corr(g.s2) if len(g) > 3 else np.nan
        print("  %-14s %6d %26s %8.2f %9.2f %9s"
              % (fam, len(g), best["name"][:26], best.s1, best.s2,
                 "%+.2f" % corr if np.isfinite(corr) else "-"))

    print("\n" + "=" * 82)
    print("  THE OVERALL PICTURE")
    print("=" * 82)
    print("  configurations tested                  %d" % len(r))
    print("  median Sharpe, search period           %+.2f" % r.s1.median())
    print("  median Sharpe, held-back period        %+.2f" % r.s2.median())
    print("  median Sharpe on the NULL series       %+.2f" % r.snull.median())
    print("  best Sharpe in search period           %+.2f" % r.s1.max())
    print("  best on the NULL series                %+.2f" % r.snull.max())
    print("  correlation search vs held back        %+.3f" % r.s1.corr(r.s2))
    top = r.nlargest(30, "s1")
    print("\n  top 30 by search-period Sharpe:")
    print("    mean Sharpe in search                %+.2f" % top.s1.mean())
    print("    mean Sharpe held back                %+.2f" % top.s2.mean())
    print("    still positive when held back        %d of 30" % (top.s2 > 0).sum())
    print("\n  %-30s %8s %8s %9s" % ("top 10 configs", "Sharpe1", "Sharpe2", "CAGR2"))
    for _, x in r.nlargest(10, "s1").iterrows():
        print("  %-30s %8.2f %8.2f %+8.2f%%"
              % ((x.family + " " + x["name"])[:30], x.s1, x.s2, 100 * x.c2))


if __name__ == "__main__":
    main()
