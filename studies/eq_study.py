"""eq_study.py -- the textbook range trade ("EQ"), on every name and chart.

Owner 2026-09-08: "eq is one of the best simplest trades, usually there's a
couple more factors that go into it but they're almost always the textbook
simplest trade."

The range, his rule (structure.py): it needs four pivots, two higher/equal
lows and two lower/equal highs among the last four. The floor is the last
higher/equal low, the ceiling the last lower/equal high, both move as new
ones confirm. It dies the moment a wick goes through an edge (0.15 of a
normal bar past it) or a higher high / lower low prints beyond it.

The trade, buy side: price comes back to the floor (a low within a quarter of
a normal bar of it, without breaking it). Buy the next open. Sell at the
ceiling (a limit at the ceiling price), or at the next open after the range
dies. Short side is the mirror. Two more exits are tested: sell at the middle
of the range, and "ride the breakout" (no target; a stop 5 normal bars under
the highest close, so a range that breaks upward keeps paying).

Everything fills at the next open after its signal bar (rule 14). Costs by
class. Compared to the drift over the same bars.

    pythonw studies/eq_study.py --procs 20 --log logs/eq_study.log   [--focus]
Writes validation/eq_study.json (+_focus): by_side_exit, by_side_exit_tf,
by_side_exit_kind, by_side_exit_era, by_touch, by_width, by_hi, by_rsi;
validation/eq_names.json: per name/timeframe: how often it ranges, how wide,
how long, and what the trade made. validation/eq_events.csv.gz: every buy-side
trade (for the charts).
"""
import concurrent.futures as cf
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "studies"))
import backburner_study as B      # noqa: E402
import panel as P                 # noqa: E402
import trend_ride as R            # noqa: E402
import exit_managers as XM        # noqa: E402

TFS = ["5m", "15m", "1h", "4h", "1d", "1w"]
OUT = os.path.join("validation", "eq_study.json")
NAMES_OUT = os.path.join("validation", "eq_names.json")
EVENTS_OUT = os.path.join("validation", "eq_events.csv.gz")
TOUCH = 0.25          # a low within this many normal bars of the floor is a touch
KEYS = ["mode", "side", "exit", "tf", "kind", "era", "touches", "width", "hi", "rsi"]
CAP_DAYS = 30
MODE_NAMES = {"box": "the box around the four pivots, a wick beyond it kills it",
              "box_close": "the box around the four pivots, only a CLOSE beyond it kills it",
              "flat_close": "a flat box (equal lows, equal highs within half a bar), a close beyond kills it",
              "last": "the last two pivots as edges, they move (the rule taken literally)"}


