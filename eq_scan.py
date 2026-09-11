"""eq_scan.py -- live scan for EQs across every market, every chart
size, 5 minute to weekly. Owner 2026-09-08: "make a page that scans for EQs
across everything ... on all time-frames too, and we need it to be as up to
current time as possible."

Every few minutes (the server runs it), for crypto (Coinbase/Kraken, 150 most
traded), stocks and ETFs (Yahoo, 300 most traded, pre/after-hours included) and
the focus futures (Yahoo), it builds the 5m, 15m, 1h, 4h, 1d and 1w charts and
asks one question on each: is an EQ alive right now? An EQ is his rule
(studies/eq_study.py): four pivots, two higher/equal lows and two lower/equal
highs; floor = last higher/equal low, ceiling = last lower/equal high; dead the
moment a wick goes through an edge.

For each live EQ: floor, ceiling, width in normal bars, where the last price
sits between them (0 = on the floor, 1 = on the ceiling), how many times each
edge has been touched, how old it is, and what the next chart up is doing.
"At the floor" rows are the textbook buy; "at the ceiling" the textbook short.

State: livelog/eq_scan.json. Threads for the fetches (network-bound), a process
pool for the maths (all cores).
"""
import concurrent.futures as cf
import json
import multiprocessing as mp
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "studies"))
import backburner_log as BL       # noqa: E402  live frames, yahoo prefetch, universe
import backburner_study as S      # noqa: E402
import crypto                     # noqa: E402
import focus                      # noqa: E402
import structure as ST            # noqa: E402

warnings.filterwarnings("ignore")
OUT = os.path.join("livelog", "eq_scan.json")
TFS = ["5m", "15m", "1h", "4h", "1d", "1w"]
BARS = {"5m": 700, "15m": 700, "1h": 900, "1d": 700}
NEAR = 0.20          # within this share of the EQ's height counts as "at" an edge


def _frames_crypto(sym, source):
    out = {}
    for tf in ("5m", "15m", "1h", "1d"):
        try:
            d = crypto.candles(sym, tf, BARS[tf], source=source)
        except Exception:
            d = None
        if d is not None and len(d) >= 60:
            out[tf] = d
    return _fill(out)


def _frames_stock(sym, pre):
    out = {}
    for tf in ("5m", "15m", "1h", "1d"):
        d = pre.get((sym, tf))
        if d is not None and len(d) >= 60:
            out[tf] = d
    return _fill(out)


def _frames_future(sym):
    import yfinance as yf
    out = {}
    yh = sym.replace("_F", "=F")
    for tf, period in (("5m", "59d"), ("15m", "59d"), ("1h", "2y"), ("1d", "5y")):
        try:
            f = yf.download(yh, interval=tf, period=period, progress=False, auto_adjust=False)
            f.columns = [c_[0] if isinstance(c_, tuple) else c_ for c_ in f.columns]
            if getattr(f.index, "tz", None) is not None:
                f.index = f.index.tz_localize(None)
            f = f[["Open", "High", "Low", "Close", "Volume"]].dropna()
            if len(f) >= 60:
                out[tf] = f
        except Exception:
            pass
    return _fill(out)


def _fill(out):
    """4h from the 1h, 1w from the 1d."""
    if "1h" in out:
        h4 = S.resample(out["1h"], "4h")
        if h4 is not None:
            out["4h"] = h4
    if "1d" in out:
        w = S.resample(out["1d"], "W-FRI")
        if w is not None and len(w) >= 40:
            out["1w"] = w
    return out


def yahoo_prefetch_all(syms):
    """15m/1h/1d from backburner_log's prefetch, plus 5m (59 days, all hours)."""
    import yfinance as yf
    pre = BL.yahoo_prefetch(syms)
    for i in range(0, len(syms), 150):
        part = syms[i:i + 150]
        try:
            d = yf.download(part, interval="5m", period="59d", progress=False, auto_adjust=False, prepost=True, group_by="ticker", threads=True)
        except Exception:
            continue
        for s_ in part:
            try:
                f = (d[s_] if isinstance(d.columns, pd.MultiIndex) else d).dropna()
            except Exception:
                continue
            if getattr(f.index, "tz", None) is not None:
                f.index = f.index.tz_localize(None)
            if len(f) >= 60:
                pre[(s_, "5m")] = f[["Open", "High", "Low", "Close", "Volume"]]
    return pre


