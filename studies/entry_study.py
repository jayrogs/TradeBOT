"""entry_study.py -- twenty ways to BUY, with the exit held fixed.

Owner 2026-09-07: "see if theres a better way to buy also. use as much energy
and cores as possible."

Every entry fills at the NEXT bar's open after its signal bar (rule 14). Each is
run under two exits: the chandelier that won the exit study (a stop 5 normal
bars under the highest close, sold on a close under it) and the rule as graded
(the last higher low, wick half a bar, trail raises it once up 3R). One trade
at a time per entry type: a new signal is ignored while that type is in a trade.
A "buy any bar" control (every 25th bar) shows what the exit alone does.

    pythonw studies/entry_study.py --procs 16 --log logs/entry_study.log   [--focus]
Results: validation/entry_study.json (+_focus): by_entry_tf, by_entry_kind,
by_entry_era, by_entry_exit (keys "entry | exit | tf" etc.).
"""
import bisect
import concurrent.futures as cf
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "studies"))
import backburner_study as B      # noqa: E402
import structure as ST            # noqa: E402
import trend_ride as R            # noqa: E402
import exit_managers as XM        # noqa: E402

TFS = ["5m", "15m", "1h", "4h", "1d"]
UP = R.UP
OUT = os.path.join("validation", "entry_study.json")
CHAND = 5.0
KEYS = ["entry", "exit", "tf", "kind", "era"]

ENTRIES = [
    "second higher low (the rule)",
    "first higher low of the trend",
    "any higher low in an uptrend",
    "third or later higher low",
    "equal low in an uptrend",
    "the uptrend opens (higher low + higher high confirmed)",
    "close above the last higher high (breakout)",
    "close above the 20-bar high (breakout)",
    "dip to the 12 EMA in an uptrend, then a close back above it",
    "12 EMA cross up (close from under to over)",
    "RSI back over 30 after being under (the backburner bounce)",
    "RSI crosses over 50",
    "supertrend flips up",
    "parabolic SAR flips up",
    "close 3 bars above the lowest low (a reversal off a low)",
    "a lower low that fails: close back above the broken higher low within 5 bars",
    "second higher low, and the next chart is in an uptrend",
    "any higher low, and the next chart is in an uptrend",
    "the uptrend opens, and the next chart is in an uptrend",
    "20-bar high, and the next chart is in an uptrend",
    "buy any bar (control)",
]


def chandelier_exit(c, o, l, h, a14, e, n, cap, day):
    peak = c[e]; worst = 0.0
    for k in range(e, n - 1):
        worst = min(worst, c[k] / o[e] - 1)
        peak = max(peak, c[k])
        atr = a14[k] if np.isfinite(a14[k]) else 0.0
        if c[k] < peak - CHAND * atr:
            return k, o[k + 1], "chandelier hit", worst
        if day is not None and k + 1 < n and day[k + 1] != day[k]:
            return k, c[k], "session end", worst
        if k - e >= cap:
            return k, o[k + 1], "time", worst
    return None


