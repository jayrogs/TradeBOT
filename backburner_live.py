"""backburner_live.py -- the BACKBURNER method, causal, for the scanner and
for grading pictures. The vocabulary is the owner's: a backburner is a 5m
oversold print on a name that is running. (An earlier draft called these
"ladders" and "rungs" -- owner 2026-09-04: "i never said that, these are
backburners".) backburner.py is the older one-name CLI tracker; this module
is the detector the scanner and the pictures use.

THE METHOD, in the owner's words (backburner.py docstring) plus the
2026-09-04 correction "rsi has to be at or under 30, not 40":
  1. the move goes vertical
  2. the first thing to look for is a 5m oversold -- a BACKBURNER
  3. while it keeps bouncing off 5m OS and running hard, keep buying those
  4. when it finally reaches its first 15m OS, buy that
  5. rinse and repeat, the timeframe escalating as the move matures

DRAFT DEFINITIONS -- to be graded on pictures (/backburner):
  running    the 1h LIVE span is UP: structure says the move is on. The
             24h change is reported beside it so the owner can say whether
             "vertical" also needs a size test.
  5m print   5m RSI(14, Wilder -- identical to TradingView's) closes at or
             under 30 while running. Consecutive bars <= 30 are ONE print.
  15m print  the same on a closed 15m bar; 30m and 1h likewise. These are
             the escalation: the first 15m print is the next thing to buy.
  run        a maximal stretch of running with at least one print -- the
             unit for pictures. It ends when the 1h span dies.

Clocks: causal throughout. A higher frame is read off its LAST CLOSED bar
at each 5m close; the bar still forming is never consulted.
"""

import numpy as np
import pandas as pd

import indicators as IND
import structure as ST

OS = 30                       # at or under (owner)
WIND_TF = "1h"                # the span that says "running"
ESCALATE = ("15m", "30m", "1h")
DUR = {"5m": "5min", "15m": "15min", "30m": "30min", "1h": "1h", "4h": "4h",
       "12h": "12h", "1d": "1D"}
RELVOL_N = 288                # a day of 5m bars, for the volume panel
AFTER = 36                    # 3h of "what happened next", pictures only


def _resample(df5, rule):
    o = df5.resample(rule).agg({"Open": "first", "High": "max", "Low": "min",
                                "Close": "last", "Volume": "sum"}).dropna()
    return o if len(o) >= 30 else None


def _close_index(df5, dfh, tf):
    """For each bar of the higher frame: the index of the 5m bar at whose
    close that higher bar is known (its start + duration), or -1."""
    t5_close = df5.index.values + np.timedelta64(5, "m")
    closes = (dfh.index + pd.Timedelta(DUR[tf])).values
    pos = np.searchsorted(t5_close, closes, side="left")
    ok = (pos < len(df5)) & (pos >= 0)
    out = np.full(len(dfh), -1)
    out[ok] = pos[ok]
    # only exact alignments count (a higher bar must close ON a 5m close)
    out[ok] = np.where(t5_close[pos[ok]] == closes[ok], pos[ok], -1)
    return out


def wind_at(df5, dfh, tf=WIND_TF):
    """Live span state of the higher frame's last CLOSED bar, per 5m bar."""
    arr = np.array(["FLAT"] * len(df5), dtype=object)
    if dfh is None or len(dfh) < 40:
        return arr
    st = ST.states(dfh, causal=True)
    t5_close = df5.index.values + np.timedelta64(5, "m")
    closes = (dfh.index + pd.Timedelta(DUR[tf])).values
    pos = np.searchsorted(closes, t5_close, side="right") - 1
    ok = pos >= 0
    arr[ok] = st[pos[ok]]
    return arr


