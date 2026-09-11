"""eq_playbook.py -- The Chart Guys' actual trade, with the fast chart used as TIMING (2026-09-11).

From three years of their #swingtrade posts (tcg_slack/swingtrade_digest.md, TCG_METHOD.md #9):
  WHERE   a bigger chart's higher low at a known place: its 12 EMA ("weekly higher low off EMA12")
  WHEN    a smaller chart shows it: a small EQ breaking ("if this QQQ 5 min equilibrium breaks bear"), a small higher
          low ("Scouting a TSLA hourly higher low entry"), or small-chart oversold ("keeping an eye for 5 min oversold";
          "our strongest up trends have hourly oversold mark daily higher lows")
  STOP    just past the small structure ("That is either the weekly higher low or I am wrong")
  PARTIAL half, early, to get risk free: into the big chart's overbought ("in 1hr and 4hr overbought conditions") or
          at twice the risk; stop to breakeven
  RUNNER  no target; stop walked up under each new higher low on the big chart ("I will walk up stops with the trend")
          or out when the big chart's 12 EMA is lost ("XLF daily EMA12 rider guide for trimming or exiting")

Pairs: idea on the 1h, timed on the 5m; idea on the 4h, timed on the 15m. Everything is walked bar by bar on the small
chart, with the big chart's values taken from its last CLOSED bar.
  big setup (long)   the big chart is in an uptrend (the pivots), or its last confirmed high was a higher high
  location           the small bar's low within half a big normal bar of the big chart's 12 EMA, that EMA rising
  triggers           (a) a small EQ breaks up   (b) a small higher low confirms   (c) small RSI crosses back over 30
  control rows       the same triggers with no location; and "no trigger": the next open once setup + location appear
  entry              next small open; one trade at a time per chart pair
  stop               (a) under the EQ floor  (b) under that higher low  (c) under the lowest low of the last 10 bars,
                     each a normal small bar's equal-low tolerance deeper; sold at the next open after a wick through
  exits              half at big-chart RSI 70 or 2x the risk (first), stop to breakeven, runner walked up under each
                     new big-chart higher low | same partial, runner out on a close under the big 12 EMA |
                     all out at 2x the risk (control)
Shorts are the mirror. Costs out. 30-day cap. Stocks and ETFs on regular-hours bars. Three eras, against drift.

    pythonw studies/eq_playbook.py --procs 20 --log logs/eq_playbook.log
Writes validation/eq_playbook.json
"""
import concurrent.futures as cf
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as B      # noqa: E402
import panel as P                 # noqa: E402
import structure as ST            # noqa: E402
import trend_ride as R            # noqa: E402
import exit_managers as XM        # noqa: E402
import indicators as IND          # noqa: E402
import eq_coil as EC              # noqa: E402
import eq_freeride as FR          # noqa: E402
import eq_freeride2 as FR2        # noqa: E402

OUT = os.path.join("validation", "eq_playbook.json")
PAIRS = [("1h", "5m"), ("4h", "15m")]
NEAR = 0.5
CAP_DAYS = 30
TRIGGERS = ["small EQ breaks our way", "small higher low confirms", "small RSI back over 30", "no trigger (next open)"]
EXITS = [("half at big RSI 70 or 2x risk, runner under each big higher low", "steps"),
         ("half at big RSI 70 or 2x risk, runner out on a close through the big 12 EMA", "ema"),
         ("all out at 2x the risk", "t2")]
LOCS = ["at the big 12 EMA", "anywhere (no location)"]
SIDES = ["long", "short"]
ERAS = ["before", "first", "second"]
DIMS = [("pair", ["%s idea, %s timing" % p for p in PAIRS]), ("trigger", TRIGGERS), ("exit", [x[0] for x in EXITS]),
        ("loc", LOCS), ("side", SIDES), ("era", ERAS)]
SIZES = [len(v) for _, v in DIMS]


def encode(vals):
    code = 0
    for v, size in zip(vals, SIZES):
        code = code * size + v
    return code


def aligned_float(small, stf, big, btf, values):
    out = FR.align(small, stf, big, btf, np.asarray(values, dtype=object))
    return np.array([np.nan if isinstance(x, str) else float(x) for x in out], dtype=float)