def signals(df, tf, kind, frames):
    """{entry: sorted list of (signal_bar, line_price)} for one frame. The line
    is the last higher low for pivot entries, else the last confirmed low pivot."""
    c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    a14 = B.atr(h, l, c)
    piv = ST.pivots(df)
    pos_by_ci = {pv[0]: i for i, pv in enumerate(piv)}
    lows = [(ci, j, p, lab) for ci, j, p, k_, lab in piv if k_ == "low"]
    highs = [(ci, j, p, lab) for ci, j, p, k_, lab in piv if k_ == "high"]
    ind = XM.indicators(c, o, h, l, a14)
    ema12 = ind["ema12"]; rsi = ind["rsi"]; st = ind["st"]; sard = ind["sard"]
    # live state and the bar each uptrend opened on
    state = np.array(["FLAT"] * n, dtype=object); opened = np.zeros(n, bool)
    for kind_, s0, s1 in ST.spans(df, causal=True):
        state[s0:s1 + 1] = kind_
        if kind_ == "UP":
            opened[s0] = True
    up = state == "UP"
    hdf = frames.get(UP.get(tf))
    hi_up = np.zeros(n, bool)
    if hdf is not None and len(hdf) >= 60:
        t1 = B.higher_view(df, tf, hdf, UP[tf])[0]
        hi_up = np.array([str(x) == "UP" for x in t1])
    # last confirmed low pivot price at each bar, and last HH price
    last_low = np.full(n, np.nan); last_hh = np.full(n, np.nan); last_hl = np.full(n, np.nan)
    cur = np.nan; k = 0
    for i in range(n):
        while k < len(lows) and lows[k][0] <= i:
            cur = lows[k][2]; k += 1
        last_low[i] = cur
    cur = np.nan; k = 0
    for i in range(n):
        while k < len(lows) and lows[k][0] <= i:
            if lows[k][3] == "HL":
                cur = lows[k][2]
            k += 1
        last_hl[i] = cur
    cur = np.nan; k = 0
    for i in range(n):
        while k < len(highs) and highs[k][0] <= i:
            if highs[k][3] == "HH":
                cur = highs[k][2]
            k += 1
        last_hh[i] = cur
    hi20 = np.full(n, np.nan)
    for i in range(20, n):
        hi20[i] = h[i - 20:i].max()
    lo20 = np.full(n, np.nan)
    for i in range(20, n):
        lo20[i] = l[i - 20:i].min()
    S = {e_: [] for e_ in ENTRIES}
    line = lambda i: last_low[i] if np.isfinite(last_low[i]) else (lo20[i] if np.isfinite(lo20[i]) else l[i])
    # ---- pivot entries
    for ci, j, price, lab in lows:
        if ci < 60 or ci + 2 >= n - 1:
            continue
        if lab not in ("HL", "EL"):
            continue
        cnt, has_hh, nhl = R.trend_pivots_before(piv, pos_by_ci, ci)
        if cnt < 3 or not has_hh:
            continue
        if lab == "EL":
            S["equal low in an uptrend"].append((ci, price)); continue
        S["any higher low in an uptrend"].append((ci, price))
        if nhl == 1:
            S["first higher low of the trend"].append((ci, price))
        elif nhl == 2:
            S["second higher low (the rule)"].append((ci, price))
            if hi_up[ci]:
                S["second higher low, and the next chart is in an uptrend"].append((ci, price))
        else:
            S["third or later higher low"].append((ci, price))
        if hi_up[ci]:
            S["any higher low, and the next chart is in an uptrend"].append((ci, price))
    # the lower low that fails
    for idx, (ci, j, price, lab) in enumerate(lows):
        if lab != "LL" or ci < 60 or ci + 7 >= n:
            continue
        prev_hl = last_hl[ci - 1] if ci >= 1 else np.nan
        if not np.isfinite(prev_hl) or price >= prev_hl:
            continue
        rb = next((k2 for k2 in range(ci + 1, min(n - 2, ci + 6)) if c[k2] > prev_hl), None)
        if rb is not None:
            S["a lower low that fails: close back above the broken higher low within 5 bars"].append((rb, price))
    # ---- bar entries
    for i in range(60, n - 2):
        ln = line(i)
        if opened[i]:
            S["the uptrend opens (higher low + higher high confirmed)"].append((i, ln))
            if hi_up[i]:
                S["the uptrend opens, and the next chart is in an uptrend"].append((i, ln))
        if up[i] and np.isfinite(last_hh[i - 1]) and c[i] > last_hh[i - 1] and c[i - 1] <= last_hh[i - 1]:
            S["close above the last higher high (breakout)"].append((i, ln))
        if np.isfinite(hi20[i]) and c[i] > hi20[i] and c[i - 1] <= hi20[i - 1]:
            S["close above the 20-bar high (breakout)"].append((i, ln))
            if hi_up[i]:
                S["20-bar high, and the next chart is in an uptrend"].append((i, ln))
        if up[i] and c[i] > ema12[i] and c[i - 1] < ema12[i - 1]:
            S["dip to the 12 EMA in an uptrend, then a close back above it"].append((i, ln))
        if c[i] > ema12[i] and c[i - 1] < ema12[i - 1]:
            S["12 EMA cross up (close from under to over)"].append((i, ln))
        if rsi[i] > 30 and rsi[i - 1] <= 30:
            S["RSI back over 30 after being under (the backburner bounce)"].append((i, ln))
        if rsi[i] > 50 and rsi[i - 1] <= 50:
            S["RSI crosses over 50"].append((i, ln))
        if st[i] == 1 and st[i - 1] == -1:
            S["supertrend flips up"].append((i, ln))
        if sard[i] == 1 and sard[i - 1] == -1:
            S["parabolic SAR flips up"].append((i, ln))
        if np.isfinite(lo20[i]) and np.isfinite(a14[i]) and c[i] > lo20[i] + 3 * a14[i] and c[i - 1] <= lo20[i - 1] + 3 * a14[i - 1]:
            S["close 3 bars above the lowest low (a reversal off a low)"].append((i, ln))
        if i % 25 == 0:
            S["buy any bar (control)"].append((i, ln))
    return S, dict(c=c, o=o, h=h, l=l, a14=a14, lows=lows, n=n)


