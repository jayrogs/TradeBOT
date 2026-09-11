"""eq_playbook2.py -- the TCG playbook, version 2: their trade, not a machine gun (2026-09-11).

Version 1 (eq_playbook.py, CLAUDE.md #26i) took a trade on EVERY 5m pivot while the 1h leaned up (1.65 million of them)
with stops smaller than the cost (ES futures: cost = 80% of the middle 5m stop). That tested costs, not the trade.
Their trade (TCG_METHOD.md #9, from three years of #swingtrade): ONE position per bigger-chart higher low, "That is
either the weekly higher low or I am wrong", a partial to get risk free, the runner walked up under higher lows.

What changes here:
  ONE IDEA AT A TIME     per chart pair and side: after a trade, no new entry until the big chart confirms a NEW higher
                         low (short: lower high) -- the next idea. Big-chart pivots only confirm on closed big bars.
  THE STOP HAS ROOM      the stop is the small structure's stop, pushed further away if needed so the risk is at least
                         FLOOR x one normal big bar: floors 0 (their tight stop), 0.5 and 1.0
  THE SETUP              the big chart is in an uptrend (the pivots); the pullback reached its 12 EMA (a small bar's low
                         within half a big normal bar of it), the EMA rising. Only while the pullback is live: the setup
                         ends when a new big higher high confirms.
  TRIGGERS               the first, per idea, of: a small EQ breaking our way; a small higher low confirming; and "no
                         trigger" (the next open once price reaches the 12 EMA) as the control
  EXITS                  half at big RSI 70 or 2x the risk, stop to breakeven, runner walked up under each new big higher
                         low; the same with the runner out on a close through the big 12 EMA; all out at 2x the risk
Results split by market (stocks, ETFs, crypto, futures). Costs out. 30-day cap. Stocks and ETFs on regular hours.

    pythonw studies/eq_playbook2.py --procs 20 --log logs/eq_playbook2.log
Writes validation/eq_playbook2.json
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
import eq_coil as EC              # noqa: E402
import eq_freeride2 as FR2        # noqa: E402
import eq_playbook as PB          # noqa: E402

OUT = os.path.join("validation", "eq_playbook2.json")
PAIRS = PB.PAIRS
NEAR = 0.5
FLOORS = [0.0, 0.5, 1.0]
TRIGGERS = ["small EQ breaks our way", "small higher low confirms", "no trigger (next open at the 12 EMA)"]
EXITS = PB.EXITS
KINDS = ["stock", "etf", "crypto", "futures"]
SIDES = ["long", "short"]
ERAS = ["before", "first", "second"]
DIMS = [("pair", ["%s idea, %s timing" % p for p in PAIRS]), ("trigger", TRIGGERS), ("floor", [str(x) for x in FLOORS]),
        ("exit", [x[0] for x in EXITS]), ("kind", KINDS), ("side", SIDES), ("era", ERAS)]
SIZES = [len(v) for _, v in DIMS]


def encode(vals):
    code = 0
    for v, size in zip(vals, SIZES):
        code = code * size + v
    return code


def _work(args):
    sym, kind, start = args
    try:
        all_frames = B.frames_for(sym, kind)
    except Exception as ex:
        return None, ["%s %s: %s" % (kind, sym, ex)]
    frames = FR2.regular_hours(all_frames) if kind in ("stock", "etf") else all_frames
    cost = B.CLASS_COST.get(kind, B.COST)
    kind_i = KINDS.index(kind) if kind in KINDS else 0
    mid = start + (pd.Timestamp.now() - start) / 2
    codes, rets, drifts, tooks, risks = [], [], [], [], []
    errs = []
    for p_i, (btf, stf) in enumerate(PAIRS):
        small, big = frames.get(stf), frames.get(btf)
        if small is None or big is None or len(small) < 500 or len(big) < 100:
            continue
        try:
            c = small["Close"].values.astype(float); o = small["Open"].values.astype(float)
            h = small["High"].values.astype(float); l = small["Low"].values.astype(float)
            n = len(c)
            bs = PB.big_series(small, stf, big, btf)
            satr = P._atr(small)
            floor_, ceil_, cid, recs, _ = EC.coils(small, min_gap=0)
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
            cap = PB.CAP_DAYS * B.BARS_DAY[stf]
            day = small.index.normalize().values if kind in ("stock", "etf") else None
            lr = np.diff(np.log(c), prepend=np.log(c[0]))
            drift = float(np.nanmean(lr[np.isfinite(lr)]))
            state = bs["state"].astype(str)
            big_hl, big_lh = bs["hl"], bs["lh"]
            for s_i, sgn in enumerate((1, -1)):
                # an "idea" is identified by the big chart's last confirmed higher low (long) / lower high (short);
                # once a trigger has been traded for an idea, that trigger waits for the next idea
                done_for = {t_i: None for t_i in range(len(TRIGGERS))}
                busy_until = {t_i: -1 for t_i in range(len(TRIGGERS))}
                reached = None                        # the idea for which the pullback has reached the 12 EMA
                for k in range(61, n - 2):
                    ba = bs["atr"][k]
                    a = satr[k]
                    if not (np.isfinite(ba) and np.isfinite(a) and np.isfinite(bs["e12"][k]) and np.isfinite(bs["slope"][k])):
                        continue
                    idea = big_hl[k] if sgn > 0 else big_lh[k]
                    trend_ok = state[k] == ("UP" if sgn > 0 else "DOWN")
                    if not trend_ok or not np.isfinite(idea):
                        reached = None
                        continue
                    at_loc = (abs(l[k] - bs["e12"][k]) <= NEAR * ba and bs["slope"][k] > 0) if sgn > 0 else \
                             (abs(h[k] - bs["e12"][k]) <= NEAR * ba and bs["slope"][k] < 0)
                    first_touch = False
                    if at_loc and reached != idea:
                        reached = idea
                        first_touch = True
                    if reached != idea:
                        continue                      # the pullback has not come to the 12 EMA for this idea yet
                    tol = P.SAME_LEVEL_ATR * a
                    fired = []
                    if sgn > 0 and k in breaks_up:
                        fired.append((0, breaks_up[k]["floor"] - tol))
                    if sgn < 0 and k in breaks_dn:
                        fired.append((0, breaks_dn[k]["ceil"] + tol))
                    if sgn > 0 and k in hl_at:
                        fired.append((1, hl_at[k] - tol))
                    if sgn < 0 and k in lh_at:
                        fired.append((1, lh_at[k] + tol))
                    if first_touch:
                        lo10 = float(np.min(l[k - 9:k + 1])); hi10 = float(np.max(h[k - 9:k + 1]))
                        fired.append((2, (lo10 - tol) if sgn > 0 else (hi10 + tol)))
                    if not fired:
                        continue
                    e = k + 1
                    fill = o[e]
                    t = small.index[e]
                    era_i = 0 if t < start else 1 if t < mid else 2
                    for t_i, stop0 in fired:
                        if done_for[t_i] == idea or busy_until[t_i] >= e:
                            continue
                        if not ((sgn > 0 and stop0 < fill) or (sgn < 0 and fill < stop0)):
                            continue
                        done_for[t_i] = idea
                        ends = []
                        for f_i, fl in enumerate(FLOORS):
                            min_risk = fl * ba
                            stop = min(stop0, fill - min_risk) if sgn > 0 else max(stop0, fill + min_risk)
                            for x_i, (_, mode) in enumerate(EXITS):
                                res = PB.walk(sgn, c, o, h, l, bs, e, fill, stop, n, cap, day, mode)
                                if res is None:
                                    continue
                                xb, px, took = res
                                held = xb + 1 - e
                                codes.append(encode([p_i, t_i, f_i, x_i, kind_i, s_i, era_i]))
                                rets.append(sgn * (px / fill - 1) - cost)
                                drifts.append(sgn * (np.exp(drift * held) - 1) - cost)
                                tooks.append(1 if took else 0)
                                risks.append(abs(fill - stop) / fill)
                                ends.append(xb)
                        if ends:
                            busy_until[t_i] = max(ends)
        except Exception as ex:
            errs.append("%s %s %s/%s: %s" % (kind, sym, btf, stf, ex))
    if not codes:
        return None, errs
    return (np.asarray(codes, dtype=np.int32), np.asarray(rets, dtype=np.float32), np.asarray(drifts, dtype=np.float32),
            np.asarray(tooks, dtype=np.int8), np.asarray(risks, dtype=np.float32)), errs


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
                      "took": np.concatenate([p[3] for p in parts]).astype(float),
                      "risk": np.concatenate([p[4] for p in parts]).astype(float)})
    rem = code
    for (name, vals), size in reversed(list(zip(DIMS, SIZES))):
        f[name] = (rem % size).astype(np.int16)
        rem = rem // size
    f["won"] = (f.ret > 0).astype(float)
    f["edge"] = f.ret - f.drift
    print("  %d trade rows, folding  (%.0fs)" % (len(f), time.time() - t0), flush=True)
    names_of = dict(DIMS)
    trades = {}
    for kind_name, s1 in [("every market", f)] + [(KINDS[i], f[f.kind == i]) for i in range(len(KINDS))]:
        for keys in (["pair", "trigger", "floor", "exit"], ["pair", "trigger", "floor", "exit", "era"]):
            agg = s1.groupby(keys).agg(n=("ret", "size"), mean=("ret", "mean"), median=("ret", "median"),
                                       edge=("edge", "mean"), won=("won", "mean"), reached=("took", "mean"),
                                       risk=("risk", "median"))
            for kk, row in agg.iterrows():
                if row["n"] < 30:
                    continue
                lab = [names_of[c_][int(v)] for c_, v in zip(keys, kk)]
                era = lab[4] if len(keys) == 5 else "all"
                trades[" | ".join(lab[:4] + [kind_name, era])] = dict(
                    n=int(row["n"]), mean=float(row["mean"]), median=float(row["median"]), edge=float(row["edge"]),
                    won=float(row["won"]), reached=float(row["reached"]), risk=float(row["risk"]))
    res = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names),
                         pairs=names_of["pair"], triggers=TRIGGERS, floors=[str(x) for x in FLOORS],
                         exits=[x[0] for x in EXITS], kinds=["every market"] + KINDS, eras=["all"] + ERAS, near=NEAR,
                         rows=int(len(f)), seconds=int(time.time() - t0)),
               trades=trades)
    json.dump(res, open(OUT, "w"))
    print("\n  TCG PLAYBOOK v2: ONE IDEA AT A TIME, STOP WITH ROOM  %d names  (%.0fs)" % (len(names), time.time() - t0))
    ex0 = EXITS[0][0]
    for pair in names_of["pair"]:
        print("\n   %s | %s   (avg / middle / edge  n  won  middle stop   eras avg/middle)" % (pair, ex0))
        for kind_name in ["every market"] + KINDS:
            for trig in TRIGGERS:
                for fl in [str(x) for x in FLOORS]:
                    t = trades.get(" | ".join([pair, trig, fl, ex0, kind_name, "all"]))
                    if not t:
                        continue
                    eras = "  ".join(("%+.2f/%+.2f" % (100 * e["mean"], 100 * e["median"])) if e else "   -   "
                                     for e in (trades.get(" | ".join([pair, trig, fl, ex0, kind_name, er])) for er in ERAS))
                    print("     %-12s %-38s floor %-3s %+6.2f / %+6.2f / %+6.2f  n%-7d %3.0f%%  %.2f%%  %s" % (
                        kind_name, trig, fl, 100 * t["mean"], 100 * t["median"], 100 * t["edge"], t["n"], 100 * t["won"],
                        100 * t["risk"], eras))
    if log:
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