def check(sym, kind, frames):
    """Rows for every chart size of one name where an EQ is alive on the last closed bar."""
    from eq_break import get_ranges, reads, pivot_lists
    import exit_managers as XM
    rows = []
    hi_of = {"5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d", "1d": "1w"}
    states = {}
    for tf in TFS:
        df = frames.get(tf)
        if df is None or len(df) < 60:
            continue
        try:
            states[tf] = str(ST.states(df, causal=True)[-1])
        except Exception:
            states[tf] = "NA"
    for tf in TFS:
        df = frames.get(tf)
        if df is None or len(df) < 60:
            continue
        floor, ceil, rid, rlist, atr = get_ranges(df, "rectangle")      # the long sideways box (his EQ), 30-bar window
        n = len(df)
        last = n - 2 if n >= 2 else n - 1          # the last CLOSED bar (the final row may still be forming)
        if rid[last] < 0 or not np.isfinite(floor[last]) or not np.isfinite(ceil[last]):
            continue
        a = atr[last] if np.isfinite(atr[last]) and atr[last] > 0 else np.nan
        if not np.isfinite(a):
            continue
        born = rlist[rid[last]][0] if rid[last] < len(rlist) else last
        f, ce = float(floor[last]), float(ceil[last])
        width = (ce - f) / a
        # the 4-bar height test is made when the box FORMS, with that day's bar size. Measured
        # against today's bar size an older box can read taller or shorter than 4 without the rule
        # having been broken, so both numbers are carried to the page.
        decl = min(born + 29, last)                      # the bar the box was declared on
        a0 = atr[decl] if np.isfinite(atr[decl]) and atr[decl] > 0 else a
        width_born = (ce - f) / a0
        # the 4-bar height test is applied when the box FORMS, with the bar size of that day.
        # Measured against today's bar size an old box can read taller (or shorter) than 4 without
        # the rule having been broken, so both numbers are carried.
        decl = min(born + 29, last)                      # the bar the box was declared on
        a0 = atr[decl] if np.isfinite(atr[decl]) and atr[decl] > 0 else a
        width_born = (ce - f) / a0
        if width < 1.0 or width > 40 or a / max(float(df["Close"].values[-1]), 1e-9) < 0.0003:
            continue                      # too narrow, or a dead flat name (stablecoins) where a normal bar is nothing
        l = df["Low"].values.astype(float); h = df["High"].values.astype(float); c = df["Close"].values.astype(float)
        touches_f = int(np.sum(l[born:last + 1] <= f + 0.25 * a))
        touches_c = int(np.sum(h[born:last + 1] >= ce - 0.25 * a))
        price = float(c[-1])                          # the newest price, forming bar included
        where = (price - f) / (ce - f) if ce > f else 0.5
        # the reads a trader would use to call the break direction
        try:
            pl, ph = pivot_lists(ST.pivots(df))
            rd = reads(last, born, df, c, h, l, atr, floor, ceil, ST.states(df, causal=True),
                       np.array([states.get(hi_of.get(tf), "NA")] * n, dtype=object), XM.rsi(c), XM.ema(c, 50), pl, ph)
        except Exception as ex:
            rd = {"error": "%s: %s" % (type(ex).__name__, ex)}
        rows.append(dict(sym=sym, kind=kind, tf=tf, floor=f, ceil=ce, width=round(float(width), 2),
                         width_born=round(float(width_born), 2),
                         price=price, where=round(float(where), 2),
                         zone="at the floor" if where <= NEAR else "at the ceiling" if where >= 1 - NEAR else "in the middle",
                         touches_floor=touches_f, touches_ceil=touches_c, age=int(last - born + 1),
                         next_chart=states.get(hi_of.get(tf), "NA"), own=states.get(tf, "NA"),
                         came_from=rd.get("read_prior", ""), inside=rd.get("read_inside", ""), call=rd.get("read_call", ""),
                         rsi=(int(round(rd["rsi"])) if np.isfinite(rd.get("rsi", float("nan"))) else None),
                         read_error=rd.get("error", ""),
                         bar=str(df.index[last]), asof=str(df.index[-1])))
    return rows