def big_series(small, stf, big, btf):
    """The big chart as seen from every small bar (last closed big bar only)."""
    bc = big["Close"].values.astype(float)
    e12 = XM.ema(bc, 12)
    slope = e12 - np.r_[np.full(3, np.nan), e12[:-3]]
    rsi = IND.rsi_parts(bc)[0]
    batr = P._atr(big)
    st = ST.states(big, causal=True)
    hb = len(big)
    last_high_lab = np.array(["NA"] * hb, dtype=object)
    last_hl = np.full(hb, np.nan)          # the latest confirmed higher low (or equal low) price
    last_lh = np.full(hb, np.nan)          # the latest confirmed lower high (or equal high) price
    piv = ST.pivots(big)
    p = 0
    lh_lab, cur_hl, cur_lh = "NA", np.nan, np.nan
    last_low_lab = "NA"
    last_low_lab_arr = np.array(["NA"] * hb, dtype=object)
    for k in range(hb):
        while p < len(piv) and piv[p][0] <= k:
            ci, j, pr, kd, lab = piv[p]
            p += 1
            if kd == "high":
                lh_lab = lab
                if lab in ("LH", "EH"):
                    cur_lh = float(pr)
            else:
                last_low_lab = lab
                if lab in ("HL", "EL"):
                    cur_hl = float(pr)
        last_high_lab[k] = lh_lab
        last_low_lab_arr[k] = last_low_lab
        last_hl[k] = cur_hl
        last_lh[k] = cur_lh
    return dict(e12=aligned_float(small, stf, big, btf, e12), slope=aligned_float(small, stf, big, btf, slope),
                rsi=aligned_float(small, stf, big, btf, rsi), atr=aligned_float(small, stf, big, btf, batr),
                state=FR.align(small, stf, big, btf, st),
                high_lab=FR.align(small, stf, big, btf, last_high_lab),
                low_lab=FR.align(small, stf, big, btf, last_low_lab_arr),
                hl=aligned_float(small, stf, big, btf, last_hl), lh=aligned_float(small, stf, big, btf, last_lh))


def walk(sgn, c, o, h, l, bs, e, fill, stop, n, cap, day, mode):
    risk = abs(fill - stop)
    if risk <= 0:
        return None
    t2 = fill + sgn * 2 * risk
    took = False
    stop_now = stop
    part_px = None
    for k in range(e, n - 1):
        if (sgn > 0 and l[k] < stop_now) or (sgn < 0 and h[k] > stop_now):
            px = o[k + 1]
            return k, (0.5 * part_px + 0.5 * px) if took else px, took
        if mode == "t2":
            if (sgn > 0 and h[k] >= t2) or (sgn < 0 and l[k] <= t2):
                return k, t2, True
        else:
            if not took:
                hot = np.isfinite(bs["rsi"][k]) and ((sgn > 0 and bs["rsi"][k] >= 70) or (sgn < 0 and bs["rsi"][k] <= 30))
                if (sgn > 0 and h[k] >= t2) or (sgn < 0 and l[k] <= t2):
                    took, part_px, stop_now = True, t2, fill
                elif hot and ((sgn > 0 and c[k] > fill) or (sgn < 0 and c[k] < fill)):
                    took, part_px, stop_now = True, c[k], fill
            if took:
                if mode == "steps":
                    a = bs["atr"][k] if np.isfinite(bs["atr"][k]) else 0.0
                    tol = P.SAME_LEVEL_ATR * a
                    if sgn > 0 and np.isfinite(bs["hl"][k]):
                        stop_now = max(stop_now, bs["hl"][k] - tol)
                    if sgn < 0 and np.isfinite(bs["lh"][k]):
                        stop_now = min(stop_now, bs["lh"][k] + tol)
                elif mode == "ema" and np.isfinite(bs["e12"][k]):
                    if (sgn > 0 and c[k] < bs["e12"][k]) or (sgn < 0 and c[k] > bs["e12"][k]):
                        return k, 0.5 * part_px + 0.5 * o[k + 1], True
        if day is not None and k + 1 < n and day[k + 1] != day[k]:
            return k, (0.5 * part_px + 0.5 * c[k]) if took else c[k], took
        if k - e >= cap:
            px = o[k + 1]
            return k, (0.5 * part_px + 0.5 * px) if took else px, took
    return None


