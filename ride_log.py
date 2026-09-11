"""ride_log.py -- the trend ride, live. Same shape as backburner_log.py.

Every 15 minutes (server thread) or by hand:

    python ride_log.py            # one tick
    python ride_log.py --show     # print the open rides

THE RULE (CLAUDE.md #17, his gradings of 2026-09-06): the uptrend already has
a higher low and a higher high; a SECOND higher low confirms on the last
closed bar -> buy at the next bar's open, unless that open is under the low
or ran more than one normal bar's move above it (three on the daily). Sell a
third when up twice the risk (risk floored at one normal bar's move). Sell
the rest when a wick goes half a normal bar under the last higher low; once
up 3x the risk, trail 8 normal bars' moves under the highest close instead.
Lower highs are ignored. 5m/15m stock rides close at the bell; 1h and up hold.

Every open ride is rebuilt from its first bar on every tick, so nothing is
counted twice and a restart loses nothing. State: livelog/ride_campaigns.csv,
livelog/ride_status.json. Names: focus.py (the 40 we are refining on).
"""

import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "studies"))
import backburner_study as S      # noqa: E402  atr, session_only
import backburner_log as BL       # noqa: E402  live frames (crypto.candles / yahoo)
import focus                      # noqa: E402
import structure as ST            # noqa: E402

warnings.filterwarnings("ignore")
VERSION = "ride-v1 2026-09-07 2ndHL/wick0.5/trail8@3R/third@2R"
TFS = ("15m", "1h", "4h", "1d")
TOL, TRAIL_AFTER_R, TRAIL_BARS, PART_R, PART_SIZE = 0.5, 3.0, 8.0, 2.0, 1 / 3
LIVE = "livelog"
CSV = os.path.join(LIVE, "ride_campaigns.csv")
STATUS = os.path.join(LIVE, "ride_status.json")
COLS = ["id", "sym", "kind", "tf", "confirm", "opened", "state", "fill", "pivot", "risk", "level", "trailing",
        "part_at", "part_px", "exit_at", "exit_px", "exit_why", "ret", "worst", "hi", "version"]


def _pivots(df):
    piv = ST.pivots(df)
    return piv, {p[0]: i for i, p in enumerate(piv)}


def _count_before(piv, pos_by_ci, ci):
    k = pos_by_ci.get(ci)
    if k is None:
        return 0, False, 0
    cnt, has_hh, nhl = 0, False, 0
    for m in range(k, -1, -1):
        lab = piv[m][4]
        if lab in ("LH", "LL", "H", "L"):
            break
        cnt += 1
        has_hh = has_hh or lab == "HH"
        nhl += lab in ("HL", "EL")
    return cnt, has_hh, nhl


def live_walk(df, tf, kind, opened):
    """Rebuild one ride from its entry bar on the current frame. Returns the
    row fields (state open/closed and everything else), or None if the entry
    bar is not in the frame."""
    c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    e = int(df.index.get_indexer([pd.Timestamp(opened)])[0])
    if e < 1 or e >= n:
        return None
    a14 = S.atr(h, l, c)
    piv, pos = _pivots(df)
    lows = [p for p in piv if p[3] == "low"]
    trig = next((p for p in lows if p[0] == e - 1), None)
    if trig is None:
        return None
    fill, pivot = o[e], trig[2]
    atr0 = a14[e - 1]
    R = max(fill - pivot, atr0)
    last = last_closed(df, tf, kind)           # the last CLOSED bar
    if e > last:
        return dict(state="open", fill=float(fill), pivot=float(pivot), risk=float(R), level=float(pivot),
                    trailing=False, part_at=None, part_px=None, worst=0.0, exit_at=None, exit_px=None, exit_why=None, ret=None)
    level, peak, trailing = pivot, c[e], False
    worst = 0.0
    part_at = part_px = None
    tgt = fill + PART_R * R
    intraday_stock = kind in ("stock", "etf") and tf in ("5m", "15m")
    q = next((i for i, p in enumerate(lows) if p[0] > e - 1), len(lows))
    for k in range(e, last + 1):
        while q < len(lows) and lows[q][0] <= k:
            ci, j2, price, lab = lows[q][0], lows[q][1], lows[q][2], lows[q][4]; q += 1
            if j2 >= e and lab in ("HL", "EL") and price > level:
                level = price
        peak = max(peak, c[k])
        worst = min(worst, c[k] / fill - 1)
        atr_k = a14[k] if np.isfinite(a14[k]) else 0.0
        if part_at is None and h[k] >= tgt:
            part_at, part_px = str(df.index[k]), float(tgt)
        if not trailing and c[k] >= fill + TRAIL_AFTER_R * R:
            trailing = True
        if trailing:
            level = max(level, peak - TRAIL_BARS * atr_k)
            if c[k] < level:
                return _closed(df, k, o, c, fill, R, level, trailing, part_at, part_px, worst,
                               "closed under the trailing stop at %.4g" % level, next_open=True)
        elif l[k] < level - TOL * atr_k:
            return _closed(df, k, o, c, fill, R, level, trailing, part_at, part_px, worst,
                           "wick under the last higher low at %.4g" % level, next_open=True)
        if intraday_stock and k + 1 < n and df.index[k + 1].normalize() != df.index[k].normalize():
            return _closed(df, k, o, c, fill, R, level, trailing, part_at, part_px, worst,
                           "session ended", next_open=False)
    return dict(state="open", fill=float(fill), pivot=float(pivot), risk=float(R), level=float(level),
                trailing=bool(trailing), part_at=part_at, part_px=part_px, worst=float(worst),
                exit_at=None, exit_px=None, exit_why=None, ret=None)


