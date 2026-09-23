"""bb_live.py -- THE BACKBURNER, LIVE (2026-09-23). The page /bb.

It runs the EXACT trade code the studies run (pics_backburner_tcg.trades_for) on live data, so the live page and the
backtest cannot drift apart. Everything he picked is in: the first hourly RSI-30 touch after a 10%+ run to fresh highs,
trend intact, company news days skipped (stocks), stocks + crypto + the 24 liquid commodity futures, 5 buckets, the whole
bucket at 30 and the later buys on top (crypto: 2x at 25, 3x at 20, at most 3 buckets a coin), half at the hourly 12 EMA,
the rest walked under the higher lows, crypto sells a quarter more 3 normal bars up.

Two lists:
  ARMED  every condition is met now and the first RSI-30 touch has NOT happened: the price to rest the buy at (the RSI-30
         price for the next hour), and the later buys. Found by asking the trade code itself: nine made-up hours are added
         after the last real one, the first falling through every buy level; if the code takes a trade on that hour, the
         name is armed, and its fills ARE the order prices. Nothing about the real bars changes.
  OPEN   trades the code has taken in the last 10 days and not closed: what was bought, where the half sells (the hourly
         12 EMA now), the stop.
Data: crypto from Coinbase / Kraken (live). Stocks: the history on disk plus the bars since, from Polygon / Massive (his paid
feed, 15 minutes late) -- Yahoo rate-limited 220 of 600 names on the first pass. Futures: the Databento history on disk plus
recent hourly bars from Yahoo (24 names).

    python bb_live.py                  # one pass (the server runs it every 15 minutes)
Writes livelog/bb_live.json
"""
import io
import json
import os
import sys
import time
import traceback
import warnings

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "studies"))
import backburner_study as S      # noqa: E402
import pics_backburner_tcg as PB  # noqa: E402
import exit_managers as XM        # noqa: E402

warnings.filterwarnings("ignore")
OUT = os.path.join("livelog", "bb_live.json")
FUT_YAHOO = lambda s: s.replace("_F", "=F")       # CL_F -> CL=F


