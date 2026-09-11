"""
events.py -- event study on the frozen chart patterns.

    python events.py

THE QUESTION
    A setup appears. You buy at the next close and hold N days. Did you beat
    simply holding SPY for those same N days?

Every triggered name is held for a fixed horizon, all open holdings are equally
weighted, and the resulting daily portfolio return is compared against SPY on
the same days. That produces one daily excess-return series per pattern, which
is what the t-statistic is computed on -- no overlapping-window inflation, and
the number means something tradeable rather than something abstract.

Reported for each pattern and horizon:
    events    how many times it fired
    exc/yr    annualised return of the pattern portfolio minus SPY
    t         is that distinguishable from zero
    hit       share of individual events that beat SPY over the horizon

16 patterns x 3 horizons is 48 looks, so a couple of |t| > 2 results are
expected from luck alone. Benjamini-Hochberg is applied across all of them, and
anything that survives still has to repeat on 2023-2025.
"""

import numpy as np
import pandas as pd

import patterns as P
import survey as V

HORIZONS = [5, 21, 63]
DISCOVERY = ("2010-01-01", "2022-12-31")
CONFIRM = ("2023-01-01", "2025-12-31")


def pattern_returns(trig, d, hold, start, end):
    """Daily return of an equal-weight book holding every trigger for `hold`
    days, minus SPY. Entry is the close AFTER the trigger."""
    close = d["close"]
    ret = close.pct_change()
    elig = d["elig"]

    fired = (trig & elig).fillna(False)
    # held from the day after the trigger, for `hold` days
    book = fired.shift(1).fillna(False).astype(float) \
                .rolling(hold, min_periods=1).max()
    w = book.div(book.sum(axis=1).replace(0, np.nan), axis=0)

    days = (close.index >= pd.Timestamp(start)) & (close.index <= pd.Timestamp(end))
    port = (w * ret).sum(axis=1).where(book.sum(axis=1) > 0)

    # TWO benchmarks, because they answer two different questions.
    #   vs SPY  -- would this have beaten buying the index? (the goal)
    #   vs UNI  -- did the pattern PICK better stocks than picking at random
    #              from the same universe? (whether the pattern itself works)
    # Over 2023-2025 an equal-weight S&P basket lost ~10pp/yr to cap-weighted
    # SPY on mega-cap concentration alone, so vs SPY alone would score every
    # pattern as a failure regardless of whether it selects well.
    uw = d["elig"].astype(float)
    uw = uw.div(uw.sum(axis=1).replace(0, np.nan), axis=0)
    uni = (uw * ret).sum(axis=1)

    out = pd.DataFrame({"port": port, "spy": d["spy_ret"], "uni": uni})[days].dropna()
    out["exc"] = out["port"] - out["spy"]
    out["exc_uni"] = out["port"] - out["uni"]
    n_events = int(fired[days].sum().sum())
    invested = float((book[days].sum(axis=1) > 0).mean())
    return out, n_events, invested


def event_hit_rate(trig, d, hold, start, end):
    """Share of individual events that beat SPY over the holding window."""
    close, spy = d["close"], d["spy_close"]
    fwd = close.shift(-hold - 1) / close.shift(-1) - 1.0
    sfwd = (spy.shift(-hold - 1) / spy.shift(-1) - 1.0)
    exc = fwd.sub(sfwd, axis=0)
    days = (close.index >= pd.Timestamp(start)) & (close.index <= pd.Timestamp(end))
    m = (trig & d["elig"]).fillna(False) & days[:, None]
    vals = exc.where(m).stack().dropna()
    if len(vals) == 0:
        return np.nan, np.nan
    return float((vals > 0).mean()), float(vals.mean())