def ranges(df, mode="box"):
    """The live range machine, bar by bar. Returns floor[], ceil[], rid[] (range id
    per bar, -1 outside), and a list of (birth_bar, death_bar, how_it_died).
    mode "last": the edges are the LAST higher/equal low and lower/equal high, and
    move with each new one (structure.py, taken literally). The range is then born
    right where price just was, so it usually dies on the next dip.
    mode "box": the edges are the lowest low pivot and the highest high pivot of
    the four that made it (the box a trader draws), fixed until a wick or a pivot
    goes through one of them."""
    c = df["Close"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    seq = P.zigzag(df, P.PIVOT_BARS)
    atr = P._atr(df)
    floor = np.full(n, np.nan); ceil = np.full(n, np.nan); rid = np.full(n, -1)
    lows, highs = [], []
    last4_meta = []
    alive = False; ceil_p = floor_p = np.nan
    born = None; out = []
    k = 0
    for i in range(n):
        tol = P.SAME_LEVEL_ATR * (atr[i] if np.isfinite(atr[i]) else 0.0)
        while k < len(seq) and seq[k][0] <= i:
            _, j, price, kind = seq[k]; k += 1
            if kind == "low":
                prev = lows[-1] if lows else np.nan
                lab = (("HL" if price > prev + tol else "LL" if price < prev - tol else "EL") if np.isfinite(prev) else None)
                lows.append(price)
            else:
                prev = highs[-1] if highs else np.nan
                lab = (("HH" if price > prev + tol else "LH" if price < prev - tol else "EH") if np.isfinite(prev) else None)
                highs.append(price)
            if lab is None:
                continue
            last4_meta = (last4_meta + [(kind, lab, price)])[-4:]
            if alive:
                if (lab == "HH" and price > ceil_p + tol) or (lab == "LL" and price < floor_p - tol):
                    out.append((born, i, "a %s printed beyond the edge" % ("higher high" if lab == "HH" else "lower low")))
                    alive = False; ceil_p = floor_p = np.nan; last4_meta = []; born = None
                elif mode == "last" and lab in ("LH", "EH"):
                    ceil_p = price
                elif mode == "last" and lab in ("HL", "EL"):
                    floor_p = price
            if (not alive and len(last4_meta) == 4
                    and sum(1 for kk, ll, p in last4_meta if ll in ("HL", "EL")) >= 2
                    and sum(1 for kk, ll, p in last4_meta if ll in ("LH", "EH")) >= 2):
                alive = True
                if mode in ("box", "box_close", "flat_close"):
                    lows4 = [p for kk, ll, p in last4_meta if kk == "low"]; highs4 = [p for kk, ll, p in last4_meta if kk == "high"]
                    if mode == "flat_close" and (max(lows4) - min(lows4) > 0.5 * atr[i] or max(highs4) - min(highs4) > 0.5 * atr[i]):
                        alive = False; last4_meta = last4_meta[-3:]; continue      # a coil, not a flat range
                    floor_p = min(lows4)
                    ceil_p = max(highs4)
                else:
                    ceil_p = next((p for kk, ll, p in reversed(last4_meta) if ll in ("LH", "EH")), np.nan)
                    floor_p = next((p for kk, ll, p in reversed(last4_meta) if ll in ("HL", "EL")), np.nan)
                born = i
        hi_t, lo_t = (c[i], c[i]) if mode.endswith("_close") else (h[i], l[i])       # a close beyond, or a wick beyond
        if alive and ((np.isfinite(ceil_p) and hi_t > ceil_p + tol) or (np.isfinite(floor_p) and lo_t < floor_p - tol)):
            out.append((born, i, ("a close above the ceiling" if hi_t > ceil_p + tol else "a close under the floor") if mode.endswith("_close")
                        else ("a wick through the ceiling" if hi_t > ceil_p + tol else "a wick through the floor")))
            alive = False; ceil_p = floor_p = np.nan; last4_meta = []; born = None
        if alive:
            floor[i] = floor_p; ceil[i] = ceil_p; rid[i] = len(out)
    if alive and born is not None:
        out.append((born, n - 1, "still open"))
    return floor, ceil, rid, out, atr


def study_frame(sym, kind, tf, frames, start):
    rows, name_row = [], None
    for mode in ("box", "box_close", "flat_close", "last"):
        rr, nr = study_frame_mode(sym, kind, tf, frames, start, mode)
        rows += rr
        if mode == "box_close":
            name_row = nr
    return rows, name_row


def study_frame_mode(sym, kind, tf, frames, start, mode):
    df = frames[tf]
    if len(df) < 300:
        return [], None
    c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    floor, ceil, rid, rlist, atr = ranges(df, mode)
    rsi = XM.rsi(c)
    hdf = frames.get(R.UP.get(tf))
    hi_state = B.higher_view(df, tf, hdf, R.UP[tf])[0] if hdf is not None and len(hdf) >= 60 else np.array(["NA"] * n, dtype=object)
    cost = B.CLASS_COST.get(kind, B.COST)
    cap = CAP_DAYS * B.BARS_DAY[tf]
    lr = np.diff(np.log(c), prepend=np.log(c[0]))
    drift = float(np.nanmean(lr[np.isfinite(lr)]))
    mid_t = start + (pd.Timestamp.now() - start) / 2
    day = df.index.normalize().values if kind in ("stock", "etf") and tf in ("5m", "15m") else None
    bpd = B.BARS_DAY[tf]
    rows = []
    touches_seen = {}          # range id -> touches so far (each side)
    busy = {}                  # (side, exit) -> bar we are busy until
    events = []
    for i in range(60, n - 2):
        if rid[i] < 0 or not np.isfinite(floor[i]) or not np.isfinite(ceil[i]):
            continue
        a = atr[i] if np.isfinite(atr[i]) and atr[i] > 0 else np.nan
        if not np.isfinite(a):
            continue
        width = (ceil[i] - floor[i]) / a
        if width < 1.0:
            continue                          # too narrow to trade
        r_ = rid[i]
        t = df.index[i + 1]
        era = "before" if t < start else "first" if t < mid_t else "second"
        for side in ("buy the floor", "short the ceiling"):
            if side == "buy the floor":
                touch = l[i] <= floor[i] + TOUCH * a and c[i] > floor[i] - P.SAME_LEVEL_ATR * a
            else:
                touch = h[i] >= ceil[i] - TOUCH * a and c[i] < ceil[i] + P.SAME_LEVEL_ATR * a
            if not touch:
                continue
            key = (r_, side)
            touches_seen[key] = touches_seen.get(key, 0) + 1
            nt = touches_seen[key]
            e = i + 1
            fill = o[e]
            if fill <= 0:
                continue
            base = dict(mode=MODE_NAMES[mode], side=side, tf=tf, kind=kind, era=era,
                        touches="1st touch" if nt == 1 else "2nd touch" if nt == 2 else "3rd touch or later",
                        width="narrow (1-2 bars)" if width < 2 else "2-4 bars" if width < 4 else "4-8 bars" if width < 8 else "wide (8+ bars)",
                        hi=("next chart up" if str(hi_state[i]) == "UP" else "next chart down" if str(hi_state[i]) == "DOWN" else "next chart flat"),
                        rsi=("RSI under 30 at the touch" if rsi[i] <= 30 else "RSI 30-50" if rsi[i] <= 50 else "RSI over 50") if side == "buy the floor"
                            else ("RSI over 70 at the touch" if rsi[i] >= 70 else "RSI 50-70" if rsi[i] >= 50 else "RSI under 50"))
            f0, c0 = floor[i], ceil[i]
            for ex in ("sell at the ceiling", "sell at the middle", "ride the breakout (chandelier 5)"):
                bk = (side, ex)
                if e <= busy.get(bk, -1):
                    continue
                res = walk(side, ex, c, o, h, l, atr, floor, ceil, rid, r_, e, f0, c0, n, cap, day)
                if res is None:
                    busy[bk] = n; continue
                xb, xpx, why, worst = res
                busy[bk] = xb + 1
                sgn = 1.0 if side == "buy the floor" else -1.0
                ret = sgn * (xpx / fill - 1) - cost
                after = min(n - 1, xb + 60)
                rows.append(dict(base, exit=ex, ret=float(ret), held=int(xb + 1 - e), why=why, took=False,
                                 worst=float(worst), best_after=float(sgn * (np.max(c[xb:after + 1]) / fill - 1)) if sgn > 0 else float(sgn * (np.min(c[xb:after + 1]) / fill - 1)),
                                 drift=float(sgn * (np.exp(drift * (xb + 1 - e)) - 1) - cost)))
                if side == "buy the floor" and ex == "sell at the ceiling":
                    events.append(dict(mode=mode, sym=sym, kind=kind, tf=tf, t=str(t), ret=round(float(ret), 5), held=int(xb + 1 - e), why=why,
                                       touches=nt, width=round(float(width), 2), floor=float(f0), ceil=float(c0), hi=base["hi"]))
    # how this name ranges
    closed = [(b0, d0, how) for b0, d0, how in rlist if how != "still open"]
    months = max(1.0, (df.index[-1] - df.index[max(0, n - 1)]).days / 30.4) if n else 1.0
    months = max(1.0, (df.index[-1] - df.index[0]).days / 30.4)
    inrange = float(np.mean(rid >= 0))
    widths = [(np.nanmean(ceil[b0:d0 + 1]) - np.nanmean(floor[b0:d0 + 1])) / np.nanmean(atr[b0:d0 + 1]) for b0, d0, how in closed if d0 > b0]
    lives = [(d0 - b0 + 1) / bpd for b0, d0, how in closed]
    name_row = dict(sym=sym, kind=kind, tf=tf, ranges=len(closed), ranges_per_month=len(closed) / months,
                    time_in_range=inrange, width_bars=float(np.nanmean(widths)) if widths else None,
                    life_days=float(np.mean(lives)) if lives else None,
                    died_up=float(np.mean([how == "a wick through the ceiling" or how.startswith("a higher high") for b0, d0, how in closed])) if closed else None)
    buy = [x for x in rows if x["side"] == "buy the floor" and x["exit"] == "sell at the ceiling"]
    if buy:
        rr = np.array([x["ret"] for x in buy])
        name_row.update(trades=len(buy), ret=float(rr.mean()), win=float((rr > 0.005).mean()),
                        half1=float(np.mean([x["ret"] for x in buy if x["era"] == "first"])) if sum(1 for x in buy if x["era"] == "first") >= 8 else None,
                        half2=float(np.mean([x["ret"] for x in buy if x["era"] == "second"])) if sum(1 for x in buy if x["era"] == "second") >= 8 else None)
    else:
        name_row.update(trades=0, ret=None, win=None, half1=None, half2=None)
    name_row["events"] = events
    return rows, name_row


def walk(side, ex, c, o, h, l, atr, floor, ceil, rid, r_, e, f0, c0, n, cap, day):
    """From bar e, holding one range trade. Returns (exit_bar, exit_price, why, worst)."""
    fill = o[e]
    long = side == "buy the floor"
    peak = c[e]; trough = c[e]; worst = 0.0
    for k in range(e, n - 1):
        a = atr[k] if np.isfinite(atr[k]) else 0.0
        worst = min(worst, (c[k] / fill - 1) if long else (1 - c[k] / fill))
        peak = max(peak, c[k]); trough = min(trough, c[k])
        alive = rid[k] == r_
        fl = floor[k] if alive else f0; ce = ceil[k] if alive else c0
        if ex == "ride the breakout (chandelier 5)":
            if long and c[k] < peak - 5 * a:
                return k, o[k + 1], "chandelier hit", worst
            if not long and c[k] > trough + 5 * a:
                return k, o[k + 1], "chandelier hit", worst
        else:
            tgt = ce if ex == "sell at the ceiling" else (fl + ce) / 2
            if long and h[k] >= tgt and k > e:
                return k, tgt, "hit the %s" % ("ceiling" if ex == "sell at the ceiling" else "middle"), worst
            tgt_s = fl if ex == "sell at the ceiling" else (fl + ce) / 2
            if not long and l[k] <= tgt_s and k > e:
                return k, tgt_s, "hit the %s" % ("floor" if ex == "sell at the ceiling" else "middle"), worst
            if not alive and k > e:
                # the range died on this bar: out at the next open
                return k, o[k + 1], "the range broke", worst
        if day is not None and k + 1 < n and day[k + 1] != day[k]:
            return k, c[k], "session end", worst
        if k - e >= cap:
            return k, o[k + 1], "time", worst
    return None


def fold(rows):
    R.KEYS, keep = KEYS, R.KEYS
    try:
        return R.fold(rows)
    finally:
        R.KEYS = keep


def _work(args):
    sym, kind, start = args
    errs, rows, names = [], [], []
    try:
        frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, [], ["%s %s: %s" % (kind, sym, ex)]
    for tf in TFS:
        if tf not in frames:
            continue
        try:
            rr, nr = study_frame(sym, kind, tf, frames, start)
            rows += rr
            if nr:
                names.append(nr)
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    return fold(rows), names, errs


def main():
    procs, log = max(1, os.cpu_count() or 4), None
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            log = sys.argv[i + 1]
            sys.stdout = sys.stderr = open(log, "w", buffering=1, encoding="utf-8", errors="replace")
    global OUT, NAMES_OUT, EVENTS_OUT
    t0 = time.time()
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * B.YEARS)
    names = [(s_, k_) for s_, k_ in B.universe() if k_ != "forex"]
    if "--focus" in sys.argv:
        import focus
        names = [(s_, k_) for s_, k_ in focus.names() if focus.have(s_, k_)]
        OUT = OUT.replace(".json", "_focus.json"); NAMES_OUT = NAMES_OUT.replace(".json", "_focus.json")
        EVENTS_OUT = EVENTS_OUT.replace(".csv.gz", "_focus.csv.gz")
    names = R._by_size(names)
    R.quiet_workers()
    parts, name_rows, done, errs = [], [], 0, []
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for out, nr, err in ex.map(_work, [(s_, k_, start) for s_, k_ in names], chunksize=1):
            done += 1
            errs += err or []
            if out is not None:
                parts.append(out)
            name_rows += nr
            if done % 50 == 0:
                print("  %d/%d names  (%.0fs)" % (done, len(names), time.time() - t0), flush=True)
    for e_ in errs[:20]:
        print("  ERR " + e_)
    f = pd.concat(parts, ignore_index=True)
    res = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names), tfs=TFS,
                         modes=[MODE_NAMES[m] for m in ("box", "box_close", "flat_close", "last")],
                         sides=["buy the floor", "short the ceiling"],
                         exits=["sell at the ceiling", "sell at the middle", "ride the breakout (chandelier 5)"]),
               by_side_exit=R.by(f, ["mode", "side", "exit"]),
               by_side_exit_tf=R.by(f, ["mode", "side", "exit", "tf"]),
               by_side_exit_kind=R.by(f, ["mode", "side", "exit", "kind"]),
               by_side_exit_era=R.by(f, ["mode", "side", "exit", "era"]),
               by_touch=R.by(f, ["mode", "side", "exit", "touches"]),
               by_width=R.by(f, ["mode", "side", "exit", "width"]),
               by_hi=R.by(f, ["mode", "side", "exit", "hi"]),
               by_rsi=R.by(f, ["mode", "side", "exit", "rsi"]),
               by_touch_tf=R.by(f, ["mode", "side", "exit", "touches", "tf"]),
               by_width_tf=R.by(f, ["mode", "side", "exit", "width", "tf"]))
    json.dump(res, open(OUT, "w"))
    # per-name scorecard and the event file
    ev = [dict(e_) for nr in name_rows for e_ in nr.pop("events", [])]
    pd.DataFrame(ev).to_csv(EVENTS_OUT, index=False)
    bench = {"crypto": "BTC", "stock": "SPY", "etf": "SPY", "futures": "ES_F"}
    d = pd.DataFrame(name_rows)
    bl = {(r_.sym, r_.tf): r_.ret for r_ in d.itertuples() if r_.ret is not None}
    d["vs_bench"] = [None if r_.ret is None or bl.get((bench.get(r_.kind), r_.tf)) is None else float(r_.ret - bl[(bench.get(r_.kind), r_.tf)]) for r_ in d.itertuples()]
    d = d.replace({np.nan: None})
    json.dump(dict(generated=res["meta"]["generated"], tfs=TFS, bench=bench, rows=json.loads(d.to_json(orient="records"))), open(NAMES_OUT, "w"))
    print("  EQ STUDY  %d names, %d trades  (%.0fs)" % (len(names), int(f.n.sum()), time.time() - t0))
    for side in res["meta"]["sides"]:
        for ex in res["meta"]["exits"]:
            print("\n  %s / %s" % (side, ex))
            for tf in TFS:
                b = res["by_side_exit_tf"].get("%s | %s | %s" % (side, ex, tf))
                if b:
                    print("    %-3s n=%7d  %+.2f%%  vs drift %+.2f%%  won %2.0f%%  held %4.0f" % (tf, b["n"], 100 * b["ret"], 100 * b["edge"], 100 * b["win"], b["held"]))
    if log:
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
