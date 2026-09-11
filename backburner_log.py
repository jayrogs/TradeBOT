"""backburner_log.py -- the backburner FORWARD LOG. Every campaign the rules
would open, tracked live from its first oversold close to its exit, with
the same mechanics the study scored (studies/backburner_study.py), so the
live record is comparable to the 4-year backtest.

    python backburner_log.py            # one tick (the server runs this every 15 minutes)
    python backburner_log.py --status

RULES (frozen 2026-09-05 from the study; do not tune on live results):
  open      RSI(14) closes at or under 30 -> buy 1 unit at the NEXT bar's open
  add       every further close at or under 30 buys another (cap 10)
  bad       close under avg - max(half the 3-day run-up, 3 ATR) -> sell all
  bounce    RSI closes above 50 -> sell the fraction that makes a stop at the
            campaign low breakeven; ride the rest
  ride      out when a close breaks the campaign low, or the frozen 12 EMA
            rider exit fires once price is back above the 12 EMA
  select    flagged (and alerted) when: hot (up 10%+ on the day or 20%+ in
            3 days) AND no oversold on this chart for 3+ days AND relative
            volume >= 1.5 AND a liquid name

Universe: the scanner's crypto universe (Coinbase + Kraken) and the most
liquid stocks/ETFs; timeframes 15m, 4h, 1d. Fills are the first open AFTER
the signal bar; a campaign is `late` if the tick saw the signal more than
one bar after it closed. State lives in livelog/bb_campaigns.csv (one row
per campaign, rewritten each tick) and livelog/bb_status.json.
"""

import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "studies"))
import backburner_study as S   # noqa: E402  the frozen rules (hl_break_exit, low_pivots)

import crypto
import indicators as IND
import rider
import rider_lab as RL
import structure as ST

warnings.filterwarnings("ignore")
DIR = "livelog"
PATH = os.path.join(DIR, "bb_campaigns.csv")
STATUS = os.path.join(DIR, "bb_status.json")
LIVE_ALL_HOURS = True     # stocks: pre-market and after-hours bars count (owner 2026-09-07)
VERSION = "bb-v3 2026-09-06 os30/b50/run0.5/units10/higher-low-ride"
OS, BOUNCE, STOP_FRAC, STOP_ATR, MAX_UNITS = 30, 50, 0.5, 3.0, 10
EMA_TOL_ATR = 0.25
TFS = ("15m", "4h", "1d")
BARS_DAY = {"15m": 96, "4h": 6, "1d": 5}
BARS = {"15m": 500, "1h": 900, "1d": 600}
N_CRYPTO, N_STOCKS = 150, 300
COLS = ["id", "sym", "kind", "tf", "opened", "state", "units", "avg", "low", "stop",
        "run_up", "hot", "gap_days", "relvol", "liq_rank", "higher", "grade", "select", "late",
        "bounce_at", "bounce_px", "part", "exit_at", "exit_px", "exit_why", "ret", "version"]


def _atr(h, l, c, n=14):
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1.0 / n, adjust=False).mean().values


def _load():
    if os.path.exists(PATH):
        d = pd.read_csv(PATH)
        for c in COLS:
            if c not in d:
                d[c] = np.nan
        return d[COLS]
    return pd.DataFrame(columns=COLS)


def _save(d):
    os.makedirs(DIR, exist_ok=True)
    tmp = PATH + ".tmp"
    d[COLS].to_csv(tmp, index=False)
    os.replace(tmp, PATH)


def universe():
    """[(sym, kind, source)] -- crypto from the scanner universe, stocks from tier1."""
    out = []
    try:
        u = crypto.universe(N_CRYPTO)
        out += [(x["sym"], "crypto", x["source"]) for _, x in u.iterrows()]
    except Exception:
        pass
    try:
        k = pd.read_csv(os.path.join("cache", "tier1.csv"))
        k = k[k.kind.isin(["equity", "etf"])].dropna(subset=["dollar"]).sort_values("dollar", ascending=False)
        for r in k.head(N_STOCKS).itertuples():
            out.append((str(r.symbol), "etf" if r.kind == "etf" else "stock", "yahoo"))
    except Exception:
        pass
    return out


