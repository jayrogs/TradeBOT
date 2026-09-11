"""trend_names.py -- which names actually trend. Per name and timeframe:
how often it trends, how long the trends last, how clean they are, how much
an uptrend pays, and what the trend ride (his rules) made on it, against its
benchmark (BTC for crypto, SPY for stocks, ES for futures).

    pythonw studies/trend_names.py --procs 16 --log logs/trend_names.log            # every name
    pythonw studies/trend_names.py --focus --procs 16 --log logs/trend_names.log    # the focus list

Everything comes from the same live trend read the charts use (structure.spans,
causal): an uptrend opens on a higher low + higher high and dies on a wick under
the last higher low or a contrary pivot; downtrends mirror it.
"""

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
import panel as P_               # noqa: E402

TFS = ["5m", "15m", "1h", "4h", "1d", "1w"]
BENCH = {"crypto": ("BTC", "crypto"), "stock": ("SPY", "etf"), "etf": ("SPY", "etf"),
         "futures": ("ES_F", "futures"), "forex": ("EURUSD_X", "forex"), "cfd": ("ES_F", "futures")}
OUT = os.path.join("validation", "trend_names.json")


def measure(sym, kind, tf, df, start, allfr=None):
    """One name, one timeframe. allfr: every timeframe of the name, so the ride
    study can read the next chart up (without it every trade says "higher chart flat")."""
    df = df[df.index >= start - pd.Timedelta(days=30)]
    if len(df) < 300:
        return None
    c = df["Close"].values.astype(float)
    n = len(c)
    bpd = B.BARS_DAY[tf]
    spans = ST.spans(df, causal=True)
    ups = [(s0, s1) for k, s0, s1 in spans if k == "UP" and s1 > s0]
    dns = [(s0, s1) for k, s0, s1 in spans if k == "DOWN" and s1 > s0]
    days = max(1.0, (df.index[-1] - df.index[0]).days)
    months = days / 30.4
    def gain(pairs):
        g = [c[s1] / c[s0] - 1 for s0, s1 in pairs if c[s0] > 0]
        return float(np.mean(g)) if g else 0.0
    def length_days(pairs):
        return float(np.mean([(s1 - s0 + 1) / bpd for s0, s1 in pairs])) if pairs else 0.0
    up_bars = sum(s1 - s0 + 1 for s0, s1 in ups); dn_bars = sum(s1 - s0 + 1 for s0, s1 in dns)
    # ---- how well the name BEHAVES in a trend (his ask 2026-09-07): once a trend
    # opens, how many more pivots does it make before it dies, how often does it die
    # with nothing more (a fakeout), and does it die on a wick or on a contrary pivot
    piv = ST.pivots(df)
    atr = P_._atr(df)
    hh_ = df["High"].values.astype(float); ll_ = df["Low"].values.astype(float)
    # "a full session or more": stocks trade ~6.5 hours a day, crypto and futures round the clock
    SESSION = {"5m": 78, "15m": 26, "1h": 7, "4h": 2, "1d": 1, "1w": 1} if kind in ("stock", "etf") else B.BARS_DAY
    sess = SESSION.get(tf, 1)
    by_ci = {}
    for ci, j, price, k_, lab in piv:
        by_ci.setdefault(ci, []).append(lab)
    trends = []
    for k_, s0, s1 in spans:
        if s1 <= s0 and k_ not in ("UP", "DOWN"):
            continue
        build = ("HL", "HH") if k_ == "UP" else ("LH", "LL")
        killers = ("LH", "LL") if k_ == "UP" else ("HH", "HL")
        more = sum(1 for ci in range(s0 + 1, s1 + 1) for lab in by_ci.get(ci, []) if lab in build)
        nxt = by_ci.get(s1 + 1, [])
        died = ("open" if s1 >= n - 1 else
                "pivot" if any(lab in killers for lab in nxt) else "wick")
        g_ = (c[s1] / c[s0] - 1) if c[s0] > 0 else 0.0
        # how far it travelled in its own direction, in normal bars' moves at the open
        a0 = atr[s0] if np.isfinite(atr[s0]) and atr[s0] > 0 else np.nan
        ext = (np.nanmax(hh_[s0:s1 + 1]) - c[s0]) if k_ == "UP" else (c[s0] - np.nanmin(ll_[s0:s1 + 1]))
        travel = float(ext / a0) if np.isfinite(a0) else None
        trends.append(dict(k="U" if k_ == "UP" else "D", s=str(df.index[s0]), e=str(df.index[s1]),
                           bars=int(s1 - s0 + 1), piv=int(more), died=died, gain=round(float(g_), 5),
                           trav=None if travel is None else round(travel, 2)))
    closed_ = [t_ for t_ in trends if t_["died"] != "open"]
    pivs = [t_["piv"] for t_ in closed_]
    n_tr = len(closed_)
    travs = [t_["trav"] for t_ in closed_ if t_["trav"] is not None]
    pw = [(t_["piv"] + 2) * t_["trav"] for t_ in closed_ if t_["trav"] is not None]
    behave = dict(trends=n_tr,
                  piv_all=float(np.mean(pivs)) + 2 if pivs else None,          # counting the two that opened it
                  travel=float(np.mean(travs)) if travs else None,             # normal bars' moves, open to extreme
                  piv_w=float(np.mean(pw)) if pw else None,                    # pivots (incl. openers) x travel
                  piv_per_trend=float(np.mean(pivs)) if pivs else None,
                  piv_median=float(np.median(pivs)) if pivs else None,
                  fakeout=float(np.mean([p_ == 0 for p_ in pivs])) if pivs else None,     # died with no new pivot
                  long_share=float(np.mean([p_ >= 3 for p_ in pivs])) if pivs else None,  # 3+ more pivots
                  wick_death=float(np.mean([t_["died"] == "wick" for t_ in closed_])) if closed_ else None,
                  longest_piv=int(max(pivs)) if pivs else 0,
                  up_piv=float(np.mean([t_["piv"] for t_ in closed_ if t_["k"] == "U"])) if any(t_["k"] == "U" for t_ in closed_) else None,
                  down_piv=float(np.mean([t_["piv"] for t_ in closed_ if t_["k"] == "D"])) if any(t_["k"] == "D" for t_ in closed_) else None,
                  trend_list=trends)
    out = dict(sym=sym, kind=kind, tf=tf, months=round(months, 1), **behave,
               ups_per_month=len(ups) / months, downs_per_month=len(dns) / months,
               pct_up=up_bars / n, pct_down=dn_bars / n, pct_flat=1 - (up_bars + dn_bars) / n,
               up_len_days=length_days(ups), down_len_days=length_days(dns),
               up_gain=gain(ups), down_gain=gain(dns),
               longest_up_days=max([(s1 - s0 + 1) / bpd for s0, s1 in ups], default=0.0),
               # "clean": share of the trend's bars that closed on the right side of the 12 EMA
               up_clean=float(np.mean([np.mean(c[s0:s1 + 1] >= _ema(c)[s0:s1 + 1]) for s0, s1 in ups])) if ups else 0.0)
    # the ride, his rules, on this name: second higher low, trail once up 3R, no partial
    try:
        frames = dict(allfr or {}); frames[tf] = df
        rows = R.study_frame(sym, kind, tf, frames, start)
    except Exception:
        rows = []
    r = [x for x in rows if x["exit"] == "higher low breaks, trail once up 3R" and x["take"] == "no partial"
         and x["leg"] == "first try" and x["nth"] == "2nd higher low"]
    if r:
        rets = np.array([x["ret"] for x in r])
        halves = {}
        for hv in ("first", "second"):
            hh = [x["ret"] for x in r if x["era"] == hv]
            if len(hh) >= 10:
                halves[hv] = float(np.mean(hh))
        out.update(ride_n=len(r), ride=float(rets.mean()), ride_win=float((rets > 0.005).mean()),
                   ride_worst=float(np.mean([x["worst"] for x in r])),
                   ride_avg_win=float(rets[rets > 0.005].mean()) if (rets > 0.005).any() else None,
                   ride_avg_loss=float(rets[rets < -0.005].mean()) if (rets < -0.005).any() else None,
                   ride_held=float(np.mean([x["held"] for x in r])),
                   half1=halves.get("first"), half2=halves.get("second"),
                   trades=[dict(t=x["t"], ret=round(x["ret"], 5), held=x["held"], why=x["why"],
                                worst=round(x["worst"], 5), best_after=round(x["best_after"], 5),
                                hi=x["hi"], chop=x["chop"]) for x in r])
    else:
        out.update(ride_n=0, ride=None, ride_win=None, ride_worst=None, ride_avg_win=None, ride_avg_loss=None,
                   ride_held=None, half1=None, half2=None, trades=[])
    return out


