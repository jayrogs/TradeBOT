"""
run_test.py -- press go.

    python run_test.py                # build window 2023-2025 (default)
    python run_test.py --null         # synthetic random data, no edge possible
    python run_test.py --holdout      # 2026. ONE run, only after a build pass.

First run downloads several hundred symbols and their earnings dates; that
takes a few minutes. Everything is cached in ./cache afterwards.
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

import data as D
import harness as H

BUILD = ("2023-01-01", "2025-12-31")
HOLDOUT = ("2026-01-01", "2026-12-31")
WARMUP_DAYS = 420          # calendar days of history needed before the window


def load_real(start, end):
    warm = (pd.Timestamp(start) - pd.Timedelta(days=WARMUP_DAYS)).strftime("%Y-%m-%d")
    end_dl = (pd.Timestamp(end) + pd.Timedelta(days=5)).strftime("%Y-%m-%d")

    print("universe: rebuilding point-in-time S&P 500 membership...")
    memb, sectors = D.membership_intervals(warm, end)
    syms = sorted(memb)
    print("  %d symbols were in the index at some point in the window" % len(syms))

    bars = D.download_bars(syms + ["SPY"], warm, end_dl)
    spy = bars.pop("SPY", None)
    if spy is None:
        sys.exit("could not download SPY -- no benchmark and no regime gate")
    print("  bars for %d/%d symbols" % (len(bars), len(syms)))

    sectors = D.fill_missing_sectors(list(bars), sectors)
    earn = D.download_earnings(list(bars))
    n_missing = sum(1 for s in bars if len(earn.get(s, [])) == 0)
    print("  earnings dates missing for %d symbols (no blackout applied there)"
          % n_missing)

    print("computing indicators...")
    feats = H.build_features(bars, earn, H.DEFAULTS)
    print("  %d symbols have enough history" % len(feats))
    return feats, sectors, spy, memb


def load_null(start, end, n_syms=400, seed=7):
    """
    Synthetic prices: random walks with no edge of any kind. If the engine
    reports a real edge on this, the engine is broken.

    Drift is set to match a rising market so the regime gate is active and the
    strategy actually trades -- a null test where nothing trades proves nothing.
    """
    rng = np.random.default_rng(seed)
    warm = pd.Timestamp(start) - pd.Timedelta(days=WARMUP_DAYS)
    cal = pd.bdate_range(warm, end)
    n = len(cal)
    out = {}
    for i in range(n_syms + 1):
        sym = "SPY" if i == 0 else "N%03d" % i
        vol = 0.012 if sym == "SPY" else rng.uniform(0.012, 0.035)
        mu = 0.08 / 252.0
        r = rng.normal(mu, vol, n)
        close = 100.0 * np.exp(np.cumsum(r))
        intr = np.abs(rng.normal(0, vol * 0.7, n))
        high = close * (1 + intr)
        low = close * (1 - intr)
        openp = np.concatenate([[close[0]], close[:-1]]) * (1 + rng.normal(0, vol * 0.3, n))
        openp = np.clip(openp, low, high)
        out[sym] = pd.DataFrame({"Open": openp, "High": high, "Low": low,
                                 "Close": close,
                                 "Volume": rng.uniform(2e6, 2e7, n)}, index=cal)
    spy = out.pop("SPY")
    sectors = {s: "S%d" % (i % 11) for i, s in enumerate(out)}
    feats = H.build_features(out, {}, H.DEFAULTS)
    return feats, sectors, spy, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--null", action="store_true",
                    help="run on synthetic random data (machinery check)")
    ap.add_argument("--holdout", action="store_true",
                    help="run on 2026. Only once, only after a build-window pass.")
    ap.add_argument("--label", default=None)
    ap.add_argument("--no-log", action="store_true",
                    help="do not count this run as a trial (use for debugging only)")
    args = ap.parse_args()

    start, end = HOLDOUT if args.holdout else BUILD
    label = args.label or ("NULL (synthetic)" if args.null else
                           "weakness_reversion " + ("HOLDOUT 2026" if args.holdout
                                                    else "build 2023-2025"))

    if args.holdout and not os.path.exists(os.path.join(H.HERE, "BUILD_PASSED")):
        sys.exit("Refusing to run the holdout: no BUILD_PASSED marker.\n"
                 "The 2026 data is the one honest test available and it can only "
                 "be spent once, on a strategy that already cleared the build window.")

    loader = load_null if args.null else load_real
    feats, sectors, spy, memb = loader(start, end)

    print("\nrunning backtest %s -> %s ..." % (start, end))
    eq, tr, meta = H.run_backtest(feats, sectors, spy, memb, start, end,
                                  H.weakness_reversion)
    res = H.report(eq, tr, meta, spy, label, count_trial=not args.no_log)
    passed = H.check_criteria(res, tr)

    eq.to_csv(os.path.join(H.HERE, "last_equity.csv"))
    if len(tr):
        tr.to_csv(os.path.join(H.HERE, "last_trades.csv"), index=False)
    print("\nwrote last_equity.csv / last_trades.csv")

    if args.null and passed:
        print("\n  *** WARNING: the null run PASSED. The engine is finding edge in "
              "random numbers. Do not believe any real result until this is fixed.")


if __name__ == "__main__":
    main()