def frames(sym, kind, source, yahoo_pre=None):
    """{tf: df} live frames: 15m, 4h (from 1h), 1d."""
    out = {}
    if kind == "crypto":
        d15 = crypto.candles(sym, "15m", BARS["15m"], source=source)
        d1h = crypto.candles(sym, "1h", BARS["1h"], source=source)
        d1d = crypto.candles(sym, "1d", BARS["1d"], source=source)
    else:
        # Owner 2026-09-07: "we need to trade all hours". Yahoo brings the full 4:00-20:00
        # New York bars; keep them. (LIVE_ALL_HOURS=False goes back to the regular session only.)
        d15 = (yahoo_pre or {}).get((sym, "15m"))
        d1h = (yahoo_pre or {}).get((sym, "1h"))
        if not LIVE_ALL_HOURS:
            d15 = S.session_only(d15); d1h = S.session_only(d1h)
        d1d = (yahoo_pre or {}).get((sym, "1d"))
    if d15 is not None and len(d15) >= 60:
        out["15m"] = d15
    if d1h is not None and len(d1h) >= 120:
        h4 = d1h.resample("4h").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
        if len(h4) >= 60:
            out["4h"] = h4
    if d1d is not None and len(d1d) >= 60:
        out["1d"] = d1d
    return out


_PRE_CACHE = {}


def yahoo_prefetch(syms):
    """One batched Yahoo download for a list of stocks. Cached for 8 minutes per list,
    because three live loops (backburners, rides, ranges) ask for the same names and
    Yahoo rate-limits when they all pull at once."""
    import yfinance as yf
    key = tuple(sorted(syms))
    hit = _PRE_CACHE.get(key)
    if hit and time.time() - hit[0] < 480:
        return hit[1]
    pre = {}
    for base, period in (("15m", "59d"), ("1h", "2y"), ("1d", "5y")):
        for i in range(0, len(syms), 150):
            part = syms[i:i + 150]
            try:
                d = yf.download(part, interval=base, period=period, progress=False,
                                auto_adjust=False, prepost=True, group_by="ticker", threads=True)
            except Exception:
                continue
            for s in part:
                try:
                    f = (d[s] if isinstance(d.columns, pd.MultiIndex) else d).dropna()
                except Exception:
                    continue
                if getattr(f.index, "tz", None) is not None:
                    f.index = f.index.tz_localize(None)
                if len(f) >= 40:
                    pre[(s, base)] = f[["Open", "High", "Low", "Close", "Volume"]]
    _PRE_CACHE.clear(); _PRE_CACHE[key] = (time.time(), pre)
    return pre


def conditions(df, i, tf, higher_df=None):
    """What the study recorded at the first print, computed live."""
    c = df["Close"].values.astype(float); v = df["Volume"].values.astype(float)
    bpd = BARS_DAY[tf]
    r = IND.rsi_parts(c)[0]
    k = min(i, bpd); move = c[i] / c[i - k] - 1 if k > 0 else 0.0
    k3 = min(i, 3 * bpd); move3 = c[i] / c[i - k3] - 1 if k3 > 0 else 0.0
    med = pd.Series(v).rolling(bpd * 5, min_periods=bpd).median().values
    relvol = float(v[i] / med[i]) if np.isfinite(med[i]) and med[i] > 0 else np.nan
    # days since the previous oversold stretch started
    os_ = r <= OS
    prev = None
    for j in range(i - 1, 0, -1):
        if os_[j] and not os_[j - 1]:
            prev = j; break
    gap = (i - prev) / bpd if prev is not None else None
    higher = "NA"
    if higher_df is not None and len(higher_df) >= 60:
        st = ST.states(higher_df, causal=True)
        pos = int(higher_df.index.searchsorted(df.index[i], side="right")) - 2   # last CLOSED higher bar
        if pos >= 0:
            higher = str(st[pos])
    return dict(run_up=max(0.0, move3), hot=bool(move >= 0.10 or move3 >= 0.20),
                gap_days=gap, relvol=relvol, higher=higher)


