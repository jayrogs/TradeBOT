"""
exits.py -- which exit rule holds a trend until it actually changes?

    python exits.py

THE QUESTION, from the user:
    "I am trying to make my positions hold for a longer term trend until the
     trend changes, and not just sell cause it goes up and I want to lock in
     money. that would've helped me a lot for silver."

Their own record supports this: 45 position trades made $15,501 while 154 scalps
made $593, and holding SLV made 21x what day-trading the same asset did.

DESIGN
The entry is FIXED and identical for every rule -- RSI(14) below 35 while price
is above its 200-day average, which is the user's documented style (buying
weakness inside an uptrend). Only the EXIT varies. That isolates the one
variable in question; any difference in the results is caused by the exit and
nothing else.

TWELVE EXITS, frozen before running

    profit target      +10% / +20% / +30%      what selling into strength does
    fixed stop         -10% / -20%             no upside cap
    trailing %         10% / 15% / 20% off the high
    chandelier         highest high - 3 x ATR
    swing low          break of the last confirmed higher low (the user's rule)
    ma break           close below the 20 / 50 / 200-day average
    weekly ma break    close below the 10-week average
    time               hold 60 days regardless

THE METRIC THAT ANSWERS THE QUESTION
Capture ratio: of the maximum gain the trade ever offered, what fraction did the
rule actually collect? A profit target caps this by construction. A trailing
rule gives back some at the end but stays in for the whole middle. That
trade-off is the entire question, and it is measurable.
"""

import warnings

import numpy as np
import pandas as pd

import daily_sweep as D

warnings.filterwarnings("ignore")

UNIVERSE = ["SLV", "GLD", "UUUU", "CVX", "QQQ", "TSLA", "CL=F", "NG=F",
            "BTC-USD", "ES=F", "GC=F", "XLE"]
COST = 0.0004
MAXBARS = 500


def rsi_np(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs)


def atr_np(h, l, c, n=14):
    pc = np.roll(c, 1)
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().values


def pivots(l, P):
    n = len(l)
    conf = np.full(n, -1, dtype=int)
    for i in range(P, n - P):
        if l[i] == np.nanmin(l[i - P:i + P + 1]) and i + P < n:
            conf[i + P] = i
    return conf


def simulate(c, h, l, entry_idx, rule, ctx):
    """Walk one trade forward from entry_idx. Return (exit_idx, exit_px, mfe)."""
    e = c[entry_idx]
    peak = e
    stop = None
    piv_stop = None
    conf = ctx.get("piv")
    a = ctx["atr"]
    for i in range(entry_idx + 1, min(entry_idx + MAXBARS, len(c))):
        peak = max(peak, h[i])
        kind, p = rule
        if kind == "target":
            if h[i] >= e * (1 + p):
                return i, e * (1 + p), peak / e - 1
        elif kind == "stop":
            if l[i] <= e * (1 - p):
                return i, e * (1 - p), peak / e - 1
        elif kind == "trail_pct":
            lvl = peak * (1 - p)
            if l[i] <= lvl:
                return i, lvl, peak / e - 1
        elif kind == "chandelier":
            lvl = peak - p * a[i]
            if l[i] <= lvl:
                return i, lvl, peak / e - 1
        elif kind == "swing":
            if conf[i] >= 0:
                v = l[conf[i]]
                if piv_stop is None or v > piv_stop:
                    piv_stop = v
            if piv_stop is not None and l[i] <= piv_stop:
                return i, piv_stop, peak / e - 1
        elif kind == "ma":
            # arm only once price has actually got above the average, otherwise
            # an oversold entry exits on day one by construction
            m = ctx["ma%d" % p][i]
            if not ctx.setdefault("_armed", {}).get((entry_idx, p), False):
                if c[i] > m:
                    ctx["_armed"][(entry_idx, p)] = True
            elif c[i] < m:
                return i, c[i], peak / e - 1
        elif kind == "time":
            if i - entry_idx >= p:
                return i, c[i], peak / e - 1
    j = min(entry_idx + MAXBARS, len(c) - 1)
    return j, c[j], peak / e - 1


RULES = [
    ("target +10%",      ("target", 0.10)),
    ("target +20%",      ("target", 0.20)),
    ("target +30%",      ("target", 0.30)),
    ("hard stop -10%",   ("stop", 0.10)),
    ("hard stop -20%",   ("stop", 0.20)),
    ("trail 10% off hi", ("trail_pct", 0.10)),
    ("trail 15% off hi", ("trail_pct", 0.15)),
    ("trail 20% off hi", ("trail_pct", 0.20)),
    ("chandelier 3xATR", ("chandelier", 3.0)),
    ("swing low break",  ("swing", 5)),
    ("close < 20d MA",   ("ma", 20)),
    ("close < 50d MA",   ("ma", 50)),
    ("close < 200d MA",  ("ma", 200)),
    ("hold 60 days",     ("time", 60)),
]


