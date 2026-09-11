"""portfolio.py -- the question he asked (2026-09-08): "the main difference is being able to
make multiple trades vs just holding, the number of trades is everything."

Per-trade numbers cannot answer that. This runs the actual money: every trend-ride signal
across the whole universe, in time order, into a wallet with a fixed number of slots. When a
slot is free and a signal comes, it takes it; when nothing is on, the cash sits idle. Then it
compares the wallet against buying and holding the benchmark over the same 4 years.

    pythonw studies/portfolio.py --procs 20 --log logs/portfolio.log
    add --focus for the focus list only.

Writes validation/portfolio.json and validation/portfolio_trades.csv.gz.
Every trade is: buy the second higher low at the next open (his rules, #17), a third off at
twice the risk, out on a wick half a normal bar under the last higher low, trail once up 3x.
Costs are taken out of every trade. A slot can only hold one name at a time.
"""
import bisect
import concurrent.futures as cf
import gzip
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as B      # noqa: E402
import structure as ST            # noqa: E402
import trend_ride as T            # noqa: E402

TFS = ["1h", "4h", "1d"]                 # the charts that made money per trade
SLOTS = [1, 3, 5, 10, 20]                # how many trades the wallet can hold at once
PROCS = max(1, os.cpu_count() or 4)
YEARS = B.YEARS
OUT = os.path.join("validation", "portfolio.json")
OUT_CSV = os.path.join("validation", "portfolio_trades.csv.gz")


def trades_for(sym, kind, tf, frames):
    """Every signal on one chart: when it bought, when it sold, what it made. His rules."""
    df = frames[tf]
    if len(df) < 300:
        return []
    c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    cap = T.CAP_DAYS * B.BARS_DAY[tf]
    cost = B.CLASS_COST.get(kind, B.COST)
    a14 = B.atr(h, l, c)
    piv = ST.pivots(df)
    lows = [(ci, j, p, lab) for ci, j, p, k_, lab in piv if k_ == "low"]
    lcis = [x[0] for x in lows]
    pos_by_ci = {pv[0]: i for i, pv in enumerate(piv)}
    day = df.index.normalize().values if kind in ("stock", "etf") and tf in ("5m", "15m") else None
    out = []
    for idx, (ci, j, price, lab) in enumerate(lows):
        if lab not in ("HL", "EL") or ci < 60 or ci + 2 >= n - 1:
            continue
        e = ci + 1
        cnt, has_hh, nhl = T.trend_pivots_before(piv, pos_by_ci, ci)
        if cnt < 3 or not has_hh or nhl > 2:          # his rule: the SECOND higher low only
            continue
        atr = a14[ci] if np.isfinite(a14[ci]) and a14[ci] > 0 else np.nan
        if not np.isfinite(atr):
            continue
        fill = o[e]
        if fill < price:
            continue
        if (fill - price) / atr > (1.0 if tf in ("5m", "15m", "1h") else 3.0):
            continue
        risk = max(fill - price, atr)
        res = T.hl_break_exit(c, o, l, h, a14, lows, lcis, e, price, n, cap, 0.5, day=day, trail_after=3.0)
        if res is None:
            continue
        xb, xpx, why, worst = res
        tgt = fill + 2 * risk
        pbar = next((k for k in range(e, xb + 1) if h[k] >= tgt), None)
        sz = 1 / 3 if pbar is not None else 0.0
        ret = sz * (tgt / fill - 1) + (1 - sz) * (xpx / fill - 1) - cost
        t_in = df.index[e]; t_out = df.index[min(xb + 1, n - 1)]
        out.append(dict(sym=sym, kind=kind, tf=tf, t_in=t_in, t_out=t_out, ret=float(ret),
                        bars=int(xb + 1 - e), days=float((t_out - t_in).total_seconds() / 86400.0),
                        worst=float(worst)))
    return out


def _work(args):
    sym, kind = args
    try:
        fr = B.frames_for(sym, kind)
    except Exception as ex:
        return [], ["%s %s: %s" % (kind, sym, ex)]
    rows = []
    for tf in TFS:
        if tf in fr:
            try:
                rows += trades_for(sym, kind, tf, fr)
            except Exception as ex:
                return rows, ["%s %s %s: %s" % (kind, sym, tf, ex)]
    return rows, []


