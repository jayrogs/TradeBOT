"""trend_variants.py -- the trend ride, done several ways, because the first
version's technique was wrong in two visible ways (2026-09-06, owner-caught on
the charts at /trendcases):

  1. it BOUGHT at the next open after the pivot confirmed, which on a fast bar
     is a long way above the pivot -- CRDO 1h 2022-07-19 filled 3.7 ATR above
     its own stop reference;
  2. it RAISED the stop to every new higher low the moment one confirmed, even
     one printed two bars ago and sitting above the entry, so an ordinary
     pullback sold the trade.

    python studies/trend_variants.py        # writes validation/trend_variants.json

ENTRY VARIANTS
  next open        buy at the next bar's open after the higher low confirms (v1)
  no chase         same, but skip it if that open is more than MAX_CHASE ATR
                   above the pivot low
  bid at the pivot a resting buy at the pivot price, good for WAIT bars; fills
                   only if price comes back to it (and fills on the ones that
                   keep falling too -- no cherry-picking)

STOP VARIANTS (the line that gets held)
  newest HL        the last confirmed higher low (v1)
  one behind       hold the PREVIOUS higher low; the newest one only becomes
                   the stop after a further higher low confirms
  after a new high raise to the newest higher low only once a new higher high
                   has confirmed -- the trend has to actually advance first
  each of the above also run with a BUFFER: the close must be more than
  BUFFER ATR under the line, not a hair under it

Every variant is scored against the same control (buy any bar, same stop rule)
and against drift, on the same trades, so the comparison is like for like.
"""

import bisect
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "studies"))
import backburner_study as B      # noqa: E402
import structure as ST            # noqa: E402
import rider                      # noqa: E402

CHAIN = ["15m", "1h", "4h", "1d"]
BARS_DAY, CLASS_COST = B.BARS_DAY, B.CLASS_COST
CAP_DAYS = 30
MAX_CHASE = 1.0          # normal bars' moves above the pivot, for the "no chase" entry
WAIT = 10                # bars a resting bid stays live
NULL_EVERY = 25
OUT = os.path.join("validation", "trend_variants.json")

# (label, entry, raise_mode, buffer_atr)
VARIANTS = [
    ("first version: next open, stop at the newest higher low", "open", "new", 0.0),
    ("buy the next open, stop one pivot behind", "open", "lag", 0.0),
    ("buy the next open, raise the stop only after a new high", "open", "hh", 0.0),
    ("buy the next open, newest, needs a clear break", "open", "new", 0.5),
    ("buy the next open, one behind, needs a clear break", "open", "lag", 0.5),
    ("don't chase, stop at the newest higher low", "nochase", "new", 0.0),
    ("don't chase, stop one pivot behind", "nochase", "lag", 0.0),
    ("don't chase, one behind, needs a clear break", "nochase", "lag", 0.5),
    ("don't chase, raise the stop only after a new high", "nochase", "hh", 0.0),
    ("limit order at the pivot, stop at the newest higher low", "bid", "new", 0.0),
    ("limit order at the pivot, stop one pivot behind", "bid", "lag", 0.0),
    ("limit order at the pivot, one behind, needs a clear break", "bid", "lag", 0.5),
    ("limit order at the pivot, raise the stop only after a new high", "bid", "hh", 0.0),
]


def exit_ride(c, o, a14, lows, lcis, highs, hcis, e, level, n, cap, mode, buf_atr):
    """Hold from bar e with `level` as the line. Returns (exit_bar, exit_px,
    why, best_after) or None. `mode`: new / lag / hh."""
    p = bisect.bisect_right(lcis, e - 1)
    q = bisect.bisect_right(hcis, e - 1)
    pending = None          # a higher low waiting to become the stop
    armed = True if mode != "hh" else False
    for k in range(e, n - 1):
        while q < len(highs) and highs[q][0] <= k:
            ci, j, price, lab = highs[q]; q += 1
            if j >= e and lab == "HH":
                armed = True
                if mode == "hh" and pending is not None and pending > level:
                    level = pending; pending = None
        while p < len(lows) and lows[p][0] <= k:
            ci, j, price, lab = lows[p]; p += 1
            if j < e or price <= level:
                continue
            if mode == "new":
                level = price
            elif mode == "lag":
                if pending is not None and pending > level:
                    level = pending          # the one behind becomes the stop
                pending = price
            else:                            # hh: wait for a new high
                if armed:
                    level = price; armed = False
                else:
                    pending = price
        buf = buf_atr * (a14[k] if np.isfinite(a14[k]) else 0.0)
        if c[k] < level - buf:
            return k, o[k + 1], "stopped"
        if k - e >= cap:
            return k, o[k + 1], "cap"
    return None