def _work(args):
    sym, kind, start = args
    try:
        all_frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    frames = FR2.regular_hours(all_frames) if kind in ("stock", "etf") else all_frames
    cost = B.CLASS_COST.get(kind, B.COST)
    mid = start + (pd.Timestamp.now() - start) / 2
    codes, rets, drifts, tooks = [], [], [], []
    errs = []
    for p_i, (btf, stf) in enumerate(PAIRS):
        small, big = frames.get(stf), frames.get(btf)
        if small is None or big is None or len(small) < 500 or len(big) < 100:
            continue
        try:
            c = small["Close"].values.astype(float); o = small["Open"].values.astype(float)
            h = small["High"].values.astype(float); l = small["Low"].values.astype(float)
            n = len(c)
            bs = big_series(small, stf, big, btf)
            satr = P._atr(small)
            srsi = IND.rsi_parts(c)[0]
            floor, ceil, cid, recs, _ = EC.coils(small, min_gap=0)
            breaks_up, breaks_dn = {}, {}
            for r in recs:
                if not r["tradeable"] or r["born"] < 60:
                    continue
                if "wick through the ceiling" in str(r["how"]):
                    breaks_up[r["end"]] = r
                elif "wick through the floor" in str(r["how"]):
                    breaks_dn[r["end"]] = r
            hl_at, lh_at = {}, {}
            for ci, j, pr, kd, lab in ST.pivots(small):
                if kd == "low" and lab in ("HL", "EL"):
                    hl_at[ci] = float(pr)
                elif kd == "high" and lab in ("LH", "EH"):
                    lh_at[ci] = float(pr)
            cap = CAP_DAYS * B.BARS_DAY[stf]
            day = small.index.normalize().values if kind in ("stock", "etf") else None
            lr = np.diff(np.log(c), prepend=np.log(c[0]))
            drift = float(np.nanmean(lr[np.isfinite(lr)]))
            state = bs["state"].astype(str); hlab = bs["high_lab"].astype(str); llab = bs["low_lab"].astype(str)
            busy_until = {}                                   # (trigger, loc, side) -> bar the last trade ended
            was_live = {}
            for k in range(61, n - 2):
                a = satr[k] if np.isfinite(satr[k]) and satr[k] > 0 else np.nan
                ba = bs["atr"][k]
                if not (np.isfinite(a) and np.isfinite(ba) and np.isfinite(bs["e12"][k]) and np.isfinite(bs["slope"][k])):
                    continue
                tol = P.SAME_LEVEL_ATR * a
                for s_i, sgn in enumerate((1, -1)):
                    setup = (state[k] == "UP" or hlab[k] == "HH") if sgn > 0 else (state[k] == "DOWN" or llab[k] == "LL")
                    if not setup:
                        was_live[(s_i, 0)] = False
                        continue
                    at_loc = (abs(l[k] - bs["e12"][k]) <= NEAR * ba and bs["slope"][k] > 0) if sgn > 0 else \
                             (abs(h[k] - bs["e12"][k]) <= NEAR * ba and bs["slope"][k] < 0)
                    fired = []                                 # (trigger index, stop)
                    if sgn > 0 and k in breaks_up:
                        fired.append((0, breaks_up[k]["floor"] - tol))
                    if sgn < 0 and k in breaks_dn:
                        fired.append((0, breaks_dn[k]["ceil"] + tol))
                    if sgn > 0 and k in hl_at:
                        fired.append((1, hl_at[k] - tol))
                    if sgn < 0 and k in lh_at:
                        fired.append((1, lh_at[k] + tol))
                    if np.isfinite(srsi[k]) and np.isfinite(srsi[k - 1]):
                        if sgn > 0 and srsi[k - 1] <= 30 < srsi[k]:
                            fired.append((2, float(np.min(l[k - 9:k + 1])) - tol))
                        if sgn < 0 and srsi[k - 1] >= 70 > srsi[k]:
                            fired.append((2, float(np.max(h[k - 9:k + 1])) + tol))
                    if at_loc and not was_live.get((s_i, 0), False):
                        fired.append((3, (float(np.min(l[k - 9:k + 1])) - tol) if sgn > 0 else (float(np.max(h[k - 9:k + 1])) + tol)))
                    was_live[(s_i, 0)] = at_loc
                    if not fired:
                        continue
                    e = k + 1
                    fill = o[e]
                    t = small.index[e]
                    era_i = 0 if t < start else 1 if t < mid else 2
                    for trig_i, stop in fired:
                        if not ((sgn > 0 and stop < fill) or (sgn < 0 and fill < stop)):
                            continue
                        for loc_i in ((0, 1) if at_loc else (1,)):
                            if trig_i == 3 and loc_i == 1:
                                continue
                            key = (trig_i, loc_i, s_i)
                            if busy_until.get(key, -1) >= e:
                                continue
                            ends = []
                            for x_i, (_, mode) in enumerate(EXITS):
                                res = walk(sgn, c, o, h, l, bs, e, fill, stop, n, cap, day, mode)
                                if res is None:
                                    continue
                                xb, px, took = res
                                held = xb + 1 - e
                                codes.append(encode([p_i, trig_i, x_i, loc_i, s_i, era_i]))
                                rets.append(sgn * (px / fill - 1) - cost)
                                drifts.append(sgn * (np.exp(drift * held) - 1) - cost)
                                tooks.append(1 if took else 0)
                                ends.append(xb)
                            if ends:
                                busy_until[key] = max(ends)
        except Exception as ex:
            errs.append("%s %s %s/%s: %s" % (kind, sym, btf, stf, ex))
    if not codes:
        return None, errs
    return (np.asarray(codes, dtype=np.int32), np.asarray(rets, dtype=np.float32),
            np.asarray(drifts, dtype=np.float32), np.asarray(tooks, dtype=np.int8)), errs