def run_wallet(t_in, t_out, rets, slots, span, rounds=60, seed=0):
    """The real thing. One wallet, `slots` equal parts. A new trade is sized at the CURRENT
    wallet value divided by the slots, so the position size follows the account. Cash sits idle
    when nothing is on. When more signals arrive than there are free slots, which one you catch
    is arbitrary -- so the run is repeated `rounds` times with a random pick each time and the
    spread is reported. That spread is part of the honest answer: with few slots, which trades
    you happen to catch is most of the result."""
    n = len(t_in)
    if n == 0:
        return None
    rng = np.random.default_rng(seed)
    mults, takens, deployeds = [], [], []
    for r_ in range(rounds):
        idx = np.lexsort((rng.random(n), t_in))          # time order, ties broken at random
        cash = 1.0
        open_t = []              # exit times of the open trades, kept sorted
        open_m = []              # what each will pay back
        busy = 0.0
        taken = 0
        for i in idx:
            ti = t_in[i]; to = t_out[i]
            k = 0
            while k < len(open_t) and open_t[k] <= ti:   # settle anything that closed
                cash += open_m[k]; k += 1
            if k:
                del open_t[:k]; del open_m[:k]
            if len(open_t) >= slots:
                continue                                  # every slot busy: this signal is missed
            stake = (cash + sum(open_m)) / slots
            if stake > cash:
                stake = cash
            if stake <= 0:
                continue
            cash -= stake
            j = bisect.bisect_left(open_t, to)
            open_t.insert(j, to); open_m.insert(j, stake * (1 + rets[i]))
            busy += float(to - ti); taken += 1
        cash += sum(open_m)
        mults.append(cash); takens.append(taken); deployeds.append(busy / (slots * span))
    q = np.percentile(mults, [10, 50, 90])
    return dict(mult=float(q[1]), mult_low=float(q[0]), mult_high=float(q[2]),
                trades=int(np.median(takens)), deployed=float(np.median(deployeds)), rounds=rounds)


def _wallet_job(args):
    key, t_in, t_out, rets, slots, span = args
    return key, run_wallet(t_in, t_out, rets, slots, span)


def bench(sym, kind, start, end):
    try:
        df = B.frames_for(sym, kind).get("1d")
    except Exception:
        return None
    if df is None:
        return None
    d = df[(df.index >= start) & (df.index <= end)]
    if len(d) < 100:
        return None
    c = d["Close"].values.astype(float)
    return float(c[-1] / c[0])