def study_frame(sym, kind, tf, frames, start):
    df = frames[tf]
    if len(df) < 300:
        return []
    c = df["Close"].values.astype(float); o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float); l = df["Low"].values.astype(float)
    n = len(c)
    cap = CAP_DAYS * BARS_DAY[tf]
    cost = CLASS_COST.get(kind, B.COST)
    a14 = B.atr(h, l, c)
    piv = ST.pivots(df)
    lows = [(ci, j, p, lab) for ci, j, p, k_, lab in piv if k_ == "low"]
    highs = [(ci, j, p, lab) for ci, j, p, k_, lab in piv if k_ == "high"]
    lcis = [x[0] for x in lows]; hcis = [x[0] for x in highs]
    lr = np.diff(np.log(c), prepend=np.log(c[0]))
    drift = float(np.nanmean(lr[np.isfinite(lr)]))
    mid = start + (pd.Timestamp.now() - start) / 2
    rows = []
    for idx, (ci, j, price, lab) in enumerate(lows):
        if lab != "HL" or ci < 30 or ci + 2 >= n - 1:
            continue
        e0 = ci + 1
        atr = a14[ci] if np.isfinite(a14[ci]) and a14[ci] > 0 else np.nan
        chase = (o[e0] - price) / atr if np.isfinite(atr) else np.nan
        t = df.index[e0]
        era = "before" if t < start else "first" if t < mid else "second"
        for label, ent, mode, buf in VARIANTS:
            if ent == "open":
                e, fill = e0, o[e0]
            elif ent == "nochase":
                if not (np.isfinite(chase) and chase <= MAX_CHASE):
                    continue
                e, fill = e0, o[e0]
            else:                                   # resting bid at the pivot
                hit = next((k for k in range(e0, min(e0 + WAIT, n - 1)) if l[k] <= price), None)
                if hit is None:
                    continue
                e, fill = hit, min(o[hit], price)   # a gap through the bid fills at the open
            res = exit_ride(c, o, a14, lows, lcis, highs, hcis, e, price, n, cap, mode, buf)
            if res is None:
                continue
            xb, px, why = res
            after = min(n - 1, xb + 60)
            rows.append(dict(sym=sym, kind=kind, tf=tf, t=str(t), era=era, variant=label, null=0,
                             ret=float(px / fill - 1 - cost), held=int(xb + 1 - e), why=why,
                             chase=float(chase) if np.isfinite(chase) else None,
                             best_after=float(np.max(c[xb:after + 1]) / fill - 1),
                             drift=float(np.exp(drift * (xb + 1 - e)) - 1 - cost)))
    # control: buy any bar, each stop rule, same machinery
    off = hash(sym + tf) % NULL_EVERY
    for e in range(max(31, off), n - 2, NULL_EVERY):
        p = bisect.bisect_right(lcis, e - 1) - 1
        if p < 0 or c[e - 1] < lows[p][2]:
            continue
        t = df.index[e]
        era = "before" if t < start else "first" if t < mid else "second"
        for mode in ("new", "lag", "hh"):
            for buf in (0.0, 0.5):
                res = exit_ride(c, o, a14, lows, lcis, highs, hcis, e, lows[p][2], n, cap, mode, buf)
                if res is None:
                    continue
                xb, px, why = res
                rows.append(dict(sym=sym, kind=kind, tf=tf, t=str(t), era=era, null=1,
                                 variant="buy any bar, %s%s" % ({"new": "newest higher low", "lag": "one pivot behind", "hh": "raise after a new high"}[mode], ", clear break" if buf else ""),
                                 ret=float(px / o[e] - 1 - cost), held=int(xb + 1 - e), why=why,
                                 chase=None, best_after=None,
                                 drift=float(np.exp(drift * (xb + 1 - e)) - 1 - cost)))
    return rows


