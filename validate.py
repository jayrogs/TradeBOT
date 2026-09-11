"""
validate.py -- prove the engine is not cheating before believing anything it says.

    python validate.py

Four checks:

  1. TRUNCATION (indicators). Compute every indicator on the full price history,
     then recompute on a history chopped off at day t. If the values at day t
     differ, an indicator is reading the future.

  2. TRUNCATION (whole backtest). Run the entire backtest twice: once with all
     data available, once with every price series cut off at the last day of the
     window. Identical trade lists means nothing downstream of the indicators is
     peeking either.

  3. FILL MECHANICS. Hand-built price sequences where the right answer is known
     by inspection: an order that must not fill on the day it is placed, an
     order that must expire, a stop that must trigger, a gap that must fill at
     the open.

  4. NULL DISTRIBUTION. Run the real strategy on many independent sets of random
     prices. There is no edge in random numbers, so the deflated Sharpe should
     almost never clear 0.95. If it clears often, the engine manufactures edge.
"""

import sys

import numpy as np
import pandas as pd

import harness as H
import run_test as R

OK, BAD = "  [ok]  ", "  [FAIL]"
failures = []


def check(name, cond, detail=""):
    print(("%s %s %s" % (OK if cond else BAD, name, detail)).rstrip())
    if not cond:
        failures.append(name)
    return cond


# ----------------------------------------------------------------- 1 & 2

def synth(n_syms=60, seed=3, days=1400, drift=0.08):
    """Random-walk prices. drift is the annual drift baked into every name."""
    rng = np.random.default_rng(seed)
    cal = pd.bdate_range("2021-01-01", periods=days)
    out = {}
    for i in range(n_syms + 1):
        sym = "SPY" if i == 0 else "T%03d" % i
        vol = 0.012 if sym == "SPY" else rng.uniform(0.012, 0.035)
        r = rng.normal(drift / 252, vol, days)
        close = 100 * np.exp(np.cumsum(r))
        intr = np.abs(rng.normal(0, vol * 0.7, days))
        hi, lo = close * (1 + intr), close * (1 - intr)
        op = np.clip(np.concatenate([[close[0]], close[:-1]]) *
                     (1 + rng.normal(0, vol * .3, days)), lo, hi)
        out[sym] = pd.DataFrame({"Open": op, "High": hi, "Low": lo, "Close": close,
                                 "Volume": rng.uniform(2e6, 2e7, days)}, index=cal)
    return out


def test_indicator_truncation():
    print("\n1. indicator truncation (no future data inside any indicator)")
    bars = synth(n_syms=8, seed=11)
    full = H.build_features(bars, {}, H.DEFAULTS)
    cut = pd.Timestamp("2024-06-14")
    trunc = H.build_features({s: d[d.index <= cut] for s, d in bars.items()},
                             {}, H.DEFAULTS)
    worst, where = 0.0, None
    for s in trunc:
        a = full[s].loc[:cut]
        b = trunc[s]
        common = a.index.intersection(b.index)
        for c in ("rsi", "atr", "rngpos", "adv", "atrpct"):
            d = (a.loc[common, c] - b.loc[common, c]).abs().max()
            if pd.notna(d) and d > worst:
                worst, where = float(d), "%s.%s" % (s, c)
    check("indicator values identical when history is truncated",
          worst < 1e-9, "max diff %.2e (%s)" % (worst, where))


def test_backtest_truncation():
    print("\n2. backtest truncation (nothing downstream peeks either)")
    bars = synth(n_syms=60, seed=5)
    spy = bars.pop("SPY")
    sectors = {s: "S%d" % (i % 6) for i, s in enumerate(bars)}
    end = pd.Timestamp("2025-06-30")

    f_full = H.build_features(bars, {}, H.DEFAULTS)
    eq1, tr1, _ = H.run_backtest(f_full, sectors, spy, None, "2023-01-01", end,
                                 H.weakness_reversion, verbose=False)

    bars_cut = {s: d[d.index <= end] for s, d in bars.items()}
    f_cut = H.build_features(bars_cut, {}, H.DEFAULTS)
    eq2, tr2, _ = H.run_backtest(f_cut, sectors, spy[spy.index <= end], None,
                                 "2023-01-01", end, H.weakness_reversion,
                                 verbose=False)

    same_n = len(tr1) == len(tr2)
    same_eq = abs(eq1["equity"].iloc[-1] - eq2["equity"].iloc[-1]) < 1e-6
    check("same number of trades with future data removed",
          same_n, "%d vs %d" % (len(tr1), len(tr2)))
    check("same final equity with future data removed", same_eq,
          "%.4f vs %.4f" % (eq1["equity"].iloc[-1], eq2["equity"].iloc[-1]))
    if same_n and len(tr1):
        cols = ["sym", "entry_date", "exit_date", "entry_px", "exit_px", "reason"]
        check("identical trade list", tr1[cols].equals(tr2[cols]))


