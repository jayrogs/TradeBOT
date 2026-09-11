"""
server.py -- the web app.

    python server.py            then open http://127.0.0.1:5001

PAGES
    /            the desk: your positions, the backburner prints, bid prices
    /scan        the live scanner: crypto / stocks / futures / forex, 8 timeframes
    /markets     the all-market scan produced by bigscan.py
    /validate    grade charts, which is how the engines were built

EVERYTHING IS READ-ONLY. There is no order path anywhere in this file and there
is not meant to be one.

WHY SCANS RUN IN THREADS
A scan is minutes of downloading, far past any web request. Each category keeps
its OWN last finished result and its own age, so switching tabs is instant and
only refetches when that category has gone stale. An earlier version kept a
single slot, so flipping from crypto to stocks and back cleared the table and
started a three-minute rescan every time.
"""

import argparse
import os
import threading as _th
import time
import warnings

import numpy as np
import pandas as pd
from flask import redirect, Flask, jsonify, request, send_file, send_from_directory

import chartweb
import crypto
import desk
import scanner as SC

warnings.filterwarnings("ignore")

app = Flask(__name__, static_folder="static", static_url_path="")
CACHE_TTL = 45          # the desk: one symbol, cheap
SCAN_TTL = 1200         # a full-universe scan is ~8 min; serve it for twenty
VAL = "validation"
BIG = "bigscan_latest.json"

_cache = {}
_lock = _th.Lock()

SCANS = {}
RUNNING = set()
CHANGES = []


def _slot(cat):
    return SCANS.setdefault(cat, {"rows": [], "at": 0, "err": None, "prev": {}})