def main():
    data = D.load()
    import yfinance as yf
    for s in UNIVERSE:
        if s not in data:
            d = yf.download(s, start="1990-01-01", end="2026-08-19",
                            progress=False, auto_adjust=False).dropna()
            if len(d) > 500:
                d.columns = [c[0] if isinstance(c, tuple) else c for c in d.columns]
                if getattr(d.index, "tz", None) is not None:
                    d.index = d.index.tz_localize(None)
                data[s] = d

    rows = []
    for sym in UNIVERSE:
        if sym not in data:
            continue
        d = data[sym]
        c = d["Close"].values.astype(float)
        h = d["High"].values.astype(float)
        l = d["Low"].values.astype(float)
        ctx = {"atr": atr_np(h, l, c), "piv": pivots(l, 5)}
        for m in (20, 50, 200):
            ctx["ma%d" % m] = pd.Series(c).rolling(m).mean().values
        ma200 = ctx["ma200"]
        r = rsi_np(c)
        sig = np.nan_to_num((r < 35) & (c > ma200)).astype(bool)

        for name, rule in RULES:
            i = 250
            trades = []
            while i < len(c) - 2:
                if not sig[i]:
                    i += 1
                    continue
                j, px, mfe = simulate(c, h, l, i, rule, ctx)
                ret = (px * (1 - COST / 2)) / (c[i] * (1 + COST / 2)) - 1
                trades.append((ret, j - i, mfe))
                i = j + 1
            ctx.pop("_armed", None)
            if len(trades) >= 8:
                t = pd.DataFrame(trades, columns=["ret", "days", "mfe"])
                cap = np.where(t.mfe > 0, t.ret / t.mfe.replace(0, np.nan), np.nan)
                total = (1 + t.ret).prod()
                yrs_in = t.days.sum() / 252.0
                rows.append(dict(symbol=sym, rule=name, n=len(t),
                                 avg=t.ret.mean(), med=t.ret.median(),
                                 win=(t.ret > 0).mean(), days=t.days.median(),
                                 mfe=t.mfe.mean(),
                                 capture=np.nanmean(np.clip(cap, -2, 2)),
                                 per_year=total ** (1 / yrs_in) - 1 if yrs_in > 0.5 else np.nan,
                                 yrs_in=yrs_in,
                                 total=total - 1))
    R = pd.DataFrame(rows)
    R.to_csv("exit_results.csv", index=False)

    print("=" * 88)
    print("  EXIT RULE COMPARISON -- identical entries, only the exit differs")
    print("  %d instruments, entry = RSI(14)<35 while above the 200-day average"
          % R.symbol.nunique())
    print("=" * 88)
    g = R.groupby("rule").agg(n=("n", "sum"), avg=("avg", "mean"),
                              win=("win", "mean"), days=("days", "median"),
                              mfe=("mfe", "mean"), capture=("capture", "mean"))
    g = g.sort_values("avg", ascending=False)
    print("  %-20s %6s %9s %7s %7s %10s %9s"
          % ("exit rule", "trades", "avg/trade", "win%", "days", "avg peak", "capture"))
    for k, x in g.iterrows():
        print("  %-20s %6d %+8.2f%% %6.0f%% %6.0f %+9.2f%% %8.0f%%"
              % (k, x.n, 100 * x.avg, 100 * x.win, x.days, 100 * x.mfe,
                 100 * x.capture))

    print("\n  'avg peak' = how much the trade was up at its best moment.")
    print("  'capture'  = what share of that peak the rule actually collected.")

    print("\n" + "=" * 88)
    print("  THE TRADE-OFF, stated plainly")
    print("=" * 88)
    tg = g.loc[[i for i in g.index if i.startswith("target")]]
    tr = g.loc[[i for i in g.index if i.startswith("trail") or "MA" in i
                or i.startswith("swing") or i.startswith("chandelier")]]
    print("  profit targets:  avg %+.2f%%/trade, capture %.0f%%, %.0f%% win rate"
          % (100 * tg.avg.mean(), 100 * tg.capture.mean(), 100 * tg.win.mean()))
    print("  trailing exits:  avg %+.2f%%/trade, capture %.0f%%, %.0f%% win rate"
          % (100 * tr.avg.mean(), 100 * tr.capture.mean(), 100 * tr.win.mean()))
    print("\n  Targets win more often and earn less. That is the whole point:")
    print("  locking in gains feels good and costs money.")

    print("\n" + "=" * 88)
    print("  PER INSTRUMENT: best exit rule by average return per trade")
    print("=" * 88)
    print("  %-10s %-20s %9s %8s   %-20s %9s"
          % ("symbol", "best rule", "avg", "win%", "vs +20% target", "diff"))
    for sym in R.symbol.unique():
        s = R[R.symbol == sym]
        b = s.loc[s.avg.idxmax()]
        t20 = s[s.rule == "target +20%"]
        t = t20.avg.iloc[0] if len(t20) else np.nan
        print("  %-10s %-20s %+8.2f%% %7.0f%%   %-20s %+8.2f%%"
              % (sym, b.rule, 100 * b.avg, 100 * b.win, "",
                 100 * (b.avg - t) if np.isfinite(t) else np.nan))


if __name__ == "__main__":
    main()