def grades():
    """(sym, tf) -> letter from validation/name_scores.json ("all" as fallback)."""
    try:
        sc = json.load(open(os.path.join("validation", "name_scores.json")))
    except Exception:
        return {}
    return {(r["sym"], r["tf"]): r["grade"] for r in sc["rows"]}


def tick(log=print):
    """Advance every campaign to the latest closed bar; open new ones."""
    d = _load()
    gr = grades()
    uni = universe()
    stocks = [s for s, k, _ in uni if k != "crypto"]
    pre = yahoo_prefetch(stocks) if stocks else {}
    liq = {}
    try:
        k = pd.read_csv(os.path.join("cache", "tier1.csv")).sort_values("dollar", ascending=False)
        liq = {s: i for i, s in enumerate(k.symbol.astype(str))}
    except Exception:
        pass
    opened = closed = 0
    now = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = d.to_dict("records")
    open_keys = {(r["sym"], r["tf"]) for r in rows if r["state"] in ("open", "riding")}
    for sym, kind, source in uni:
        try:
            fr = frames(sym, kind, source, pre)
        except Exception as ex:
            log("  %s frames: %s" % (sym, ex)); continue
        for tf, df in fr.items():
            if len(df) < 60:
                continue
            c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
            h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
            r = IND.rsi_parts(c)[0]; ema = rider.ema(c); a14 = _atr(h, l, c)
            last = len(df) - 2           # the last CLOSED bar (the final row may be forming)
            key = (sym, tf)
            # ---- advance an open campaign: REBUILD it from its first bar every
            # tick (deterministic from the data; nothing accumulates across ticks)
            for row in rows:
                if (row["sym"], row["tf"]) != key or row["state"] not in ("open", "riding"):
                    continue
                i0 = int(df.index.get_indexer([pd.Timestamp(row["opened"])])[0])
                if i0 < 0 or i0 + 1 > last:
                    continue
                units, avg = 1, float(o[i0 + 1]); low = float(l[i0 + 1]); run_up = float(row["run_up"])
                state, j = "open", i0 + 1
                bounce = None
                while j <= last:
                    low = min(low, float(l[j]))
                    if r[j] > BOUNCE:
                        P = float(o[j + 1]) if j + 1 < len(df) else float(c[j])
                        part = min(1.0, max(0.0, (avg - low) / (P - low))) if (P > avg and P > low) else 0.0
                        bounce = (j, P, part); state = "riding"; break
                    if c[j] < avg - max(STOP_FRAC * run_up * avg, STOP_ATR * a14[j]):
                        px = float(o[j + 1]) if j + 1 < len(df) else float(c[j])
                        row.update(state="closed", exit_at=str(df.index[j]), exit_px=px, exit_why="bad",
                                   ret=px / avg - 1); state = "closed"; closed += 1; break
                    if r[j] <= OS and units < MAX_UNITS and j + 1 < len(df):
                        units += 1; avg = (avg * (units - 1) + float(o[j + 1])) / units
                    j += 1
                row.update(units=units, avg=avg, low=low,
                           stop=avg - max(STOP_FRAC * run_up * avg, STOP_ATR * a14[last]))
                if state == "riding":
                    jb, P, part = bounce
                    row.update(state="riding", bounce_at=str(df.index[jb]), bounce_px=P, part=part)
                    v = dict(c=c, lo=l, hi=h, e=ema, hold=(c >= ema), o=o,
                             atr=np.where(np.isfinite(a14), a14, np.inf), n=len(c))
                    exit_ = next(((k, float(o[k + 1]) if k + 1 < len(df) else float(c[k]), "low broke")
                                  for k in range(jb + 1, last + 1) if c[k] < low), None)
                    # the standard ride (2026-09-06): hold until a bar closes under
                    # the last higher low -- the most recent confirmed low pivot that
                    # formed after the first buy and sits above the backburner low.
                    # Same code as the study (hl_break_exit).
                    lpiv, lcis = S.low_pivots(df)
                    hx = S.hl_break_exit(c, o, lpiv, lcis, i0 + 1, jb, low, last + 2 if last + 2 <= len(c) else len(c))
                    if hx and hx[0] <= last and (exit_ is None or hx[0] < exit_[0]):
                        px = float(o[hx[0] + 1]) if hx[0] + 1 < len(df) else float(c[hx[0]])
                        exit_ = (hx[0], px, "closed under last higher low")
                    if exit_:
                        k, px, why = exit_
                        row.update(state="closed", exit_at=str(df.index[k]), exit_px=px, exit_why=why,
                                   ret=(part * P + (1 - part) * px) / avg - 1); closed += 1
            # ---- open a new campaign on the last closed bar
            if key not in open_keys and r[last] <= OS and r[last - 1] > OS and last + 1 < len(df):
                hi_df = fr.get({"15m": "4h", "4h": "1d", "1d": None}.get(tf))
                cond = conditions(df, last, tf, hi_df)
                rank = liq.get(sym, 9999) if kind != "crypto" else 0
                grade = gr.get((sym, tf)) or gr.get((sym, "all")) or "?"
                # selective = a good name (A/B on the scorecard) doing the right thing
                select = bool(cond["hot"] and (cond["gap_days"] is None or cond["gap_days"] >= 3)
                              and np.isfinite(cond["relvol"]) and cond["relvol"] >= 1.5
                              and (kind == "crypto" or rank < 300) and grade in ("A", "B"))
                fill = o[last + 1]
                # late = the signal bar closed more than two bars ago (a stale
                # frame, e.g. stocks over a weekend): logged, never alerted
                dur = {"15m": 15, "4h": 240, "1d": 1440}[tf]
                now_ts = pd.Timestamp.now(tz="UTC").tz_localize(None) if kind == "crypto" else                     pd.Timestamp.now(tz="America/New_York").tz_localize(None)
                late = bool((now_ts - df.index[last]) > pd.Timedelta(minutes=2 * dur))
                select = select and not late
                rows.append(dict(id="%s-%s-%s" % (sym, tf, df.index[last].strftime("%Y%m%d%H%M")), sym=sym, kind=kind, tf=tf,
                                 opened=str(df.index[last]), state="open", units=1, avg=fill,
                                 low=float(l[last]), stop=fill - max(STOP_FRAC * cond["run_up"] * fill, STOP_ATR * a14[last]),
                                 run_up=cond["run_up"], hot=cond["hot"], gap_days=cond["gap_days"],
                                 relvol=cond["relvol"], liq_rank=rank, higher=cond["higher"], grade=grade, select=select,
                                 late=late, bounce_at=None, bounce_px=None, part=None,
                                 exit_at=None, exit_px=None, exit_why=None, ret=None, version=VERSION))
                open_keys.add(key); opened += 1
                if select:
                    try:
                        import notify
                        notify.alert("BACKBURNER %s %s (grade %s)  fill %.6g  hot, %s days since last oversold, vol %.1fx" % (
                            sym, tf, grade, fill, "many" if cond["gap_days"] is None else "%.0f" % cond["gap_days"], cond["relvol"]), "backburner")
                    except Exception:
                        pass
    d = pd.DataFrame(rows)
    for c in COLS:
        if c not in d:
            d[c] = np.nan
    _save(d)
    os.makedirs(DIR, exist_ok=True)
    json.dump(dict(last_tick=now, opened=opened, closed=closed,
                   open=int((d["state"].isin(["open", "riding"])).sum()), total=int(len(d))),
              open(STATUS, "w"))
    log("  backburner tick %s: %d opened, %d closed, %d live, %d total" % (
        now, opened, closed, int((d["state"].isin(["open", "riding"])).sum()), len(d)))
    return opened, closed


if __name__ == "__main__":
    if "--status" in sys.argv:
        print(open(STATUS).read() if os.path.exists(STATUS) else "no ticks yet")
    else:
        tick()
