"""backburner_account.py -- THE WHOLE BACKBURNER AS AN ACCOUNT, EVERY MARKET, MARKED EVERY DAY (2026-09-23).

Everything he picked today is on: the run 10%+ in price, the news / earnings skip on stocks, stocks and commodity futures
buying 30 and 20, crypto pyramiding $10k / $20k / $30k at 30 / 25 / 20 and selling a quarter more 3 normal bars up, the
honest stop check, the rebuilt futures daily. The page's own trades (pics_backburner_tcg.trades_for), nothing tuned here.

THE ACCOUNT: cash only, nothing borrowed. N slots; a new trade takes a free slot and gets free cash / free slots. The slot
is split the way the page buys (stocks and futures half at 30, half waiting at 20; crypto 1/6 at 30, 2/6 at 25, 3/6 at
20). Money for a buy that never fills is only held back until that order is pulled (12 hours at most), then it is free
cash again. Open positions are MARKED AT EVERY DAY'S CLOSE (#37: a drawdown is marked every day or it is not called one).
Signals on the same day are taken in a random order; 20 runs.

THE WINDOW: 2022-09-06 on -- when the futures hourly data starts -- for every row, so the rows compare. SPY bought and
held over the same days, marked the same way.

    pythonw studies/backburner_account.py --procs 8 --log logs/backburner_account.log
Writes validation/backburner_account.json
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

OUT = os.path.join("validation", "backburner_account.json")
START = pd.Timestamp("2022-09-06")
SLOTS = [5, 10, 20]
RUNS = 20


def _naive(ix):
    ix = pd.DatetimeIndex(ix)
    return ix.tz_localize(None) if ix.tz is not None else ix


def _work(args):
    sym, kind = args
    trades, closes = [], None
    try:
        fr = {k_: v for k_, v in S.frames_for(sym, kind).items() if k_ in ("1h", "1d")}
        if kind in ("stock", "etf"):
            fr = FR2.regular_hours(fr)
        h, d = fr["1h"], fr["1d"]
        hix = _naive(h.index)
        closes = pd.Series(d["Close"].values.astype(float), index=_naive(d.index).normalize())
        closes = closes[~closes.index.duplicated(keep="last")]
        for r in PB.trades_for(sym, kind):
            t_in = hix[r["k"]]
            if t_in < START:
                continue
            t_out = hix[min(r["end"], len(hix) - 1)]
            t_win = hix[min(r["k"] + 12, len(hix) - 1)]
            dol = r.get("dollars")
            if dol:
                lv = r.get("fill_lv") or [30]
                filled = sum(float(dol.get(x, dol.get(str(x), 0.0))) for x in lv) / sum(float(v) for v in dol.values())
            else:
                filled = len(r["fills"]) / 2.0
            trades.append(dict(sym=sym, kind=kind, t_in=t_in, t_out=t_out, t_win=t_win, pct=float(r["pct"]),
                               entry=float(r["entry"]), filled=float(min(1.0, filled))))
    except Exception:
        return [], None, sym, kind
    return trades, closes, sym, kind


def account(trades, closes, days, slots, seed):
    """Cash only. Returns the daily equity curve (marked at every close), trades taken, average share deployed."""
    rng = np.random.default_rng(seed)
    order = sorted(range(len(trades)), key=lambda i: (trades[i]["t_in"], rng.random()))
    by_day = {}
    for i in order:
        by_day.setdefault(trades[i]["t_in"].normalize(), []).append(trades[i])
    cash, open_, held = 1.0, [], []          # held = (release_time, dollars): money waiting for a later buy
    curve, taken, dep = [], 0, []
    for day in days:
        # 1. close what has exited by this day's end, release money whose waiting buy was pulled
        still = []
        for p in open_:
            if p["t_out"].normalize() <= day:
                cash += p["dollars"] * (1 + p["pct"] / 100.0)
            else:
                still.append(p)
        open_ = still
        keep = []
        for rel, dol in held:
            if rel.normalize() <= day:
                cash += dol
            else:
                keep.append((rel, dol))
        held = keep
        # 2. new trades today, in time order
        for tr in by_day.get(day, []):
            if len(open_) >= slots:
                continue
            per = cash / (slots - len(open_)) if slots > len(open_) else 0.0
            if per <= 0:
                continue
            inv = per * tr["filled"]
            cash -= per
            open_.append(dict(tr, dollars=inv))
            if per - inv > 0:
                held.append((tr["t_win"], per - inv))
            taken += 1
        # 3. mark everything at today's close
        val = cash + sum(dol for _r, dol in held)
        inv_val = 0.0
        for p in open_:
            c = closes.get((p["kind"], p["sym"]))
            px = c.asof(day) if c is not None and len(c) else np.nan
            v = p["dollars"] * px / p["entry"] if np.isfinite(px) and p["entry"] > 0 else p["dollars"]
            inv_val += v
        eq = val + inv_val
        curve.append(eq)
        dep.append(inv_val / eq if eq > 0 else 0.0)
    return np.array(curve), taken, float(np.mean(dep))


def stats(curve, days):
    yrs = (days[-1] - days[0]).days / 365.25
    peak = np.maximum.accumulate(curve)
    s = pd.Series(curve, index=days)
    by_year = s.groupby(s.index.year).agg(lambda x: x.iloc[-1] / x.iloc[0] - 1)
    return dict(a_year=float(curve[-1] ** (1 / yrs) - 1), dip=float((curve / peak - 1).min()),
                years={int(k): float(v) for k, v in by_year.items()})


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
        for tr, c, sym, kind in ex.map(_work, names, chunksize=2):
            trades += tr
            if c is not None:
                closes[(kind, sym)] = c
    spy = closes.get(("etf", "SPY"))
    end = max(t["t_out"] for t in trades).normalize()
    days = pd.date_range(START, end, freq="D")
    yrs = (days[-1] - days[0]).days / 365.25
    print("\n  THE WHOLE BACKBURNER AS AN ACCOUNT: %d trades %s .. %s (%.1f years), cash, marked daily, %d runs  (%.0fs)\n"
          % (len(trades), days[0].date(), days[-1].date(), yrs, RUNS, time.time() - t0))
    out = dict(meta=dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), trades=len(trades),
                         start=str(days[0].date()), end=str(days[-1].date()), runs=RUNS), table={})
    s_curve = spy.reindex(days, method="ffill").values
    s_curve = s_curve / s_curve[np.isfinite(s_curve)][0]
    ss = stats(np.nan_to_num(s_curve, nan=1.0), days)
    out["table"]["SPY bought and held"] = ss
    print("    %-34s %5s %9s %13s %9s %9s %10s   %s" % ("", "slots", "a year", "10%-90%", "worst dip", "deployed",
                                                     "trades/yr", "each year"))
    print("    %-34s %5s %+8.1f%% %13s %+8.1f%% %9s %10s   %s" % (
        "SPY bought and held", "", 100 * ss["a_year"], "", 100 * ss["dip"], "100%", "",
        "  ".join("%d %+.0f%%" % (k, 100 * v) for k, v in ss["years"].items())))
    groups = [("EVERYTHING (stocks, crypto, futures)", lambda t: True),
              ("stocks + ETFs only", lambda t: t["kind"] in ("stock", "etf")),
              ("crypto only", lambda t: t["kind"] == "crypto"),
              ("commodity futures only", lambda t: t["kind"] == "futures")]
    for lab, sel in groups:
        tr = [t for t in trades if sel(t)]
        if not tr:
            continue
        print()
        for n_ in SLOTS:
            res = [account(tr, closes, days, n_, s_) for s_ in range(RUNS)]
            st_ = [stats(r[0], days) for r in res]
            ann = np.array([x["a_year"] for x in st_]); dips = np.array([x["dip"] for x in st_])
            mid = int(np.argsort(ann)[len(ann) // 2])
            d = dict(a_year=float(np.median(ann)), p10=float(np.percentile(ann, 10)), p90=float(np.percentile(ann, 90)),
                     dip=float(np.median(dips)), deployed=float(np.mean([r[2] for r in res])),
                     trades_a_year=float(np.mean([r[1] for r in res]) / yrs), signals=len(tr), years=st_[mid]["years"])
            out["table"]["%s | %d" % (lab, n_)] = d
            print("    %-34s %5d %+8.1f%% %+5.1f/%+5.1f%% %+8.1f%% %8.0f%% %10.0f   %s" % (
                lab if n_ == SLOTS[0] else "", n_, 100 * d["a_year"], 100 * d["p10"], 100 * d["p90"], 100 * d["dip"],
                100 * d["deployed"], d["trades_a_year"],
                "  ".join("%d %+.0f%%" % (k, 100 * v) for k, v in d["years"].items())))
    print("\n  deployed = the average share of the account actually in positions (the rest is cash). No leverage.")
    json.dump(out, io.open(OUT, "w", encoding="utf-8"), indent=1)
    if log:
        io.open(os.path.splitext(log)[0] + ".done", "w", encoding="utf-8").write("done")


if __name__ == "__main__":
    main()