def study_frame(sym, kind, tf, frames, start):
    df = frames[tf]
    if len(df) < 300:
        return []
    S, A = signals(df, tf, kind, frames)
    c, o, h, l, a14, lows, n = A["c"], A["o"], A["h"], A["l"], A["a14"], A["lows"], A["n"]
    lcis = [x[0] for x in lows]
    cap = R.CAP_DAYS * B.BARS_DAY[tf]
    cost = B.CLASS_COST.get(kind, B.COST)
    lr = np.diff(np.log(c), prepend=np.log(c[0]))
    drift = float(np.nanmean(lr[np.isfinite(lr)]))
    mid = start + (pd.Timestamp.now() - start) / 2
    day = df.index.normalize().values if kind in ("stock", "etf") and tf in ("5m", "15m") else None
    rows = []
    for entry, sig in S.items():
        busy_until = {"chandelier 5 bars under the high": -1, "the rule as graded": -1}
        for ci, ln in sig:
            e = ci + 1
            if e >= n - 2:
                continue
            fill = o[e]
            atr0 = a14[e - 1]
            if not (np.isfinite(atr0) and atr0 > 0) or fill <= 0:
                continue
            t = df.index[e]
            era = "before" if t < start else "first" if t < mid else "second"
            for ex_name in busy_until:
                if e <= busy_until[ex_name]:
                    continue                     # still in a trade under this entry type
                if ex_name.startswith("chandelier"):
                    res = chandelier_exit(c, o, l, h, a14, e, n, cap, day)
                else:
                    level = ln if np.isfinite(ln) and ln < fill else min(fill, l[e - 1])
                    res = R.hl_break_exit(c, o, l, h, a14, lows, lcis, e, level, n, cap, 0.5, day=day, trail_after=3.0)
                if res is None:
                    busy_until[ex_name] = n
                    continue
                xb, xpx, why, worst = res
                busy_until[ex_name] = xb + 1
                after = min(n - 1, xb + 60)
                rows.append(dict(entry=entry, exit=ex_name, tf=tf, kind=kind, era=era,
                                 ret=float(xpx / fill - 1 - cost), held=int(xb + 1 - e), why=why, took=False,
                                 worst=float(worst), best_after=float(np.max(c[xb:after + 1]) / fill - 1),
                                 drift=float(np.exp(drift * (xb + 1 - e)) - 1 - cost)))
    return rows


def fold(rows):
    R.KEYS, keep = KEYS, R.KEYS
    try:
        return R.fold(rows)
    finally:
        R.KEYS = keep


def _by_size(names):
    """Biggest files first, so the slow names start early and the cores stay full to the end."""
    import glob as _g
    def sz(sk):
        s_, k_ = sk
        folder = {"crypto": "history", "stock": "history/stocks", "etf": "history/stocks", "futures": "history/futures"}.get(k_, "history")
        return sum(os.path.getsize(p) for p in _g.glob(os.path.join(folder, "%s_*.csv.gz" % s_)))
    return sorted(names, key=sz, reverse=True)


def _work(args):
    sym, kind, start = args
    errs, rows = [], []
    try:
        frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    for tf in TFS:
        if tf not in frames:
            continue
        try:
            rows += study_frame(sym, kind, tf, frames, start)
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    return fold(rows), errs


def main():
    procs, log = 20, None
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            log = sys.argv[i + 1]
            sys.stdout = sys.stderr = open(log, "w", buffering=1, encoding="utf-8", errors="replace")
    global OUT
    t0 = time.time()
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * B.YEARS)
    names = [(s_, k_) for s_, k_ in B.universe() if k_ != "forex"]
    if "--focus" in sys.argv:
        import focus
        names = [(s_, k_) for s_, k_ in focus.names() if focus.have(s_, k_)]
        OUT = OUT.replace(".json", "_focus.json")
    names = _by_size(names)
    R.quiet_workers()
    parts, done, errs = [], 0, []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for out, err in ex.map(_work, [(s_, k_, start) for s_, k_ in names], chunksize=1):
            done += 1
            errs += err or []
            if out is not None:
                parts.append(out)
            if done % 50 == 0:
                print("  %d/%d names  (%.0fs)" % (done, len(names), time.time() - t0), flush=True)
    for e_ in errs[:20]:
        print("  ERR " + e_)
    f = pd.concat(parts, ignore_index=True)
    res = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names), entries=ENTRIES,
                         exits=["chandelier 5 bars under the high", "the rule as graded"]),
               by_entry_exit=R.by(f, ["entry", "exit"]),
               by_entry_exit_tf=R.by(f, ["entry", "exit", "tf"]),
               by_entry_exit_kind=R.by(f, ["entry", "exit", "kind"]),
               by_entry_exit_era=R.by(f, ["entry", "exit", "era"]))
    json.dump(res, open(OUT, "w"))
    print("  ENTRY STUDY  %d names  (%.0fs)" % (len(names), time.time() - t0))
    for ex_name in ("chandelier 5 bars under the high", "the rule as graded"):
        print("\n  exit: %s" % ex_name)
        print("  %-78s %8s %8s %8s %8s %8s" % ("entry", "n", "per tr", "vs drft", "win", "held"))
        for entry in ENTRIES:
            b = res["by_entry_exit"].get("%s | %s" % (entry, ex_name))
            if b:
                print("  %-78s %8d %+7.2f%% %+7.2f%% %7.0f%% %8.0f" % (entry[:78], b["n"], 100 * b["ret"], 100 * b["edge"], 100 * b["win"], b["held"]))
    if log:
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