def num(v):
    """JSON-safe: NaN and numpy scalars are not valid JSON."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(f) else round(f, 6)


# ------------------------------------------------------------------ the desk

def cached(sym, positions):
    now = time.time()
    with _lock:
        hit = _cache.get(sym)
        if hit and now - hit["at"] < CACHE_TTL:
            return hit["data"]
    try:
        r = desk.read(sym, positions)
    except Exception as e:
        r = None
        print("  %s failed: %s" % (sym, e))
    data = serialise(r) if r else {"sym": sym, "error": "no data"}
    with _lock:
        _cache[sym] = {"at": now, "data": data}
    return data


def serialise(r):
    tfs = []
    for lab, _ in desk.TFS:
        t = r["tfs"].get(lab)
        if not t:
            continue
        tfs.append(dict(
            tf=lab, rsi=num(t["rsi"]), livelow=num(t["intra_now"]),
            today=int(t["today_hits"]), today_min=num(t.get("today_min")),
            bid40=num(t["bid40"]), bid35=num(t["bid35"]), bid30=num(t["bid30"]),
            steps=int(t["steps"]), ema12=num(t["ema12"]),
            last_hit=t.get("last_hit") or None))
    lights = [dict(name=n, on=bool(o), detail=d) for n, o, d in desk.lights(r)]
    p = r["pos"]
    return dict(
        sym=r["sym"], px=num(r["px"]), vwap=num(r["vwap"]),
        avg=num(p["avg"]) if p else None,
        shares=num(p.get("shares")) if p else None,
        open_pct=num(100 * (r["px"] / p["avg"] - 1)) if p else None,
        tfs=tfs, lights=lights,
        green=sum(1 for l in lights if l["on"]), total=len(lights),
        rungs=[t["tf"] for t in tfs if t["today"] > 0])


STARTED = time.time()


@app.route("/")
def home():
    """The dashboard: every page, with its live status (owner ask 2026-09-03)."""
    return send_from_directory("static", "home.html")


@app.route("/favicon.ico")
def favicon():
    return ("", 204)


@app.route("/desk")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/home")
def api_home():
    import json as _j
    now = time.time()
    out = dict(now=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
               uptime=int(now - STARTED), scans=[], log={}, bigscan={},
               backburner={}, alerts={}, gen={}, alpaca=False, universe=0,
               stock_history=0, tests=None)
    for key, v in sorted(SCANS.items()):
        out["scans"].append(dict(key=key, rows=len(v["rows"]), n=v.get("n"),
                                 running=key in RUNNING,
                                 age=int(now - v["at"]) if v["at"] else None))
    try:
        st = _j.load(open(os.path.join("livelog", "status.json")))
        sig = os.path.join("livelog", "signals.csv")
        total = open_ = 0
        if os.path.exists(sig):
            d = pd.read_csv(sig)
            total = len(d)
            if "exit_at" in d:
                open_ = int(d["exit_at"].isna().sum()
                            + (d["exit_at"].astype(str).str.strip() == "").sum())
        out["log"] = dict(last_tick=st.get("last_tick"), open=open_, total=total)
    except Exception:
        pass
    try:
        p = BIG
        rows = _j.load(open(p))
        rows = rows["rows"] if isinstance(rows, dict) else rows
        out["bigscan"] = dict(rows=len(rows), at=pd.Timestamp.fromtimestamp(
            os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M"))
    except Exception:
        pass
    try:
        li = _j.load(open(os.path.join(VAL, "backburner_index.json")))
        out["backburner"] = dict(items=len(li.get("items", [])), live=li.get("live", 0),
                             generated=li.get("generated"))
    except Exception:
        pass
    try:
        st = _j.load(open(os.path.join(VAL, "backburner_study.json")))["meta"]
        out["study"] = dict(campaigns=st.get("campaigns"), names=st.get("names"),
                            generated=st.get("generated"))
    except Exception:
        out["study"] = {}
    try:
        out["bb"] = _j.load(open(os.path.join("livelog", "bb_status.json")))
    except Exception:
        out["bb"] = {}
    try:
        out["rides"] = _j.load(open(os.path.join("livelog", "ride_status.json")))
    except Exception:
        out["rides"] = {}
    try:
        out["alerts"] = dict(webhook=bool(_j.load(open(
            os.path.join("livelog", "alerts.json"))).get("webhook")))
    except Exception:
        out["alerts"] = dict(webhook=False)
    try:
        import alpaca
        out["alpaca"] = bool(alpaca.enabled())
    except Exception:
        pass
    try:
        out["universe"] = len(_j.load(open(os.path.join(crypto.CACHE, "universe.json"))))
    except Exception:
        pass
    try:
        out["stock_history"] = len([f for f in os.listdir(os.path.join("history", "stocks"))
                                    if f.endswith(".csv.gz")])
    except Exception:
        pass
    try:
        out["gen"] = api_gen().get_json()
    except Exception:
        pass
    try:
        p = os.path.join("logs", "tests_last.txt")
        out["tests"] = open(p).read().strip()[:80] if os.path.exists(p) else None
    except Exception:
        pass
    for key, fn, pick in (("trendnames", "trend_names.json", lambda j: dict(generated=j.get("generated"), names=len({r["sym"] for r in j.get("rows", [])}))),
                          ("ridecharts", "ride_cases_index.json", lambda j: dict(generated=j.get("generated"), items=len(j.get("items", [])))),
                          ("trends", "trend_ride.json", lambda j: dict(generated=j.get("meta", {}).get("generated")))):
        try:
            out[key] = pick(_j.load(open(os.path.join(VAL, fn))))
        except Exception:
            out[key] = {}
    try:
        e_ = _j.load(open(os.path.join("livelog", "eq_scan.json")))
        out["eq"] = dict(last_tick=e_.get("last_tick"), ranges=len(e_.get("rows", [])),
                         floor=sum(1 for r in e_.get("rows", []) if r.get("zone") == "at the floor"))
    except Exception:
        out["eq"] = {}
    return jsonify(out)


@app.route("/api/desk")
def api_desk():
    positions = desk.load_positions()
    watch = request.args.get("watch")
    syms = ([s.strip().upper() for s in watch.split(",") if s.strip()] if watch
            else sorted(positions))
    if not syms:
        syms = ["MRNA"]
    rows = [cached(s, positions) for s in syms]
    return jsonify(dict(
        ts=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        ttl=CACHE_TTL, symbols=syms, rows=rows,
        note="assistant only -- lights are the described conditions, "
             "not validated"))


@app.route("/api/positions", methods=["GET", "POST"])
def api_positions():
    if request.method == "GET":
        return jsonify(desk.load_positions())
    body = request.get_json(force=True, silent=True) or {}
    clean = []
    for r in body.get("positions", []):
        s = str(r.get("symbol", "")).upper().strip()
        if not s:
            continue
        try:
            clean.append(dict(symbol=s, avg=float(r.get("avg") or 0),
                              shares=float(r.get("shares") or 0)))
        except (TypeError, ValueError):
            continue
    pd.DataFrame(clean, columns=["symbol", "avg", "shares"]).to_csv(
        desk.POSFILE, index=False)
    with _lock:
        _cache.clear()
    return jsonify(dict(ok=True, saved=len(clean)))


# ------------------------------------------------------------- the scanner

_MOVERS = {"at": 0, "rows": None}


def _stock_movers(n, min_dollar=2e6, ttl=600):
    """Today's biggest gainers among every liquid US name (tier1, ~4,400):
    one batched daily download, ranked by the last close over the prior
    close. Cached ten minutes. The 'am I missing a great mover' pass."""
    if _MOVERS["rows"] is not None and time.time() - _MOVERS["at"] < ttl:
        return _MOVERS["rows"][:n]
    import yfinance as yf
    p = os.path.join("cache", "tier1.csv")
    if not os.path.exists(p):
        return []
    k = pd.read_csv(p)
    # equities only: leveraged single-stock ETFs (MSTX, HOOG, CRCG...) would
    # otherwise own the top of every movers list, and they are just 2x the
    # stock that is already on it
    syms = k[k.kind == "equity"].symbol.dropna().astype(str).tolist()
    out = []
    for i in range(0, len(syms), 300):
        part = syms[i:i + 300]
        try:
            d = yf.download(part, interval="1d", period="5d", progress=False,
                            auto_adjust=False, group_by="ticker", threads=True)
        except Exception:
            continue
        for s in part:
            try:
                f = (d[s] if len(part) > 1 else d).dropna()
                if len(f) < 2:
                    continue
                c0, c1 = float(f["Close"].iloc[-2]), float(f["Close"].iloc[-1])
                dollar = c1 * float(f["Volume"].iloc[-1])
                if c0 > 0 and dollar >= min_dollar:
                    out.append((s, c1 / c0 - 1.0))
            except Exception:
                continue
    out.sort(key=lambda x: -x[1])
    _MOVERS["rows"] = [(s, "yahoo") for s, _ in out]
    _MOVERS["at"] = time.time()
    return _MOVERS["rows"][:n]


def _universe_for(cat, n, rank="volume"):
    """(symbol, source) pairs for one asset class. rank='movers' orders by
    24h change (crypto: every Coinbase/Kraken name over $1M; stocks: every
    tier1 name) instead of by volume."""
    if cat == "crypto":
        u = (crypto.universe(n, min_volume=1e6, rank="movers")
             if rank == "movers" else crypto.universe(n))
        return [(x["sym"], x["source"]) for _, x in u.iterrows()]
    if cat == "stocks" and rank == "movers":
        return _stock_movers(n)
    if cat in ("futures", "forex"):
        import bigscan
        lst = bigscan.FUTURES if cat == "futures" else bigscan.FOREX
        return [(s, "yahoo") for s in lst]
    if cat == "stocks":
        # tier1.csv is the liquidity pass bigscan already did: >= $2M a day and
        # >= 0.5% of daily range. Take the most liquid n.
        p = os.path.join("cache", "tier1.csv")
        if not os.path.exists(p):
            return []
        k = pd.read_csv(p)
        k = k[k.kind.isin(["equity", "etf"])].dropna(subset=["dollar"])
        k = k.sort_values("dollar", ascending=False).head(n)
        # Yahoo by default: consolidated volume, one batch call per base.
        # Alpaca's free feed is IEX-only volume (~2% of consolidated) and
        # pages by calendar span, so it is slower AND breaks volume flags.
        # Opt in with "scanner": true in livelog/alpaca.json if ever wanted.
        import alpaca
        src = "alpaca" if (alpaca.enabled() and alpaca.opt("scanner")) else "yahoo"
        return [(r.symbol, src) for r in k.itertuples()]
    return []


def _prefetch(pairs):
    """All the base bars for a category, in as few round trips as possible."""
    pre = {}
    yh = [s for s, src in pairs if src == "yahoo"]
    if yh:
        import yfinance as yf
        # One request per base timeframe for the WHOLE list. One symbol at a
        # time took over seven minutes for 57 futures.
        for base, period in (("5m", "1mo"), ("15m", "59d"),
                             ("1h", "2y"), ("1d", "10y")):
            try:
                d = yf.download(yh, interval=base, period=period,
                                progress=False, auto_adjust=False, prepost=True,
                                group_by="ticker", threads=True)
            except Exception:
                continue
            for sym in yh:
                try:
                    f = d[sym].dropna() if len(yh) > 1 else d.dropna()
                except Exception:
                    continue
                if getattr(f.index, "tz", None) is not None:
                    f.index = f.index.tz_localize(None)
                if len(f) >= 40:
                    pre[(sym, base)] = f

    al = [s for s, src in pairs if src == "alpaca"]
    if al:
        import alpaca
        # one paginated pull per base timeframe for the whole list
        for base in ("5m", "15m", "1h", "1d"):
            try:
                got = alpaca.scan_bars(al, base)
            except Exception as e:
                print("  alpaca %s failed: %s" % (base, e))
                continue
            for sym, f in got.items():
                if len(f) >= 40:
                    pre[(sym, base)] = f

    cx = [(s, src) for s, src in pairs if src not in ("yahoo", "alpaca")]
    if cx:
        # Crypto is one HTTP call per (name, base). Thirty names x four bases
        # was 120 sequential requests and 195 seconds; a small pool makes it
        # about twenty. Coinbase tolerates ~10 req/s, so eight workers is safe.
        from concurrent.futures import ThreadPoolExecutor
        jobs = [(s, src, b) for s, src in cx
                for b in ("5m", "15m", "1h", "1d")]

        def grab(job):
            sym, src, b = job
            try:
                return (sym, b), SC._crypto_fetch(sym, src, b)
            except Exception:
                return (sym, b), None

        with ThreadPoolExecutor(max_workers=8) as ex:
            for key, df in ex.map(grab, jobs):
                if df is not None:
                    pre[key] = df
    return pre


def _chg_day(fr, cat):
    """The 24h column, from the bars we already fetched: crypto trades
    around the clock so it is the close 24 hourly bars back; everything
    else is versus the prior DAILY close. Was hard-coded 0.0 (2026-09-03)."""
    try:
        d, k = (fr.get("1h"), 24) if cat == "crypto" else (fr.get("1d"), 1)
        c = d["Close"].values.astype(float)
        if len(c) > k and c[-1 - k] > 0:
            return round(100.0 * (c[-1] / c[-1 - k] - 1.0), 2)
    except Exception:
        pass
    return 0.0


def _key(cat, rank):
    return cat + (":movers" if rank == "movers" else "")


def _run_scan(cat="crypto", n=30,
              tfs=("5m", "15m", "1h", "4h", "12h", "1d", "1w", "1mo"),
              rank="volume"):
    key = _key(cat, rank)
    slot = _slot(key)
    try:
        pairs = _universe_for(cat, n, rank)
        if not pairs:
            slot["err"] = ("no stocks universe -- run: python bigscan.py "
                           "--tier1-only" if cat == "stocks"
                           else "no %s universe" % cat)
            return
        pre = _prefetch(pairs)

        def prefetched(sym, source, base):
            return pre.get((sym, base))

        rows = []
        for urank, (sym, src) in enumerate(pairs):
            fr = SC.frames_for(sym, src, list(tfs), prefetched)
            data = {}
            for t in tfs:
                try:
                    data[t] = SC.read_tf(fr.get(t))
                except Exception:
                    data[t] = None
            if not any(data.values()):
                continue
            fl = SC.flags(data)
            last = next((v for v in data.values() if v), {})
            # urank = position in the ranked universe, so a smaller "top N"
            # is a filter on this result instead of another scan.
            # source = the exchange the name is listed on for us; feeds =
            # every exchange that actually served a base frame this scan
            # (a Kraken name's deep frames may come from OKX)
            feeds = sorted({pre[(sym, b)].attrs.get("source")
                            for b in ("5m", "15m", "1h", "1d")
                            if (sym, b) in pre and pre[(sym, b)] is not None
                            and pre[(sym, b)].attrs.get("source")})
            rows.append(dict(sym=sym, price=last.get("close"), volume=0,
                             chg24=_chg_day(fr, cat), kind=cat, tfs=data,
                             urank=urank, source=src, feeds=feeds,
                             flags=[{"key": k, "why": w, "wt": t}
                                    for k, w, t in fl],
                             score=SC.score(fl)))
        rows.sort(key=lambda r: -r["score"])

        # what STARTED firing since this category's last completed scan
        now = {r["sym"]: {f["key"] for f in r["flags"] if f["wt"]} for r in rows}
        was = slot["prev"] or {}
        fresh = []
        for sym, keys in now.items():
            if sym not in was:
                continue
            for k in sorted(keys - was[sym]):
                why = next((f["why"] for r in rows if r["sym"] == sym
                            for f in r["flags"] if f["key"] == k), k)
                fresh.append({"sym": sym, "cat": cat, "key": k, "why": why,
                              "at": pd.Timestamp.now().strftime("%H:%M:%S")})
        slot["prev"] = now
        CHANGES[:] = (fresh + CHANGES)[:40]
        slot["rows"] = rows
        slot["err"] = None
    except Exception as e:
        slot["err"] = "%s: %s" % (type(e).__name__, e)
    finally:
        slot["at"] = time.time()
        slot["n"] = n
        RUNNING.discard(key)


def _kick(cat="crypto", n=30, rank="volume"):
    key = _key(cat, rank)
    if key in RUNNING:
        return
    RUNNING.add(key)
    _th.Thread(target=_run_scan, args=(cat, n), kwargs=dict(rank=rank),
               daemon=True).start()


@app.route("/scan")
def scan_page():
    return send_from_directory("static", "scan.html")


@app.route("/api/scan")
def api_scan():
    n = max(10, min(400, int(request.args.get("n", 30))))
    cat = request.args.get("cat", "crypto")
    rank = "movers" if request.args.get("rank") == "movers" else "volume"
    key = _key(cat, rank)
    slot = _slot(key)
    stale = time.time() - slot["at"] > SCAN_TTL
    have = slot.get("n") or 0
    # a scan covers the WIDEST size asked for; a smaller "top N" is served
    # by filtering, instantly. Only asking for more than we have rescans.
    if request.args.get("refresh") == "1" or stale or n > have:
        _kick(cat, max(n, have), rank)
    rows = [r for r in slot["rows"] if r.get("urank", 0) < n]
    return jsonify(dict(
        rows=rows, changes=CHANGES, running=key in RUNNING,
        err=slot["err"], cat=cat, rank=rank, n=slot.get("n"), want=n,
        age=int(time.time() - slot["at"]) if slot["at"] else None,
        at=(pd.Timestamp.fromtimestamp(slot["at"]).strftime("%H:%M:%S")
            if slot["at"] else None),
        ready=sorted(c for c, v in SCANS.items() if v["rows"])))


# ------------------------------------------------------------- all markets

# A scan written by an older build carries no weights and no score. Rebuild
# both from the flag keys rather than showing a blank page.
WT = {"rider-dip": 5, "rider-": 5, "backburner-5m": 5, "backburner-15m": 4,
      "ladder-5m": 5, "ladder-15m": 4,   # old key, older scan files
      "backburner": 5, "dip-15m": 4, "riding-1d": 4, "riding-12h": 3,
      "riding-4h": 3, "riding-1h": 3, "riding-15m": 2, "riding-": 2,
      "eq-1w": 4, "eq-1d": 4, "eq-12h": 3, "eq-4h": 3, "eq-1h": 2,
      "eq-15m": 1, "eq-": 2, "trend-up": 2, "trend-down": 2, "trend-up1": 1,
      "hist-os": 2, "hist-ob": 1, "stair-": 0}


def _weight(key):
    if key in WT:
        return WT[key]
    for pre, w in WT.items():
        if pre.endswith("-") and key.startswith(pre):
            return w
    return 1


@app.route("/markets")
def markets_page():
    return send_from_directory("static", "markets.html")


@app.route("/api/bigscan")
def api_bigscan():
    if not os.path.exists(BIG):
        return jsonify(dict(rows=[], total=0, kinds=[], flags=[],
                            err="no scan yet -- run: python bigscan.py", at=None))
    import json as _j
    try:
        allrows = _j.load(open(BIG))
    except Exception as e:
        return jsonify(dict(rows=[], total=0, kinds=[], flags=[],
                            err=str(e), at=None))

    for r in allrows:
        for f in r.get("flags", []):
            if "wt" not in f:
                f["wt"] = _weight(f["key"])
        if "score" not in r:
            r["score"] = sum(f["wt"] for f in r.get("flags", []))

    rows = allrows
    kind = request.args.get("kind")
    want = request.args.get("flag")
    if kind and kind != "all":
        rows = [r for r in rows if r.get("kind") == kind]
    if want and want != "all":
        rows = [r for r in rows
                if any(f["key"].startswith(want) for f in r.get("flags", []))]
    rows = [r for r in rows if r.get("score", 0) >= int(request.args.get("min", 0))]
    rows.sort(key=lambda r: -r.get("score", 0))
    mt = os.path.getmtime(BIG)
    return jsonify(dict(
        rows=rows[:400], total=len(rows),
        kinds=sorted({r.get("kind") for r in allrows if r.get("kind")}),
        flags=sorted({f["key"].rsplit("-", 1)[0] for r in allrows
                      for f in r.get("flags", []) if f.get("wt")}),
        at=pd.Timestamp.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M"),
        age_min=int((time.time() - mt) / 60), err=None))


# ------------------------------------------------------------------ charts

@app.route("/api/chart.png")
def api_chart():
    """Our chart: trend shading, pivots, the level, the rider and its dips."""
    sym = request.args.get("sym", "").upper()
    kind = request.args.get("kind", "equity")
    tf = request.args.get("tf", "5m")
    if not sym:
        return "no symbol", 400
    try:
        buf = chartweb.png(sym, kind, tf)
    except Exception as e:
        print("  chart %s failed: %s" % (sym, e))
        buf = None
    if buf is None:
        return "no data", 404
    return send_file(buf, mimetype="image/png")


@app.route("/api/tvlink")
def api_tvlink():
    sym = request.args.get("sym", "").upper()
    kind = request.args.get("kind", "equity")
    tf = request.args.get("tf", "5m")
    return jsonify(dict(url=chartweb.tv_url(sym, kind, tf),
                        symbol=chartweb.tv_symbol(sym, kind),
                        name=chartweb.display_name(sym, kind)))


# ------------------------------------------------------- trend validation


@app.route("/api/tradenote", methods=["GET", "POST"])
def api_tradenote():
    """Notes left on the trade charts. One row per chart, overwritten in place.
    Optional `set` (e.g. "backburner") keeps each grading round in its own file."""
    b = {} if request.method == "GET" else (request.get_json(force=True, silent=True) or {})
    raw = request.args.get("set") if request.method == "GET" else b.get("set")
    set_ = "".join(ch for ch in str(raw or "").lower() if ch.isalnum())
    path = os.path.join(VAL, "trade_notes%s.csv" % ("_" + set_ if set_ else ""))
    if request.method == "GET":
        if not os.path.exists(path):
            return jsonify({})
        d = pd.read_csv(path, dtype={"n": str})
        return jsonify({str(r.n): ("" if pd.isna(r.note) else str(r.note))
                        for r in d.itertuples()})
    # `key`/`text` are accepted too: pages written 2026-09-09/10 sent those names and every save was rejected
    n = str(b.get("n") or b.get("key") or "").strip()[:80]
    if not n:
        return jsonify(dict(ok=False)), 400
    rows = pd.read_csv(path, dtype={"n": str}).to_dict("records") if os.path.exists(path) else []
    rows = [r for r in rows if str(r["n"]) != n]
    rows.append(dict(n=n, note=str(b.get("note", b.get("text", "")))[:2000],
                     at=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")))
    pd.DataFrame(rows).sort_values("n").to_csv(path, index=False)
    return jsonify(dict(ok=True, saved=len(rows)))


@app.route("/v4")
def v4_page():
    return send_from_directory("static", "v4trades.html")


@app.route("/trades")
def trades_page():
    return send_from_directory("static", "trades.html")


@app.route("/backburner")
def backburner_page():
    return send_from_directory("static", "backburner.html")


@app.route("/study")
def study_page():
    return send_from_directory("static", "study.html")


@app.route("/trends")
def trends_page():
    return send_from_directory("static", "trends.html")


@app.route("/trendcases")
def trendcases_page():
    return send_from_directory("static", "trendcases.html")


@app.route("/exitcharts")
def exitcharts_page():
    return send_from_directory("static", "exitcharts.html")


@app.route("/ridecharts")
def ridecharts_page():
    return send_from_directory("static", "ridecharts.html")


@app.route("/trendstudy")
def trendstudy_page():
    return send_from_directory("static", "trendstudy.html")


@app.route("/trendnames")
def trendnames_page():
    return redirect("/trendstudy", code=302)      # old name


@app.route("/rules")
def rules_page():
    """The one rules file, readable in the browser."""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CLAUDE.md")
    txt = open(p, encoding="utf-8").read() if os.path.exists(p) else "no CLAUDE.md"
    import html as _h
    body = "<!doctype html><meta charset=utf-8><title>The rules</title><style>body{background:#0d0f12;color:#e6e9ee;font:14px/1.55 -apple-system,Segoe UI,Roboto,sans-serif;max-width:900px;margin:0 auto;padding:28px 22px}pre{white-space:pre-wrap;font:13px/1.6 ui-monospace,Consolas,monospace;color:#c9ced6}a{color:#5aa9ff}</style>"
    body += "<a href='/'>&larr; dashboard</a><h1 style='font-size:18px'>The rules (CLAUDE.md)</h1><pre>%s</pre>" % _h.escape(txt)
    return body


@app.route("/trendstudy/<kind>/<sym>")
def trendstudy_name_page(kind, sym):
    return send_from_directory("static", "trendstudy_name.html")


@app.route("/trendname/<kind>/<sym>")
def trendname_page(kind, sym):
    return redirect("/trendstudy/%s/%s" % (kind, sym), code=302)   # old name


@app.route("/api/trend_window")
def api_trend_window():
    """Draw one trend (up or down) from the trend study, with its floor/ceiling and the bar that ended it."""
    sym = "".join(ch for ch in request.args.get("sym", "") if ch.isalnum() or ch in "-_.=")
    kind = "".join(ch for ch in request.args.get("kind", "") if ch.isalpha())
    tf = "".join(ch for ch in request.args.get("tf", "") if ch.isalnum())
    try:
        t0 = pd.Timestamp(request.args.get("s", "")); t1 = pd.Timestamp(request.args.get("e", ""))
    except Exception:
        return jsonify(dict(ok=False, error="bad time")), 400
    folder = os.path.join(VAL, "trend_windows")
    os.makedirs(folder, exist_ok=True)
    fn = "%s_%s_%s_%s.png" % (kind, sym, tf, t0.strftime("%Y%m%d%H%M"))
    path = os.path.join(folder, fn)
    if not os.path.exists(path):
        import pics_trendwin as PW
        import pics_ride as PR
        with _CHART_LOCK:
            key = ("trend", kind, sym)
            hit = _FRAMES_CACHE.get(key)
            if hit is None or time.time() - hit[0] > 900:
                frames = PR.S.frames_for(sym, kind)
                _FRAMES_CACHE.clear()
                _FRAMES_CACHE[key] = (time.time(), frames)
            frames = _FRAMES_CACHE[key][1]
            if tf not in frames:
                return jsonify(dict(ok=False, error="no %s history for %s" % (tf, sym))), 404
            try:
                row = PW.render(sym, kind, tf, frames, t0, t1, path)
            except Exception as ex:
                return jsonify(dict(ok=False, error=str(ex))), 500
            if row is None:
                return jsonify(dict(ok=False, error="could not find that trend in the history")), 404
    return jsonify(dict(ok=True, url="/validation/trend_windows/%s" % fn))


@app.route("/api/trend_chart")
def api_trend_chart():
    """Draw one trend ride from the study on demand (same drawing as /ridecharts)."""
    sym = "".join(ch for ch in request.args.get("sym", "") if ch.isalnum() or ch in "-_.=")
    kind = "".join(ch for ch in request.args.get("kind", "") if ch.isalpha())
    tf = "".join(ch for ch in request.args.get("tf", "") if ch.isalnum())
    try:
        ts = pd.Timestamp(request.args.get("t", ""))
    except Exception:
        return jsonify(dict(ok=False, error="bad time")), 400
    folder = os.path.join(VAL, "trend_cases")
    os.makedirs(folder, exist_ok=True)
    fn = "%s_%s_%s_%s.png" % (kind, sym, tf, ts.strftime("%Y%m%d%H%M"))
    path = os.path.join(folder, fn)
    if not os.path.exists(path):
        import pics_ride as PR
        with _CHART_LOCK:
            key = ("trend", kind, sym)
            hit = _FRAMES_CACHE.get(key)
            if hit is None or time.time() - hit[0] > 900:
                frames = PR.S.frames_for(sym, kind)
                _FRAMES_CACHE.clear()
                _FRAMES_CACHE[key] = (time.time(), frames)
            frames = _FRAMES_CACHE[key][1]
            if tf not in frames:
                return jsonify(dict(ok=False, error="no %s history for %s" % (tf, sym))), 404
            try:
                row = PR.render(sym, kind, tf, ts, frames, "from the trend study", path)
            except Exception as ex:
                return jsonify(dict(ok=False, error=str(ex))), 500
            if row is None:
                return jsonify(dict(ok=False, error="that trade did not resolve inside the history")), 404
    return jsonify(dict(ok=True, url="/validation/trend_cases/%s" % fn))


@app.route("/cases")
def cases_page():
    return send_from_directory("static", "cases.html")


@app.route("/names")
def names_page():
    return send_from_directory("static", "names.html")


@app.route("/name/<kind>/<sym>")
def name_page(kind, sym):
    return send_from_directory("static", "name.html")


_CHART_LOCK = _th.Lock()
_FRAMES_CACHE = {}          # (kind, sym) -> (loaded_at, frames)


@app.route("/api/name_chart")
def api_name_chart():
    """Draw one backburner from the 4-year study on demand (same drawing as
    /cases) and return its image path. Cached on disk under validation/name_cases."""
    sym = "".join(ch for ch in request.args.get("sym", "") if ch.isalnum() or ch in "-_.=")
    kind = "".join(ch for ch in request.args.get("kind", "") if ch.isalpha())
    tf = "".join(ch for ch in request.args.get("tf", "") if ch.isalnum())
    t = request.args.get("t", "")
    try:
        ts = pd.Timestamp(t)
    except Exception:
        return jsonify(dict(ok=False, error="bad time")), 400
    folder = os.path.join(VAL, "name_cases")
    os.makedirs(folder, exist_ok=True)
    fn = "%s_%s_%s_%s.png" % (kind, sym, tf, ts.strftime("%Y%m%d%H%M"))
    path = os.path.join(folder, fn)
    if not os.path.exists(path):
        import pics_cases as PC
        with _CHART_LOCK:
            key = (kind, sym)
            hit = _FRAMES_CACHE.get(key)
            if hit is None or time.time() - hit[0] > 900:
                frames = PC.S.frames_for(sym, kind)
                _FRAMES_CACHE.clear()
                _FRAMES_CACHE[key] = (time.time(), frames)
            frames = _FRAMES_CACHE[key][1]
            if tf not in frames:
                return jsonify(dict(ok=False, error="no %s history for %s" % (tf, sym))), 404
            try:
                row = PC.render(0, sym, kind, tf, ts, frames, "", "from the 4-year study", path=path)
            except Exception as ex:
                return jsonify(dict(ok=False, error=str(ex))), 500
            if row is None:
                return jsonify(dict(ok=False, error="that campaign did not resolve inside the history")), 404
    return jsonify(dict(ok=True, url="/validation/name_cases/%s" % fn))


@app.route("/bb")
def bb_page():
    return send_from_directory("static", "bb.html")


@app.route("/eq")
def eq_page():
    return send_from_directory("static", "eq.html")


@app.route("/eqfree")
def eqfree_page():
    return send_from_directory("static", "eqfree.html")


@app.route("/eqtrades")
def eqtrades_page():
    return send_from_directory("static", "eqtrades.html")


@app.route("/eqcoils")
def eqcoils_page():
    return send_from_directory("static", "eqcoils.html")


@app.route("/eqcharts")
def eqcharts_page():
    return send_from_directory("static", "eqcharts.html")


_EQ_CHART_LOCK = _th.Lock()


@app.route("/api/eq_chart/<kind>/<sym>/<tf>")
def api_eq_chart(kind, sym, tf):
    """Draw one live range on demand (the picture for a row on /eq). Cached for 5 minutes
    per name and chart size. ?json=1 returns the story and the measured problems instead."""
    import time as _t
    import json as _j
    from flask import request, send_file, abort
    if tf not in ("5m", "15m", "1h", "4h", "1d", "1w") or not sym.replace("_", "").replace("-", "").isalnum():
        abort(404)
    folder = os.path.join("livelog", "eq_charts"); os.makedirs(folder, exist_ok=True)
    base = os.path.join(folder, "%s_%s_%s" % (kind, sym, tf))
    png, meta = base + ".png", base + ".json"
    fresh = os.path.exists(png) and os.path.exists(meta) and _t.time() - os.path.getmtime(png) < 300
    if not fresh:
        with _EQ_CHART_LOCK:
            fresh = os.path.exists(png) and os.path.exists(meta) and _t.time() - os.path.getmtime(png) < 300
            if not fresh:
                import eq_scan, pics_eq
                frames = eq_scan.frames_for_one(sym, kind)
                info = pics_eq.render_live(sym, kind, tf, frames, png) if frames else None
                if info is None:
                    info = dict(story="No data for this chart right now.", problems=[], png=False)
                _j.dump(info, open(meta, "w"))
    info = _j.load(open(meta))
    if request.args.get("json"):
        return jsonify(info)
    if not info.get("png") or not os.path.exists(png):
        abort(404)
    return send_file(os.path.abspath(png), mimetype="image/png", max_age=0)


@app.route("/livelog/eq_scan.json")
def eq_scan_json():
    p = os.path.join("livelog", "eq_scan.json")
    if not os.path.exists(p):
        return jsonify(dict(rows=[], names=0, last_tick=None, seconds=0)), 200
    return send_file(p, mimetype="application/json")


@app.route("/api/focus")
def api_focus():
    import focus
    return jsonify(list(focus.names()))


@app.route("/rides")
def rides_page():
    return send_from_directory("static", "rides.html")


@app.route("/api/rides")
def api_rides():
    import json as _j
    p = os.path.join("livelog", "ride_campaigns.csv")
    rows = pd.read_csv(p, dtype={"id": str}).replace({np.nan: None}).to_dict("records") if os.path.exists(p) else []
    st = {}
    try:
        st = _j.load(open(os.path.join("livelog", "ride_status.json")))
    except Exception:
        pass
    return jsonify(dict(rows=rows, status=st))


@app.route("/api/bb")
def api_bb():
    import json as _j
    p = os.path.join("livelog", "bb_campaigns.csv")
    rows = pd.read_csv(p).replace({np.nan: None}).to_dict("records") if os.path.exists(p) else []
    st = {}
    try:
        st = _j.load(open(os.path.join("livelog", "bb_status.json")))
    except Exception:
        pass
    return jsonify(dict(rows=rows, status=st))


@app.route("/ladder")
def ladder_redirect():
    from flask import redirect
    return redirect("/backburner")


@app.route("/validate")
def validate_page():
    return send_from_directory("static", "validate.html")


@app.route("/validation/<path:fn>")
def validation_file(fn):
    return send_from_directory(VAL, fn)


@app.route("/api/manifest")
def api_manifest():
    p = os.path.join(VAL, "manifest.json")
    if not os.path.exists(p):
        return jsonify(dict(items=[], error="run: python validate_trend.py"))
    import json as _j
    man = _j.load(open(p))
    done = {}
    g = os.path.join(VAL, "grades.csv")
    if os.path.exists(g):
        for r in pd.read_csv(g).itertuples():
            done[int(r.id)] = dict(verdict=str(r.verdict),
                                   note=("" if pd.isna(r.note) else str(r.note)))
    man["graded"] = done
    return jsonify(man)


@app.route("/api/grade", methods=["POST"])
def api_grade():
    """Append one verdict. Rewrites the row if that chart was graded before."""
    b = request.get_json(force=True, silent=True) or {}
    try:
        cid = int(b.get("id"))
    except (TypeError, ValueError):
        return jsonify(dict(ok=False, error="bad id")), 400
    path = os.path.join(VAL, "grades.csv")
    rows = pd.read_csv(path).to_dict("records") if os.path.exists(path) else []
    rows = [r for r in rows if int(r["id"]) != cid]
    rows.append(dict(id=cid, verdict=str(b.get("verdict", ""))[:20],
                     note=str(b.get("note", ""))[:500],
                     at=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")))
    pd.DataFrame(rows).sort_values("id").to_csv(path, index=False)
    return jsonify(dict(ok=True, graded=len(rows)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5001)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--log", default=None, help="write output here (so it can run under pythonw, "
                                                "with no console window popping up)")
    a = ap.parse_args()
    if a.log:
        import sys
        os.makedirs(os.path.dirname(a.log) or ".", exist_ok=True)
        sys.stdout = sys.stderr = open(a.log, "a", buffering=1, encoding="utf-8", errors="replace")
    print("desk running at http://%s:%d" % (a.host, a.port))
    app.run(host=a.host, port=a.port, debug=False, threaded=True)



@app.route("/log")
def log_page():
    return app.send_static_file("log.html")


@app.route("/api/log")
def api_log():
    import signal_log
    d = signal_log._load()
    rows = d.tail(300).fillna("").to_dict("records") if len(d) else []
    return jsonify(dict(signals=rows, summary=signal_log.summary(),
                        heartbeat=signal_log.last_tick()))


@app.route("/api/log/tick", methods=["POST"])
def api_log_tick():
    import signal_log
    added, closed = signal_log.tick()
    return jsonify(dict(added=added, closed=closed))


@app.route("/api/mytrade", methods=["GET", "POST"])
def api_mytrade():
    import signal_log
    path = signal_log.MY
    if request.method == "GET":
        if not os.path.exists(path):
            return jsonify([])
        return jsonify(pd.read_csv(path).fillna("").to_dict("records"))
    b = request.get_json(force=True, silent=True) or {}
    row = dict(at=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
               sym=str(b.get("sym", ""))[:12].upper(),
               side=str(b.get("side", "long"))[:6],
               entry=str(b.get("entry", ""))[:16],
               exit=str(b.get("exit", ""))[:16],
               note=str(b.get("note", ""))[:400])
    rows = (pd.read_csv(path).to_dict("records")
            if os.path.exists(path) else [])
    rows.append(row)
    os.makedirs(signal_log.DIR, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)
    return jsonify(dict(ok=True, n=len(rows)))


def _bb_loop():
    """Backburner forward log: one tick every 15 minutes (the 15m bar is the
    fastest chart it tracks), a minute after the bar closes."""
    import traceback
    last = None
    while True:
        try:
            now = pd.Timestamp.now()
            slot = now.floor("15min")
            if last is None or (slot > last and now.minute % 15 >= 1):
                last = slot                      # claim the slot first: a failed tick waits for the next one, no retry storm
                import backburner_log
                backburner_log.tick(log=lambda m: print(m, flush=True))
        except Exception:
            traceback.print_exc()
        time.sleep(20)


def _ride_loop():
    """Trend rides, live: one tick every 15 minutes, two minutes after the
    bar closes (a minute after the backburner tick so they do not fight over
    the same fetches)."""
    import traceback
    last = None
    while True:
        try:
            now = pd.Timestamp.now()
            slot = now.floor("15min")
            if last is None or (slot > last and now.minute % 15 >= 2):
                last = slot                      # claim the slot first: a failed tick waits for the next one, no retry storm
                import ride_log
                ride_log.tick(log=lambda m: print(m, flush=True))
        except Exception:
            traceback.print_exc()
        time.sleep(20)


def _eq_loop():
    """The range scan: one tick after another, every market, every chart size (a tick
    is a few minutes, most of it fetching), so the page is as current as the feeds allow."""
    import traceback
    while True:
        try:
            import eq_scan
            eq_scan.tick(log=lambda m: print(m, flush=True))
        except Exception:
            traceback.print_exc()
        time.sleep(60)


def _live_loop():
    """Hourly forward-test tick: scan for new signals, settle outcomes."""
    import signal_log
    import traceback
    last_hour = None
    while True:
        try:
            now = pd.Timestamp.now(tz="UTC")
            hour = now.floor("h")
            if last_hour is None or (hour > last_hour and now.minute >= 3):
                added, closed = signal_log.tick()
                last_hour = hour
                # a bot you don't have to open: every new forward-log signal
                # and every settled one goes out through notify (log file
                # always; webhook if livelog/alerts.json has one)
                if added or closed:
                    import notify
                    d = signal_log._load()
                    if added:
                        for _, r in d.tail(added).iterrows():
                            notify.alert("SIGNAL %s %s  fill %s  wind %s  "
                                         "vol %sx  span %s" % (
                                             r["sym"], r["tf"], r["fill"],
                                             r["wind"], r["relvol"],
                                             r.get("span", "")), "signal")
                    if closed:
                        cl = d[d["status"] == "closed"].tail(closed)
                        for _, r in cl.iterrows():
                            notify.alert("CLOSED %s %s  %s  net %+.2f%%" % (
                                r["sym"], r["tf"], r["why"],
                                100 * float(r["net"])), "closed")
        except Exception:
            traceback.print_exc()
        time.sleep(300)


import threading
threading.Thread(target=_live_loop, daemon=True).start()
threading.Thread(target=_bb_loop, daemon=True).start()
threading.Thread(target=_ride_loop, daemon=True).start()
threading.Thread(target=_eq_loop, daemon=True).start()



@app.route("/paint")
def paint_page():
    return app.send_static_file("paint.html")


@app.route("/api/trendwin")
def api_trendwin():
    import json as _json
    p = os.path.join(VAL, "trend_windows.json")
    if not os.path.exists(p):
        return jsonify([])
    return jsonify(_json.load(open(p)))


@app.route("/api/trendmark", methods=["GET", "POST"])
def api_trendmark():
    import json as _json
    p = os.path.join(VAL, "trend_marks.json")
    if request.method == "GET":
        return jsonify(_json.load(open(p)) if os.path.exists(p) else {})
    b = request.get_json(force=True, silent=True) or {}
    try:
        n = str(int(b.get("n")))
        marks = [str(x)[:1] for x in (b.get("marks") or [])]
    except (TypeError, ValueError):
        return jsonify(dict(ok=False)), 400
    d = _json.load(open(p)) if os.path.exists(p) else {}
    d[n] = marks
    _json.dump(d, open(p, "w"))
    return jsonify(dict(ok=True))



@app.route("/api/gen")
def api_gen():
    """Render-generation stamps so a stale browser tab is self-evident."""
    out = {}
    for name, p in (("charts", os.path.join(VAL, "v4_index.csv")),
                    ("windows", os.path.join(VAL, "trend_windows.json"))):
        try:
            out[name] = pd.Timestamp(os.path.getmtime(p), unit="s")                 .strftime("%Y-%m-%d %H:%M:%S")
        except OSError:
            out[name] = "?"
    return jsonify(out)



@app.after_request
def _no_stale(resp):
    """Grading charts must NEVER be served stale: the browser was caching
    PNGs and API responses for hours, so the owner kept grading renders
    that had already been replaced. Nothing this server sends is cacheable."""
    resp.headers["Cache-Control"] = "no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


if __name__ == "__main__":
    main()
