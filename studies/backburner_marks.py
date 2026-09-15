"""backburner_marks.py -- the wallet's drawdown MARKED EVERY DAY, not just when something sells (2026-09-15 review).

`backburner_wallet.py` measures the account only at trade exits. With ten positions open through March 2020 the
account was far lower on the way down than any exit ever showed, and SPY's -34% IS a daily mark. Same measure or
no comparison. This replays the same cash wallet, same rules, and marks every open position at each day's close.

Also answers a second review question: 15% of trades open in a name that is already held (equal-share cap, so
up to two shares of the account in one name). "no doubling" skips those and shows what it costs.

    python studies/backburner_marks.py
Writes validation/backburner_marks.json
"""
import io
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backburner_study as B      # noqa: E402
import backburner_wallet as W     # noqa: E402

OUT = os.path.join("validation", "backburner_marks.json")


def marked_wallet(trades, closes, slots, seed, no_double=False, risk=W.RISK):
    """Same rules as backburner_wallet.wallet, plus a daily mark-to-market equity curve."""
    rng = np.random.default_rng(seed)
    days = sorted({d for c in closes.values() for d in c.index})
    by_day = {}
    for tr in trades:
        by_day.setdefault(tr["t_in"], []).append(tr)
    cash = 1.0
    open_ = []          # dict(sym, t_out, pct, dollars, entry_px)
    curve = []
    peak = -1.0
    dd = 0.0
    taken = skipped = 0
    for day in days:
        ds = str(day.date())
        # exits first (the sale is at this day's open, the same as the wallet)
        still = []
        for p in open_:
            if p["t_out"] <= ds:
                cash += p["dollars"] * (1.0 + p["pct"] / 100.0)
            else:
                still.append(p)
        open_ = still
        # then today's entries
        free = slots - len(open_)
        todays = by_day.get(ds, [])
        if no_double:
            held = {p["sym"] for p in open_}
            keep = [t for t in todays if t["sym"] not in held]
            skipped += len(todays) - len(keep)
            todays = keep
        if len(todays) > free:
            idx = rng.permutation(len(todays))[:max(0, free)]
            todays = [todays[i] for i in idx]
        eq_now = cash + sum(p["dollars"] * p["mark"] for p in open_)
        for tr in todays:
            want = min(risk * eq_now / (tr["risk_pct"] / 100.0), eq_now / max(1, slots))
            dollars = min(want, cash)
            if dollars <= 0:
                continue
            cash -= dollars
            c = closes[tr["sym"]]
            px = float(c.asof(day))
            open_.append(dict(sym=tr["sym"], t_out=tr["t_out"], pct=tr["pct"], dollars=dollars, entry_px=px,
                              mark=1.0))
            taken += 1
        # mark everything still open at today's close
        for p in open_:
            px = float(closes[p["sym"]].asof(day))
            p["mark"] = px / p["entry_px"] if p["entry_px"] > 0 else 1.0
        eq = cash + sum(p["dollars"] * p["mark"] for p in open_)
        peak = max(peak, eq)
        dd = min(dd, eq / peak - 1.0)
        curve.append((ds, eq, dd))
    for p in open_:
        cash += p["dollars"] * (1.0 + p["pct"] / 100.0)
    return cash, dd, curve, taken, skipped


def main():
    w = json.load(io.open(os.path.join("validation", "backburner_wallet_trades.json"), encoding="utf-8"))
    trades = sorted(w["trades"], key=lambda x: x["t_in"])
    syms = {(t["sym"], t["kind"]) for t in trades}
    closes = {}
    for s, k in syms:
        try:
            closes[s] = B.frames_for(s, k)["1d"]["Close"]
        except Exception:
            pass
    trades = [t for t in trades if t["sym"] in closes]
    yrs = (pd.Timestamp(trades[-1]["t_in"]) - pd.Timestamp(trades[0]["t_in"])).days / 365.25
    out = {}
    print("  %d trades, %d names loaded" % (len(trades), len(closes)))
    print("  %-38s %8s %12s %12s %8s" % ("", "a year", "worst dip", "(exit-only)", "skipped"))
    for label, nd, key in (("10 slots, as the wallet runs it", False, "as_is"),
                           ("10 slots, no doubling in a name", True, "no_double")):
        res = [marked_wallet(trades, closes, 10, s, no_double=nd) for s in range(12)]
        ann = np.mean([r[0] ** (1 / yrs) - 1 for r in res])
        dip = np.mean([r[1] for r in res])
        wx = [W.wallet([t for t in trades], 10, s) for s in range(12)]
        xdip = np.mean([r[1] for r in wx])
        sk = np.mean([r[4] for r in res])
        print("  %-38s %7.1f%% %11.1f%% %11.1f%% %8.0f" % (label, 100 * ann, 100 * dip, 100 * xdip, sk))
        out[key] = dict(a_year=float(ann), worst_dip_marked=float(dip), worst_dip_exit_only=float(xdip),
                        skipped=float(sk))
        if key == "as_is":
            c = res[0][2]
            worst_i = int(np.argmin([x[2] for x in c]))
            out["worst_day"] = c[worst_i][0]
            print("    the low point of the account was %s (%.1f%% under its high)" % (c[worst_i][0], 100 * c[worst_i][2]))
    json.dump(out, io.open(OUT, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
