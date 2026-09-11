"""size_by_runup.py -- does putting MORE money on a backburner when the name
ran up harder beforehand make more per dollar?  Uses the 4-year events file
plus each name's DAILY chart for a real run-up measure.

Run-up = how far the name rallied into its recent high: the highest close in
the 30 days before the oversold print, divided by the close 30 days before
THAT high, minus 1.  (The study's own "3-day move" is always negative at an
oversold print on slow charts, so it is not a run-up.)  Drop = close at the
print vs that high.

Sizing rules tested (first-unit size; adds keep the same unit size):
  flat        every campaign gets 1 unit
  run x2      1 + 2 * run_up   (a 50% rally buys 2 units, 150% buys 4)
  steps       rally <10%: 1, 10-30%: 2, 30-100%: 3, 100%+: 4
  inverse     the opposite, as a control
Return per dollar = sum(net * size * units) / sum(size * units): what a fixed
pot of money would have made, not an average of percentages.

    python studies/size_by_runup.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from studies.backburner_study import CLASS_COST, load_csv, resample, RULE   # noqa: E402

RULES = {
    "flat": lambda r: np.ones_like(r),
    "run x2": lambda r: 1 + 2 * r,
    "steps": lambda r: np.select([r < .10, r < .30, r < 1.0], [1, 2, 3], 4),
    "inverse (control)": lambda r: np.select([r < .10, r < .30, r < 1.0], [4, 3, 2], 1),
}
BUCKETS = ((-1, .10, "rally <10%"), (.10, .30, "10-30%"), (.30, 1.0, "30-100%"), (1.0, 99, "100%+"))


def daily(sym, kind):
    if kind == "crypto":
        h1 = load_csv(os.path.join("history", "%s_1h.csv.gz" % sym))
        return resample(h1, RULE["1d"]) if h1 is not None else None
    folder = {"futures": "futures", "forex": "forex", "cfd": "futures_cfd"}.get(kind, "stocks")
    return load_csv(os.path.join("history", folder, "%s_1d.csv.gz" % sym))


def runup_table(d1):
    """Per day: rally into the trailing-30-day high, and drop from it."""
    c = d1["Close"].astype(float)
    hi = c.rolling(30, min_periods=5).max()
    # close 30 days before the day the trailing high was set
    idx = c.rolling(30, min_periods=5).apply(lambda w: int(np.argmax(w)), raw=True)
    pos = np.arange(len(c)) - (29 - idx.fillna(0).values.astype(int))    # bar index of the high
    pos = np.clip(pos, 0, len(c) - 1)
    before = np.clip(pos - 30, 0, len(c) - 1)
    rally = hi.values / c.values[before] - 1
    drop = c.values / hi.values - 1
    return pd.DataFrame(dict(rally=rally, drop=drop), index=d1.index.normalize())


def per_dollar(g, w):
    m = w * g["units"].values
    return float((g["net"].values * m).sum() / m.sum()) if m.sum() > 0 else np.nan


def main():
    ev = pd.read_csv(os.path.join("validation", "backburner_events.csv.gz"), low_memory=False)
    ev["net"] = ev["ret_ride"] - ev["kind"].map(CLASS_COST).fillna(0.0005)
    ev = ev[np.isfinite(ev["net"])].copy()
    ev["day"] = pd.to_datetime(ev["t"]).dt.normalize()
    parts = []
    for (kind, sym), g in ev.groupby(["kind", "sym"]):
        d1 = daily(sym, kind)
        if d1 is None or len(d1) < 60:
            continue
        rt = runup_table(d1)
        rt = rt[~rt.index.duplicated()]
        # use the day BEFORE the print so the print's own day does not leak in
        m = rt.reindex(g["day"] - pd.Timedelta(days=1), method="ffill")
        g = g.copy(); g["rally"] = m["rally"].values; g["drop"] = m["drop"].values
        parts.append(g)
    ev = pd.concat(parts)
    ev = ev[np.isfinite(ev["rally"])]
    ev["rally"] = ev["rally"].clip(lower=0)
    lines = ["run-up = rally into the trailing 30-day high, measured on the daily chart the day before the print",
             "%d campaigns with a run-up measure" % len(ev)]

    def block(title, g):
        if len(g) < 200:
            return
        lines.append("\n%s  (%d campaigns)" % (title, len(g)))
        base = None
        for name, f in RULES.items():
            v = per_dollar(g, f(g["rally"].values))
            if base is None: base = v
            lines.append("  %-18s %+6.2f%% per $   %s" % (name, 100 * v, "" if name == "flat" else "(%+.2f%% vs flat)" % (100 * (v - base))))
        for lo, hi, lab in BUCKETS:
            b = g[(g.rally >= lo) & (g.rally < hi)]
            if len(b) >= 50:
                lines.append("     %-11s n=%6d  %+6.2f%% per $  won %3.0f%%  typical drop from the high %5.1f%%" % (
                    lab, len(b), 100 * per_dollar(b, np.ones(len(b))), 100 * (b.net > 0.005).mean(), 100 * b["drop"].median()))
    block("ALL", ev)
    for tf in ["5m", "15m", "1h", "4h", "12h", "1d", "1w"]:
        block("all classes  %s" % tf, ev[ev.tf == tf])
    for kind in ["crypto", "stock", "etf", "futures", "forex"]:
        for tf in ["15m", "1h", "4h", "1d"]:
            block("%s  %s" % (kind, tf), ev[(ev.kind == kind) & (ev.tf == tf)])
    hot = ev[(ev["move"].fillna(0) >= .10) | (ev["move3"].fillna(0) >= .20)]
    block("HOT names only (up 10% on the day or 20% in 3 days), all tfs", hot)
    for h in ("first", "second"):
        block("ALL, %s half of the 4 years" % h, ev[ev.half == h])
    txt = "\n".join(lines)
    print(txt)
    open(os.path.join("validation", "size_by_runup.txt"), "w").write(txt)
    ev[["sym", "kind", "tf", "t", "rally", "drop"]].to_csv(os.path.join("validation", "runup_by_event.csv.gz"), index=False)


if __name__ == "__main__":
    main()