def main():
    procs = PROCS
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            sys.stdout = sys.stderr = open(sys.argv[i + 1], "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    global OUT, OUT_CSV
    names = [(s_, k_) for s_, k_ in B.universe() if k_ != "forex"]
    if "--with-forex" not in sys.argv:
        pass
    else:
        # only the pairs whose intraday bars are REAL (Dukascopy minutes, repaired 2026-09-08):
        # a real 4-year 1h file has ~24,000 bars; a Yahoo one has 2 years, and the old broken
        # ones had one bar a day.
        import glob
        for fp in sorted(glob.glob(os.path.join("history", "forex", "*_1h.csv.gz"))):
            sym = os.path.basename(fp)[:-len("_1h.csv.gz")]
            try:
                nrows = sum(1 for _ in gzip.open(fp, "rt")) - 1
            except Exception:
                continue
            if nrows >= 15000:
                names.append((sym, "forex"))
    if "--focus" in sys.argv:
        import focus
        names = [(s_, k_) for s_, k_ in focus.names() if focus.have(s_, k_)]
        OUT = OUT.replace(".json", "_focus.json"); OUT_CSV = OUT_CSV.replace(".csv.gz", "_focus.csv.gz")
    names = T._by_size(names)
    T.quiet_workers()
    rows, errs, done = [], [], 0
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for out, err in ex.map(_work, names, chunksize=1):
            done += 1; rows += out; errs += err
            if done % 100 == 0 or done == len(names):
                print("  %d/%d names, %d trades  (%.0fs)" % (done, len(names), len(rows), time.time() - t0), flush=True)
    f = pd.DataFrame(rows)
    f.to_csv(OUT_CSV, index=False, compression="gzip")
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * YEARS)
    end = pd.Timestamp.now().normalize()
    f = f[(f.t_in >= start) & (f.t_out <= end)]
    years = (end - start).days / 365.25

    res = {"meta": dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names),
                        years=round(years, 2), tfs=TFS, slots=SLOTS, seconds=int(time.time() - t0))}
    # 1. how long a trade lasts and what it makes per DAY held
    hold = {}
    for tf in TFS:
        g = f[f.tf == tf]
        for k_ in ["all"] + sorted(g.kind.unique().tolist()):
            gg = g if k_ == "all" else g[g.kind == k_]
            if len(gg) < 50:
                continue
            hold["%s | %s" % (tf, k_)] = dict(
                n=int(len(gg)), bars=float(gg.bars.mean()), days=float(gg.days.mean()),
                ret=float(gg.ret.mean()), per_day=float(gg.ret.mean() / max(gg.days.mean(), 1e-9)),
                trades_per_name_year=float(len(gg) / max(gg.sym.nunique(), 1) / years),
                signals_per_year=float(len(gg) / years))
    res["hold"] = hold
    # 2. the wallet: signals in time order into N slots
    span = float((end - start).total_seconds())
    f["_in"] = f.t_in.values.astype("datetime64[s]").astype(np.int64).astype(float)
    f["_out"] = f.t_out.values.astype("datetime64[s]").astype(np.int64).astype(float)
    cases = []
    for tf in TFS + ["all three"]:
        g0 = f if tf == "all three" else f[f.tf == tf]
        for who in ("everything", "stocks and ETFs", "crypto", "futures"):
            g = (g0 if who == "everything" else
                 g0[g0.kind.isin(["stock", "etf"])] if who == "stocks and ETFs" else
                 g0[g0.kind == "crypto"] if who == "crypto" else g0[g0.kind == "futures"])
            if len(g) < 100:
                continue
            a_, b_, r_ = g._in.values, g._out.values, g.ret.values
            for s_ in SLOTS:
                cases.append(("%s | %s | %d slots" % (tf, who, s_), a_, b_, r_, s_, span))
    wallet = {}
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for key, w in ex.map(_wallet_job, cases, chunksize=1):
            if w is None:
                continue
            w["per_year"] = float(w["mult"] ** (1 / years) - 1)
            w["per_year_low"] = float(w["mult_low"] ** (1 / years) - 1)
            w["per_year_high"] = float(w["mult_high"] ** (1 / years) - 1)
            wallet[key] = w
    res["wallet"] = {k: wallet[k] for k in [c[0] for c in cases] if k in wallet}
    wallet = res["wallet"]
    # the ceiling: what the per-day rate would compound to if a slot were never idle
    ceiling = {}
    for k, v in hold.items():
        ceiling[k] = float((1 + v["per_day"]) ** 365.25 - 1)
    res["ceiling_if_never_idle"] = ceiling
    # 3. what costs do to it, and what picking names on movement does -- both out of sample.
    # These used to be typed into the page by hand; now the page reads them.
    COSTS = [0.0, 0.0005, 0.0010, 0.0020, 0.0035, 0.0055]
    mid = start + (end - start) / 2
    yrs2 = (end - mid).days / 365.25
    span2 = float((end - mid).total_seconds())
    later = f[(f.t_in >= mid) & (f.tf == "1h") & (f.kind.isin(["stock", "etf"]))]
    movers = set()
    tr_path = os.path.join("validation", "name_traits.json")
    if os.path.exists(tr_path):
        tr = pd.DataFrame(json.load(open(tr_path))["rows"])
        tr = tr[tr.kind.isin(["stock", "etf"])].dropna(subset=["moves"])
        if len(tr) > 50:
            movers = set(tr[tr.moves >= tr.moves.quantile(0.75)].sym)      # picked on the FIRST half only
    groups = {"every stock and ETF": later}
    if movers:
        groups["the biggest movers"] = later[later.sym.isin(movers)]
        groups["all the others"] = later[~later.sym.isin(movers)]
    cases2 = []
    for who, g in groups.items():
        if len(g) < 100:
            continue
        a_ = g._in.values if "_in" in g else g.t_in.values.astype("datetime64[s]").astype(np.int64).astype(float)
        b_ = g._out.values if "_out" in g else g.t_out.values.astype("datetime64[s]").astype(np.int64).astype(float)
        for c_ in COSTS:
            cases2.append(("%s | +%.2f%% cost" % (who, 100 * c_), a_, b_, g.ret.values - c_, 10, span2))
    oos = {}
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for key, w in ex.map(_wallet_job, cases2, chunksize=1):
            if w is None:
                continue
            w["per_year"] = float(w["mult"] ** (1 / yrs2) - 1)
            w["per_year_low"] = float(w["mult_low"] ** (1 / yrs2) - 1)
            w["per_year_high"] = float(w["mult_high"] ** (1 / yrs2) - 1)
            oos[key] = w
    res["out_of_sample"] = dict(
        starts=str(mid.date()), years=round(yrs2, 2), slots=10, tf="1h",
        movers=len(movers), universe=int(later.sym.nunique()),
        base_cost=B.CLASS_COST.get("stock", 0.0005),
        costs=[float(c_) for c_ in COSTS], wallet={k: oos[k] for k in [c[0] for c in cases2] if k in oos},
        mover_names=sorted(movers))
    b = bench("SPY", "stock", mid, end)
    if b:
        res["out_of_sample"]["spy"] = dict(mult=b, per_year=float(b ** (1 / yrs2) - 1))

    # 4. what buying and holding made over the same window
    bm = {}
    for sym, kind, label in (("SPY", "stock", "SPY"), ("BTC", "crypto", "BTC"), ("QQQ", "stock", "QQQ")):
        m = bench(sym, kind, start, end)
        if m:
            bm[label] = dict(mult=m, per_year=float(m ** (1 / years) - 1))
    res["benchmarks"] = bm
    json.dump(res, open(OUT, "w"), indent=1)
    print()
    print("  PORTFOLIO  %d names, %d trades, %.1f years  (%.0fs)" % (len(names), len(f), years, time.time() - t0))
    print("  how long a trade lasts")
    for k, v in hold.items():
        print("    %-16s n %7d  %5.1f bars  %6.2f days  %+6.2f%% a trade  %+6.3f%%/day  %5.1f signals/name/yr" % (
            k, v["n"], v["bars"], v["days"], 100 * v["ret"], 100 * v["per_day"], v["trades_per_name_year"]))
    print()
    print("  if a slot were NEVER idle, the per-day rate compounds to:")
    for k, v in ceiling.items():
        print("    %-16s %+7.1f%% a year" % (k, 100 * v))
    print()
    print("  the wallet (60 runs each, random pick when signals collide; middle and the 10-90% spread)")
    for k, v in wallet.items():
        print("    %-38s %6d trades  %4.0f%% deployed  x%.2f  =%+7.1f%% a year   (%+.1f%% to %+.1f%%)" % (
            k, v["trades"], 100 * v["deployed"], v["mult"], 100 * v["per_year"],
            100 * v["per_year_low"], 100 * v["per_year_high"]))
    print()
    for k, v in bm.items():
        print("  buy and hold %-4s x%.2f  =%+6.1f%% a year" % (k, v["mult"], 100 * v["per_year"]))
    o = res.get("out_of_sample")
    if o and o.get("wallet"):
        print()
        print("  OUT OF SAMPLE: names picked on the first half, traded from %s (%.1f years, 1h, 10 slots)" % (o["starts"], o["years"]))
        print("  %d of %d stocks/ETFs are 'biggest movers' (top quarter by a normal bar as a share of price)" % (o["movers"], o["universe"]))
        for k, v in o["wallet"].items():
            print("    %-46s %+7.1f%% a year  (%+.1f to %+.1f)" % (k, 100 * v["per_year"], 100 * v["per_year_low"], 100 * v["per_year_high"]))
        if o.get("spy"):
            print("    %-46s %+7.1f%% a year" % ("SPY over the same stretch", 100 * o["spy"]["per_year"]))
    for e in errs[:20]:
        print("  " + e)


if __name__ == "__main__":
    main()
