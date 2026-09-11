"""
bot.py -- full portfolio backtest of system_spec_v2.md, plus a live signal scan.

    python bot.py            backtest, search window then confirmation window
    python bot.py --today    what the system says right now

Entry:  close > 200-day MA and RSI(14) < 35, buy next open
Exit:   trailing stop 20% below the highest close since entry. Nothing else.
Size:   12.5% of equity per position, max 8 concurrent
Costs:  0.05% per side
"""

import argparse
import os
import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

CACHE = os.path.join("cache", "bot_prices.pkl")

UNIVERSE = ["GLD", "SLV", "GDX", "UUUU", "PLG",
            "XLE", "CVX", "XOM", "USO",
            "SPY", "QQQ", "IWM", "DIA",
            "XLF", "XLK", "XLV", "XLI", "XLU", "XLP",
            "AAPL", "MSFT", "NVDA", "TSLA", "AMD", "JPM",
            "TLT", "EEM", "EFA", "VNQ", "BTC-USD"]

TRAIL = 0.20
MAX_POS = 8
WEIGHT = 0.125
COST = 0.0005
RSI_MAX = 35
SEARCH = ("2007-01-01", "2018-12-31")
CONFIRM = ("2019-01-01", "2026-08-19")


def load(refresh=False):
    if os.path.exists(CACHE) and not refresh:
        return pd.read_pickle(CACHE)
    import yfinance as yf
    out = {}
    for s in UNIVERSE:
        d = yf.download(s, start="2004-01-01", end="2026-08-20",
                        progress=False, auto_adjust=False).dropna()
        if len(d) < 400:
            continue
        d.columns = [c[0] if isinstance(c, tuple) else c for c in d.columns]
        if getattr(d.index, "tz", None) is not None:
            d.index = d.index.tz_localize(None)
        out[s] = d
    pd.to_pickle(out, CACHE)
    return out


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs)


def features(data):
    f = {}
    for s, d in data.items():
        c = d["Close"].values.astype(float)
        x = pd.DataFrame(index=d.index)
        x["open"] = d["Open"].values
        x["close"] = c
        x["low"] = d["Low"].values
        x["ma200"] = pd.Series(c).rolling(200).mean().values
        x["rsi"] = rsi(c)
        x["adv"] = (pd.Series(c).rolling(20).mean() *
                    pd.Series(d["Volume"].values.astype(float)).rolling(20).mean()).values
        f[s] = x
    return f


@dataclass
class Pos:
    sym: str
    shares: float
    entry: float
    peak: float
    day: int


def backtest(f, cal, start, end, trail=TRAIL, verbose=False):
    days = cal[(cal >= pd.Timestamp(start)) & (cal <= pd.Timestamp(end))]
    cash = 100_000.0
    pos = {}
    trades = []
    curve = []

    for i, day in enumerate(days):
        # ---- exits first
        for s in list(pos):
            x = f[s]
            if day not in x.index:
                continue
            r = x.loc[day]
            p = pos[s]
            p.peak = max(p.peak, r["close"])
            stop = p.peak * (1 - trail)
            if r["low"] <= stop:
                px = min(r["open"], stop) if r["open"] < stop else stop
                px *= (1 - COST)
                cash += p.shares * px
                trades.append(dict(sym=s, entry_day=p.day, exit_day=i,
                                   entry=p.entry, exit=px,
                                   ret=px / p.entry - 1,
                                   days=i - p.day))
                del pos[s]

        equity = cash + sum(p.shares * f[s]["close"].asof(day) for s, p in pos.items())
        curve.append((day, equity, len(pos)))

        # ---- entries on tomorrow's open
        if i + 1 >= len(days) or len(pos) >= MAX_POS:
            continue
        nxt = days[i + 1]
        cands = []
        for s, x in f.items():
            if s in pos or day not in x.index or nxt not in x.index:
                continue
            r = x.loc[day]
            if not np.isfinite(r["ma200"]) or not np.isfinite(r["rsi"]):
                continue
            if r["close"] > r["ma200"] and r["rsi"] < RSI_MAX and \
               r["close"] > 5 and r["adv"] > 10e6:
                cands.append((r["rsi"], s))
        cands.sort()
        for _, s in cands:
            if len(pos) >= MAX_POS:
                break
            px = f[s].loc[nxt, "open"] * (1 + COST)
            size = equity * WEIGHT
            if size > cash or px <= 0:
                continue
            sh = size / px
            cash -= sh * px
            pos[s] = Pos(s, sh, px, f[s].loc[nxt, "close"], i + 1)

    eq = pd.DataFrame(curve, columns=["date", "equity", "n"]).set_index("date")
    return eq, pd.DataFrame(trades)


