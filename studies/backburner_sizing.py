"""backburner_sizing.py -- HOW BIG AND HOW MANY: the backburner account's sizing, tested wide (2026-09-23, his words: "Test as
broad and wide as you need", after backburner_account showed only 29-40% of the money is ever in a trade).

The account of backburner_account.py (cash only, every position marked at every day's close, 2022-09-06 on, 20 runs), and
ONE thing changed per row from the base (5 slots, the page's buys, same-day signals in random order):
  1. SLOTS        1, 2, 3, 4, 5, 6, 8, 10 at once -- each gets free cash / free slots
  2. RISK SIZING  no slots: each trade sized so the wide disaster line costs 1%, 2% or 3% of the account (Murphy's 1-2%
                  per trade, TCG's "size backed out of the stop"), capped at 25% or 50% of the account a position and at the
                  cash there is
  3. ALL IN AT 30 the page's trade with ONE buy (no order waiting at 20 / 25), the whole slot at the touch of 30
  4. FASTEST FIRST when more signals come in a day than there is room for, the fastest dips get the slots (#44f: the
                  fastest quarter of dips made +1.44% a trade against about +0.9%)

    pythonw studies/backburner_sizing.py --procs 8 --log logs/backburner_sizing.log
Writes validation/backburner_sizing.json
"""
import concurrent.futures as cf
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
import eq_freeride2 as FR2        # noqa: E402
import panel as P                 # noqa: E402
from backburner_account import START, _naive, stats  # noqa: E402

OUT = os.path.join("validation", "backburner_sizing.json")
RUNS = 20


def _trades(sym, kind, v, h, hix, atr):
    out = []
    for r in PB.trades_for(sym, kind, v):
        t_in = hix[r["k"]]
        if t_in < START:
            continue
        dol = r.get("dollars")
        if dol:
            lv = r.get("fill_lv") or [30]
            filled = sum(float(dol.get(x, dol.get(str(x), 0.0))) for x in lv) / sum(float(x) for x in dol.values())
        else:
            filled = len(r["fills"]) / float(1 + len(v.get("bids", [20])))
        k = r["k"]
        top_i = max(0, k - 50) + int(np.argmax(h[max(0, k - 50):k])) if k > 1 else k
        a = atr[k - 1] if k >= 1 and np.isfinite(atr[k - 1]) and atr[k - 1] > 0 else np.nan
        speed = (h[top_i] - r["fills"][0]) / a / max(k - top_i, 1) if np.isfinite(a) else 0.0
        cost = PB.COST.get(kind, 0.05)
        c_ = cost * (1.5 if r["half_at"] is not None else 1.0)
        gross = r["entry"] * (1 + (r["pct"] + c_) / 100.0)        # the average sale price per share, before cost
        lvs = r.get("fill_lv") or [30, 20][:len(r["fills"])]
        base = float(dol.get(30, dol.get("30", 1.0))) if dol else 1.0
        legs = []
        for lv_, fb_, fx_ in zip(lvs, r["fill_bars"], r["fills"]):
            mult = (float(dol.get(lv_, dol.get(str(lv_), 0.0))) / base) if dol else 1.0
            legs.append((hix[min(fb_, len(hix) - 1)], mult, 100.0 * (gross / fx_ - 1) - c_, float(fx_)))
        out.append(dict(sym=sym, kind=kind, t_in=t_in, t_out=hix[min(r["end"], len(hix) - 1)], legs=legs,
                        t_win=hix[min(k + 12, len(hix) - 1)], pct=float(r["pct"]), entry=float(r["entry"]),
                        filled=float(min(1.0, filled)), risk=float(r["risk_pct"]), speed=float(speed),
                        first=float((float(dol.get(30, dol.get("30", 0.0))) / sum(float(x) for x in dol.values())) if dol
                                    else 1.0 / float(1 + len(v.get("bids", [20]))))))
    return out