def _closed(df, k, o, c, fill, R, level, trailing, part_at, part_px, worst, why, next_open):
    n = len(c)
    if next_open:
        if k + 1 >= n:
            px, at = float(c[k]), str(df.index[k])          # the next open is not known yet
            state = "open"
        else:
            px, at = float(o[k + 1]), str(df.index[k + 1]); state = "closed"
    else:
        px, at, state = float(c[k]), str(df.index[k]), "closed"
    sz = PART_SIZE if part_at is not None else 0.0
    ret = sz * ((part_px / fill - 1) if part_at else 0.0) + (1 - sz) * (px / fill - 1)
    return dict(state=state, fill=float(fill), pivot=None, risk=float(R), level=float(level),
                trailing=bool(trailing), part_at=part_at, part_px=part_px, worst=float(worst),
                exit_at=at if state == "closed" else None, exit_px=px if state == "closed" else None,
                exit_why=why if state == "closed" else "about to sell: " + why, ret=float(ret) if state == "closed" else None)


BAR = {"15m": pd.Timedelta("15min"), "1h": pd.Timedelta("1h"), "4h": pd.Timedelta("4h"), "1d": pd.Timedelta("1D")}


def _now_like(kind):
    """The clock the bars are stamped in: crypto bars are UTC, stock and
    futures bars are New York time. (His PC clock is neither.)"""
    if kind == "crypto":
        return pd.Timestamp.utcnow().tz_localize(None)
    return pd.Timestamp.now(tz="America/New_York").tz_localize(None)


def last_closed(df, tf, kind="crypto"):
    """Index of the last CLOSED bar: the final row counts as closed once its
    time plus one bar is in the past (a weekend daily bar is closed; a crypto
    bar fetched mid-bar is not)."""
    now = _now_like(kind)
    return len(df) - 1 if df.index[-1] + BAR[tf] <= now else len(df) - 2


def new_entries(df, tf, kind):
    """A second higher low confirmed on the last closed bar -> (confirm_time, pivot)."""
    n = len(df)
    last = last_closed(df, tf, kind)
    piv, pos = _pivots(df)
    trig = next((p for p in piv if p[3] == "low" and p[0] == last), None)
    if trig is None or trig[4] not in ("HL", "EL"):
        return None
    cnt, has_hh, nhl = _count_before(piv, pos, last)
    if cnt < 3 or not has_hh or nhl != 2:
        return None
    return str(df.index[last]), float(trig[2])


def _load():
    if os.path.exists(CSV):
        d = pd.read_csv(CSV, dtype={"id": str})
        for col in COLS:
            if col not in d:
                d[col] = None
        return d[COLS]
    return pd.DataFrame(columns=COLS)


