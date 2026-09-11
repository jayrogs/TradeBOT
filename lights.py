"""
lights.py -- the condition panel: green/red lights, a confluence score, and the
             validation that decides whether the score means anything.

    python lights.py --validate      does a higher score actually predict?
    python lights.py --scan          today's panel across the universe
    python lights.py --symbol GLD    one chart, every light explained

THE DESIGN
The user wants a bot that shows a light per condition and green-lights an entry
once enough conditions agree, then eventually trades it. That is a confluence
score, and it is a sound design with exactly one failure mode that matters.

THE FAILURE MODE
Indicators are mostly the same measurement in different clothes. RSI,
stochastics, Williams %R and CCI all read "how far below its recent range is
this thing". Score eight of those and a 6/8 reading feels like six independent
confirmations when it is one signal counted six times -- so the score looks
robust and carries no more information than its first component.

This module therefore does three things, in order:
  1. computes the lights
  2. measures how much each condition ACTUALLY overlaps with the others
  3. tests whether forward returns improve MONOTONICALLY with the score

Step 3 is the gate. If 6/8 does not beat 3/8, the score is decoration. The same
test previously killed the multi-timeframe alignment idea, where requiring more
agreement made results steadily worse.

EVIDENCE LABEL on every condition, from this project's own testing:
    VERIFIED    measured edge that survived an out-of-sample check
    SUPPORTED   consistent with the user's own trade record
    NEUTRAL     no measured edge; included as context
    CONTRARY    measured and found to have no edge or a negative one
"""

import argparse
import os
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

CACHE = os.path.join("cache", "scan_prices.pkl")

# name, evidence label, description
ENTRY_CONDITIONS = [
    ("above_200d",   "VERIFIED",  "price above the 200-day average"),
    ("weekly_os",    "VERIFIED",  "weekly RSI(14) below 40"),
    ("daily_dip",    "SUPPORTED", "daily RSI(14) between 30 and 50"),
    ("below_50d",    "SUPPORTED", "below the 50-day (an actual pullback)"),
    ("off_high",     "SUPPORTED", "10-30% below the 52-week high"),
    ("body_ema12",   "VERIFIED",  "candle body still above the EMA12"),
    ("vol_elevated", "SUPPORTED", "volatility in the top half of its range"),
    ("mom_3m",       "SUPPORTED", "3-month return still positive"),
    ("spring",       "CONTRARY",  "failed weekly breakdown (no measured edge)"),
]
EXIT_CONDITIONS = [
    ("close_lt_ema12", "VERIFIED",  "CLOSE below EMA12 (wicks ignored)"),
    ("close_lt_50d",   "VERIFIED",  "close below the 50-day"),
    ("swing_break",    "SUPPORTED", "broke the last confirmed higher low"),
    ("off_peak_20",    "VERIFIED",  "20% below the highest close since entry"),
    ("weekly_ob",      "NEUTRAL",   "weekly RSI above 70"),
]


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs)


