"""pics_backburner_tcg.py -- the BackBurner as Dan teaches it, drawn, winners and losers (2026-09-21).

THE TRADE (`studies/backburner_dan.py`, TCG_METHOD.md #5b, #11): the name has RUN to a new high on the daily; the
FIRST time the hourly RSI touches 30 after that high he buys -- inside the candle, at the touch -- with a second bid at
RSI 20; half comes off when the bounce reaches the hourly 12 EMA; the stop then goes UNDER THE LOW OF THE DROP; the
rest is for the old high. Each drawing shows the hourly with its RSI underneath (the 30 line is the trigger) and the
daily beside it (the run, the old high, where the dip sits against the daily 12 EMA).

Nothing is claimed about this trade until these are looked at (rule 10).

    python pics_backburner_tcg.py --procs 8
Writes validation/backburner_tcg/*.png + index.json  ->  /backburners
"""
import concurrent.futures as cf
import glob as _glob
import io
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "studies"))
import backburner_study as S      # noqa: E402
import chartkit as CK             # noqa: E402
import panel as P                 # noqa: E402
import indicators as IND          # noqa: E402
import exit_managers as XM        # noqa: E402
import eq_freeride2 as FR2        # noqa: E402
import tcg_lab as L               # noqa: E402
import backburner_tcg as T        # noqa: E402
import backburner_dan as D        # noqa: E402

DARK, DIM = "#0d0f12", "#8b93a1"
PURPLE, GREEN, RED, AMBER, BLUE = "#b48cff", "#3ddc97", "#ff5c72", "#ffb84d", "#5aa9ff"
OUT = os.path.join("validation", "backburner_tcg")
COST = L.COST


FRESH_MIN = 2.0                # HIS RULE: the run must clear its own 60-day high by this many daily normal bars
RUN_PCT_MIN = 10.0             # HIS RULE: the 20-day run must be at least this many PERCENT (a real-size run up).
                               # 6% was his eye on /messymark; 10% is his pick after the account test (backburner_runwallet:
                               # +25.3% a year at 10 slots vs +22.7% at 6%, 20%+ only +15.5%). 2026-09-22.
CLEAN_MIN = 0.60               # a clean run: this share of the last 20 daily bars made a higher low than the day before
DISASTER_BARS = 6.0            # the only line while the hourly is still oversold: a "day loser", not a chart stop


# THE STOP VARIANTS (his ask 2026-09-22: "spend some time analyzing different methods"). One dict per way:
#   first    a chart stop from the buy bar, this many normal bars under the lowest fill (None = disaster line only)
#   arm      when the stop under the low of the drop goes live: "rsi" (RSI closes back over 30), "half" (when the
#            half is sold at the 12 EMA), "never"
#   wiggle   how far under the low of the drop, in normal bars
#   off      the stop switches off again while RSI is back under 30 (his "never sell while it's oversold")
STOPS = {
    "round 1: 3 bars under the fill from the start":           dict(first=3.0, arm="half", wiggle=0.1, off=False),
    "round 2: none while oversold, RSI cross, 0.1 bar":        dict(first=None, arm="rsi", wiggle=0.1, off=True),
    "RSI cross, 0.25 bar of room":                             dict(first=None, arm="rsi", wiggle=0.25, off=True),
    "RSI cross, 0.5 bar of room":                              dict(first=None, arm="rsi", wiggle=0.5, off=True),
    "RSI cross, 1 bar of room":                                dict(first=None, arm="rsi", wiggle=1.0, off=True),
    "Dan as written: no stop until the half is sold, then under the low":
                                                               dict(first=None, arm="half", wiggle=0.1, off=False),
    "half sold, then under the low with 0.5 bar of room":      dict(first=None, arm="half", wiggle=0.5, off=False),
    "never: disaster line only, half at the EMA, rest for the high":
                                                               dict(first=None, arm="never", wiggle=0.0, off=False),
}
STOP = dict(STOPS["Dan as written: no stop until the half is sold, then under the low"],     # round 3, after backburner_stops
            rest="hl_close", thirds=False)      # and the rest walked under the higher lows (e-book plan 3, his #16), after backburner_rests