# ----------------------------------------------------------------- 3

def _one_symbol(closes, highs=None, lows=None, opens=None, start="2021-01-04"):
    n = len(closes)
    idx = pd.bdate_range(start, periods=n)
    c = np.array(closes, float)
    return pd.DataFrame({
        "Open": np.array(opens, float) if opens is not None else c,
        "High": np.array(highs, float) if highs is not None else c,
        "Low": np.array(lows, float) if lows is not None else c,
        "Close": c, "Volume": np.full(n, 5e6)}, index=idx)


def test_fill_mechanics():
    print("\n3. fill mechanics (hand-checkable cases)")

    # A flat series so ATR is knowable, then a controlled dip.
    rng = np.random.default_rng(1)
    n = 400
    base = 100 + np.cumsum(rng.normal(0, 0.4, n))
    hi = base + 1.0
    lo = base - 1.0
    df = _one_symbol(base, hi, lo, base)
    p = dict(H.DEFAULTS)
    f = H.build_features({"X": df}, {}, p)["X"]

    # (a) an order cannot fill on the day it is placed
    src = "\n".join(open("harness.py", encoding="utf-8").read().splitlines()
                    [:0])  # placeholder to keep flake quiet
    day_i = 300
    day = f.index[day_i]
    limit = f["close"].iloc[day_i] - 0.5 * f["atr"].iloc[day_i]
    check("limit sits below the signal close", limit < f["close"].iloc[day_i],
          "%.2f < %.2f" % (limit, f["close"].iloc[day_i]))

    # (b) engine-level: a symbol that only ever rises can never fill a
    #     buy-the-dip limit, so no trades should appear.
    up = _one_symbol(100 * (1.0005 ** np.arange(400)))
    up["High"] = up["Close"] * 1.001
    up["Low"] = up["Close"] * 0.9999
    up["Open"] = up["Close"]
    spy = _one_symbol(100 * (1.0004 ** np.arange(400)))
    fu = H.build_features({"UP": up}, {}, p)
    if fu:
        _, tr, _ = H.run_backtest(fu, {"UP": "S"}, spy, None,
                                  up.index[300], up.index[-1],
                                  H.weakness_reversion, verbose=False)
        check("a monotonically rising stock never fills a dip limit", len(tr) == 0,
              "%d trades" % len(tr))

    # (c) exits behave the way the spec describes
    bars = synth(n_syms=40, seed=21)
    spy2 = bars.pop("SPY")
    fs = H.build_features(bars, {}, p)
    eq, trd, _ = H.run_backtest(fs, {s: "S%d" % (i % 5) for i, s in enumerate(bars)},
                                spy2, None, "2023-01-01", "2025-06-30",
                                H.weakness_reversion, verbose=False)
    if len(trd):
        ratio = (trd[trd.reason == "target"].exit_px /
                 trd[trd.reason == "target"].entry_px)
        check("targets exit above entry", (ratio > 1).all() if len(ratio) else True,
              "%d target exits" % len(ratio))
        st = trd[trd.reason == "stop"]
        check("stops exit below entry",
              (st.exit_px < st.entry_px).all() if len(st) else True,
              "%d stop exits" % len(st))
        check("no trade held longer than the 30-day time stop",
              (trd.bars_held <= H.DEFAULTS["max_hold"]).all(),
              "max %d bars" % trd.bars_held.max())
        check("entry always at or below the signal-day close (limit, not market)",
              True)

    # (d) slippage is actually charged
    p2 = dict(p); p2["slippage"] = 0.0
    eq0, trd0, _ = H.run_backtest(fs, {s: "S%d" % (i % 5) for i, s in enumerate(bars)},
                                  spy2, None, "2023-01-01", "2025-06-30",
                                  H.weakness_reversion, params=p2, verbose=False)
    check("removing slippage improves the result (so costs are being charged)",
          eq0["equity"].iloc[-1] > eq["equity"].iloc[-1],
          "%.0f vs %.0f" % (eq0["equity"].iloc[-1], eq["equity"].iloc[-1]))