_EMA = {}


def _ema(c):
    key = (len(c), float(c[0]), float(c[-1]))
    if key not in _EMA:
        import rider
        _EMA.clear(); _EMA[key] = rider.ema(c)
    return _EMA[key]


_BENCH_RET = {}


def bench_returns(kind):
    bs, bk = BENCH.get(kind, ("SPY", "etf"))
    if bs not in _BENCH_RET:
        try:
            fr = B.frames_for(bs, bk)
            d1 = fr.get("1d")
            _BENCH_RET[bs] = None if d1 is None else np.log(d1["Close"].astype(float)).diff().dropna()
        except Exception:
            _BENCH_RET[bs] = None
    return _BENCH_RET[bs]


def beta_of(fr, kind):
    d1 = fr.get("1d"); br = bench_returns(kind)
    if d1 is None or br is None:
        return None, None
    r_ = np.log(d1["Close"].astype(float)).diff().dropna()
    r_ = r_[r_.index >= r_.index[-1] - pd.Timedelta(days=365 * 4)]
    j = r_.index.intersection(br.index)
    if len(j) < 60:
        return None, None
    x, y = br.loc[j].values, r_.loc[j].values
    beta = float(np.cov(x, y)[0, 1] / np.var(x)) if np.var(x) > 0 else None
    return beta, float(np.corrcoef(x, y)[0, 1])


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
    try:
        fr = B.frames_for(sym, kind)
    except Exception as ex:
        return [], ["%s %s: %s" % (kind, sym, ex)]
    out, errs = [], []
    beta, corr = beta_of(fr, kind)
    for tf in TFS:
        if tf not in fr:
            continue
        try:
            m = measure(sym, kind, tf, fr[tf], start, fr)
            if m:
                m["beta"] = beta; m["corr"] = corr
                out.append(m)
        except Exception as ex:
            errs.append("%s %s %s: %s" % (kind, sym, tf, ex))
    return out, errs