def walk(kind, o, h, l, c, k, e_last, entry, stop, ema12, target, a, rsi, v=None):
    """ROUND 2 (his grading of round 1, 2026-09-21: JBHT "why did this even sell??? we need sharp dips", MNST "it
    feels really bad to sell while it's oversold"). Round 1 put a stop 3 normal bars under the fill on the buy bar
    itself, and on a waterfall candle that same candle went through it. Dan: with one fill there is NO stop, the
    unfilled second bid is the protection. So now: while the hourly RSI is still at or under 30 there is no chart
    stop, only a wide disaster line (`stop`, DISASTER_BARS under the lowest fill). The moment RSI closes back over
    30 -- the bounce is on -- the stop goes UNDER THE LOW OF THE DROP. Half at the 12 EMA, the rest for the old high."""
    n = len(c)
    last = min(n - 1, e_last + L.MAX_BARS)
    cost = COST.get(kind, 0.05)
    low0 = float(np.min(l[k:e_last + 1]))
    if l[e_last] <= stop:
        j2 = min(e_last + 1, n - 1)
        return dict(end=j2, exit_px=float(o[j2]), pct=float((o[j2] - entry) / entry * 100 - cost), half_at=None,
                    half_px=None, steps=[(int(e_last), float(stop))], how="through the disaster line on the buy bar")
    v = v or STOP
    line = stop if v["first"] is None else (stop + DISASTER_BARS * a - v["first"] * a)
    steps = [(int(e_last), float(line))]
    if l[e_last] <= line:
        j2 = min(e_last + 1, n - 1)
        return dict(end=j2, exit_px=float(o[j2]), pct=float((o[j2] - entry) / entry * 100 - cost), half_at=None,
                    half_px=None, steps=steps, how="through the stop on the bar it was bought")
    half_at = half_px = None
    armed = False
    for j in range(e_last + 1, last + 1):
        if half_at is None and v["arm"] == "rsi":
            # his rule: never sell while it is still oversold. The stop is live only while the last close had RSI
            # over 30; when RSI goes back under, the stop is off again and re-arms under the new low of the drop.
            if rsi[j - 1] <= 30:
                low0 = min(low0, float(l[j]))
                if armed and v["off"]:
                    armed = False
                    line = stop
                    steps.append((int(j), float(line)))
            elif not armed:
                armed = True
                line = low0 - v["wiggle"] * a
                steps.append((int(j), float(line)))
        elif half_at is None:
            low0 = min(low0, float(l[j]))
        if l[j] <= line:
            px = o[j + 1] if j + 1 <= last else c[last]
            got = 0.5 * (half_px - entry) / entry if half_at is not None else 0.0
            share = 0.5 if half_at is not None else 1.0
            pct = (got + share * (px - entry) / entry) * 100 - cost * (1.5 if half_at is not None else 1.0)
            return dict(end=int(j), exit_px=float(px), pct=float(pct), half_at=half_at, half_px=half_px, steps=steps,
                        how="the rest stopped under the low" if half_at is not None else "stopped out")
        if half_at is None:
            if np.isfinite(ema12[j]) and h[j] >= ema12[j]:
                half_at = int(j)
                half_px = float(max(o[j], ema12[j]))
                low0 = min(low0, float(np.min(l[e_last + 1:j + 1])))
                if v["arm"] != "never" and low0 - v["wiggle"] * a != line:
                    line = low0 - v["wiggle"] * a
                    steps.append((int(j), float(line)))
        elif np.isfinite(target) and h[j] >= target:
            px = float(max(o[j], target))
            pct = (0.5 * (half_px - entry) / entry + 0.5 * (px - entry) / entry) * 100 - cost * 1.5
            return dict(end=int(j), exit_px=px, pct=float(pct), half_at=half_at, half_px=half_px, steps=steps,
                        how="the rest reached the old high")
    px = float(c[last])
    got = 0.5 * (half_px - entry) / entry if half_at is not None else 0.0
    share = 0.5 if half_at is not None else 1.0
    pct = (got + share * (px - entry) / entry) * 100 - cost * (1.5 if half_at is not None else 1.0)
    return dict(end=int(last), exit_px=px, pct=float(pct), half_at=half_at, half_px=half_px, steps=steps,
                how="time ran out")


# THE REST (his ask 2026-09-22: "is the old high the best sale target you could find? that's kind of an odd target").
# Same buys, same first piece at the hourly 12 EMA, Dan's stop (nothing until the first piece is sold, then under the
# low of the drop). Only what the REST does changes. "thirds" = a third at the 12 EMA, a third at hourly RSI 70, the
# last third by the rule; otherwise half at the EMA and half by the rule.
RESTS = {
    "the old high (what the page does now)":                    dict(rest="high", thirds=False),
    "hourly RSI 70 (sell into overbought)":                     dict(rest="rsi70", thirds=False),
    "a close under the hourly 12 EMA, once it has closed above": dict(rest="ema_close", thirds=False),
    "a close under the last higher low (your standard exit)":   dict(rest="hl_close", thirds=False),
    "chandelier: 3 normal bars under the highest high":         dict(rest="chand3", thirds=False),
    "hold: only the stop under the low, time out at 480 bars":  dict(rest="hold", thirds=False),
    "THIRDS: 12 EMA, RSI 70, last third under the higher lows":  dict(rest="hl_close", thirds=True),
    "THIRDS: 12 EMA, RSI 70, last third for the old high":       dict(rest="high", thirds=True),
    "THIRDS: 12 EMA, RSI 70, last third on the 12 EMA close":    dict(rest="ema_close", thirds=True),
}


# THE FIRST SELL (his ask 2026-09-22: "since the ema12 sell is so good, is there any other type of sell you can test
# that's even better?? using all the tools we know about"). Only where the half sells changes; Dan's stop arms when it
# sells; the rest is walked. `ctx` carries the levels: hourly 26/50 EMA, the price where hourly RSI reads 50/60/70,
# the daily 12 EMA on the hourly clock, the top of the drop (last confirmed hourly high before the buy), yesterday's low.
FIRST_SELLS = {
    "hourly 12 EMA touch (the page)":                 "ema12",
    "hourly 12 EMA, on a CLOSE above it":             "ema12_close",
    "hourly 26 EMA touch":                            "ema26",
    "hourly 50 EMA touch":                            "ema50",
    "hourly RSI back over 30 (sell the first bounce)": "rsi30",
    "hourly RSI 50":                                  "rsi50",
    "hourly RSI 60":                                  "rsi60",
    "hourly RSI 70 (overbought)":                     "rsi70",
    "1 normal bar above the average paid":            "atr1",
    "2 normal bars above the average paid":           "atr2",
    "38.2% of the drop won back":                     "fib382",
    "50% of the drop won back":                       "fib50",
    "61.8% of the drop won back":                     "fib618",
    "the top of the drop (the last hourly high)":     "top",
    "the daily 12 EMA touch":                         "d12",
    "yesterday's low (the gap filled; stocks only)":  "ylow",
}


def _level(rule, j, ctx, entry, low0, a):
    """The price the first piece sells at on bar j, or None if that rule has no level here."""
    if rule == "ema12" or rule == "ema12_close":
        return ctx["ema12"][j]
    if rule == "ema26":
        return ctx["ema26"][j]
    if rule == "ema50":
        return ctx["ema50"][j]
    if rule.startswith("rsi"):
        return ctx["p" + rule[3:]][j]
    if rule == "atr1":
        return entry + a
    if rule == "atr2":
        return entry + 2 * a
    if rule.startswith("fib"):
        top = ctx["top"]
        if not np.isfinite(top) or top <= low0:
            return np.nan
        return low0 + {"fib382": 0.382, "fib50": 0.5, "fib618": 0.618}[rule] * (top - low0)
    if rule == "top":
        return ctx["top"]
    if rule == "d12":
        return ctx["d12"][j]
    if rule == "ylow":
        return ctx["ylow"][j]
    return np.nan


