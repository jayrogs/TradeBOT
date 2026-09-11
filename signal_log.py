"""signal_log.py -- the forward test. The only clean data left is the future.

The FROZEN rule (2 defended touches, confirmed-close fill, wind >= 5 bars,
quarter-ATR exit tolerance, promote at +1%, 3% trail, liquid names) stamps
every signal it fires from now on. Rows are append-only: fills are the
historical closes the backtest would have used, outcomes get filled in by
the same exit walk, and nothing is ever edited after the fact. If the rule
changes later, new rows carry a new version tag and old rows stand.

    python signal_log.py --tick      one scan + outcome update (the server
                                     does this automatically every hour)
    python signal_log.py --status    print the ledger summary

Honesty notes baked in:
  - the fill is the confirmed close, exactly like the backtest; logged_at
    records how long after the bar the signal was seen, so a scan that ran
    late is visible, and anything caught more than LOOKBACK bars late is
    flagged late=1
  - outcomes come from rider_lab.run_exit, the tested canonical exit
  - expectation to beat: +0.67%/trade raw, +0.28% over null (mined era)
"""

import argparse
import os
import time
import warnings

import numpy as np
import pandas as pd

import crypto
import rider_lab as L
import scanner as SC

warnings.filterwarnings("ignore")

DIR = "livelog"
SIG = os.path.join(DIR, "signals.csv")
MY = os.path.join(DIR, "mytrades.csv")
VERSION = "rider-v1 2026-08-29 t2/wind5/tol.25/prom1/trail3"
BARS = 2400
DOLLAR = 1e6
LOOKBACK = 3          # bars: how far back a scan may pick up a missed signal
TFS = (("1h", 1), ("4h", 4))

COLS = ["logged_at", "bar", "sym", "tf", "fill", "stop0", "wind", "relvol",
        "ret7d", "late", "in_range", "span", "status", "promoted", "last_px",
        "unreal", "exit_at", "exit_px", "why", "net", "version"]

_UNIVERSE = {"day": None, "pairs": []}


def _now():
    return pd.Timestamp.now(tz="UTC").tz_localize(None)


STR_COLS = ("logged_at", "bar", "sym", "tf", "status", "exit_at", "why",
            "version", "span")


def _load():
    if os.path.exists(SIG):
        d = pd.read_csv(SIG)
        for k in COLS:
            if k not in d:
                d[k] = np.nan
        # an all-empty column loads as float64 and then REFUSES a string --
        # outcome settlement crashed on exactly that for a day. Strings stay
        # strings.
        for k in STR_COLS:
            d[k] = d[k].astype(object).where(d[k].notna(), "")
        return d[COLS]
    return pd.DataFrame(columns=COLS)


def _save(d):
    # atomic-ish: never leave a half-written ledger if the process dies
    os.makedirs(DIR, exist_ok=True)
    tmp = SIG + ".tmp"
    d.to_csv(tmp, index=False)
    os.replace(tmp, SIG)


UNI_FILE = os.path.join(DIR, "universe.json")


def universe():
    import json
    day = _now().strftime("%Y-%m-%d")
    if _UNIVERSE["day"] != day or not _UNIVERSE["pairs"]:
        try:
            u = crypto.universe(30)
            _UNIVERSE["pairs"] = [(r["sym"], r["source"])
                                  for _, r in u.iterrows()]
            _UNIVERSE["day"] = day
            os.makedirs(DIR, exist_ok=True)
            json.dump(_UNIVERSE["pairs"], open(UNI_FILE, "w"))
        except Exception:
            # a restart during a CoinGecko outage must not silently scan
            # NOTHING -- fall back to the last known universe on disk
            if not _UNIVERSE["pairs"] and os.path.exists(UNI_FILE):
                _UNIVERSE["pairs"] = [tuple(x) for x in
                                      json.load(open(UNI_FILE))]
    return _UNIVERSE["pairs"]