def _yahoo_recent(syms, period="60d"):
    """recent hourly bars from Yahoo, New York wall time (futures only: 24 names)."""
    import yfinance as yf
    out = {}
    try:
        d = yf.download(syms, interval="1h", period=period, progress=False, auto_adjust=False, prepost=True,
                        group_by="ticker", threads=True)
    except Exception:
        return out
    for s_ in syms:
        try:
            f = (d[s_] if isinstance(d.columns, pd.MultiIndex) else d).dropna()
        except Exception:
            continue
        if getattr(f.index, "tz", None) is not None:
            f.index = f.index.tz_convert("America/New_York").tz_localize(None)
        if len(f):
            out[s_] = f[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    return out


def _polygon(sym, span, start, key):
    """Polygon / Massive aggregates since `start` (span "hour" or "day"), New York wall time, split-adjusted."""
    import requests
    end = pd.Timestamp.now(tz="America/New_York").strftime("%Y-%m-%d")
    url = ("https://api.polygon.io/v2/aggs/ticker/%s/range/1/%s/%s/%s?adjusted=true&sort=asc&limit=50000"
           % (sym, span, start, end))
    r = None
    for attempt in range(5):
        try:
            r = requests.get(url, params={"apiKey": key}, timeout=30)
        except Exception:                 # a dropped connection is one name's problem, never the whole pass's
            time.sleep(2 + 3 * attempt)
            continue
        if r.status_code == 429:
            time.sleep(2 + 3 * attempt)
            continue
        break
    if r is None or r.status_code != 200:
        return None
    rows = r.json().get("results") or []
    if not rows:
        return None
    d = pd.DataFrame(rows)
    t = pd.to_datetime(d["t"], unit="ms", utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
    if span == "day":
        t = t.dt.normalize()
    return pd.DataFrame({"Open": d["o"].astype(float).values, "High": d["h"].astype(float).values,
                         "Low": d["l"].astype(float).values, "Close": d["c"].astype(float).values,
                         "Volume": d["v"].astype(float).values}, index=pd.DatetimeIndex(t.values))


def _join(old, new):
    if old is None:
        return new
    if new is None or not len(new):
        return old
    old = old.copy()
    old.index = pd.DatetimeIndex(old.index)
    if old.index.tz is not None:
        old.index = old.index.tz_localize(None)
    both = pd.concat([old[old.index < new.index[0]], new])
    return both[~both.index.duplicated(keep="last")].sort_index()


def _stock_frames(sym, kind, key):
    try:
        return _stock_frames_(sym, kind, key)
    except Exception:
        return None, None


def _stock_frames_(sym, kind, key):
    fr = S.frames_for(sym, kind)
    h1, d1 = fr.get("1h"), fr.get("1d")
    if h1 is None or d1 is None:
        return None, None
    start = (pd.DatetimeIndex(d1.index)[-1] - pd.Timedelta(days=4)).strftime("%Y-%m-%d")
    return _join(h1, _polygon(sym, "hour", start, key)), _join(d1, _polygon(sym, "day", start, key))


def _session_daily(h1):
    """futures: the daily built from the hourly on the futures clock (18:00-17:00 New York), as in the studies (#50)."""
    sess = pd.DatetimeIndex(h1.index) + pd.Timedelta(hours=6)
    g = h1.groupby(sess.normalize())
    d = pd.DataFrame({"Open": g["Open"].first(), "High": g["High"].max(), "Low": g["Low"].min(),
                      "Close": g["Close"].last(), "Volume": g["Volume"].sum()})
    return d[d.index.dayofweek < 5]


def _frames(h1, d1):
    return {"1h": h1, "1d": d1, "1w": S.resample(d1, S.RULE["1w"])}


def _next_hours(last, kind, n=9):
    out, t = [], pd.Timestamp(last)
    while len(out) < n:
        t = t + pd.Timedelta(hours=1)
        if kind in ("stock", "etf") and (t.dayofweek >= 5 or not (9 <= t.hour <= 15)):
            continue
        out.append(t)
    return out


def armed(sym, kind, fr, sector_daily):
    """Ask the trade code whether the NEXT hour would be a trade if it fell far enough; return its order prices."""
    h1 = fr["1h"]
    last_c = float(h1["Close"].iloc[-1])
    ts = _next_hours(h1.index[-1], kind)
    fake = pd.DataFrame({"Open": last_c, "High": last_c, "Low": last_c * 0.30, "Close": last_c * 0.999,
                         "Volume": float(h1["Volume"].iloc[-20:].mean())}, index=[ts[0]])
    rest = pd.DataFrame({"Open": last_c, "High": last_c, "Low": last_c, "Close": last_c,
                         "Volume": float(h1["Volume"].iloc[-20:].mean())}, index=ts[1:])
    h2 = pd.concat([h1, fake, rest])
    k_new = len(h1)
    if kind in ("stock", "etf"):
        k_new = int(((h2.index.hour >= 9) & (h2.index.hour <= 15))[:len(h1)].sum())
    got = [r for r in PB.trades_for(sym, kind, frames=dict(fr, **{"1h": h2}), sector_daily=sector_daily)
           if r["k"] == k_new]
    if not got:
        return None
    r = got[0]
    return dict(sym=sym, kind=kind, price=last_c, buy_at=r["fills"][0], later=list(zip(r.get("fill_lv", [])[1:], r["fills"][1:])),
                away=100 * (r["fills"][0] / last_c - 1), run_pct=r.get("run_pct"), fresh=r.get("fresh"),
                dollars=r.get("dollars"))


def open_trades(sym, kind, fr, sector_daily):
    h1 = fr["1h"]
    n = len(h1)
    if kind in ("stock", "etf"):
        n = int(((h1.index.hour >= 9) & (h1.index.hour <= 15)).sum())
    out = []
    for r in PB.trades_for(sym, kind, frames=fr, sector_daily=sector_daily):
        if r["how"] != "time ran out" or r["end"] < n - 2 or r["k"] < n - 240:
            continue
        hh = h1[(h1.index.hour >= 9) & (h1.index.hour <= 15)] if kind in ("stock", "etf") else h1
        c = hh["Close"].values.astype(float)
        e12 = float(XM.ema(c, 12)[-1])
        out.append(dict(sym=sym, kind=kind, bought=str(hh.index[r["k"]]), fills=r["fills"], levels=r.get("fill_lv"),
                        entry=r["entry"], now=float(c[-1]), pct_now=100 * (c[-1] / r["entry"] - 1),
                        half_sold=r["half_at"] is not None, half_at=(float(r["half_px"]) if r["half_px"] else e12),
                        stop=float(r["steps"][-1][1]) if r.get("steps") else float(r["stop"]),
                        trim_done=r.get("trim_at") is not None, dollars=r.get("dollars")))
    return out


def _one(args):
    sym, kind, fr, sector = args
    try:
        return armed(sym, kind, fr, sector), open_trades(sym, kind, fr, sector), None
    except Exception as ex:
        return None, [], "%s %s: %s" % (kind, sym, ex)


def _fresh(h1, kind, now):
    """the last bar must be recent, or the name's feed failed and it would show a stale 'open' trade."""
    last = pd.Timestamp(h1.index[-1])
    limit = pd.Timedelta(hours=6) if kind == "crypto" else pd.Timedelta(days=4)
    return now - last <= limit


def tick(log=print):
    t0 = time.time()
    import crypto
    pool = [(s_, k_) for s_, k_ in S.universe()
            if (k_ in ("stock", "etf", "crypto") or (k_ == "futures" and s_ in PB.COMMODITY_FUTURES))
            and s_ not in PB.T.SUSPECT]
    stocks = sorted({s_ for s_, k_ in pool if k_ in ("stock", "etf")})
    futs = sorted({s_ for s_, k_ in pool if k_ == "futures"})
    smap = json.load(open(os.path.join("validation", "sector_map.json")))
    key = json.load(open(os.path.join("livelog", "polygon.json")))["key"]
    import concurrent.futures as cf
    sfr = {}
    kinds = {s_: k_ for s_, k_ in pool if k_ in ("stock", "etf")}
    need = sorted(set(stocks) | {v[0].split("|")[1] for v in smap.values() if v and v[0].startswith("etf|")} | {"SPY"})
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for s_, got in zip(need, ex.map(lambda x: _stock_frames(x, kinds.get(x, "etf"), key), need)):
            sfr[s_] = got
    yrec = _yahoo_recent([FUT_YAHOO(s_) for s_ in futs])
    try:
        cu = crypto.universe(250)
        src = {str(x.sym): x.source for x in cu.itertuples()}
    except Exception:
        src = {}
    arm, opn, errs, seen, stale = [], [], 0, 0, []
    now_ny = pd.Timestamp.now(tz="America/New_York").tz_localize(None)
    now_utc = pd.Timestamp.utcnow().tz_localize(None)
    jobs = []
    for sym, kind in pool:
        try:
            sector = None
            if kind in ("stock", "etf"):
                h1, d1 = sfr.get(sym, (None, None))
                lead = smap.get("%s|%s" % (kind, sym))
                ls_ = lead[0].split("|")[1] if lead and lead[0] != "%s|%s" % (kind, sym) else "SPY"
                sector = (sfr.get(ls_) or (None, None))[1]
            elif kind == "futures":
                h1 = _join(S.frames_for(sym, kind).get("1h"), yrec.get(FUT_YAHOO(sym)))
                d1 = _session_daily(h1) if h1 is not None else None
            else:
                if sym not in src:
                    continue
                h1 = crypto.candles(sym, "1h", 720, source=src[sym])
                d1 = crypto.candles(sym, "1d", 600, source=src[sym])
                for d_ in (h1, d1):
                    if d_ is not None and getattr(d_.index, "tz", None) is not None:
                        d_.index = d_.index.tz_localize(None)
            if h1 is None or d1 is None or len(h1) < 500 or len(d1) < 120:
                continue
            if not _fresh(h1, kind, now_utc if kind == "crypto" else now_ny):
                stale.append(sym)
                continue
            seen += 1
            jobs.append((sym, kind, _frames(h1, d1), sector))
        except Exception:
            errs += 1
    import concurrent.futures as cf
    with cf.ProcessPoolExecutor(max_workers=8) as ex:
        for a, o, err in ex.map(_one, jobs, chunksize=4):
            if a:
                arm.append(a)
            opn += o
            if err:
                errs += 1
    arm.sort(key=lambda x: -x["away"])          # nearest to its buy price first
    out = dict(updated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=seen, errors=errs, stale=stale,
               seconds=int(time.time() - t0), account=PB.ACCOUNT, armed=arm, open=opn)
    os.makedirs("livelog", exist_ok=True)
    json.dump(out, io.open(OUT + ".tmp", "w", encoding="utf-8"), indent=1, default=float)
    os.replace(OUT + ".tmp", OUT)
    log("bb_live: %d names, %d armed, %d open, %d errors, %d stale feeds skipped, %ds" % (
        seen, len(arm), len(opn), errs, len(stale), time.time() - t0))
    return out


if __name__ == "__main__":
    try:
        tick()
    except Exception:
        traceback.print_exc()
