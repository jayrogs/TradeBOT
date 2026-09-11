"""
desk.py -- the live assistant. Watches a short list, tracks the backburner prints on every
           timeframe, and says which rung just printed and where the next bid is.

    python desk.py                          watch positions.csv, refresh 60s
    python desk.py --watch MRNA,NVDA        watch these instead
    python desk.py --every 30               refresh interval, seconds
    python desk.py --once                   single snapshot, no loop

WHAT IT IS
An assistant, not a trader. It places nothing and decides nothing. It watches
the handful of names you are actually in and answers, continuously, the two
questions the backburner method turns on:

    which rung just printed?
    what price puts us on the next one?

WHY IT READS 1-MINUTE BARS
The method triggers on the LIVE RSI, not the closed-bar RSI. A 15m candle can
dip to 29.6 while it is open and close back at 30.4, and every closed-bar
calculation on earth will then report that the rung never happened. So every
timeframe here is rebuilt from 1m bars, and the oversold test runs against what
the chart showed while the candle was still forming. One download per symbol
per refresh serves 5m, 15m, 30m and 1h.

HONESTY ABOUT THE LIGHTS
The lights below are the conditions described as the method. They are NOT
validated. Roughly 22,000 configurations have been tested in this project and
none beat buy-and-hold out of sample; the backburner method has not been tested
at all, because testing it needs intrabar readings and free data only reaches
back seven days. So a full green panel means "the conditions you described are
present", not "this is likely to work". Nothing here should be automated until
it has been forward-tested on paper.

POSITIONS
Optional. Create positions.csv with: symbol,avg,shares
The panel then shows your average, open P&L, and which rungs you have filled.
"""

import argparse
import os
import time
import warnings

import numpy as np
import pandas as pd

import indicators as IND

warnings.filterwarnings("ignore")

TFS = [("5m", 5), ("15m", 15), ("30m", 30), ("1h", 60)]
RSI_N = IND.RSI_N

# one definition, in indicators.py
rsi_parts = IND.rsi_parts
reverse_rsi = IND.reverse_rsi
session_vwap = IND.session_vwap
OS = 30                 # the rung threshold
GRAZE = 1.0             # within this of OS still counts as a touch
POSFILE = "positions.csv"


# ------------------------------------------------------------------ maths







def backburner_tf(m1, minutes):
    """Everything about one timeframe, rebuilt from 1m bars.

    Returns closed-bar RSI, the lowest reading each bar showed while it was
    still forming, and the reverse-RSI bid prices off the last closed bar.
    """
    rule = "%dmin" % minutes
    o = m1.resample(rule).agg({"Open": "first", "High": "max",
                               "Low": "min", "Close": "last",
                               "Volume": "sum"}).dropna()
    if len(o) < RSI_N + 3:
        return None
    c = o["Close"].values.astype(float)
    r, au, ad = rsi_parts(c)

    # what the chart displayed mid-candle
    step = pd.Timedelta(minutes=minutes)
    intra = np.full(len(o), np.nan)
    for i in range(1, len(o)):
        t = o.index[i]                      # pandas labels bins by their START
        win = m1["Close"].loc[(m1.index >= t) & (m1.index < t + step)]
        pu, pdn, pc = au[i - 1], ad[i - 1], c[i - 1]
        vals = []
        for p in list(win.values.astype(float)) + [float(o["Low"].values[i])]:
            ch = p - pc
            u = (pu * (RSI_N - 1) + max(ch, 0.0)) / RSI_N
            dd = (pdn * (RSI_N - 1) + max(-ch, 0.0)) / RSI_N
            vals.append(100 - 100 / (1 + (u / dd if dd > 0 else np.inf)))
        intra[i] = min(vals) if vals else r[i]

    e12 = pd.Series(c).ewm(span=12, adjust=False).mean().values
    lows = o["Low"].values.astype(float)
    steps = 0
    for i in range(len(lows) - 1, 0, -1):
        if lows[i] > lows[i - 1]:
            steps += 1
        else:
            break
    return dict(idx=o.index, close=c[-1], rsi=r[-1], rsi_series=r,
                intra=intra, intra_now=intra[-1] if len(intra) else np.nan,
                ema12=e12[-1], steps=steps,
                bid40=reverse_rsi(c[-1], au[-1], ad[-1], 40),
                bid35=reverse_rsi(c[-1], au[-1], ad[-1], 35),
                bid30=reverse_rsi(c[-1], au[-1], ad[-1], 30))




# ------------------------------------------------------------------ data

def pull(sym):
    import yfinance as yf
    d = yf.download(sym, interval="1m", period="7d", progress=False,
                    auto_adjust=False, prepost=True)
    if d is None or len(d) == 0:
        return None
    d.columns = [c[0] if isinstance(c, tuple) else c for c in d.columns]
    if getattr(d.index, "tz", None) is not None:
        d.index = d.index.tz_localize(None)
    return d.dropna()


def load_positions():
    if not os.path.exists(POSFILE):
        return {}
    p = pd.read_csv(POSFILE)
    return {str(r.symbol).upper(): dict(avg=float(r.avg),
                                        shares=float(getattr(r, "shares", 0)))
            for r in p.itertuples()}


# ------------------------------------------------------------------ panel