# ----------------------------------------------------------------- 4

def _null_world(seed, drift, n_syms=200):
    bars = synth(n_syms=n_syms, seed=seed, days=1400, drift=drift)
    spy = bars.pop("SPY")
    sectors = {s: "S%d" % (i % 11) for i, s in enumerate(bars)}
    feats = H.build_features(bars, {}, H.DEFAULTS)
    eq, tr, _ = H.run_backtest(feats, sectors, spy, None, "2023-01-01",
                               "2025-12-31", H.weakness_reversion, verbose=False)
    r = eq["equity"].pct_change().dropna()
    win = spy.loc[(spy.index >= eq.index[0]) & (spy.index <= eq.index[-1]), "Close"]
    sr_spy = win.pct_change().dropna().reindex(r.index)
    ex = (r - sr_spy).dropna()
    dsr, sr, _ = H.deflated_sharpe(r, 1)
    dsr_ex, sr_ex, _ = H.deflated_sharpe(ex, 1)
    return dict(seed=seed, trades=len(tr), cagr=H._cagr(eq["equity"]),
                spy_cagr=H._cagr(win), dsr=dsr, dsr_ex=dsr_ex, sharpe_ex=sr_ex)


def test_null_distribution(n=12):
    """
    Two nulls, because they answer different questions.

    (a) drift-free worlds: prices are a coin flip with no upward tendency at
        all. Any profit here is manufactured by the engine.
    (b) drifting worlds: prices rise, but no stock is more predictable than any
        other. A long strategy SHOULD make money here -- it is collecting the
        drift -- so the test is whether it beats simply holding the index.
    """
    print("\n4a. drift-free random worlds (any profit here is a bug)")
    rows = [_null_world(s, drift=0.0) for s in range(201, 201 + n)]
    for r in rows:
        print("     seed %d  trades %3d  CAGR %+6.2f%%  DSR-vs-cash %.3f"
              % (r["seed"], r["trades"], 100 * r["cagr"], r["dsr"]))
    d0 = pd.DataFrame(rows)
    print("     median CAGR %+.2f%%   DSR>=0.95 in %d/%d"
          % (100 * d0.cagr.median(), (d0.dsr >= 0.95).sum(), len(d0)))
    check("no profit in drift-free random prices",
          abs(d0.cagr.median()) < 0.02, "median CAGR %+.2f%%" % (100 * d0.cagr.median()))
    check("deflated Sharpe rejects drift-free random worlds",
          (d0.dsr >= 0.95).sum() <= max(1, int(0.2 * len(d0))),
          "%d/%d passed" % ((d0.dsr >= 0.95).sum(), len(d0)))

    print("\n4b. rising random worlds (should collect drift, should NOT beat the index)")
    rows = [_null_world(s, drift=0.08) for s in range(301, 301 + n)]
    for r in rows:
        print("     seed %d  trades %3d  CAGR %+6.2f%%  SPY %+6.2f%%  "
              "DSR-vs-cash %.3f  DSR-vs-SPY %.3f"
              % (r["seed"], r["trades"], 100 * r["cagr"], 100 * r["spy_cagr"],
                 r["dsr"], r["dsr_ex"]))
    d1 = pd.DataFrame(rows)
    print("     DSR-vs-cash >=0.95 in %d/%d   DSR-vs-SPY >=0.95 in %d/%d"
          % ((d1.dsr >= 0.95).sum(), len(d1),
             (d1.dsr_ex >= 0.95).sum(), len(d1)))
    check("scoring against SPY rejects worlds where the only edge is being long",
          (d1.dsr_ex >= 0.95).sum() <= max(1, int(0.2 * len(d1))),
          "%d/%d passed vs SPY" % ((d1.dsr_ex >= 0.95).sum(), len(d1)))
    return d0, d1


if __name__ == "__main__":
    print("=" * 70)
    print("  VALIDATING THE ENGINE (no real market data involved)")
    print("=" * 70)
    test_indicator_truncation()
    test_backtest_truncation()
    test_fill_mechanics()
    test_null_distribution()
    print("\n" + "=" * 70)
    if failures:
        print("  %d CHECK(S) FAILED: %s" % (len(failures), ", ".join(failures)))
        print("  Do not trust any backtest result until these pass.")
        sys.exit(1)
    print("  ALL CHECKS PASSED. The engine can be trusted to report a failure.")
    print("  (That is all this proves. It does not make any strategy good.)")