def prints_on(df5, dfx, tf, running):
    """Backburner prints on frame dfx, placed on the 5m timeline at the bar
    where they became known. Consecutive <= OS bars are one print."""
    if dfx is None or len(dfx) < 40:
        return [], np.full(len(df5), np.nan)
    r = IND.rsi_parts(dfx["Close"].values.astype(float))[0]
    idx = _close_index(df5, dfx, tf) if tf != "5m" else np.arange(len(df5))
    out, was = [], False
    line = np.full(len(df5), np.nan)
    for k in range(len(dfx)):
        i = idx[k]
        if i < 0:
            was = False
            continue
        line[i:] = r[k]           # step line for the picture
        hit = np.isfinite(r[k]) and r[k] <= OS and running[i]
        if hit and not was:
            out.append(dict(tf=tf, bar=int(i), rsi=float(r[k]),
                            close=float(dfx["Close"].values[k])))
        was = bool(hit)
    return out, line


def read(df5, df1h):
    """All backburner runs in a 5m frame, causal, plus the live state.
    Returns dict(runs, now, rsi5, lines, running, relvol)."""
    c = df5["Close"].values.astype(float)
    v = df5["Volume"].values.astype(float)
    n = len(c)
    r5, au, ad = IND.rsi_parts(c)
    med = pd.Series(v).rolling(RELVOL_N, min_periods=48).median().values
    relvol = np.divide(v, med, out=np.full(n, np.nan), where=med > 0)
    running = wind_at(df5, df1h) == "UP"
    chg24 = np.full(n, np.nan)
    chg24[288:] = c[288:] / c[:-288] - 1.0

    frames = {"5m": df5, "15m": _resample(df5, "15min"),
              "30m": _resample(df5, "30min"), "1h": df1h}
    prints, lines = {}, {}
    for tf in ("5m",) + ESCALATE:
        prints[tf], lines[tf] = prints_on(df5, frames[tf], tf, running)

    # runs: maximal running stretches holding at least one 5m print
    runs, i = [], 0
    while i < n:
        if not running[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and running[j + 1]:
            j += 1
        inside = {tf: [p for p in prints[tf] if i <= p["bar"] <= j]
                  for tf in prints}
        if inside["5m"]:
            for tf in inside:
                for p in inside[tf]:
                    seg = c[p["bar"] + 1:p["bar"] + 1 + AFTER]
                    if len(seg):
                        p["best_after"] = float(seg.max() / c[p["bar"]] - 1)
                        p["close_after"] = float(seg[-1] / c[p["bar"]] - 1)
            runs.append(dict(start=i, end=j, live=(j == n - 1),
                             prints=inside,
                             chg24=float(chg24[i]) if np.isfinite(chg24[i]) else None))
        i = j + 1

    live = runs[-1] if runs and runs[-1]["live"] else None
    stage = None
    if live:
        for tf in reversed(("5m",) + ESCALATE):
            if live["prints"][tf]:
                stage = tf
                break
    now = dict(
        running=bool(running[-1]),
        on_backburner=bool(running[-1] and r5[-1] <= OS),
        rsi5=float(r5[-1]),
        os_price=IND.reverse_rsi(c[-1], au[-1], ad[-1], OS),
        prints_5m=len(live["prints"]["5m"]) if live else 0,
        prints_15m=len(live["prints"]["15m"]) if live else 0,
        stage=stage,
        chg24=float(chg24[-1]) if np.isfinite(chg24[-1]) else None,
        relvol=float(relvol[-1]) if np.isfinite(relvol[-1]) else None)
    return dict(runs=runs, now=now, rsi5=r5, lines=lines, running=running,
                relvol=relvol, chg24=chg24)


# QUESTIONS FOR THE OWNER (batched):
#  1. "running": is the 1h up-span the right test, or does the move have to
#     be a certain size (24h %, distance above the EMA) -- "vertical"?
#  2. is EVERY 5m print a buy while it runs, or only the first few?
#  3. when do you step up to the 15m -- the first 15m print, or when 5m
#     prints stop bouncing?
#  4. when is the name off the backburner -- the 1h span dying, a broken
#     5m HL, or something else?
#  5. does volume matter to the print, or only to the move?