def main():
    procs, log = max(1, os.cpu_count() or 4), None
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            log = sys.argv[i + 1]
            sys.stdout = sys.stderr = open(log, "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * B.YEARS)
    names = R._by_size([(s_, k_) for s_, k_ in B.universe() if k_ != "forex"])
    R.quiet_workers()
    parts, errs, done = [], [], 0
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for part, err in ex.map(_work, [(s_, k_, start) for s_, k_ in names], chunksize=1):
            done += 1
            errs += err or []
            if part is not None:
                parts.append(part)
            if done % 50 == 0 or done == len(names):
                print("  %d/%d names  (%.0fs)" % (done, len(names), time.time() - t0), flush=True)
    for e_ in errs[:20]:
        print("  ERR " + e_)
    code = np.concatenate([p[0] for p in parts]).astype(np.int64)
    f = pd.DataFrame({"ret": np.concatenate([p[1] for p in parts]).astype(float),
                      "drift": np.concatenate([p[2] for p in parts]).astype(float),
                      "took": np.concatenate([p[3] for p in parts]).astype(float)})
    rem = code
    for (name, vals), size in reversed(list(zip(DIMS, SIZES))):
        f[name] = (rem % size).astype(np.int16)
        rem = rem // size
    f["won"] = (f.ret > 0).astype(float)
    f["edge"] = f.ret - f.drift
    print("  %d trade rows, folding  (%.0fs)" % (len(f), time.time() - t0), flush=True)
    names_of = dict(DIMS)
    trades = {}
    for side_name, s1 in (("both sides", f), ("long", f[f.side == 0]), ("short", f[f.side == 1])):
        for keys in (["pair", "trigger", "exit", "loc"], ["pair", "trigger", "exit", "loc", "era"]):
            agg = s1.groupby(keys).agg(n=("ret", "size"), mean=("ret", "mean"), median=("ret", "median"),
                                       edge=("edge", "mean"), won=("won", "mean"), reached=("took", "mean"))
            for kk, row in agg.iterrows():
                if row["n"] < 30:
                    continue
                lab = [names_of[c_][int(v)] for c_, v in zip(keys, kk)]
                era = lab[4] if len(keys) == 5 else "all"
                trades[" | ".join(lab[:4] + [side_name, era])] = dict(
                    n=int(row["n"]), mean=float(row["mean"]), median=float(row["median"]), edge=float(row["edge"]),
                    won=float(row["won"]), reached=float(row["reached"]))
    res = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names),
                         pairs=[names_of["pair"][i] for i in range(len(PAIRS))], triggers=TRIGGERS,
                         exits=[x[0] for x in EXITS], locs=LOCS, sides=["both sides"] + SIDES, eras=["all"] + ERAS,
                         near=NEAR, rows=int(len(f)),
                         hours="stocks and ETFs on regular-hours bars; crypto and futures all hours",
                         seconds=int(time.time() - t0)),
               trades=trades)
    json.dump(res, open(OUT, "w"))
    print("\n  THE TCG PLAYBOOK, FAST CHART AS TIMING  %d names  (%.0fs)" % (len(names), time.time() - t0))
    for pair in res["meta"]["pairs"]:
        for ex_name, _ in EXITS:
            print("\n   %s | %s   (both sides: avg / middle / edge  n  won   eras avg/middle)" % (pair, ex_name))
            for trig in TRIGGERS:
                for loc in LOCS:
                    t = trades.get(" | ".join([pair, trig, ex_name, loc, "both sides", "all"]))
                    if not t:
                        continue
                    eras = "  ".join(("%+.2f/%+.2f" % (100 * e["mean"], 100 * e["median"])) if e else "   -   "
                                     for e in (trades.get(" | ".join([pair, trig, ex_name, loc, "both sides", er])) for er in ERAS))
                    print("     %-26s %-24s %+6.2f / %+6.2f / %+6.2f  n%-7d %3.0f%%  %s" % (
                        trig, loc, 100 * t["mean"], 100 * t["median"], 100 * t["edge"], t["n"], 100 * t["won"], eras))
    if log:
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
