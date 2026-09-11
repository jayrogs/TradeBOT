"""
daily_sweep.py -- systems on DAILY and WEEKLY bars, across ten markets,
                  with 12 to 30 years of history each.

    python daily_sweep.py

WHY THIS IS THE BEST-POSED TEST IN THE PROJECT
    - 12-30 years per market instead of 29 months
    - trading costs stop dominating: a few dozen trades a year, not thousands
    - crude, gas and the FX pairs have no long-term drift, so "beat buy and
      hold" is a fair bar rather than a race against a rising index
    - daily and weekly trend following is where the documented managed-futures
      evidence actually lives

MARKETS
    BTC-USD 11.9yr   TSLA 16.1yr   UUUU 19.4yr   CL=F 26yr    NG=F 26yr
    QQQ 27.4yr       EURUSD 22.7yr USDJPY 29.8yr GBPUSD 22.7yr ES=F 25.9yr

FAMILIES  (long-only and long-short where it makes sense)
    ma_cross      fast over slow moving average
    donchian      turtle-style N-day breakout, exit on M-day extreme
    tsmom         time-series momentum: hold while the N-day return is positive
    atr_trail     enter on trend, trail an ATR-based stop
    swing_trail   enter on a higher low, trail the stop under each new one
                  (the user's own rule, generalised)
    rsi_mr        buy oversold, exit on recovery or timeout
    bollinger     buy N standard deviations below, exit at the mean
    vol_target    trend signal, position scaled inversely to volatility
    weekly_*      the main families recomputed on weekly bars

SPLIT
    Per market, first 60% of bars to search, last 40% held back and not looked
    at until the end. The headline is always the held-back number.

THE TEST THAT MATTERS
    Average each configuration across all ten markets in the search period,
    take the top, and see what those same configurations did held back. A rule
    that describes markets should survive markets it was not fitted to.
"""

import itertools
import os
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

CACHE = os.path.join("cache", "daily_multi.pkl")
SPLIT = 0.60
MIN_TRADES = 15

MARKETS = {
    "BTC-USD":  ("Bitcoin",      0.0006),
    "TSLA":     ("Tesla",        0.0004),
    "UUUU":     ("uranium",      0.0020),
    "CL=F":     ("crude",        0.0002),
    "NG=F":     ("nat gas",      0.0005),
    "QQQ":      ("Nasdaq",       0.0002),
    "EURUSD=X": ("EUR/USD",      0.0002),
    "USDJPY=X": ("USD/JPY",      0.0002),
    "GBPUSD=X": ("GBP/USD",      0.0002),
    "ES=F":     ("S&P futures",  0.0001),
}


def load(refresh=False):
    if os.path.exists(CACHE) and not refresh:
        return pd.read_pickle(CACHE)
    import yfinance as yf
    out = {}
    for s in MARKETS:
        d = yf.download(s, start="1990-01-01", end="2026-08-19",
                        progress=False, auto_adjust=False).dropna()
        if len(d) < 500:
            continue
        d.columns = [c[0] if isinstance(c, tuple) else c for c in d.columns]
        if getattr(d.index, "tz", None) is not None:
            d.index = d.index.tz_localize(None)
        out[s] = d
        print("  %-10s %5d bars  %s -> %s"
              % (s, len(d), d.index[0].date(), d.index[-1].date()))
    pd.to_pickle(out, CACHE)
    return out


# ---------------------------------------------------------------- indicators

def ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().values


def sma(x, n):
    return pd.Series(x).rolling(n).mean().values


def atr(h, l, c, n):
    pc = np.roll(c, 1)
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1.0 / n, adjust=False).mean().values


def rsi_np(c, n):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs)


def trail_stop(c, h, l, entry_sig, stop_dist, long_only=True):
    """Generic trailing-stop runner: enter on signal, trail stop by stop_dist,
    exit when breached. stop_dist is an array (ATR-based or fixed)."""
    n = len(c)
    pos = np.zeros(n)
    in_p = False
    stop = np.nan
    for i in range(n):
        if in_p:
            if l[i] <= stop:
                in_p = False
            else:
                stop = max(stop, c[i] - stop_dist[i])
                pos[i] = 1.0
        if not in_p and entry_sig[i] and np.isfinite(stop_dist[i]) and stop_dist[i] > 0:
            in_p = True
            stop = c[i] - stop_dist[i]
            pos[i] = 1.0
    return pos


def swing_trail(c, h, l, ma_ok, P):
    """The user's rule: enter on a confirmed higher low in an uptrend, trail the
    stop under each new higher low, exit when one breaks."""
    n = len(c)
    conf = np.full(n, -1, dtype=int)
    for i in range(P, n - P):
        if l[i] == np.nanmin(l[i - P:i + P + 1]) and i + P < n:
            conf[i + P] = i
    pos = np.zeros(n)
    in_p = False
    stop = prev = np.nan
    for i in range(n):
        pi = conf[i]
        v = l[pi] if pi >= 0 else np.nan
        if in_p:
            if l[i] <= stop:
                in_p = False
            else:
                pos[i] = 1.0
                if pi >= 0 and v > stop:
                    stop = v
        if not in_p and pi >= 0 and np.isfinite(v) and np.isfinite(prev) \
                and v > prev and ma_ok[i]:
            in_p, stop, pos[i] = True, v, 1.0
        if pi >= 0 and np.isfinite(v):
            prev = v
    return pos