def walk_rest(kind, o, h, l, c, k, e_last, entry, stop, ema12, target, a, rsi, p70, lows, v, ctx=None):
    """Pieces come off one at a time; the stop under the low of the drop goes live when the first piece sells and
    applies to whatever is left. `lows` = every LIVE low confirmation (confirm bar, form bar, price), phantoms
    included (rule 40), for the walked stop."""
    n = len(c)
    last = min(n - 1, e_last + L.MAX_BARS)
    cost = COST.get(kind, 0.05)
    low0 = float(np.min(l[k:e_last + 1]))
    steps = [(int(e_last), float(stop))]
    if l[e_last] <= stop:
        j2 = min(e_last + 1, n - 1)
        return dict(end=j2, exit_px=float(o[j2]), pct=float((o[j2] - entry) / entry * 100 - cost), half_at=None,
                    half_px=None, steps=steps, how="through the disaster line on the buy bar")
    first = v.get("first_sell", "ema12")
    pieces = [(1 / 3, "ema"), (1 / 3, "rsi70"), (1 / 3, v["rest"])] if v["thirds"] else [(0.5, "ema"), (0.5, v["rest"])]
    got, sold = 0.0, 0.0                      # profit share booked, share sold
    half_at = half_px = None
    line = stop
    hi = float(np.max(h[k:e_last + 1]))
    seen_above = False
    hl_line = None
    li = 0
    # HIS BURL RULE (round 1 and 3): "if it bounces to cool off rsi that's a red flag ... the long stop is for when we
    # are scaling in during a solid dip". Once a bounce has lifted the hourly RSI to `cool` BEFORE the half sold, the
    # dip is no longer dipping and the wide disaster line stops protecting it. v["cool"] = (level, mode):
    #   "low"   the stop goes under the low of the drop as it stood when RSI cooled, oversold or not
    #   "exit"  out at the open after the next close back at or under 30 (the second leg down has started)
    # Decided on the LAST CLOSE (rsi[j-1]), so nothing is known before it could be.
    cool = v.get("cool")
    cooled = False
    cool_line = None
    # HIS JBHT NOTE, round 1: "Slow, steady RSI cooling drops are not good for buying" -- and on BURL, "the faster the
    # dips the better ... bulls showed up to buy discounted stock". v["slow"] = hours: when RSI first closes back over 31
    # before the half sold, if it took this many hours or more from its lowest point, the buyers did not show up. Out at
    # the next open. (backburner_coolshape: 4-6 hours -0.84% a trade, 7+ -1.56%, against +1.50% for 3 or less.)
    slow = v.get("slow")
    slow_done = False
    for j in range(e_last + 1, last + 1):
        hi = max(hi, float(h[j]))
        if slow and not slow_done and half_at is None and pieces and rsi[j - 1] >= 31:
            slow_done = True
            cb = j - 1
            lo_i = k + int(np.argmin(rsi[k:cb + 1]))
            if cb - lo_i >= slow:
                px = float(o[j])
                share = sum(p_ for p_, _ in pieces)
                pct = (got + share * (px - entry) / entry) * 100 - cost
                return dict(end=int(j), exit_px=px, pct=float(pct), half_at=None, half_px=None, steps=steps,
                            how="out: RSI took %d hours to climb back over 31 -- a slow bounce" % (cb - lo_i))
        if cool and half_at is None and pieces:
            if not cooled and rsi[j - 1] >= cool[0]:
                cooled = True
                cool_line = low0 - 0.1 * a
                steps.append((int(j), float(cool_line)))
            if cooled and cool[1] == "exit" and rsi[j - 1] <= 30:
                px = float(o[j])
                share = sum(p_ for p_, _ in pieces)
                pct = (got + share * (px - entry) / entry) * 100 - cost
                return dict(end=int(j), exit_px=px, pct=float(pct), half_at=None, half_px=None, steps=steps,
                            how="out: the bounce cooled the RSI and it rolled back under 30")
            if cooled and cool[1] == "low" and l[j] <= cool_line:
                px = float(o[j + 1]) if j + 1 <= last else float(c[last])     # sold at the next open, like every stop here
                share = sum(p_ for p_, _ in pieces)
                pct = (got + share * (px - entry) / entry) * 100 - cost
                return dict(end=int(j), exit_px=px, pct=float(pct), half_at=None, half_px=None, steps=steps,
                            how="out: the bounce cooled the RSI and it went back under the low")
        if half_at is None:
            low0 = min(low0, float(l[j]))
        oversold = rsi[j] <= 30
        rest_rule = pieces[0][1] if pieces else None
        # the walked stop: every low that has CONFIRMED by now, formed after the buy, above the current line
        if half_at is not None and rest_rule == "hl_close":
            while li < len(lows) and lows[li][0] <= j:
                ci_, fj_, px_ = lows[li]; li += 1
                if fj_ > e_last and (hl_line is None or px_ > hl_line):
                    hl_line = float(px_)
                    steps.append((int(j), float(hl_line)))
        if half_at is not None and rest_rule == "chand3":
            new = hi - 3 * a
            if new > line:
                line = new; steps.append((int(j), float(line)))
        # 1. the stop, on a wick (the line under the low / chandelier) or on a close (the walked higher low).
        # HIS ROUND-3 NOTE ON MNST, "still sold while oversold": while the hourly RSI is still at or under 30 the ONLY
        # line that can take the trade out is the wide disaster line. Everything else waits for RSI to come back over.
        live = stop if oversold else line
        hit = l[j] <= live or (hl_line is not None and c[j] < hl_line and not oversold)
        if hit and pieces:
            px = o[j + 1] if j + 1 <= last else c[last]
            share = sum(p_ for p_, _ in pieces)
            pct = (got + share * (px - entry) / entry) * 100 - cost * (1 + (0.5 if sold else 0))
            how = ("the rest stopped" if half_at is not None else "stopped out") + (
                " under the higher low" if (hl_line is not None and not oversold and c[j] < hl_line and l[j] > live) else "")
            return dict(end=int(j), exit_px=float(px), pct=float(pct), half_at=half_at, half_px=half_px, steps=steps, how=how)
        # 2. the pieces, in order
        while pieces:
            share, rule = pieces[0]
            px = None
            if rule == "ema":
                if first == "ema12" or ctx is None:
                    if np.isfinite(ema12[j]) and h[j] >= ema12[j]:
                        px = float(max(o[j], ema12[j]))
                elif first == "ema12_close":
                    if np.isfinite(ema12[j]) and c[j] > ema12[j]:
                        px = float(o[j + 1]) if j + 1 <= last else float(c[last])
                else:
                    lv = _level(first, j, ctx, entry, low0, a)
                    if np.isfinite(lv) and lv > entry * 0.5 and h[j] >= lv:
                        px = float(max(o[j], lv))
            elif rule == "rsi70" and np.isfinite(p70[j]) and h[j] >= p70[j]:
                px = float(max(o[j], p70[j]))
            elif rule == "high" and np.isfinite(target) and h[j] >= target:
                px = float(max(o[j], target))
            elif rule == "ema_close":
                if c[j] > ema12[j]:
                    seen_above = True
                elif seen_above and c[j] < ema12[j]:
                    px = float(o[j + 1]) if j + 1 <= last else float(c[last])
            if px is None:
                break
            got += share * (px - entry) / entry; sold += share
            pieces.pop(0)
            if half_at is None:
                half_at, half_px = int(j), px
                low0 = min(low0, float(np.min(l[e_last + 1:j + 1])))
                line = low0 - 0.1 * a
                steps.append((int(j), float(line)))
            if not pieces:
                return dict(end=int(j), exit_px=px, pct=float(got * 100 - cost * 1.5), half_at=half_at, half_px=half_px,
                            steps=steps, how="the rest sold on its rule (%s)" % rule)
    px = float(c[last])
    share = sum(p_ for p_, _ in pieces)
    pct = (got + share * (px - entry) / entry) * 100 - cost * (1 + (0.5 if sold else 0))
    return dict(end=int(last), exit_px=px, pct=float(pct), half_at=half_at, half_px=half_px, steps=steps, how="time ran out")


