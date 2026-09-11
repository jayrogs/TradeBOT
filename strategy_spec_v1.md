# Weakness-Reversion Swing System — v1 Specification

**Status: PRE-REGISTERED. Frozen before any backtest is run.**

Written 2026-08-17. Build window 2023-01-01 → 2025-12-31.
2026 held out, to be tested exactly once.

The point of writing this down first is that it removes the option of deciding
what counts as success after seeing the result. Every number below is chosen
now, from reasoning, not from fitting.

---

## 1. What this is built on

One verified observation from 169 ChartGuys trades: **stocks falling on the daily
timeframe at signal time outperformed stocks rising** — 60.8% win / +4.60% mean
versus 45.8% / +1.75%. It replicated across all three fill-speed buckets and
survived a selection-bias confound test.

Everything else from that analysis (zone depth, zone width, rationale keywords,
weekly trend) is treated as unverified and is NOT used here.

## 2. What we're fixing about their design

| their flaw | our change |
|---|---|
| stop 1.27% below a 7.89%-wide zone | stop sized to ATR, not to the zone |
| 2 picks/week regardless of conditions | take everything that qualifies, zero some weeks |
| 89% long, no regime filter | explicit market regime gate |
| a third of setups never fill | time-limited order, capital released on expiry |
| buys strength (their worst group) | buys weakness (their best group) |

---

## 3. Universe

- S&P 500 constituents, as of each test date (survivorship-bias aware; if
  point-in-time membership is unavailable, note it as a known bias and use
  current membership)
- Minimum 20-day average dollar volume: **$20M**
- Price above **$10**
- Exclude within **5 trading days either side of earnings**

## 4. Entry conditions

All must be true on a confirmed daily close:

1. **Weakness (the verified edge):** RSI(14) ≤ 40
2. **Not a falling knife:** close ≥ 60% of the 252-day range low-to-high, i.e.
   the stock is down but not in free-fall
3. **Liquidity/vol sanity:** ATR(14) between 1.5% and 6% of price
4. **Regime gate:** SPY close > SPY SMA(200). No new longs when this fails.
5. **Rank filter:** among all names passing 1–4 on a given day, take the
   **5 with the lowest RSI**. Cross-sectional ranking, not an absolute threshold.

**Order:** limit at **close − 0.5 × ATR(14)**, good for **10 trading days**,
then cancelled and capital released.

Rationale for 0.5 ATR: shallow enough to fill often, deep enough to improve entry.
Not optimized — chosen as a round starting value.

## 5. Exit conditions

- **Stop:** entry − **2.0 × ATR(14)** measured at entry (frozen, does not trail)
- **Target:** entry + **3.0 × ATR(14)**
- **Time stop:** close at market after **30 trading days** if neither hit
- Stop is placed **at the broker** as a resting order, not held in code

R:R is 1.5:1 by construction. With the ~55% win rate the edge implies, expectancy
is positive with room to spare.

## 6. Position sizing

- Risk **1.0%** of account equity per trade
- Shares = (equity × 0.01) ÷ (2.0 × ATR)
- Hard cap: no position exceeds **20%** of equity regardless of the above
- Maximum **8 concurrent positions**
- Maximum **2 positions** per GICS sector

## 7. Costs assumed in backtest

- Slippage **0.10%** per side
- Commission $0
- Same-bar stop-and-target ties scored as **losses**
- Prices must be **nominal** (un-split, un-dividend-adjusted) to match level logic

---

## 8. Success criteria — DEFINED NOW

Measured on 2023–2025 build window:

| metric | minimum to proceed |
|---|---|
| resolved trades | ≥ 100 |
| CAGR, net of costs | > SPY same window + 3pp |
| max drawdown | < SPY max drawdown |
| profit factor | ≥ 1.3 |
| return with best 5 trades removed | still positive |

**If it fails on the build window, we do not tune it into passing.** We abandon
this hypothesis and say so. Tuning until it passes is how the 57.7% false-positive
rate gets converted into a funded strategy.

If it passes: **one** run on 2026. Same criteria. No parameter is touched between
the two runs.

## 9. Live review protocol — DEFINED NOW

Two separate questions. Do not mix them.

### A. Is it broken? (check weekly, act immediately)

- Any fill more than 0.5% from intended limit price
- Any position without a live broker-side stop
- Any duplicate order
- Position size deviating >5% from the sizing formula
- Concurrent positions or sector count exceeding limits
- Any order placed while the regime gate was false

These are bugs. Fix on discovery. No threshold, no deliberation.

### B. Is it underperforming? (check quarterly, act only on these triggers)

Change is justified ONLY if one of these fires:

1. Drawdown exceeds **1.5× the worst drawdown seen in backtest**
2. **40 consecutive resolved trades** with expectancy below zero
3. Realized win rate below **40%** over 60+ trades (backtest implies ~55%)
4. A structural assumption breaks (broker change, universe change, the
   regime gate stops being computable)

**Nothing else justifies a change.** Not a bad month. Not three bad trades in a
row. Not a better idea. Not something an AI noticed in the log.

Any parameter change resets the evaluation clock and requires a fresh out-of-sample
period before the new version is trusted.

### C. What AI review is for

Appropriate: checking execution against intent, finding bugs, computing statistics,
verifying that a proposed change meets a §9B trigger, arguing against changes.

Not appropriate: suggesting parameter tweaks from recent performance, adding
indicators because they'd have helped lately, or interpreting drawdown as a signal
to act. If a review produces a suggestion that isn't tied to a §9B trigger, the
correct response is to ignore it.

---

## 10. Known weaknesses of this spec

- The edge is derived from one vendor's 169 discretionary picks. It may not
  generalize to a mechanical screen over the S&P 500.
- RSI ≤ 40 is a proxy for "daily downtrend" as judged by a human analyst. It is
  not the same measurement and may not capture the same thing.
- Long-only with a regime gate means no return in sustained bear markets.
- Parameters (0.5/2.0/3.0 ATR, RSI 40, 5 names) are reasoned guesses, not
  optimized — deliberately, since optimizing them on the build window is the
  failure mode this document exists to prevent.
- Point-in-time S&P membership may be unavailable, introducing survivorship bias
  that flatters results.