def compute(d):
    """Every condition as a boolean series. No lookahead: all backward-looking."""
    o = d["Open"].values.astype(float)
    c = d["Close"].values.astype(float)
    h = d["High"].values.astype(float)
    l = d["Low"].values.astype(float)
    n = len(c)
    ma50 = pd.Series(c).rolling(50).mean().values
    ma200 = pd.Series(c).rolling(200).mean().values
    ema12 = pd.Series(c).ewm(span=12, adjust=False).mean().values
    rsi_d = rsi(c)
    wk = pd.Series(c, index=d.index).resample("W-FRI").last().dropna()
    rsi_w = pd.Series(rsi(wk.values.astype(float)), index=wk.index
                      ).reindex(d.index, method="ffill").values
    hi52 = pd.Series(c).rolling(252).max().values
    vol = pd.Series(c).pct_change().rolling(20).std()
    volr = vol.rank(pct=True).values
    r60 = pd.Series(c).pct_change(60).values

    # weekly failed breakdown, mapped back to daily
    wl = pd.Series(l, index=d.index).resample("W-FRI").min().dropna()
    wc = wk.values.astype(float)
    wlv = wl.values.astype(float)
    rw = rsi(wc)
    sp = np.zeros(len(wc), bool)
    piv = [i for i in range(2, len(wc) - 2) if wlv[i] == np.nanmin(wlv[i - 2:i + 3])]
    for pi in piv:
        lvl = wlv[pi]
        for j in range(pi + 3, min(pi + 55, len(wc))):
            if wlv[j] < lvl and rw[j] < 40:
                for k in range(j, min(j + 5, len(wc))):
                    if wc[k] > lvl:
                        sp[k] = True
                        break
                break
    spring_d = pd.Series(sp, index=wk.index).rolling(4, min_periods=1).max()
    spring_d = spring_d.reindex(d.index, method="ffill").fillna(0).values.astype(bool)

    # swing-low break
    piv_l = np.full(n, np.nan)
    last = np.nan
    for i in range(5, n - 5):
        if l[i] == np.nanmin(l[i - 5:i + 6]):
            last = l[i]
        piv_l[i + 5] = last
    piv_l = pd.Series(piv_l).ffill().values

    e = {}
    e["above_200d"] = c > ma200
    e["weekly_os"] = rsi_w < 40
    e["daily_dip"] = (rsi_d >= 30) & (rsi_d <= 50)
    e["below_50d"] = c < ma50
    e["off_high"] = (c / hi52 - 1 <= -0.10) & (c / hi52 - 1 >= -0.30)
    e["body_ema12"] = np.minimum(o, c) >= ema12
    e["vol_elevated"] = volr >= 0.5
    e["mom_3m"] = r60 > 0
    e["spring"] = spring_d

    x = {}
    x["close_lt_ema12"] = c < ema12
    x["close_lt_50d"] = c < ma50
    x["swing_break"] = c < piv_l
    x["off_peak_20"] = c < pd.Series(c).rolling(120).max().values * 0.80
    x["weekly_ob"] = rsi_w > 70
    return pd.DataFrame(e, index=d.index), pd.DataFrame(x, index=d.index)


def load():
    if not os.path.exists(CACHE):
        raise SystemExit("run scan.py once first to build the price cache")
    return pd.read_pickle(CACHE)


