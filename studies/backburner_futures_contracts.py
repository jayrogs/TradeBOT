"""backburner_futures_contracts.py -- THE FUTURES BACKBURNER IN REAL CONTRACTS (2026-09-26, his words: "futures is leveraged
on its own, so no need to 2x or whatever").

Every account test until now bought futures like a stock: a $20k bucket bought $20k of oil. A real account buys WHOLE
CONTRACTS and posts margin: one oil contract is 1,000 barrels (~$92k at $92), a micro is 100 barrels. So what a futures
trade makes or loses per bucket depends on how many contracts the bucket controls.

The page's own trades (pics_backburner_tcg.trades_for) and the page's account (backburner_sizing, on_top: 5 buckets, the
whole bucket at RSI 30, the later buys on top from spare cash, cash for stocks and crypto, marked at every day's close),
$100,000 to start, 20 runs. ONE thing changes, row by row: how futures are sized.
    CONTROL      futures bought like stocks (what every earlier table did)
    x N          each futures trade buys the whole number of contracts whose value is closest under N times its bucket
                 (micro contracts where they exist, else standard). x1 = no borrowing beyond the bucket.
    standard     the same with standard contracts only (micros not allowed)
    margin max   as many contracts as the bucket covers at the exchange's initial margin -- the most a broker lets you hold
A trade the bucket cannot buy even one contract of is SKIPPED (counted). The bucket's cash stays with the position as its
margin; a loss bigger than the bucket comes out of the rest of the account. The account is marked every day; if it ever
reaches zero it is BLOWN UP and stays at zero.

Contract sizes are CME / ICE specs (dollars per 1.00 of the quoted price). MARGINS ARE APPROXIMATE (a share of the
contract's value, typical of 2025-26 exchange margins); they are only used for the "margin max" row.

    pythonw studies/backburner_futures_contracts.py --procs 8 --log logs/backburner_futures_contracts.log
Writes validation/backburner_futures_contracts.json
"""
import concurrent.futures as cf
import heapq
import io
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as S      # noqa: E402
import trend_ride as R            # noqa: E402
import pics_backburner_tcg as PB  # noqa: E402
import backburner_sizing as SZ    # noqa: E402
from backburner_account import START, stats  # noqa: E402

OUT = os.path.join("validation", "backburner_futures_contracts.json")
RUNS = 20
START_USD = 100_000.0

# symbol: (dollars per 1.00 of price, standard; micro or None; approximate initial margin as a share of the value)
SPEC = {
    "CL_F": (1000, 100, 0.07), "BZ_F": (1000, None, 0.07), "NG_F": (10000, 1000, 0.15), "HO_F": (42000, None, 0.07),
    "RB_F": (42000, None, 0.07),
    "GC_F": (100, 10, 0.06), "MGC_F": (10, 10, 0.06), "SI_F": (5000, 1000, 0.08), "SIL_F": (1000, 1000, 0.08),
    "HG_F": (25000, 2500, 0.06), "PL_F": (50, None, 0.07),
    "ZC_F": (50, 5, 0.05), "ZS_F": (50, 5, 0.05), "ZW_F": (50, 5, 0.06), "KE_F": (50, None, 0.06),
    "ZL_F": (600, 60, 0.06), "ZM_F": (100, 10, 0.06),
    "CC_F": (10, None, 0.12), "KC_F": (375, None, 0.09), "SB_F": (1120, None, 0.07), "CT_F": (500, None, 0.06),
    "LE_F": (400, None, 0.04), "GF_F": (500, None, 0.04), "HE_F": (400, None, 0.05),
}