def tick(log=print):
    os.makedirs(LIVE, exist_ok=True)
    names = [(s, k) for s, k in focus.names()]
    stocks = [s for s, k in names if k == "stock"]
    pre = BL.yahoo_prefetch(stocks) if stocks else {}
    d = _load()
    rows = d.to_dict("records")
    by_key = {(r["sym"], r["tf"]): r for r in rows if r["state"] != "closed"}
    seen_ids = {str(r["id"]) for r in rows}   # a skipped signal must not come back as a new row
    opened = closed = 0
    hi_state = {}
    for sym, kind in names:
        try:
            if kind == "crypto":
                fr = BL.frames(sym, kind, "auto")
                d1h = fr.get("1h")
            elif kind == "futures":
                fr = {}
                d1h = None
                try:
                    import yfinance as yf
                    yh = sym.replace("_F", "=F")
                    for base, period, key in (("15m", "59d", "15m"), ("1h", "2y", "1h"), ("1d", "5y", "1d")):
                        f = yf.download(yh, interval=base, period=period, progress=False, auto_adjust=False)
                        if len(f) >= 60:
                            f.columns = [c_[0] if isinstance(c_, tuple) else c_ for c_ in f.columns]
                            if getattr(f.index, "tz", None) is not None:
                                f.index = f.index.tz_localize(None)
                            fr[key] = f[["Open", "High", "Low", "Close", "Volume"]]
                    if "1h" in fr:
                        h4 = fr["1h"].resample("4h").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
                        if len(h4) >= 60:
                            fr["4h"] = h4
                except Exception as ex:
                    log("  %s futures fetch: %s" % (sym, ex)); continue
            else:
                fr = BL.frames(sym, kind, None, pre)
                if not BL.LIVE_ALL_HOURS:
                    for tf_ in ("15m",):
                        if tf_ in fr:
                            fr[tf_] = S.session_only(fr[tf_])
                if "1h" not in fr and (sym, "1h") in pre:
                    fr["1h"] = pre[(sym, "1h")] if BL.LIVE_ALL_HOURS else S.session_only(pre[(sym, "1h")])
        except Exception as ex:
            log("  %s: %s" % (sym, ex)); continue
        if kind != "futures" and "1h" not in fr and (sym, "1h") in pre:
            fr["1h"] = pre[(sym, "1h")]
        for tf in TFS:
            df = fr.get(tf)
            if df is None or len(df) < 80:
                continue
            key = (sym, tf)
            # rebuild the open ride, if any
            if key in by_key and by_key[key]["state"] == "open":
                r = by_key[key]
                w = live_walk(df, tf, kind, r["opened"])
                if w is not None:
                    r.update(w)
                    if w["state"] == "closed":
                        closed += 1
                        del by_key[key]
                        try:
                            import notify
                            notify.alert("RIDE CLOSED %s %s  %s  net %+.2f%%" % (sym, tf, w["exit_why"], 100 * w["ret"]), "ride")
                        except Exception:
                            pass
            # a signal waiting for its open: fill it once the next bar exists
            if key in by_key and by_key[key]["state"] == "signal":
                r = by_key[key]
                pos = df.index.get_indexer([pd.Timestamp(r["confirm"])])[0]
                if pos >= 0 and pos + 1 < len(df):
                    e = pos + 1
                    o_ = df["Open"].values.astype(float); c_ = df["Close"].values.astype(float)
                    h_ = df["High"].values.astype(float); l_ = df["Low"].values.astype(float)
                    a14 = S.atr(h_, l_, c_); atr0 = a14[e - 1]
                    fill = float(o_[e]); pivot = float(r["pivot"])
                    max_chase = 1.0 if tf in ("5m", "15m", "1h") else 3.0
                    if fill < pivot or not np.isfinite(atr0) or (fill - pivot) / atr0 > max_chase:
                        r.update(state="closed", exit_why="skipped: the open was %s" % ("under the low" if fill < pivot else "too far above the low"),
                                 exit_at=str(df.index[e]), ret=0.0)
                        del by_key[key]
                    else:
                        r.update(state="open", opened=str(df.index[e]), fill=fill, risk=float(max(fill - pivot, atr0)), level=pivot)
                        try:
                            import notify
                            notify.alert("RIDE %s %s  bought %.4g off the higher low at %.4g" % (sym, tf, fill, pivot), "ride")
                        except Exception:
                            pass
            # a new signal on the last closed bar
            if key not in by_key:
                ne = new_entries(df, tf, kind)
                if ne and "%s-%s-%s" % (sym, tf, pd.Timestamp(ne[0]).strftime("%Y%m%d%H%M")) not in seen_ids:
                    confirm, pivot = ne
                    row = dict(id="%s-%s-%s" % (sym, tf, pd.Timestamp(confirm).strftime("%Y%m%d%H%M")),
                               sym=sym, kind=kind, tf=tf, confirm=confirm, opened=None, state="signal", fill=None,
                               pivot=pivot, risk=None, level=pivot, trailing=False,
                               part_at=None, part_px=None, exit_at=None, exit_px=None, exit_why=None,
                               ret=None, worst=0.0, hi="", version=VERSION)
                    rows.append(row); by_key[key] = row; seen_ids.add(row["id"]); opened += 1
                    try:
                        import notify
                        notify.alert("RIDE SIGNAL %s %s  second higher low at %.4g, buy the next open" % (sym, tf, pivot), "ride")
                    except Exception:
                        pass
    out = pd.DataFrame(rows, columns=COLS)
    out.to_csv(CSV, index=False)
    st = dict(last_tick=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"), opened=opened, closed=closed,
              open=int((out.state != "closed").sum()), total=int(len(out)), version=VERSION,
              names=len(names))
    json.dump(st, open(STATUS, "w"))
    log("  ride tick: %d names, %d opened, %d closed, %d open, %d total" % (len(names), opened, closed, st["open"], st["total"]))
    return st


if __name__ == "__main__":
    if "--show" in sys.argv:
        d = _load()
        print(d[d.state != "closed"][["sym", "tf", "state", "confirm", "opened", "fill", "pivot", "level", "trailing", "part_at", "worst"]].to_string())
    else:
        tick()
