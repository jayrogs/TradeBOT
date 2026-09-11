"""
evaluate.py -- the structured readout. Every name, every time, same fields.

    python evaluate.py                 whole watchlist, ranked
    python evaluate.py NVDA GLD        specific names, full detail
    python evaluate.py --intraday      include 4H and 1H (slower, live download)

THE POINT
A fixed structure you defer to, rather than reading each chart fresh and
deciding what matters that day. Same fields, same order, same thresholds, every
symbol. If the structure says nothing is set up, nothing is set up.

WHAT IS SHOWN, per timeframe (3M, M, W, D, and optionally 4H, 1H)

    trend      GREEN uptrend / RED downtrend / BLUE equilibrium / -- neither
    ema12      price above or below the 12-period EMA on that timeframe
    rsi        RSI(14) on that timeframe
    stop       the price that invalidates the trend (last higher low in an
               uptrend, last lower high in a downtrend)
    room       how far price sits above that stop

THE SUMMARY LINE, computed the same way every time

    ALIGN      how many timeframes agree, signed. +4 means four green and
               nothing red. This is the context filter.
    SETUP      fires when the higher timeframes are green AND a lower one is
               oversold -- the user's documented entry
    RISK       distance to the nearest stop on a trending timeframe

Nothing here predicts. It reports state. The evidence for each component is in
STATE.md; the entries tested at roughly break-even mechanically, so this is an
attention tool that assumes a human supplies the selection.
"""

import argparse
import os
import sys
import warnings

import numpy as np
import pandas as pd

import panel as P

warnings.filterwarnings("ignore")

CACHE = os.path.join("cache", "scan_prices.pkl")
TF_DAILY = [("3M", "QE"), ("M", "ME"), ("W", "W-FRI"), ("D", None)]
TF_INTRA = [("4H", "4h"), ("1H", None)]
OVERSOLD = 40
OVERBOUGHT = 70


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().values
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs)


def read_tf(df):
    """One timeframe -> one structured record."""
    if len(df) < 4 * P.PIVOT + 8:
        return None
    st, hl, lh = P.trend_state(df)
    c = df["Close"].values.astype(float)
    e12 = pd.Series(c).ewm(span=12, adjust=False).mean().values
    r = rsi(c)
    ineq, bhi, blo, bmid, dep, res = P.compression(df)
    s = st[-1]
    stop = hl[-1] if s == "UP" else (lh[-1] if s == "DOWN" else np.nan)
    return dict(trend=s, price=c[-1], ema12=e12[-1], above=c[-1] > e12[-1],
                rsi=r[-1], stop=stop,
                room=(c[-1] / stop - 1) if np.isfinite(stop) else np.nan,
                eq_hi=bhi[-1], eq_lo=blo[-1], eq_depth=int(dep[-1]))


def evaluate(sym, store, intraday=False):
    out = {"symbol": sym, "tf": {}}
    d = store.get(sym)
    if d is None:
        return None
    for lab, rule in TF_DAILY:
        rec = read_tf(P.resample(d, rule))
        if rec:
            out["tf"][lab] = rec
    if intraday:
        try:
            h = P.fetch(sym, "1h")
            if h is not None:
                for lab, rule in TF_INTRA:
                    rec = read_tf(P.resample(h, rule))
                    if rec:
                        out["tf"][lab] = rec
        except Exception:
            pass
    if not out["tf"]:
        return None

    tfs = out["tf"]
    ups = sum(1 for v in tfs.values() if v["trend"] == "UP")
    dns = sum(1 for v in tfs.values() if v["trend"] == "DOWN")
    out["align"] = ups - dns
    out["ups"], out["downs"] = ups, dns
    out["eq"] = sum(1 for v in tfs.values() if v["trend"] == "BALANCE")

    # the documented entry: higher timeframes green, a lower one oversold
    higher = [t for t in ("3M", "M", "W") if t in tfs]
    lower = [t for t in ("D", "4H", "1H") if t in tfs]
    ctx_ok = bool(higher) and all(tfs[t]["trend"] in ("UP", "BALANCE") for t in higher) \
        and any(tfs[t]["trend"] == "UP" for t in higher)
    trig = [t for t in lower if tfs[t]["rsi"] < OVERSOLD]
    out["setup"] = "BUY-DIP %s" % ",".join(trig) if (ctx_ok and trig) else ""
    if not out["setup"] and ctx_ok:
        out["setup"] = "in trend, no dip"

    # Risk is measured on the timeframe you would TRADE, not the highest one.
    # A quarterly stop can sit at a split-adjusted low from a decade ago
    # (NVDA's was $0.28, +77,948% away) which is true and useless.
    out["risk"] = np.nan
    out["risk_tf"] = ""
    for t in ("D", "W", "M", "3M"):
        v = tfs.get(t)
        if v and v["trend"] == "UP" and np.isfinite(v["room"]):
            out["risk"], out["risk_tf"] = v["room"], t
            break
    out["price"] = list(tfs.values())[0]["price"]
    return out