# ---------------------------------------------------------------- families

def build(d, weekly=False):
    if weekly:
        d = d.resample("W-FRI").agg({"Open": "first", "High": "max",
                                     "Low": "min", "Close": "last"}).dropna()
    c = d["Close"].values.astype(float)
    h = d["High"].values.astype(float)
    l = d["Low"].values.astype(float)
    n = len(c)
    pre = "wk_" if weekly else ""
    out = []
    if n < 300:
        return out, d

    scale = 5 if weekly else 1

    # ma cross
    for f, s in itertools.product([5, 10, 20, 50], [20, 50, 100, 200]):
        if f >= s or s // scale < 3:
            continue
        out.append((pre + "ma_cross", "ema%d>ema%d" % (f, s),
                    (ema(c, max(2, f // scale)) > ema(c, max(3, s // scale))).astype(float)))

    # donchian
    sc = pd.Series(c)
    for up, dn in itertools.product([10, 20, 55, 100], [5, 10, 20, 55]):
        u = max(3, up // scale); v = max(2, dn // scale)
        hi = sc.rolling(u).max().shift(1).values
        lo = sc.rolling(v).min().shift(1).values
        pos = np.zeros(n); st = 0.0
        for i in range(n):
            if np.isfinite(hi[i]) and c[i] > hi[i]:
                st = 1.0
            elif np.isfinite(lo[i]) and c[i] < lo[i]:
                st = 0.0
            pos[i] = st
        out.append((pre + "donchian", "hi%d/lo%d" % (up, dn), pos))

    # time series momentum
    for lb in [20, 60, 120, 250]:
        k = max(2, lb // scale)
        out.append((pre + "tsmom", "%dd return>0" % lb,
                    (c > np.roll(c, k)).astype(float)))

    # atr trailing
    for lb, mult in itertools.product([20, 50, 100], [2.0, 3.0, 4.0]):
        k = max(3, lb // scale)
        a = atr(h, l, c, max(3, 14 // scale))
        sig = c > sma(c, k)
        out.append((pre + "atr_trail", "ma%d entry, %.1fATR trail" % (lb, mult),
                    trail_stop(c, h, l, np.nan_to_num(sig).astype(bool), mult * a)))

    # swing trail (the user's rule)
    for P, lb in itertools.product([3, 5, 10], [50, 200]):
        k = max(3, lb // scale)
        out.append((pre + "swing_trail", "pivot%d ma%d" % (P, lb),
                    swing_trail(c, h, l, np.nan_to_num(c > sma(c, k)).astype(bool), P)))

    # rsi mean reversion
    for ln, th, hold in itertools.product([7, 14], [25, 30, 35], [5, 10, 20]):
        r = rsi_np(c, max(2, ln // scale))
        out.append((pre + "rsi_mr", "rsi%d<%d hold%d" % (ln, th, hold),
                    pd.Series((r < th).astype(float)).rolling(
                        max(1, hold // scale), min_periods=1).max().values))

    # bollinger
    for ln, z in itertools.product([20, 50, 100], [1.5, 2.0, 2.5]):
        k = max(3, ln // scale)
        m = sma(c, k); sd = pd.Series(c).rolling(k).std().values
        zz = (c - m) / np.where(sd > 0, sd, np.nan)
        pos = np.zeros(n); st = 0.0
        for i in range(n):
            if np.isfinite(zz[i]):
                if zz[i] < -z:
                    st = 1.0
                elif zz[i] > 0:
                    st = 0.0
            pos[i] = st
        out.append((pre + "bollinger", "z%d<-%.1f exit mid" % (ln, z), pos))

    # vol targeted trend
    for lb in [50, 100, 200]:
        k = max(3, lb // scale)
        vol = pd.Series(c).pct_change().rolling(max(5, 20 // scale)).std().values
        sig = (c > sma(c, k)).astype(float)
        w = np.where(vol > 0, np.clip(0.15 / (vol * np.sqrt(252 / scale)), 0, 3), 0)
        out.append((pre + "vol_target", "ma%d, 15%% vol target" % lb, sig * w))

    return out, d


# ---------------------------------------------------------------- evaluation

def evaluate(pos, ret, mask, cost, min_trades=MIN_TRADES, ann=252):
    p = np.nan_to_num(pos)
    r = np.zeros(len(p))
    r[1:] = p[:-1] * ret[1:]
    turn = np.abs(np.diff(p, prepend=0.0))
    r = r - turn * (cost / 2)
    r, turn = r[mask], turn[mask]
    n_tr = int((turn > 0).sum())
    if n_tr < min_trades or r.std(ddof=1) == 0:
        return None
    eq = np.cumprod(1 + r)
    yrs = len(r) / ann
    return dict(cagr=eq[-1] ** (1 / yrs) - 1 if eq[-1] > 0 else -1.0,
                sharpe=r.mean() / r.std(ddof=1) * np.sqrt(ann),
                dd=float((eq / np.maximum.accumulate(eq) - 1).min()),
                trades=n_tr)


def main():
    print("loading daily bars...")
    data = load()
    rows, bh = [], {}

    for sym, (nm, cost) in MARKETS.items():
        if sym not in data:
            continue
        for weekly in (False, True):
            systems, dd = build(data[sym], weekly)
            if not systems:
                continue
            c = dd["Close"].values.astype(float)
            ret = np.zeros(len(c)); ret[1:] = c[1:] / c[:-1] - 1
            n = len(c); cut = int(n * SPLIT)
            m1 = np.zeros(n, bool); m1[:cut] = True
            m2 = np.zeros(n, bool); m2[cut:] = True
            ann = 52 if weekly else 252
            if not weekly:
                b1 = evaluate(np.ones(n), ret, m1, 0.0, 0, ann)
                b2 = evaluate(np.ones(n), ret, m2, 0.0, 0, ann)
                bh[sym] = (b1, b2)
            for fam, name, pos in systems:
                a = evaluate(pos, ret, m1, cost, ann=ann)
                b = evaluate(pos, ret, m2, cost, ann=ann)
                if a is None or b is None:
                    continue
                rows.append(dict(symbol=sym, family=fam,
                                 config="%s | %s" % (fam, name),
                                 s1=a["sharpe"], s2=b["sharpe"],
                                 c2=b["cagr"], dd2=b["dd"]))
        print("  %-10s done" % sym)

    R = pd.DataFrame(rows)
    R.to_csv("daily_sweep_results.csv", index=False)
    print("\n%d configuration-market results" % len(R))

    print("\n" + "=" * 84)
    print("  PER MARKET: best in search, and what it did held back")
    print("=" * 84)
    print("  %-10s %-34s %8s %8s %9s" % ("market", "best config in search",
                                         "search", "HELD", "b&h held"))
    for sym in R.symbol.unique():
        g = R[R.symbol == sym]
        b = g.loc[g.s1.idxmax()]
        bhs = bh[sym][1]["sharpe"] if sym in bh and bh[sym][1] else float("nan")
        print("  %-10s %-34s %8.2f %8.2f %9.2f"
              % (sym, b.config[:34], b.s1, b.s2, bhs))

    print("\n" + "=" * 84)
    print("  CROSS-MARKET: configs averaged over all ten")
    print("=" * 84)
    p1 = R.pivot_table(index="config", columns="symbol", values="s1")
    p2 = R.pivot_table(index="config", columns="symbol", values="s2")
    keep = p1.dropna(thresh=8).index
    p1, p2 = p1.loc[keep], p2.loc[keep]
    m1, m2 = p1.mean(axis=1), p2.mean(axis=1)
    print("  %d configs ran on 8+ markets" % len(m1))
    print("  correlation of cross-market Sharpe, search vs held back: %+.3f"
          % m1.corr(m2))
    bh_h = np.nanmean([bh[s][1]["sharpe"] for s in bh if bh[s][1]])
    print("  average buy & hold, held back: %+.2f" % bh_h)
    top = m1.nlargest(25)
    print("\n  top 25 by cross-market search Sharpe:")
    print("    mean search %+.2f  ->  mean HELD BACK %+.2f" % (top.mean(), m2.loc[top.index].mean()))
    print("    positive held back:  %d of 25" % (m2.loc[top.index] > 0).sum())
    print("    beat buy & hold:     %d of 25" % (m2.loc[top.index] > bh_h).sum())
    print("\n  %-44s %8s %8s %7s" % ("config", "search", "HELD", "n mkts"))
    for cfg in top.index[:15]:
        print("  %-44s %8.2f %8.2f %7d"
              % (cfg[:44], m1[cfg], m2[cfg], int(p2.loc[cfg].notna().sum())))

    print("\n" + "=" * 84)
    print("  BY FAMILY, all markets")
    print("=" * 84)
    fam = R.groupby("family").agg(n=("s1", "size"), s1=("s1", "mean"),
                                  s2=("s2", "mean"))
    fam["corr"] = [R[R.family == f].s1.corr(R[R.family == f].s2) for f in fam.index]
    print("  %-18s %6s %9s %9s %8s" % ("family", "n", "search", "HELD", "corr"))
    for f, x in fam.sort_values("s2", ascending=False).iterrows():
        print("  %-18s %6d %9.2f %9.2f %8.2f" % (f, x.n, x.s1, x.s2, x["corr"]))


if __name__ == "__main__":
    main()