def _frames(sym, src, refresh):
    raw = crypto.candles(sym, "1h", BARS, source=src, refresh=refresh)
    if raw is None or len(raw) < 900:
        return None, {}
    out = {}
    for tf, mult in TFS:
        df = SC.resample(raw, "4h") if tf == "4h" else raw
        if df is None or len(df) < 800:
            continue
        dvm = float((df["Close"] * df["Volume"]).tail(720 // mult).median())
        if dvm < DOLLAR * mult:
            continue                     # the liquidity gate, live
        out[tf] = df
    return raw, out


def scan_once(refresh=True):
    """Log any entry the frozen rule fired within the last LOOKBACK bars."""
    d = _load()
    seen = set(zip(d["sym"], d["tf"], d["bar"].astype(str)))
    added = 0
    now = _now()
    for sym, src in universe():
        try:
            raw, frames = _frames(sym, src, refresh)
        except Exception:
            continue
        if raw is None:
            continue
        dv = raw["Close"] * raw["Volume"]
        for tf, df in frames.items():
            v = L.prep(df)
            n = v["n"]
            # owner-verified range overlay, recorded as metadata on every
            # signal -- the RULE is unchanged, so no version bump
            import structure as ST
            eq_arr, _ = ST.eq_overlay(df)
            span_arr = ST.states(df, causal=True)     # backbone, live clock
            for entry, fill in L.entries(v, 2, "promote1"):
                if entry < n - 1 - LOOKBACK:
                    continue
                bar = df.index[entry]
                key = (sym, tf, str(bar))
                if key in seen:
                    continue
                past = dv[dv.index <= bar]
                rv = (float(past.tail(24).mean()
                            / max(past.tail(24 * 30).median(), 1e-9))
                      if len(past) > 48 else np.nan)
                cpast = raw["Close"][raw["Close"].index <= bar]
                r7 = (float(cpast.iloc[-1] / cpast.iloc[-168] - 1)
                      if len(cpast) > 168 else np.nan)
                hrs = (now - bar).total_seconds() / 3600
                bar_h = 1 if tf == "1h" else 4
                d = pd.concat([d, pd.DataFrame([dict(
                    logged_at=str(now.floor("s")), bar=str(bar), sym=sym,
                    tf=tf, fill=float(fill),
                    stop0=float(v["e"][entry] * 0.97),
                    wind=int(v["upage"][entry]),
                    relvol=round(rv, 3), ret7d=round(r7, 4),
                    late=int(hrs > bar_h * (LOOKBACK + 1)),
                    in_range=int(bool(eq_arr[entry])),
                    span=str(span_arr[entry]),
                    status="open", promoted=0, last_px=float(fill),
                    unreal=0.0, exit_at="", exit_px=np.nan, why="",
                    net=np.nan, version=VERSION)])], ignore_index=True)
                seen.add(key)
                added += 1
    if added:
        _save(d)
    return added


def update_outcomes(refresh=False, fetch=None):
    """Walk each open signal through the canonical exit. `fetch` is
    injectable so the settlement logic is testable offline."""
    fetch = fetch or _frames
    d = _load()
    if d.empty:
        return 0
    closed = 0
    changed = False
    for sym in d[d["status"] == "open"]["sym"].unique():
        try:
            raw, frames = fetch(sym, None, refresh)
        except Exception:
            continue
        if raw is None:
            continue
        for i, row in d[(d["status"] == "open") & (d["sym"] == sym)].iterrows():
            df = frames.get(row["tf"])
            if df is None:
                continue
            v = L.prep(df)
            pos = df.index.get_indexer([pd.Timestamp(row["bar"])])
            if pos[0] < 0:
                continue
            entry = int(pos[0])
            fill = float(row["fill"])
            r = L.run_exit(v, entry, fill, "promote1")
            prom = next((k for k in range(entry + 1, v["n"])
                         if v["c"][k] >= fill * 1.01), None)
            if r is not None:
                k, px, why = r
                if prom is not None and prom > k:
                    prom = None
                d.loc[i, ["status", "exit_at", "exit_px", "why", "net"]] = [
                    "closed", str(df.index[k]), float(px), why,
                    float(px / fill - 1 - 2 * L.COST)]
                closed += 1
            else:
                d.loc[i, "last_px"] = float(v["c"][-1])
                d.loc[i, "unreal"] = float(v["c"][-1] / fill - 1)
            d.loc[i, "promoted"] = int(prom is not None)
            changed = True
    if changed:
        _save(d)
    return closed


def tick(refresh=True):
    import json
    added = scan_once(refresh)
    closed = update_outcomes(refresh=False)
    os.makedirs(DIR, exist_ok=True)
    json.dump(dict(last_tick=str(_now().floor("s")), added=added,
                   closed=closed),
              open(os.path.join(DIR, "status.json"), "w"))
    return added, closed


def last_tick():
    import json
    p = os.path.join(DIR, "status.json")
    try:
        return json.load(open(p))
    except Exception:
        return {}


def summary():
    d = _load()
    if d.empty:
        return dict(n=0, open=0, closed=0)
    cl = d[d["status"] == "closed"]
    out = dict(n=len(d), open=int((d["status"] == "open").sum()),
               closed=len(cl), version=VERSION)
    if len(cl):
        out.update(mean=float(cl["net"].mean()),
                   win=float((cl["net"] > 0).mean()),
                   total=float(cl["net"].sum()))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tick", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.tick:
        t0 = time.time()
        added, closed = tick()
        print("tick: %d new signals, %d closed, %.0fs" %
              (added, closed, time.time() - t0))
    print(summary())