def block(d):
    r = d["ret"]
    return dict(n=int(len(d)), ret=float(r.mean()), median=float(r.median()),
                win=float((r > 0.005).mean()),
                avg_win=float(r[r > 0.005].mean()) if (r > 0.005).any() else None,
                avg_loss=float(r[r < -0.005].mean()) if (r < -0.005).any() else None,
                held=float(d["held"].mean()), drift=float(d["drift"].mean()),
                edge=float(r.mean() - d["drift"].mean()),
                left=float(d["best_after"].mean() - r.mean()) if d["best_after"].notna().any() else None,
                capped=float((d["why"] == "cap").mean()))


def main():
    t0 = time.time()
    start = pd.Timestamp.now().normalize() - pd.Timedelta(days=365 * B.YEARS)
    names = B.universe()
    rows = []
    for sym, kind in names:
        fr = B.frames_for(sym, kind)
        for tf in CHAIN:
            if tf not in fr:
                continue
            try:
                rows += study_frame(sym, kind, tf, fr, start)
            except Exception as ex:
                print("  %s %s %s: %s" % (kind, sym, tf, ex), flush=True)
        print("  %-6s %-6s rows so far %d  (%.0fs)" % (kind, sym, len(rows), time.time() - t0), flush=True)
    ev = pd.DataFrame(rows)
    ev = ev[np.isfinite(ev.ret) & (ev.ret.abs() < 5)]
    tr, nu = ev[ev.null == 0], ev[ev.null == 1]
    res = {"by_variant": {v: block(g) for v, g in tr.groupby("variant")},
           "control": {v: block(g) for v, g in nu.groupby("variant")},
           "by_variant_tf": {"%s | %s" % (v, tf): block(g) for (v, tf), g in tr.groupby(["variant", "tf"])},
           "by_variant_era": {"%s | %s" % (v, e): block(g) for (v, e), g in tr.groupby(["variant", "era"])},
           "by_variant_asset": {"%s | %s" % (v, k): block(g) for (v, k), g in tr.groupby(["variant", "kind"])},
           "meta": dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), names=len(names),
                        rows=int(len(ev)), tfs=CHAIN, max_chase=MAX_CHASE, wait=WAIT,
                        cap_days=CAP_DAYS, seconds=int(time.time() - t0))}
    json.dump(res, open(OUT, "w"))
    print("\n  TREND VARIANTS  %d names, %d trades  (%.0fs)\n" % (len(names), len(tr), time.time() - t0))
    print("  %-46s %8s %9s %9s %6s %7s %8s" % ("variant", "n", "per trade", "vs drift", "win", "held", "left behind"))
    for v, b in sorted(res["by_variant"].items(), key=lambda kv: -kv[1]["ret"]):
        print("  %-46s %8d %+8.2f%% %+8.2f%% %5.0f%% %6.0f %+8.2f%%" % (
            v, b["n"], 100 * b["ret"], 100 * b["edge"], 100 * b["win"], b["held"], 100 * (b["left"] or 0)))
    print()
    for v, b in sorted(res["control"].items()):
        print("  %-46s %8d %+8.2f%% %+8.2f%% %5.0f%% %6.0f" % (v, b["n"], 100 * b["ret"], 100 * b["edge"], 100 * b["win"], b["held"]))
    print("\n  per timeframe, the best few:")
    for k, b in sorted(res["by_variant_tf"].items(), key=lambda kv: -kv[1]["ret"])[:20]:
        print("    %-58s n=%7d %+7.2f%% vs drift %+6.2f%%" % (k, b["n"], 100 * b["ret"], 100 * b["edge"]))


if __name__ == "__main__":
    main()