LIGHT = {"UP": "GREEN", "DOWN": "RED", "BALANCE": "BLUE", "FLAT": "--"}


def detail(e):
    print("\n" + "=" * 78)
    print("  %-10s %12.4f     ALIGN %+d   (%d up / %d down / %d eq)"
          % (e["symbol"], e["price"], e["align"], e["ups"], e["downs"], e["eq"]))
    if e["setup"]:
        print("  SETUP: %s" % e["setup"])
    print("=" * 78)
    print("  %-5s %-7s %-7s %6s %13s %8s"
          % ("TF", "trend", "ema12", "rsi", "stop", "room"))
    for lab, _ in TF_DAILY + TF_INTRA:
        if lab not in e["tf"]:
            continue
        v = e["tf"][lab]
        stop = "%13.4f" % v["stop"] if np.isfinite(v["stop"]) else "            -"
        if not np.isfinite(v["room"]):
            room = "       -"
        elif abs(v["room"]) > 1.0:
            room = "     far"          # stale level, not actionable
        else:
            room = "%+7.1f%%" % (100 * v["room"])
        tag = ""
        if v["rsi"] < OVERSOLD:
            tag = "  <- oversold"
        elif v["rsi"] > OVERBOUGHT:
            tag = "  <- overbought"
        if v["trend"] == "BALANCE" and np.isfinite(v["eq_hi"]):
            tag = "  EQ %.4g-%.4g" % (v["eq_lo"], v["eq_hi"])
        print("  %-5s %-7s %-7s %6.1f %s %s%s"
              % (lab, LIGHT[v["trend"]], "above" if v["above"] else "below",
                 v["rsi"], stop, room, tag))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbols", nargs="*")
    ap.add_argument("--intraday", action="store_true")
    a = ap.parse_args()

    store = pd.read_pickle(CACHE)
    if a.symbols:
        syms = [s.upper() for s in a.symbols]
        for s in syms:
            e = evaluate(s, store, a.intraday)
            if e:
                detail(e)
            else:
                print("  %s -- no data" % s)
        return

    if not os.path.exists("watchlist.txt"):
        sys.exit("no watchlist.txt")
    syms = [x.strip() for x in open("watchlist.txt") if x.strip()]
    rows = [e for e in (evaluate(s, store, a.intraday) for s in syms) if e]
    rows.sort(key=lambda e: (-e["align"], e["risk"] if np.isfinite(e["risk"]) else 9))

    print("=" * 92)
    print("  WATCHLIST  %s   %d names   timeframes: %s"
          % (pd.Timestamp.today().date(), len(rows),
             " ".join(t[0] for t in TF_DAILY + (TF_INTRA if a.intraday else []))))
    print("=" * 92)
    print("  %-9s %11s %6s  %-22s %8s  %s"
          % ("symbol", "price", "align", "trend by timeframe", "risk", "setup"))
    print("  " + "-" * 88)
    for e in rows:
        seq = " ".join({"UP": "G", "DOWN": "R", "BALANCE": "B", "FLAT": "."}[
            e["tf"][t]["trend"]] for t, _ in TF_DAILY + (TF_INTRA if a.intraday else [])
            if t in e["tf"])
        if np.isfinite(e["risk"]) and abs(e["risk"]) <= 1.0:
            risk = "%5.1f%% %-2s" % (100 * e["risk"], e["risk_tf"])
        elif np.isfinite(e["risk"]):
            risk = "  far %-2s" % e["risk_tf"]
        else:
            risk = "      - "
        print("  %-9s %11.4f %+5d  %-22s %9s  %s"
              % (e["symbol"], e["price"], e["align"], seq, risk, e["setup"]))
    print("\n  columns are 3M M W D (G=up R=down B=equilibrium .=neither)")
    print("  align = up timeframes minus down.")
    print("  risk  = distance to the stop on the fastest trending timeframe.")
    n_setup = sum(1 for e in rows if e["setup"].startswith("BUY-DIP"))
    print("  %d names showing the documented entry today." % n_setup)


if __name__ == "__main__":
    main()
