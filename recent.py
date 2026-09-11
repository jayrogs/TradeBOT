"""
recent.py -- everything re-measured on 2022 onward only.

    python recent.py

Run at the user's instruction: the market since 2022 is arguably a different
regime (rates off the floor, index concentration at records), so older data may
not describe it.

TWO THINGS THIS DOES

1. Tests that premise rather than assuming it. For every signal and pattern,
   the 2010-2021 result sits next to the 2022-2025 result. If the two are alike,
   the regime argument is wrong and throwing away 12 years cost power for
   nothing. If they differ, the argument is right.

2. Re-runs both studies on 2022-2025 alone.

THE COST, MEASURED (not asserted)
    40 pure-noise signals through the same pipeline:
        over 13 years  the biggest fake result was +2.3%/yr, sd 1.1%/yr
        over 4 years   the biggest fake result was +4.2%/yr, sd 1.9%/yr
    Same false-positive RATE, roughly double the SIZE. On a 2022-2025 window,
    anything below about 5%/yr cannot be told apart from noise by size alone.

THE STRUCTURAL COST
    2023-2025 was the confirmation window. Restricted to 2022 onward there is
    not enough data to both find something and check it, so everything below is
    UNCONFIRMED by construction. The only untouched data left is 2026, and it
    can be spent exactly once.
"""

import warnings

import numpy as np
import pandas as pd

import events as E
import patterns as P
import signals as S
import survey as V

warnings.filterwarnings("ignore")

OLD = ("2010-01-01", "2021-12-31")
NEW = ("2022-01-01", "2025-12-31")


def regime_compare(d):
    """Did the regime actually change? Same measurement, two eras."""
    print("\n" + "=" * 78)
    print("  DID THE REGIME CHANGE?  same signal, 2010-2021 vs 2022-2025")
    print("=" * 78)
    print("  %-14s %12s %7s %12s %7s   %s"
          % ("signal", "2010-21", "t", "2022-25", "t", ""))
    rows = []
    for name, (fn, desc) in S.SIGNALS.items():
        sig = fn(d)
        a = V.stats(V.spread_returns(sig, d, *OLD)["ls"])
        b = V.stats(V.spread_returns(sig, d, *NEW)["ls"])
        if not np.isfinite(a["t"]) or not np.isfinite(b["t"]):
            continue
        flip = np.sign(a["ann"]) != np.sign(b["ann"])
        rows.append(dict(name=name, old=a["ann"], t_old=a["t"],
                         new=b["ann"], t_new=b["t"], flip=flip))
        print("  %-14s %+11.2f%% %7.2f %+11.2f%% %7.2f   %s"
              % (name, 100 * a["ann"], a["t"], 100 * b["ann"], b["t"],
                 "sign flipped" if flip else ""))
    r = pd.DataFrame(rows)
    n_flip = int(r.flip.sum())
    print("\n  %d of %d signals flipped sign between the two eras." % (n_flip, len(r)))
    print("  For reference, if the two eras were the same and every result were")
    print("  noise centred on zero, about half would flip by chance alone.")
    both_sig = ((r.t_old.abs() > 2) & (r.t_new.abs() > 2)).sum()
    print("  Signals significant in BOTH eras: %d." % both_sig)
    return r


def main():
    d = V.load_panel("2009-01-01", "2026-12-31")

    regime_compare(d)

    sig = V.run(d, *NEW, title="SIGNALS -- 2022 onward only  [UNCONFIRMED]")
    sig.to_csv("recent_signals.csv", index=False)

    pat = E.run(d, *NEW, title="CHART PATTERNS -- 2022 onward only  [UNCONFIRMED]")
    pat.to_csv("recent_patterns.csv", index=False)

    print("\n" + "=" * 78)
    print("  READ THIS BEFORE ACTING ON ANYTHING ABOVE")
    print("=" * 78)
    print("  Noise alone produces about 4%/yr and |t| near 1.6 in a window this")
    print("  short. Nothing above was checked on data it had not already seen,")
    print("  because on 2022-2025 there is no room to hold data back.")
    print("  2026 remains untouched and is the only honest test left.")


if __name__ == "__main__":
    main()