def run(d, start, end, title):
    print("\n" + "=" * 82)
    print("  %s   %s to %s" % (title, start, end))
    print("=" * 82)
    print("  %-19s %6s %5s %10s %7s %10s %7s %6s" %
          ("pattern", "events", "hold", "vs SPY/yr", "t", "vs UNIV/yr", "t", "hit%"))
    print("  " + "-" * 78)
    rows = []
    for name, (fn, desc) in P.PATTERNS.items():
        trig = fn(d)
        first = True
        for h in HORIZONS:
            r, n_ev, inv = pattern_returns(trig, d, h, start, end)
            if len(r) < 250 or n_ev < 100:
                continue
            st = V.stats(r["exc"])
            su = V.stats(r["exc_uni"])
            hit, mean_ev = event_hit_rate(trig, d, h, start, end)
            rows.append(dict(name=name, desc=desc, hold=h, events=n_ev,
                             exc=st["ann"], t=st["t"], p=st["p"],
                             exc_uni=su["ann"], t_uni=su["t"], p_uni=su["p"],
                             hit=hit, invested=inv))
            print("  %-19s %6d %5d %+9.2f%% %7.2f %+9.2f%% %7.2f %5.1f%%"
                  % (name if first else "", n_ev, h, 100 * st["ann"], st["t"],
                     100 * su["ann"], su["t"], 100 * hit))
            first = False
    res = pd.DataFrame(rows)
    if res.empty:
        print("  nothing fired often enough to measure")
        return res
    res["survives"] = V.benjamini_hochberg(res["p"].values)
    res["survives_uni"] = V.benjamini_hochberg(res["p_uni"].values)
    print("  " + "-" * 78)
    print("\n  After correcting for %d pattern-horizon combinations tested:" % len(res))
    for col, lab in [
            ("survives", "vs SPY -- would it have beaten the index"),
            ("survives_uni", "vs equal-weight universe -- does the pattern pick well")]:
        print("    %s:" % lab)
        key = "t" if col == "survives" else "t_uni"
        surv = res[res[col]].sort_values(key, key=abs, ascending=False)
        if surv.empty:
            print("      nothing survives. All of it is consistent with luck.")
        for _, r in surv.iterrows():
            v, t = (r.exc, r.t) if col == "survives" else (r.exc_uni, r.t_uni)
            print("      %-19s hold %2dd  %+6.2f%%/yr  t=%+.2f  hit %.0f%%  %s"
                  % (r["name"], r.hold, 100 * v, t, 100 * r.hit, r["desc"]))
    return res


def main():
    d = V.load_panel("2009-01-01", "2026-12-31")

    disc = run(d, *DISCOVERY, title="DISCOVERY -- 16 chart patterns, one pass")
    disc.to_csv("events_discovery.csv", index=False)

    conf = run(d, *CONFIRM, title="CONFIRMATION -- untouched window")
    conf.to_csv("events_confirm.csv", index=False)

    m = disc[["name", "hold", "exc_uni", "t_uni", "survives_uni"]].merge(
        conf[["name", "hold", "exc_uni", "t_uni"]], on=["name", "hold"],
        suffixes=("_d", "_c")).rename(columns={"exc_uni_d": "exc_d",
                                               "t_uni_d": "t_d",
                                               "exc_uni_c": "exc_c",
                                               "t_uni_c": "t_c",
                                               "survives_uni": "survives"})
    print("\n" + "=" * 82)
    print("  DOES IT REPLICATE?  (scored against the equal-weight universe,")
    print("   i.e. did the pattern pick better than picking at random)")
    print("=" * 82)
    print("  %-19s %5s %11s %7s %11s %7s   %s"
          % ("pattern", "hold", "2010-22", "t", "2023-25", "t", "verdict"))
    for _, r in m.sort_values("t_d", key=abs, ascending=False).iterrows():
        same = np.sign(r.exc_d) == np.sign(r.exc_c)
        if r.survives and same and abs(r.t_c) > 2:
            v = "HOLDS UP"
        elif r.survives and same:
            v = "same direction, weaker"
        elif r.survives:
            v = "REVERSED"
        else:
            v = "-"
        print("  %-19s %5d %+10.2f%% %7.2f %+10.2f%% %7.2f   %s"
              % (r["name"], r.hold, 100 * r.exc_d, r.t_d,
                 100 * r.exc_c, r.t_c, v))
    print("\n2026 remains untouched.")


if __name__ == "__main__":
    main()