def _work(args):
    sym, kind = args
    try:
        fr = {k_: v for k_, v in S.frames_for(sym, kind).items() if k_ in ("1h", "1d")}
        if kind in ("stock", "etf"):
            fr = FR2.regular_hours(fr)
        h1, d = fr["1h"], fr["1d"]
        hix = _naive(h1.index)
        h = h1["High"].values.astype(float)
        atr = P._atr(h1)
        closes = pd.Series(d["Close"].values.astype(float), index=_naive(d.index).normalize())
        closes = closes[~closes.index.duplicated(keep="last")]
        page = dict(PB.STOP, **(PB.CRYPTO_BUYS if kind == "crypto" else {}))
        one = dict(page, bids=[])
        one.pop("dollars", None)
        return _trades(sym, kind, page, h, hix, atr), _trades(sym, kind, one, h, hix, atr), closes, sym, kind
    except Exception:
        return [], [], None, sym, kind


def account(trades, closes, days, seed, slots=5, risk=None, cap=0.25, fastest=False, on_top=False):
    """Every buy, sale and release of held-back money handled IN TIME ORDER (a slot freed by a 3pm sale is not there for
    a 10am buy the same day -- the first version processed a day's exits before its entries), and the account marked at
    every day's close. Signals at the same hour: random order, or fastest dip first."""
    import heapq
    rng = np.random.default_rng(seed)
    key = (lambda i: (trades[i]["t_in"], -trades[i]["speed"])) if fastest else (lambda i: (trades[i]["t_in"], rng.random()))
    order = sorted(range(len(trades)), key=key)
    cash, open_, pend = 1.0, {}, []           # pend: heap of (time, seq, kind, id) for exits and releases
    held = {}
    seq = 0
    curve, taken, dep = [], 0, []
    last_eq = 1.0
    oi = 0
    ends = [d + pd.Timedelta(days=1) for d in days]

    def settle(until):
        nonlocal cash
        while pend and pend[0][0] < until:
            _t, _s, kind_, pid = heapq.heappop(pend)
            if kind_ == "exit":
                p = open_.pop(pid)
                if "legs_in" in p:
                    cash += sum(d_ * (1 + r_ / 100.0) for d_, r_, _px in p["legs_in"])
                else:
                    cash += p["dollars"] * (1 + p["pct"] / 100.0)
            elif kind_ == "leg":
                sid, want, r_, px_ = pid
                if sid in open_ and cash > 0:
                    got_ = min(want, cash)
                    cash -= got_
                    open_[sid]["legs_in"].append((got_, r_, px_))
            else:
                cash += held.pop(pid)

    for di, day in enumerate(days):
        while oi < len(order) and trades[order[oi]]["t_in"] < ends[di]:
            tr = trades[order[oi]]
            oi += 1
            settle(tr["t_in"])
            if risk is None:
                if len(open_) >= slots:
                    continue
                per = cash / (slots - len(open_))
            else:
                per = min(last_eq * risk / max(tr["risk"] / 100.0, 1e-6), last_eq * cap, cash)
            if per <= 0:
                continue
            if on_top:
                # 5. the FULL slot goes in at 30. Each later buy the page makes is placed AT ITS OWN TIME, in the same
                # proportion to the first, and ONLY with cash that is free at that moment (the first version sized it all
                # at the first buy, knowing whether the later buys would fill -- which you cannot know). Nothing borrowed.
                seq += 1
                l0 = tr["legs"][0]
                open_[seq] = dict(tr, legs_in=[(per, l0[2], l0[3])])
                cash -= per
                heapq.heappush(pend, (tr["t_out"], seq, "exit", seq))
                for lg in tr["legs"][1:]:
                    heapq.heappush(pend, (lg[0], seq, "leg", (seq, per * lg[1], lg[2], lg[3])))
                taken += 1
                continue
            else:
                inv = per * tr["filled"]
            cash -= per
            seq += 1
            open_[seq] = dict(tr, dollars=inv)
            heapq.heappush(pend, (tr["t_out"], seq, "exit", seq))
            if per - inv > 0:
                held[seq] = per - inv
                heapq.heappush(pend, (min(tr["t_win"], tr["t_out"]), seq, "release", seq))
            taken += 1
        settle(ends[di])
        inv_val = 0.0
        for p in open_.values():
            c = closes.get((p["kind"], p["sym"]))
            px = c.asof(day) if c is not None and len(c) else np.nan
            if "legs_in" in p:
                inv_val += sum(d_ * (px / lpx if np.isfinite(px) and lpx > 0 else 1.0) for d_, _r, lpx in p["legs_in"])
            else:
                inv_val += p["dollars"] * px / p["entry"] if np.isfinite(px) and p["entry"] > 0 else p["dollars"]
        eq = cash + sum(held.values()) + inv_val
        curve.append(eq)
        dep.append(inv_val / eq if eq > 0 else 0.0)
        last_eq = eq
    return np.array(curve), taken, float(np.mean(dep)), float(np.max(dep))


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
    page, one, closes = [], [], {}
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for a_, b_, c_, sym, kind in ex.map(_work, names, chunksize=2):
            page += a_
            one += b_
            if c_ is not None:
                closes[(kind, sym)] = c_
    end = max(t["t_out"] for t in page).normalize()
    days = pd.date_range(START, end, freq="D")
    yrs = (days[-1] - days[0]).days / 365.25
    print("\n  HOW BIG AND HOW MANY: %d trades (%d with one buy), %.1f years, cash, marked daily, %d runs  (%.0fs)\n" % (
        len(page), len(one), yrs, RUNS, time.time() - t0))
    print("    %-52s %8s %13s %9s %9s %9s %9s   %s" % ("", "a year", "10%-90%", "worst dip", "deployed", "max in",
                                                      "trades/yr", "each year"))
    print("    %-52s %+7.1f%% %13s %+8.1f%%" % ("SPY bought and held (same days)", 18.5, "", -19.0))
    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), trades=len(page), runs=RUNS), table={})
    rows = [("1. SLOTS: %d at once" % n_, page, dict(slots=n_)) for n_ in (1, 2, 3, 4, 5, 6, 8, 10)]
    rows += [("2. RISK: %d%% of the account at the disaster line, cap %d%%" % (int(r_ * 100), int(c_ * 100)), page,
              dict(risk=r_, cap=c_)) for r_ in (0.01, 0.02, 0.03) for c_ in (0.25, 0.5)]
    rows += [("3. ALL IN AT 30 (one buy), %d slots" % n_, one, dict(slots=n_)) for n_ in (3, 5, 10)]
    rows += [("4. FASTEST DIPS FIRST, %d slots" % n_, page, dict(slots=n_, fastest=True)) for n_ in (3, 5, 10)]
    rows += [("5. FULL SLOT AT 30, LATER BUYS ON TOP, %d slots" % n_, page, dict(slots=n_, on_top=True)) for n_ in (3, 5, 8, 10)]
    last_group = None
    for lab, tr, kw in rows:
        if lab[:2] != last_group:
            print()
            last_group = lab[:2]
        res = [account(tr, closes, days, s_, **kw) for s_ in range(RUNS)]
        st_ = [stats(r[0], days) for r in res]
        ann = np.array([x["a_year"] for x in st_]); dips = np.array([x["dip"] for x in st_])
        mid = int(np.argsort(ann)[len(ann) // 2])
        d = dict(a_year=float(np.median(ann)), p10=float(np.percentile(ann, 10)), p90=float(np.percentile(ann, 90)),
                 dip=float(np.median(dips)), deployed=float(np.mean([r[2] for r in res])),
                 max_in=float(np.max([r[3] for r in res])), trades_a_year=float(np.mean([r[1] for r in res]) / yrs),
                 years=st_[mid]["years"])
        out["table"][lab] = d
        print("    %-52s %+7.1f%% %+5.1f/%+5.1f%% %+8.1f%% %8.0f%% %8.0f%% %9.0f   %s" % (
            lab, 100 * d["a_year"], 100 * d["p10"], 100 * d["p90"], 100 * d["dip"], 100 * d["deployed"],
            100 * d["max_in"], d["trades_a_year"], "  ".join("%d %+.0f%%" % (k, 100 * v) for k, v in d["years"].items())))
    print("\n  deployed = average share of the account in positions; max in = the most it ever had in. Cash only, no leverage.")
    json.dump(out, io.open(OUT, "w", encoding="utf-8"), indent=1)
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