def _work(args):
    sym, kind, frames = args
    try:
        return check(sym, kind, frames), None
    except Exception as ex:
        return [], "%s %s: %s" % (kind, sym, ex)


def tick(log=print, procs=None):
    t0 = time.time()
    uni = BL.universe()
    stocks = [s_ for s_, k_, src in uni if k_ in ("stock", "etf")]
    pre = yahoo_prefetch_all(stocks) if stocks else {}
    jobs = []
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        futs = {}
        STABLE = {"USDT", "USDC", "DAI", "EURC", "FDUSD", "PYUSD", "TUSD", "USDP", "FIDD", "USDS", "USDE", "RLUSD", "USD1", "EURT", "GUSD", "BUSD", "USDD", "USD0"}
        for sym, kind, src in uni:
            if kind == "crypto" and (sym in STABLE or "USD" in sym or "EUR" in sym):
                continue                        # a stablecoin is an EQ forever; not a trade
            if kind == "crypto":
                futs[ex.submit(_frames_crypto, sym, src)] = (sym, kind)
            else:
                futs[ex.submit(_frames_stock, sym, pre)] = (sym, kind)
        for sym, kind in focus.names():
            if kind == "futures":
                futs[ex.submit(_frames_future, sym)] = (sym, kind)
        for fu in cf.as_completed(futs):
            sym, kind = futs[fu]
            try:
                fr = fu.result()
            except Exception as ex:
                log("  %s frames: %s" % (sym, ex)); continue
            if fr:
                jobs.append((sym, kind, fr))
    fetched = time.time() - t0
    rows, errs = [], []
    if sys.platform == "win32":
        exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if os.path.exists(exe):
            mp.set_executable(exe)
    with cf.ProcessPoolExecutor(max_workers=procs or max(1, os.cpu_count() or 4)) as ex:
        for rr, err in ex.map(_work, jobs, chunksize=4):
            rows += rr
            if err:
                errs.append(err)
    order = {"at the floor": 0, "at the ceiling": 1, "in the middle": 2}
    rows.sort(key=lambda r: (order[r["zone"]], -r["touches_floor"] - r["touches_ceil"], r["sym"]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"                      # write whole, then swap: a reader never sees a half-written file
    def clean(v):
        return None if isinstance(v, float) and not np.isfinite(v) else v
    rows = [{k: clean(v) for k, v in r.items()} for r in rows]
    json.dump(dict(last_tick=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"), names=len(jobs), ranges=len(rows),
                   seconds=int(time.time() - t0), fetch_seconds=int(fetched), errors=errs[:10], rows=rows), open(tmp, "w"), allow_nan=False)
    os.replace(tmp, OUT)
    log("  eq scan: %d names, %d live EQs (%d at the floor, %d at the ceiling)  fetch %ds, total %ds" % (
        len(jobs), len(rows), sum(1 for r in rows if r["zone"] == "at the floor"),
        sum(1 for r in rows if r["zone"] == "at the ceiling"), fetched, time.time() - t0))
    return rows


if __name__ == "__main__":
    if "--log" in sys.argv:
        sys.stdout = sys.stderr = open(sys.argv[sys.argv.index("--log") + 1], "a", buffering=1)
    tick()


def frames_for_one(sym, kind):
    """Live frames for one name (for the on-demand chart on /eq)."""
    if kind == "crypto":
        src = next((s_ for n_, k_, s_ in BL.universe() if n_ == sym and k_ == "crypto"), None)
        return _frames_crypto(sym, src)
    if kind == "futures":
        return _frames_future(sym)
    return _frames_stock(sym, yahoo_prefetch_all([sym]))