def stats(eq, label):
    e = eq["equity"]
    yrs = (e.index[-1] - e.index[0]).days / 365.25
    r = e.pct_change().dropna()
    return dict(label=label, cagr=(e.iloc[-1] / e.iloc[0]) ** (1 / yrs) - 1,
                dd=float((e / e.cummax() - 1).min()),
                sharpe=r.mean() / r.std(ddof=1) * np.sqrt(252),
                exposure=eq["n"].mean() / MAX_POS)


def bench(data, start, end):
    c = data["SPY"]["Close"]
    c = c[(c.index >= pd.Timestamp(start)) & (c.index <= pd.Timestamp(end))]
    yrs = (c.index[-1] - c.index[0]).days / 365.25
    r = c.pct_change().dropna()
    return dict(label="SPY buy & hold", cagr=(c.iloc[-1] / c.iloc[0]) ** (1 / yrs) - 1,
                dd=float((c / c.cummax() - 1).min()),
                sharpe=r.mean() / r.std(ddof=1) * np.sqrt(252), exposure=1.0)


def row(s):
    return ("  %-24s %+9.2f%% %9.1f%% %8.2f %9.0f%%"
            % (s["label"], 100 * s["cagr"], 100 * s["dd"], s["sharpe"],
               100 * s["exposure"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", action="store_true")
    args = ap.parse_args()
    data = load()
    f = features(data)
    cal = data["SPY"].index

    if args.today:
        day = cal[-1]
        print("SIGNALS AS OF %s\n" % day.date())
        print("  %-8s %8s %8s %8s  %s" % ("symbol", "close", "RSI", "vs 200d", "signal"))
        for s, x in sorted(f.items()):
            if day not in x.index:
                continue
            r = x.loc[day]
            if not np.isfinite(r["ma200"]):
                continue
            up = r["close"] / r["ma200"] - 1
            sig = "BUY" if (r["close"] > r["ma200"] and r["rsi"] < RSI_MAX) else ""
            if sig or r["rsi"] < 45:
                print("  %-8s %8.2f %8.1f %+7.1f%%  %s"
                      % (s, r["close"], r["rsi"], 100 * up, sig))
        return

    print("=" * 74)
    print("  TREND-HOLD SYSTEM  (system_spec_v2.md)")
    print("  entry: RSI(14)<35 above the 200-day  |  exit: 20%% trailing stop")
    print("=" * 74)
    for start, end, nm in [(SEARCH[0], SEARCH[1], "SEARCH 2007-2018"),
                           (CONFIRM[0], CONFIRM[1], "CONFIRM 2019-2026")]:
        eq, tr = backtest(f, cal, start, end)
        s = stats(eq, "trend-hold")
        b = bench(data, start, end)
        print("\n  %s" % nm)
        print("  %-24s %9s %10s %8s %10s"
              % ("", "CAGR", "max DD", "Sharpe", "invested"))
        print(row(s))
        print(row(b))
        if len(tr):
            w = tr[tr.ret > 0]
            print("  %d trades | win %.0f%% | avg %+.1f%% | best %+.0f%% | median hold %.0f days"
                  % (len(tr), 100 * len(w) / len(tr), 100 * tr.ret.mean(),
                     100 * tr.ret.max(), tr.days.median()))
            top = tr.nlargest(5, "ret")
            print("  top 5 trades: " + ", ".join("%s %+.0f%%" % (r.sym, 100 * r.ret)
                                                 for _, r in top.iterrows()))
            print("  those 5 are %.0f%% of total trade profit"
                  % (100 * top.ret.sum() / tr.ret.sum()))
        eq.to_csv("bot_equity_%s.csv" % nm.split()[0].lower())

    print("\n" + "=" * 74)
    print("  ROBUSTNESS: trailing stop width (confirmation window)")
    print("=" * 74)
    print("  %-14s %10s %10s %9s %8s" % ("trail", "CAGR", "max DD", "Sharpe", "trades"))
    for t in [0.10, 0.15, 0.20, 0.25, 0.30]:
        eq, tr = backtest(f, cal, *CONFIRM, trail=t)
        s = stats(eq, "")
        print("  %-14s %+9.2f%% %9.1f%% %8.2f %8d"
              % ("%.0f%%" % (100 * t), 100 * s["cagr"], 100 * s["dd"],
                 s["sharpe"], len(tr)))


if __name__ == "__main__":
    main()