def quiet_workers():
    if sys.platform == "win32":
        exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if os.path.exists(exe):
            mp.set_executable(exe)


def main():
    procs = max(1, os.cpu_count() or 4)
    log = None
    for i, a in enumerate(sys.argv):
        if a == "--procs" and i + 1 < len(sys.argv):
            procs = int(sys.argv[i + 1])
        if a == "--log" and i + 1 < len(sys.argv):
            log = sys.argv[i + 1]
            sys.stdout = sys.stderr = open(log, "w", buffering=1, encoding="utf-8", errors="replace")
    t0 = time.time()
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * B.YEARS)
    if "--focus" in sys.argv:
        import focus
        names = [(s_, k_) for s_, k_ in focus.names() if focus.have(s_, k_)]
    else:
        names = [(s_, k_) for s_, k_ in B.universe() if k_ != "forex"]
    for b in BENCH.values():
        if b not in names:
            names.append(b)
    quiet_workers()
    rows, errs, done = [], [], 0
    if "--agg-only" in sys.argv:
        import pickle
        rows = pickle.load(open(os.path.join("validation", "trend_names_rows%s.pkl" % ("_focus" if "--focus" in sys.argv else "")), "rb"))
    else:
        names = _by_size(names)
        with cf.ProcessPoolExecutor(max_workers=procs) as ex:
            for out, err in ex.map(_work, [(s_, k_, start) for s_, k_ in names], chunksize=1):
                rows += out; errs += err; done += 1
                if done % 50 == 0:
                    print("  %d/%d  (%.0fs)" % (done, len(names), time.time() - t0), flush=True)
    for e in errs[:20]:
        print("  " + e)
    import pickle
    raw = os.path.join("validation", "trend_names_rows%s.pkl" % ("_focus" if "--focus" in sys.argv else ""))
    pickle.dump(rows, open(raw, "wb"))
    d = pd.DataFrame(rows)
    focus_run = "--focus" in sys.argv
    # the drill-down files: every ride trade of every name, by timeframe
    ev_dir = os.path.join("validation", "trend_name_events")
    os.makedirs(ev_dir, exist_ok=True)
    for (sym, kind), g in d.groupby(["sym", "kind"]):
        per = {tf_: rr["trades"] for tf_, rr in zip(g.tf, g.to_dict("records"))}
        tl = {tf_: rr["trend_list"] for tf_, rr in zip(g.tf, g.to_dict("records"))}
        json.dump(dict(sym=sym, kind=kind, by_tf=per, trends=tl), open(os.path.join(ev_dir, "%s_%s.json" % (kind, sym)), "w"))
    d = d.drop(columns=["trades", "trend_list"])
    # an "all timeframes" row per name: trades pooled, halves pooled
    allrows = []
    for (sym, kind), g in d.groupby(["sym", "kind"]):
        tr = [t for rr in rows if rr["sym"] == sym and rr["kind"] == kind for t in rr["trades"]]
        if not tr:
            continue
        rets = np.array([t["ret"] for t in tr])
        tl_all = [t_ for rr in rows if rr["sym"] == sym and rr["kind"] == kind for t_ in rr["trend_list"] if t_["died"] != "open"]
        pv_all = [t_["piv"] for t_ in tl_all]
        r1 = [t["ret"] for rr in rows if rr["sym"] == sym and rr["kind"] == kind for t in rr["trades"] if t["t"] < str(start + (pd.Timestamp.now() - start) / 2)]
        r2 = [t["ret"] for rr in rows if rr["sym"] == sym and rr["kind"] == kind for t in rr["trades"] if t["t"] >= str(start + (pd.Timestamp.now() - start) / 2)]
        allrows.append(dict(sym=sym, kind=kind, tf="all", months=float(g.months.max()),
                            # "all": each timeframe counts the same (pooling would let the 5m,
                            # with 30x the trends, drown the daily)
                            trends=int(g.trends.sum()),
                            piv_all=float(g.piv_all.astype(float).mean()) if g.piv_all.notna().any() else None,
                            travel=float(g.travel.astype(float).mean()) if g.travel.notna().any() else None,
                            piv_w=float(g.piv_w.astype(float).mean()) if g.piv_w.notna().any() else None,
                            piv_per_trend=float(g.piv_per_trend.astype(float).mean()) if g.piv_per_trend.notna().any() else None,
                            piv_median=float(np.median(pv_all)) if pv_all else None,
                            fakeout=float(g.fakeout.astype(float).mean()) if g.fakeout.notna().any() else None,
                            long_share=float(g.long_share.astype(float).mean()) if g.long_share.notna().any() else None,
                            wick_death=float(g.wick_death.astype(float).mean()) if g.wick_death.notna().any() else None,
                            longest_piv=int(max(pv_all)) if pv_all else 0,
                            up_piv=float(g.up_piv.astype(float).mean()) if g.up_piv.notna().any() else None,
                            down_piv=float(g.down_piv.astype(float).mean()) if g.down_piv.notna().any() else None,
                            ups_per_month=float(g.ups_per_month.mean()), downs_per_month=float(g.downs_per_month.mean()),
                            pct_up=float(g.pct_up.mean()), pct_down=float(g.pct_down.mean()), pct_flat=float(g.pct_flat.mean()),
                            up_len_days=float(g.up_len_days.mean()), down_len_days=float(g.down_len_days.mean()),
                            up_gain=float(g.up_gain.mean()), down_gain=float(g.down_gain.mean()),
                            longest_up_days=float(g.longest_up_days.max()), up_clean=float(g.up_clean.mean()),
                            ride_n=len(tr), ride=float(rets.mean()), ride_win=float((rets > 0.005).mean()),
                            ride_worst=float(np.mean([t["worst"] for t in tr])),
                            ride_avg_win=float(rets[rets > 0.005].mean()) if (rets > 0.005).any() else None,
                            ride_avg_loss=float(rets[rets < -0.005].mean()) if (rets < -0.005).any() else None,
                            ride_held=float(np.mean([t["held"] for t in tr])),
                            half1=float(np.mean(r1)) if len(r1) >= 10 else None,
                            half2=float(np.mean(r2)) if len(r2) >= 10 else None,
                            beta=g["beta"].iloc[0], corr=g["corr"].iloc[0]))
    d = pd.concat([d, pd.DataFrame(allrows)], ignore_index=True)
    # against the benchmark, same timeframe, keyed by the benchmark's SYMBOL
    bsym = {k: v[0] for k, v in BENCH.items()}
    bench = {(r_.sym, r_.tf): r_ for r_ in d.itertuples()}
    def vs(r_, field):
        b = bench.get((bsym.get(r_.kind), r_.tf))
        if b is None or getattr(r_, field) is None or getattr(b, field) is None:
            return None
        return float(getattr(r_, field) - getattr(b, field))
    d["vs_bench_ride"] = [vs(r_, "ride") for r_ in d.itertuples()]
    d["vs_bench_up_gain"] = [vs(r_, "up_gain") for r_ in d.itertuples()]
    def consistent(r_):
        b = bench.get((bsym.get(r_.kind), r_.tf))
        if b is None or r_.half1 is None or r_.half2 is None or b.half1 is None or b.half2 is None:
            return False
        return r_.half1 > b.half1 and r_.half2 > b.half2
    d["consistent"] = [consistent(r_) for r_ in d.itertuples()]
    def grade(r_):
        bname = bsym.get(r_.kind, "?")
        v = r_.vs_bench_ride
        if r_.ride is None or r_.ride_n < 10:
            return "?", "too few trades to grade"
        if r_.ride < -0.01:
            return "F", "loses money riding its trends"
        if v is None:
            return "?", "no benchmark on this timeframe"
        if v > 0.005 and r_.consistent:
            return "A", "rides better than %s, in both halves" % bname
        if v > 0.005:
            return "B", "rides better than %s, but only in one half" % bname
        if v >= -0.005:
            return "C", "about the same as %s" % bname
        return "D", "rides worse than %s" % bname
    gg = [grade(r_) for r_ in d.itertuples()]
    d["grade"] = [g for g, _ in gg]; d["verdict"] = [w for _, w in gg]
    d["trend_score"] = ((d.pct_up + d.pct_down) * 0.5 + d.up_clean * 0.3 +
                        np.clip(d.up_len_days / d.groupby("tf").up_len_days.transform("median").replace(0, np.nan), 0, 3).fillna(0) * 0.2 / 3)
    # "behaves": how many more pivots a trend makes on average, times the share that were not fakeouts
    d["behave_score"] = d.piv_per_trend.astype(float) * (1 - d.fakeout.astype(float))
    d = d.replace({np.nan: None})
    json.dump(dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), tfs=TFS + ["all"], focus=focus_run,
                   bench=bsym, rows=json.loads(d.to_json(orient="records"))),
              open(OUT if not focus_run else OUT.replace(".json", "_focus.json"), "w"))
    print("  %d name-timeframe rows for %d names  (%.0fs)" % (len(d), len(names), time.time() - t0))
    for tf in ("4h", "1d"):
        x = d[(d.tf == tf)].sort_values("trend_score", ascending=False)
        print("\n  %s, trends best:" % tf)
        for r in x.head(12).itertuples():
            print("    %-8s %-7s up %3.0f%% of the time, down %3.0f%%, uptrend %5.1f days long avg, gains %+5.1f%%, ride %s" % (
                r.sym, r.kind, 100 * r.pct_up, 100 * r.pct_down, r.up_len_days, 100 * r.up_gain,
                ("%+.2f%%" % (100 * r.ride)) if r.ride is not None else "-"))
    if log:
        sys.stdout.flush()
        open(os.path.splitext(log)[0] + ".done", "w").write("done")


if __name__ == "__main__":
    main()