def trades_for(sym, kind, v=None):
    v = v or STOP                                   # the page's own rules unless a study passes a variant
    frames = S.frames_for(sym, kind)
    frames = {k_: v for k_, v in frames.items() if k_ in ("1h", "1d", "1w")}
    if kind in ("stock", "etf"):
        frames = FR2.regular_hours(frames)
    df, sdf, tdf = frames.get("1h"), frames.get("1d"), frames.get("1w")
    if df is None or sdf is None or tdf is None or len(df) < 500 or len(sdf) < 120 or len(tdf) < 60:
        return []
    o = df["Open"].values.astype(float); c = df["Close"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    atr = P._atr(df)
    rsi, au, ad = IND.rsi_parts(c, D.N_RSI)
    ema12 = XM.ema(c, 12)
    p30 = D.rsi_price(c, au, ad, 30); p20 = D.rsi_price(c, au, ad, 20); p70 = D.rsi_price(c, au, ad, 70)
    lows = highs = None
    ctx = None
    if v and "rest" in v:
        import eq_livecheck as LC
        ev_ = LC.live_events(df)[0]
        lows = [(int(e_[0]), int(e_[1]), float(e_[2])) for e_ in ev_ if e_[3] == "low"]
        highs = [(int(e_[0]), int(e_[1]), float(e_[2])) for e_ in ev_ if e_[3] == "high"]
        if v.get("first_sell", "ema12") not in ("ema12",):
            ylow = np.full(n, np.nan)
            if kind in ("stock", "etf"):
                day = df.index.normalize().values
                first_i = np.r_[0, np.where(day[1:] != day[:-1])[0] + 1]
                last_i = np.r_[first_i[1:] - 1, n - 1]
                for q in range(1, len(first_i)):
                    ylow[first_i[q]:last_i[q] + 1] = float(np.min(l[first_i[q - 1]:last_i[q - 1] + 1]))
            ctx = dict(ema12=ema12, ema26=XM.ema(c, 26), ema50=XM.ema(c, 50),
                       p50=D.rsi_price(c, au, ad, 50), p60=D.rsi_price(c, au, ad, 60), p70=p70, p30=p30,
                       d12=L.align_to(df, "1h", frames, "1d", XM.ema(sdf["Close"].values.astype(float), 12)),
                       ylow=ylow, top=np.nan)
    sc = sdf["Close"].values.astype(float)
    satr = P._atr(sdf)
    run = np.full(len(sc), np.nan)
    run[T.RUN_LOOK:] = (sc[T.RUN_LOOK:] - sc[:-T.RUN_LOOK]) / np.where(satr[T.RUN_LOOK:] > 0, satr[T.RUN_LOOK:], np.nan)
    s_run = L.align_to(df, "1h", frames, "1d", run)
    # THE SAME RUN IN PLAIN PERCENT (2026-09-22). Measured in the name's own normal bars, a quiet index fund that
    # climbed 3% scores the same as a stock that climbed 45%. He rejected IWD (+3%), XYL (+5%) and XLC (+5%) as "not a
    # big run up" while my bar measure called all three big. He sees the real size.
    run_pct = np.full(len(sc), np.nan)
    run_pct[T.RUN_LOOK:] = 100.0 * (sc[T.RUN_LOOK:] / sc[:-T.RUN_LOOK] - 1.0)
    s_run_pct = L.align_to(df, "1h", frames, "1d", run_pct)
    # HIS RULE, round 1 and round 3 (BHP "does not look like a clean run up, very messy chart"; UNP "really wild daily
    # candles ... too hectic for a clean backburner play"). A big run is not the same as a CLEAN one. Of the measures I
    # tried against his 14 grades -- path straightness, body share, daily range, share of up days -- the one that keeps
    # all ten of his "clean" and drops both of his "hectic" is Dan's own language: how many of the last 20 DAILY bars
    # made a HIGHER LOW than the day before. BHP 0.58, UNP 0.53; his clean ones run 0.63 to 0.84.
    # HIS DEFINITION (2026-09-22): "back burner is after a large move, UP OFF THE EMAS"; a 12 EMA ride is a DIFFERENT
    # trade ("zoom in and use a smaller timeframe oversold bounce as an entry onto the larger timeframe ema ride").
    # So: at the top of the run, how far had price pulled away from the daily 12 and 26 EMAs, in daily normal bars.
    # AND HIS SHARPER VERSION OF THE SAME THING (2026-09-22, on the megaphone): "previous price history was already at
    # the levels we were looking at now .. that's not a significant run up, it's just oscillations." So the run has to
    # reach levels price was NOT already at: the top of the last 20 daily bars against the top of the 60 before those,
    # in daily normal bars. His three oscillation rejects (UNP 0.09, LYV 0.80, BHP 1.01) are the three lowest of the 18
    # trades he has graded; twelve of his thirteen keeps are above 2.0.
    sh_ = sdf["High"].values.astype(float)
    se12 = XM.ema(sc, 12); se26 = XM.ema(sc, 26)
    off12_d = np.full(len(sc), np.nan); off26_d = np.full(len(sc), np.nan)
    for q_ in range(T.RUN_LOOK, len(sc)):
        j_ = q_ - T.RUN_LOOK + int(np.argmax(sh_[q_ - T.RUN_LOOK:q_]))
        if satr[j_] > 0:
            off12_d[q_] = (sh_[j_] - se12[j_]) / satr[j_]
            off26_d[q_] = (sh_[j_] - se26[j_]) / satr[j_]
    top20 = pd.Series(sh_).rolling(T.RUN_LOOK, min_periods=T.RUN_LOOK).max().values
    prior60 = pd.Series(sh_).rolling(60, min_periods=30).max().shift(T.RUN_LOOK).values
    with np.errstate(invalid="ignore"):
        fresh_d = (top20 - prior60) / np.where(satr > 0, satr, np.nan)
    s_fresh = L.align_to(df, "1h", frames, "1d", fresh_d)
    # AND HIS ROUND-5 WORDS (MOD): "the daily chart had so many days for the ema12 to catch up, NOT REALLY A NAME
    # RUNNING HOT at this point for a backburner". BKNG: "a lot of time to wind down in this eq after the last HH".
    # So: at the DIP, is price still up off the daily 12 EMA -- or has the EMA caught up while it wound sideways?
    hot_d = np.where(satr > 0, (sc - se12) / satr, np.nan)
    s_hot = L.align_to(df, "1h", frames, "1d", hot_d)
    s_off12 = L.align_to(df, "1h", frames, "1d", off12_d)
    s_off26 = L.align_to(df, "1h", frames, "1d", off26_d)
    dl_ = sdf["Low"].values.astype(float)
    clean = pd.Series(np.r_[np.nan, dl_[1:] > dl_[:-1]].astype(float)).rolling(20, min_periods=20).mean().values
    s_clean = L.align_to(df, "1h", frames, "1d", clean)
    # MESSY CANDLES, fitted on 155 charts labelled by eye (2026-09-22, his ask: "we should make an automatic filter
    # to not have shitty charting names"). Of sixteen measures the only one that agrees with BOTH my 155 eye labels
    # and his own five "messy chart" rejects is how much GROUND the run covered against how far it actually went:
    # the sum of the day-to-day moves over the 55 days into the dip, divided by the net travel. A march is near 2;
    # a fight is 5 and up. The `clean` share above was fitted on two examples and barely separates (0.60 vs 0.81).
    step_ = np.abs(np.diff(sc, prepend=np.nan))
    ground = pd.Series(step_).rolling(55, min_periods=55).sum().values
    net_ = np.abs(sc - pd.Series(sc).shift(55).values)
    with np.errstate(invalid="ignore", divide="ignore"):
        chop_d = ground / np.where(net_ > 0, net_, np.nan)
    s_chop = L.align_to(df, "1h", frames, "1d", chop_d)
    top = pd.Series(sdf["High"].values.astype(float)).rolling(T.HIGH_LOOK, min_periods=T.HIGH_LOOK).max().values
    s_top = L.align_to(df, "1h", frames, "1d", top)
    ext_t = L.align_to(df, "1h", frames, "1d", T._last_extreme_time(sdf, 1)[0])
    tc = tdf["Close"].values.astype(float)
    e50 = XM.ema(tc, 50)
    up = np.zeros(len(tc))
    up[5:] = ((tc[5:] > e50[5:]) & (e50[5:] > e50[:-5])).astype(float)
    t_up = L.align_to(df, "1h", frames, "1w", up)
    touch = np.isfinite(p30) & (l <= p30)
    was_out = np.r_[False, rsi[:-1] > 30]
    starts = np.where(touch & was_out)[0]
    got, cnt, cur = [], 0, None
    cost = COST.get(kind, 0.05)
    for k in starts:
        t_ext = ext_t[k - 1] if k > 0 else np.nan
        if not np.isfinite(t_ext):
            continue
        if cur is None or t_ext != cur:
            cur, cnt = t_ext, 0
        cnt += 1
        m_ = k - 1
        if cnt != 1 or k < 150 or k + 8 >= n or not np.isfinite(atr[m_]) or atr[m_] <= 0:
            continue
        if not (np.isfinite(s_run[m_]) and s_run[m_] >= 4 and t_up[m_] > 0.5):
            continue                                    # the run into the high, and the weekly trend intact
        if not (np.isfinite(s_fresh[m_]) and s_fresh[m_] >= FRESH_MIN):
            continue      # HIS RULE (2026-09-22): "previous price history was already at the levels we were looking
                          # at now .. that's not a significant run up, it's just oscillations."
        if not (np.isfinite(s_run_pct[m_]) and s_run_pct[m_] >= RUN_PCT_MIN):
            continue      # HIS RULE (2026-09-22, /messymark): IWD +3%, XYL +5%, XLC +5% were "not a big run up" / "a
                          # beautiful uptrend ema rider, not a run up for a backburner". Measured in normal bars all three
                          # looked big; in plain percent they are small. Removes 6% of trades at no cost (backburner_run_pct).
        # NO SEPARATE CLEAN-RUN FILTER. I fitted "the share of the last 20 daily bars making a higher low" to his 14 grades
        # and it looked like it split them; coded with the study's own window it keeps BHP (0.70, which he rejected
        # twice) and drops UNP and HLT (both of which he liked). That is an overfit on 14 points, not his eye. The
        # number is still recorded on every trade so the page can show it -- and he is marking daily runs on /cleanruns
        # so the measure can be built from his marks instead of my guess.
        a = atr[m_]
        # THE BUYS, in his words (2026-09-22): "I think it's just rsi 30 and 20. Maybe we try 25 also, as long as the rsi
        # hasn't closed above 31, aka cooled down." First buy at the RSI-30 price inside the candle; then one equal-size
        # order resting at each level in v["bids"] (default 20) for SECOND_BID_BARS hours, all pulled once RSI has
        # CLOSED above v["cancel_second"] (default 40, the page until he picks; his rule is 31). One unit per level, the
        # position price is their average. A candle that falls through several levels fills each of them.
        fills = [float(min(o[k], p30[k]))]; fill_bars = [int(k)]; e_last = k
        levels = [(lv, D.rsi_price(c, au, ad, lv) if lv not in (20, 30) else (p20 if lv == 20 else p30))
                  for lv in sorted(v.get("bids", [20]), reverse=True)]
        for j in range(k, min(n - 1, k + D.SECOND_BID_BARS)):
            if not levels:
                break
            if j > k and rsi[j - 1] > v.get("cancel_second", 40):
                break     # pulled: a bounce has cooled the RSI (his BURL rule: no adding once it has bounced)
            while levels and np.isfinite(levels[0][1][j]) and l[j] <= levels[0][1][j]:
                lp = levels[0][1][j]
                fills.append(float(min(o[j], lp)) if j > k else float(lp)); fill_bars.append(int(j)); e_last = j
                levels.pop(0)
        entry = float(np.mean(fills))
        stop = min(fills) - DISASTER_BARS * a
        rp = (entry - stop) / entry * 100
        if rp < 3 * cost or rp > 40.0:
            continue
        if v and "rest" in v:
            if ctx is not None:
                # the top of the drop: the last hourly high CONFIRMED before the buy (live pivots, rule 40)
                ctx = dict(ctx, top=next((px_ for ci_, fj_, px_ in reversed(highs) if ci_ <= k), np.nan))
            r = walk_rest(kind, o, h, l, c, k, e_last, entry, stop, ema12, s_top[m_], a, rsi, p70, lows, v, ctx)
        else:
            r = walk(kind, o, h, l, c, k, e_last, entry, stop, ema12, s_top[m_], a, rsi, v)
        got.append(dict(sym=sym, kind=kind, k=int(k), e=int(e_last), entry=entry, fills=fills, fill_bars=fill_bars,
                        stop=float(stop), risk_pct=float(rp), t=str(df.index[k]), run=float(s_run[m_]),
                        run_pct=float(s_run_pct[m_]) if np.isfinite(s_run_pct[m_]) else None,
                        clean=float(s_clean[m_]),
                        chop=float(s_chop[m_]) if np.isfinite(s_chop[m_]) else None,
                        off12=float(s_off12[m_]) if np.isfinite(s_off12[m_]) else None,
                        fresh=float(s_fresh[m_]) if np.isfinite(s_fresh[m_]) else None,
                        hot=float(s_hot[m_]) if np.isfinite(s_hot[m_]) else None,
                        off26=float(s_off26[m_]) if np.isfinite(s_off26[m_]) else None,
                        target=float(s_top[m_]) if np.isfinite(s_top[m_]) else None,
                        R=float(r["pct"] / rp), **r))
    return got


def draw(sym, df, sdf, tr, path):
    import pics_ride as PR
    k, end = tr["k"], tr["end"]
    x0 = max(0, k - 70)
    x1 = min(len(df) - 1, end + 14)
    d = df.iloc[x0:x1 + 1]
    xs = np.arange(len(d))
    fig = plt.figure(figsize=(16, 8.6), dpi=100)
    fig.patch.set_facecolor(DARK)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.55, 1], height_ratios=[3.2, 1], wspace=0.12, hspace=0.06,
                          top=0.92, bottom=0.14)
    ax = fig.add_subplot(gs[0, 0])
    bnd = CK.bundle(df, x0, len(d)); bnd["spans"] = []
    CK.render(ax, bnd, "", "%m-%d %H:%M")
    c_all = df["Close"].values.astype(float)
    ax.plot(xs, XM.ema(c_all[:x1 + 1], 12)[x0:x1 + 1], color=PURPLE, lw=1.3, zorder=6)
    lo = min(float(np.nanmin(d["Low"].values)), min(y for _j, y in tr["steps"][1:]) if len(tr["steps"]) > 1 else tr["stop"])
    hi = float(np.nanmax(d["High"].values))
    if tr.get("target"):
        hi = max(hi, min(tr["target"], hi * 1.08))
    rng = max(hi - lo, 1e-9)
    ax.set_ylim(lo - 0.50 * rng, hi + 0.12 * rng)
    pad_x = max(18, int(0.16 * len(d)))
    ax.set_xlim(-1, len(d) + pad_x)
    plt.setp(ax.get_xticklabels(), visible=False)
    # the stop as it moved, the average fill, the old high
    steps = tr["steps"] + [(end, tr["steps"][-1][1])]
    for q, ((j0, y0), (j1, _y)) in enumerate(zip(steps, steps[1:])):
        ax.plot([max(j0, x0) - x0, min(j1, x1) - x0], [y0, y0], color=RED, lw=1.0 if q == 0 else 1.6,
                ls=":" if q == 0 else "--", alpha=0.55 if q == 0 else 1.0, zorder=7)
    ax.hlines(tr["entry"], k - x0, len(d) - 1, colors="#e6e9ee", lw=1.1, ls=":", zorder=8)
    if False and tr.get("target") and tr["target"] <= hi + 0.1 * rng:      # no target any more (his CDNS note)
        ax.hlines(tr["target"], 0, len(d) - 1, colors=BLUE, lw=1.1, ls="-.", zorder=6)
        an0 = ax.annotate("the old high", (len(d) - 1, tr["target"]), xytext=(5, 0), textcoords="offset points",
                          ha="left", va="center", color=BLUE, fontsize=8, zorder=20)
        PR.keep_inside(ax, an0)

    def lane(frac):
        return lo - frac * rng

    def peg(x, y_bar, y_lane, colr, marker, label):
        ax.plot([x, x], [y_bar, y_lane], color=colr, lw=0.7, ls=":", alpha=0.6, zorder=6)
        ax.scatter([x], [y_lane], marker=marker, s=130, color=colr, edgecolor="#ffffff", lw=0.8, zorder=13)
        if label:
            an = ax.annotate(label, (x, y_lane), xytext=(0, -10), textcoords="offset points", ha="center", va="top",
                             color=colr, fontsize=8.5, weight="bold", zorder=20)
            PR.keep_inside(ax, an)
    fb, fx = tr["fill_bars"], tr["fills"]
    for i_, (b_, px_) in enumerate(zip(fb, fx)):
        peg(b_ - x0, px_, lane(0.08 + 0.07 * i_), GREEN, "^",
            ("buy at the touch of 30" if len(fx) == 1 else "bought at 30, again at 20") if i_ == len(fx) - 1 else None)
    if tr["half_at"] is not None:
        peg(tr["half_at"] - x0, tr["half_px"], lane(0.08 + 0.07 * len(fx) + 0.10), AMBER, "o", "half off at the 12 EMA")
    peg(end - x0, tr["exit_px"], lane(0.08 + 0.07 * len(fx) + 0.24), "#e6e9ee", "X", "out %+.2f%%" % tr["pct"])
    ax.set_title("%s hourly   first oversold after a run of %.0f daily bars   %+.2f%%  (%+.2fR against the disaster line)" % (
        sym, tr["run"], tr["pct"], tr["R"]), color="#e6e9ee", fontsize=11, loc="left", pad=8)
    # the RSI under it: the 30 line is the trigger
    axr = fig.add_subplot(gs[1, 0], sharex=ax)
    axr.set_facecolor(DARK)
    rsi_all = IND.rsi(c_all[:x1 + 1], 14)[x0:x1 + 1]
    axr.plot(xs, rsi_all, color="#e6e9ee", lw=1.1)
    axr.axhline(30, color=GREEN, lw=0.9, ls="--"); axr.axhline(70, color=RED, lw=0.9, ls="--")
    axr.set_ylim(5, 95); axr.set_yticks([30, 50, 70])
    axr.tick_params(colors=DIM, labelsize=7)
    for sp in axr.spines.values():
        sp.set_color("#252a33")
    axr.grid(color="#1a1e25", lw=0.5)
    step_ = max(len(d) // 7, 1)
    axr.set_xticks(xs[::step_]); axr.set_xticklabels([q.strftime("%m-%d %H:%M") for q in d.index[::step_]], fontsize=6.5)
    axr.set_ylabel("RSI 14", color=DIM, fontsize=8)
    panels = [(ax, d)]
    # the daily beside it: the run, the old high, the daily 12 EMA
    t_now = df.index[k]
    end_d = int(sdf.index.searchsorted(t_now.normalize(), side="right"))
    pos = max(0, end_d - 80); stop_d = min(len(sdf), end_d + 30)
    if stop_d - pos >= 20:
        axd = fig.add_subplot(gs[:, 1])
        hb = CK.bundle(sdf, pos, stop_d - pos); hb["spans"] = []
        CK.render(axd, hb, "", "%Y-%m-%d")
        e12 = XM.ema(sdf["Close"].values.astype(float)[:stop_d], 12)[pos:stop_d]
        axd.plot(np.arange(len(e12)), e12, color=PURPLE, lw=1.5, zorder=6)
        ylo = float(np.nanmin(sdf["Low"].values[pos:stop_d])); yhi = float(np.nanmax(sdf["High"].values[pos:stop_d]))
        yr = max(yhi - ylo, 1e-9)
        axd.set_ylim(max(0, ylo - 0.12 * yr), yhi + 0.12 * yr)
        axd.set_xlim(-1, stop_d - pos + 2)
        axd.axvline(end_d - pos - 0.5, color=DIM, lw=0.9, ls=":", zorder=4)
        axd.set_title("the daily: the run, and its 12 EMA (purple)", loc="left", color=DIM, fontsize=9.5, pad=3)
        plt.setp(axd.get_xticklabels(), fontsize=6)
        panels.append((axd, hb["d"]))
    fig.text(0.045, 0.080, "green arrows = bought inside the candle as hourly RSI touched 30 (and 20)    "
             "white dotted = the average paid    orange = half sold when the bounce reached the hourly 12 EMA (purple)",
             color=DIM, fontsize=8.5, ha="left")
    fig.text(0.045, 0.048, "red dotted = NO STOP (a wide disaster line only) while the hourly RSI is 30 or under    "
             "red dashed = the stop under the low of the drop, live once the half is sold AND RSI is back over 30",
             color=DIM, fontsize=8.5, ha="left")
    fig.text(0.045, 0.016, "red dashed steps up = the stop walked under each higher low; out on a close under it. THERE IS NO TARGET.",
             color=DIM, fontsize=8.5, ha="left")
    probs = PR.overlaps(fig, panels)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return probs


def _one(args):
    try:
        return trades_for(*args), []
    except Exception as ex:
        return [], ["%s %s: %s" % (args[1], args[0], ex)]


def _draw(args):
    sym, kind, picks = args
    try:
        frames = S.frames_for(sym, kind)
        frames = {k_: v for k_, v in frames.items() if k_ in ("1h", "1d")}
        if kind in ("stock", "etf"):
            frames = FR2.regular_hours(frames)
        out = []
        for tr in picks:
            png = "%s_%s_%d.png" % (kind, sym, tr["k"])
            probs = draw(sym, frames["1h"], frames["1d"], tr, os.path.join(OUT, png))
            out.append(dict(tr, png=png, problems=probs))
        return out, []
    except Exception as ex:
        return [], ["%s %s draw: %s" % (kind, sym, ex)]


def main():
    procs = 8
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            sys.stdout = sys.stderr = io.open(sys.argv[i + 1], "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    names = [(s_, k_) for s_, k_ in S.universe() if k_ in ("stock", "etf", "crypto") and s_ not in T.SUSPECT]
    rows, errs = [], []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for got, err in ex.map(_one, names, chunksize=4):
            rows += got; errs += err
    print("  %d trades (%.0fs)" % (len(rows), time.time() - t0), flush=True)
    seen = set()
    for g_ in sorted(_glob.glob(os.path.join("validation", "trade_notes_backburners*.csv"))):
        for ln in io.open(g_, encoding="utf-8").read().splitlines()[1:]:
            seen.add(ln.split(",")[0])
    if "--fresh" in sys.argv:
        rows = [r for r in rows if "%s_%s_%d.png" % (r["kind"], r["sym"], r["k"]) not in seen]
        print("  %d of them are trades he has not graded before" % len(rows), flush=True)
    # --same [round1|round5]: redraw exactly the trades he already graded in that round, with today's rules.
    # THE SET IS READ FROM HIS NOTES, not from an index file: an index is rewritten on every run, and one run of
    # --same wiped the round-5 drawings (2026-09-22). His notes are the only copy that is safe.
    if "--same" in sys.argv:
        which = sys.argv[sys.argv.index("--same") + 1] if len(sys.argv) > sys.argv.index("--same") + 1 else "round5"
        note_file = {"round1": "trade_notes_backburners.csv", "round5": "trade_notes_backburners5.csv"}.get(which)
        want = set()
        for ln in io.open(os.path.join("validation", note_file), encoding="utf-8").read().splitlines()[1:]:
            p_ = ln.split(",")[0].rsplit(".", 1)[0].split("_")
            if len(p_) >= 3:
                want.add((p_[0], "_".join(p_[1:-1]), int(p_[-1])))
        picks = [r for r in rows if (r["kind"], r["sym"], r["k"]) in want]
        print("  --same %s: %d of his %d graded trades still pass today's rules" % (which, len(picks), len(want)))
    else:
        rng = np.random.default_rng(20260921)
        wins = [r for r in rows if r["R"] > 0.15]
        losses = [r for r in rows if r["R"] <= -0.15]
        picks = ([wins[i] for i in rng.choice(len(wins), 8, replace=False)]
                 + [losses[i] for i in rng.choice(len(losses), 8, replace=False)])
    by = {}
    for tr in picks:
        by.setdefault((tr["sym"], tr["kind"]), []).append(tr)
    drawn, derr = [], []
    with cf.ProcessPoolExecutor(max_workers=min(procs, len(by))) as ex:
        for got, err in ex.map(_draw, [(s_, k_, v) for (s_, k_), v in by.items()], chunksize=1):
            drawn += got; derr += err
    drawn.sort(key=lambda x: -x["R"])
    for i, tr in enumerate(drawn, 1):
        tr["n"] = i
    keep = {d_["png"] for d_ in drawn} | {"index.json", "index_round1.json"}
    for f in os.listdir(OUT):
        if f not in keep:
            os.remove(os.path.join(OUT, f))
    pct = np.array([r["pct"] for r in rows]); R_ = np.array([r["R"] for r in rows])
    stats = dict(n=len(rows), avg_pct=float(pct.mean()), middle_pct=float(np.median(pct)), won=float((pct > 0).mean()),
                 avg_R=float(R_.mean()), half_taken=float(np.mean([r["half_at"] is not None for r in rows])),
                 reached_high=float(np.mean([r["how"] == "the rest reached the old high" for r in rows])),
                 rest_on_rule=float(np.mean([r["how"].startswith("the rest sold on its rule") or "higher low" in r["how"] for r in rows])),
                 two_fills=float(np.mean([len(r["fills"]) > 1 for r in rows])),
                 median_risk=float(np.median([r["risk_pct"] for r in rows])))
    def _plain(v):
        return v.item() if hasattr(v, "item") else v
    slim = [{k_: _plain(v) for k_, v in d_.items() if k_ != "steps"} for d_ in drawn]
    json.dump(dict(stats=stats, charts=slim), open(os.path.join(OUT, "index.json"), "w"), indent=1)
    print("  drawn %d, problems %d  (%.0fs)" % (len(drawn), sum(1 for d_ in drawn if d_["problems"]), time.time() - t0))
    print("  stats:", {k_: round(v, 3) for k_, v in stats.items()})
    for d_ in drawn:
        print("    #%-2d %-6s %+6.2fR %+7.2f%%  risk %.2f%%  %-32s %s" % (
            d_["n"], d_["sym"], d_["R"], d_["pct"], d_["risk_pct"], d_["how"], d_["problems"] or ""))
    for e_ in (errs + derr)[:8]:
        print("  " + e_)


if __name__ == "__main__":
    main()