def account(trades, closes, days, seed, lev=None, micro=True, margin_max=False, slots=5):
    """backburner_sizing.account's on_top path, dollars from $100k, with futures in contracts. Returns
    (curve in dollars, trades taken, futures taken, futures skipped, worst futures trade as % of the account, blown)."""
    rng = np.random.default_rng(seed)
    order = sorted(range(len(trades)), key=lambda i: (trades[i]["t_in"], rng.random()))
    cash, open_, pend, seq = START_USD, {}, [], 0
    curve, taken, f_taken, f_skip, worst, blown = [], 0, 0, 0, 0.0, False
    oi = 0
    ends = [d + pd.Timedelta(days=1) for d in days]
    last_eq = START_USD

    def settle(until):
        nonlocal cash, worst
        while pend and pend[0][0] < until:
            _t, _s, kind_, pid = heapq.heappop(pend)
            if kind_ == "exit":
                p = open_.pop(pid)
                pnl = sum(d_ * p["eff"] * r_ / 100.0 for d_, r_, _px in p["legs_in"])
                cash += sum(d_ for d_, _r, _px in p["legs_in"]) + pnl
                if p["kind"] == "futures" and last_eq > 0:
                    worst = min(worst, pnl / last_eq)
            else:
                sid, want, r_, px_ = pid
                if sid in open_ and cash > 0:
                    got_ = min(want, cash)
                    cash -= got_
                    open_[sid]["legs_in"].append((got_, r_, px_))

    for di, day in enumerate(days):
        while not blown and oi < len(order) and trades[order[oi]]["t_in"] < ends[di]:
            tr = trades[order[oi]]
            oi += 1
            settle(tr["t_in"])
            if len(open_) >= slots:
                continue
            per = cash / (slots - len(open_))
            if per <= 0:
                continue
            eff = 1.0
            if tr["kind"] == "futures" and lev != "cash":
                std, mic, mrate = SPEC[tr["sym"]]
                mult = (mic or std) if micro else std
                if not micro and std == 10 and tr["sym"] == "MGC_F":
                    f_skip += 1          # the micro gold contract is not a standard contract
                    continue
                one = tr["legs"][0][3] * mult           # the value of one contract at the buy
                if margin_max:
                    n = int(per // (one * mrate))
                else:
                    n = int((lev * per) // one)
                if n < 1:
                    f_skip += 1
                    continue
                eff = n * one / per
                f_taken += 1
            seq += 1
            l0 = tr["legs"][0]
            open_[seq] = dict(tr, legs_in=[(per, l0[2], l0[3])], eff=eff)
            cash -= per
            heapq.heappush(pend, (tr["t_out"], seq, "exit", seq))
            for lg in tr["legs"][1:]:
                heapq.heappush(pend, (lg[0], seq, "leg", (seq, per * lg[1], lg[2], lg[3])))
            taken += 1
        settle(ends[di])
        val = cash
        for p in open_.values():
            c = closes.get((p["kind"], p["sym"]))
            px = c.asof(day) if c is not None and len(c) else np.nan
            for d_, _r, lpx in p["legs_in"]:
                val += d_ * (1 + p["eff"] * (px / lpx - 1)) if np.isfinite(px) and lpx > 0 else d_
        if blown or val <= 0:
            blown, val = True, 0.0
        curve.append(val)
        last_eq = val
    return np.array(curve), taken, f_taken, f_skip, worst, blown


def _row(args):
    lab, sel, kw, trades, closes, days = args
    tr = [t for t in trades if sel == "all" or t["kind"] == "futures"]
    res = [account(tr, closes, days, s_, **kw) for s_ in range(RUNS)]
    yrs = (days[-1] - days[0]).days / 365.25
    ann, dips = [], []
    for r in res:
        c = r[0]
        if c[-1] <= 0:
            ann.append(-1.0); dips.append(-1.0)
        else:
            st = stats(c / START_USD, days)
            ann.append(st["a_year"]); dips.append(st["dip"])
    ann, dips = np.array(ann), np.array(dips)
    mid = int(np.argsort(ann)[len(ann) // 2])
    return lab, dict(a_year=float(np.median(ann)), p10=float(np.percentile(ann, 10)), p90=float(np.percentile(ann, 90)),
                     dip=float(np.median(dips)), worst_dip=float(dips.min()),
                     fut_taken_a_year=float(np.mean([r[2] for r in res]) / yrs),
                     fut_skipped_a_year=float(np.mean([r[3] for r in res]) / yrs),
                     worst_fut_trade=float(min(r[4] for r in res)), blown=int(sum(r[5] for r in res)),
                     end_usd=float(np.median([r[0][-1] for r in res])),
                     years=(stats(res[mid][0] / START_USD, days)["years"] if res[mid][0][-1] > 0 else {}))


def main():
    procs, log = 8, None
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            log = sys.argv[i + 1]
            sys.stdout = sys.stderr = io.open(log, "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    names = R._by_size([(s_, k_) for s_, k_ in S.universe()
                        if (k_ in ("stock", "etf", "crypto") or (k_ == "futures" and s_ in PB.COMMODITY_FUTURES))
                        and s_ not in PB.T.SUSPECT])
    R.quiet_workers()
    trades, closes = [], {}
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for a_, _b, c_, sym, kind in ex.map(SZ._work, names, chunksize=2):
            trades += a_
            if c_ is not None:
                closes[(kind, sym)] = c_
    end = max(t["t_out"] for t in trades).normalize()
    days = pd.date_range(START, end, freq="D")
    nf = sum(1 for t in trades if t["kind"] == "futures")
    print("\n  THE FUTURES BACKBURNER IN REAL CONTRACTS: %d trades (%d futures), %s .. %s, $100k, 5 buckets, 20 runs  (%.0fs)\n"
          % (len(trades), nf, days[0].date(), days[-1].date(), time.time() - t0))
    rows = []
    for grp, sel in (("WHOLE ACCOUNT", "all"), ("FUTURES ONLY", "futures")):
        rows.append(("%s | futures bought like stocks (control)" % grp, sel, dict(lev="cash")))
        for L in (1, 2, 3, 5, 10):
            rows.append(("%s | micro first, contracts worth up to %dx the bucket" % (grp, L), sel, dict(lev=L, micro=True)))
        for L in (1, 3, 5, 10):
            rows.append(("%s | standard only, up to %dx the bucket" % (grp, L), sel, dict(lev=L, micro=False)))
        rows.append(("%s | micro first, as many as the margin allows" % grp, sel, dict(margin_max=True, micro=True)))
    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), trades=len(trades), futures=nf,
                         start=str(days[0].date()), end=str(days[-1].date()), runs=RUNS, start_usd=START_USD,
                         spec=SPEC), table={})
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for lab, d in ex.map(_row, [(l_, s_, k_, trades, closes, days) for l_, s_, k_ in rows]):
            out["table"][lab] = d
    print("    %-66s %8s %13s %9s %9s %8s %8s %9s %6s" % ("", "a year", "10%-90%", "dip", "worst", "fut/yr", "skip/yr",
                                                        "worst fut", "blown"))
    last = None
    for lab, _s, _k in rows:
        d = out["table"][lab]
        g = lab.split(" | ")[0]
        if g != last:
            print("\n  %s" % g)
            last = g
        print("    %-66s %+7.1f%% %+5.1f/%+5.1f%% %+8.1f%% %+8.1f%% %8.1f %8.1f %+8.1f%% %6d" % (
            lab.split(" | ")[1], 100 * d["a_year"], 100 * d["p10"], 100 * d["p90"], 100 * d["dip"], 100 * d["worst_dip"],
            d["fut_taken_a_year"], d["fut_skipped_a_year"], 100 * d["worst_fut_trade"], d["blown"]))
    print("\n  dip = typical worst drop, marked daily; worst = the worst run's drop; worst fut = the worst single futures trade as")
    print("  a share of the whole account; blown = runs (of 20) that reached zero. Margins approximate.")
    json.dump(out, io.open(OUT, "w", encoding="utf-8"), indent=1)
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