def validate():
    data = load()
    names = [c[0] for c in ENTRY_CONDITIONS]
    all_e, fwd_all = [], []
    for s, d in data.items():
        if len(d) < 300:
            continue
        try:
            E, X = compute(d)
        except Exception:
            continue
        f = (pd.Series(d["Close"].values).shift(-21) /
             pd.Series(d["Close"].values) - 1).values
        m = np.isfinite(f) & E.notna().all(axis=1).values
        if m.sum() < 100:
            continue
        e = E[m].copy()
        e["_fwd"] = f[m]
        e["_sym"] = s
        all_e.append(e)
    A = pd.concat(all_e, ignore_index=True)
    A["score"] = A[names].sum(axis=1)

    print("=" * 78)
    print("  1. HOW REDUNDANT ARE THE CONDITIONS?")
    print("  correlation between each pair of lights. High = same information.")
    print("=" * 78)
    C = A[names].astype(float).corr()
    print("  %-14s %s" % ("", " ".join("%6s" % n[:6] for n in names)))
    for n in names:
        print("  %-14s %s" % (n[:14],
                              " ".join("%6.2f" % C.loc[n, m] for m in names)))
    pairs = [(a, b, C.loc[a, b]) for i, a in enumerate(names)
             for b in names[i + 1:]]
    worst = sorted(pairs, key=lambda x: -abs(x[2]))[:5]
    print("\n  most redundant pairs:")
    for a, b, v in worst:
        print("    %-16s %-16s %+0.2f" % (a, b, v))

    print("\n" + "=" * 78)
    print("  2. DOES A HIGHER SCORE PREDICT BETTER?  (21-day forward return)")
    print("  THIS IS THE GATE. If it is not monotonic, the score is decoration.")
    print("=" * 78)
    print("  %-8s %10s %14s %10s" % ("score", "samples", "fwd 21d", "hit%"))
    base = A["_fwd"].mean()
    for k in range(0, len(names) + 1):
        g = A[A.score == k]
        if len(g) < 200:
            continue
        print("  %-8d %10d %+13.2f%% %9.0f%%"
              % (k, len(g), 100 * g["_fwd"].mean(), 100 * (g["_fwd"] > 0).mean()))
    print("  %-8s %10d %+13.2f%% %9.0f%%"
          % ("all", len(A), 100 * base, 100 * (A["_fwd"] > 0).mean()))

    print("\n" + "=" * 78)
    print("  3. EACH CONDITION ON ITS OWN")
    print("=" * 78)
    print("  %-16s %-10s %10s %13s %10s"
          % ("condition", "evidence", "samples", "fwd 21d", "vs baseline"))
    lab = {c[0]: c[1] for c in ENTRY_CONDITIONS}
    rows = []
    for n in names:
        g = A[A[n]]
        if len(g) < 200:
            continue
        rows.append((n, lab[n], len(g), g["_fwd"].mean(), g["_fwd"].mean() - base))
    for n, lb, k, f, e in sorted(rows, key=lambda r: -r[4]):
        print("  %-16s %-10s %10d %+12.2f%% %+9.2f%%" % (n, lb, k, 100 * f, 100 * e))
    return A


def panel(sym):
    data = load()
    if sym not in data:
        raise SystemExit("%s not in cache" % sym)
    d = data[sym]
    E, X = compute(d)
    e, x = E.iloc[-1], X.iloc[-1]
    c = d["Close"].values[-1]
    print("\n  %s   %.2f   %s\n" % (sym, c, d.index[-1].date()))
    print("  ENTRY LIGHTS      %d of %d green" % (int(e.sum()), len(e)))
    for n, lb, desc in ENTRY_CONDITIONS:
        print("    [%s] %-14s %-10s %s"
              % ("GREEN" if e[n] else "  -  ", n, lb, desc))
    print("\n  EXIT LIGHTS       %d of %d green" % (int(x.sum()), len(x)))
    for n, lb, desc in EXIT_CONDITIONS:
        print("    [%s] %-16s %-10s %s"
              % ("RED  " if x[n] else "  -  ", n, lb, desc))


def scan_all(min_score=5):
    data = load()
    rows = []
    for s, d in data.items():
        if len(d) < 300:
            continue
        try:
            E, X = compute(d)
        except Exception:
            continue
        e, x = E.iloc[-1], X.iloc[-1]
        rows.append(dict(symbol=s, price=d["Close"].values[-1],
                         entry=int(e.sum()), exit=int(x.sum()),
                         lights=",".join(n for n in E.columns if e[n])))
    R = pd.DataFrame(rows).sort_values(["entry", "exit"], ascending=[False, True])
    R.to_csv("lights_scan.csv", index=False)
    print("=" * 96)
    print("  CONDITION PANEL  %s   (%d symbols)"
          % (pd.Timestamp.today().date(), len(R)))
    print("=" * 96)
    print("  %-10s %11s %7s %6s  %s" % ("symbol", "price", "entry", "exit", "green lights"))
    for _, r in R[R.entry >= min_score].head(40).iterrows():
        print("  %-10s %11.2f %5d/9 %4d/5  %s"
              % (r.symbol, r.price, r.entry, r.exit, r.lights))
    print("\n  full panel: lights_scan.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--symbol")
    a = ap.parse_args()
    if a.validate:
        validate()
    elif a.symbol:
        panel(a.symbol.upper())
    else:
        scan_all()