def read(sym, pos):
    m1 = pull(sym)
    if m1 is None or len(m1) < 120:
        return None
    tfs = {}
    for lab, mins in TFS:
        t = backburner_tf(m1, mins)
        if t:
            tfs[lab] = t
    if not tfs:
        return None
    px = float(m1["Close"].values[-1])
    vwap = session_vwap(m1)

    # today's bars only, for "did a rung print today"
    today = m1.index[-1].normalize()
    out = dict(sym=sym, px=px, vwap=vwap, tfs=tfs, pos=pos.get(sym))
    for lab, t in tfs.items():
        m = t["idx"] >= today
        iv = t["intra"][m]
        iv = iv[np.isfinite(iv)]
        t["today_min"] = float(np.min(iv)) if len(iv) else np.nan
        t["today_hits"] = int(np.sum(iv <= OS)) if len(iv) else 0
        # the most recent bar that touched the rung
        hit_idx = [i for i in range(len(t["intra"]))
                   if np.isfinite(t["intra"][i]) and t["intra"][i] <= OS + GRAZE]
        t["last_hit"] = (t["idx"][hit_idx[-1]].strftime("%m-%d %H:%M")
                         if hit_idx else "")
    return out


def lights(r):
    """The conditions, as described. Untested -- see the module docstring."""
    t5, t15 = r["tfs"].get("5m"), r["tfs"].get("15m")
    L = []
    if t5:
        L.append(("5m backburner", t5["intra_now"] <= OS + GRAZE,
                  "5m RSI %.0f" % t5["intra_now"]))
        L.append(("5m stair-steps", t5["steps"] >= 2,
                  "%d higher lows" % t5["steps"]))
    if t15:
        L.append(("15m rung hit", t15["today_hits"] > 0,
                  "%d today" % t15["today_hits"]))
    px, vw = r.get("px"), r.get("vwap")
    # overnight or with no session data the VWAP is None -- a dead light,
    # not a dead endpoint
    if isinstance(px, (int, float)) and isinstance(vw, (int, float))             and np.isfinite(px) and np.isfinite(vw):
        L.append(("above VWAP", px > vw, "%.2f vs %.2f" % (px, vw)))
    if t15:
        L.append(("above 15m EMA12", r["px"] > t15["ema12"],
                  "%.2f" % t15["ema12"]))
    return L


def show(rows):
    print("\n" + "=" * 92)
    print("  DESK  %s     assistant only -- places nothing, decides nothing"
          % pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 92)
    for r in rows:
        p = r["pos"]
        tag = ""
        if p:
            tag = "   avg %.2f   open %+.1f%%" % (p["avg"],
                                                  100 * (r["px"] / p["avg"] - 1))
        print("\n  %-8s %10.2f%s" % (r["sym"], r["px"], tag))
        print("  %-5s %7s %8s %8s %9s %9s %9s %7s"
              % ("TF", "rsi", "livelow", "today", "bid@40", "bid@35", "bid@30",
                 "steps"))
        for lab, _ in TFS:
            t = r["tfs"].get(lab)
            if not t:
                continue

            def f(v):
                return "%9.2f" % v if v else "    above"
            hit = " *" if t["today_hits"] else "  "
            print("  %-5s %7.1f %8.1f %6d%s %s %s %s %7d"
                  % (lab, t["rsi"], t["intra_now"], t["today_hits"], hit,
                     f(t["bid40"]), f(t["bid35"]), f(t["bid30"]), t["steps"]))
        n_on = 0
        cells = []
        for name, on, detail in lights(r):
            cells.append("%s %-17s %s" % ("[GREEN]" if on else "[  -  ]",
                                          name, detail))
            n_on += bool(on)
        print("  " + "  ".join(["conditions %d/%d" % (n_on, len(cells))]))
        for c in cells:
            print("    " + c)
        rung = [lab for lab, _ in TFS if r["tfs"].get(lab)
                and r["tfs"][lab]["today_hits"]]
        print("  rungs printed today: %s" % (", ".join(rung) if rung else "none"))
    print("\n  'livelow' = lowest RSI the current bar has shown while forming.")
    print("  bid@N   = price that would print RSI N on the next bar of that TF.")
    print("  Lights are the described conditions and are NOT validated.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", default=None, help="comma-separated symbols")
    ap.add_argument("--every", type=int, default=60, help="refresh seconds")
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()

    pos = load_positions()
    syms = ([s.strip().upper() for s in a.watch.split(",")] if a.watch
            else sorted(pos))
    if not syms:
        print("nothing to watch. Pass --watch SYM or create %s "
              "with columns symbol,avg,shares" % POSFILE)
        return

    seen = {}
    while True:
        rows = []
        for s in syms:
            try:
                r = read(s, pos)
            except Exception as e:
                print("  %s failed: %s" % (s, e))
                r = None
            if r:
                rows.append(r)
        if rows:
            show(rows)
            # shout when a rung prints that was not there last refresh
            for r in rows:
                for lab, _ in TFS:
                    t = r["tfs"].get(lab)
                    if not t:
                        continue
                    k = (r["sym"], lab)
                    if t["today_hits"] > seen.get(k, t["today_hits"]):
                        print("\n  >>> %s %s RUNG PRINTED at %.2f <<<"
                              % (r["sym"], lab, r["px"]))
                    seen[k] = t["today_hits"]
        if a.once:
            return
        time.sleep(a.every)


if __name__ == "__main__":
    main()
