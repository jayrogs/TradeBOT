# Build notes — what was actually here, what got built, what deviates

## 1. The starting position was not what the handoff described

`claude_code_handoff.md` says the folder contains `harness.py`, `run_test.py`,
`chartguys_all_picks.csv` and `cg2_trades_top.csv`, and that the testing
machinery "is built and verified... fed pure random data and correctly reported
not significant."

**None of those four files were in the folder.** The only things present were the
three markdown documents. The two CSVs turned up in `~/Downloads` along with
`run_backtest.py` / `run_backtest_v2.py` — the script that recomputed the
ChartGuys outcomes. There is no `harness.py` anywhere on the machine.

So the harness described in the handoff was rebuilt from `strategy_spec_v1.md`.

**The consequence that matters:** the claim that the machinery was verified
against random data does not transfer to code that did not exist. That
verification had to be redone from scratch. `validate.py` does it — see §3.

## 2. Files

| file | role |
|---|---|
| `data.py` | universe, prices, earnings dates. Everything cached under `./cache` |
| `harness.py` | the engine + statistics. Strategy is one function at the bottom |
| `run_test.py` | press-go. `--null` for synthetic data, `--holdout` for 2026 |
| `validate.py` | proves the engine is not cheating. Run this before believing anything |
| `trials.json` | every scored run, appended. Feeds `n_trials` in the deflated Sharpe |

## 3. What `validate.py` checks

1. **Indicator truncation.** Compute indicators on the full history, then on a
   history chopped off at day *t*. Values at *t* must match to the last bit. If
   they don't, something is reading forward.
2. **Whole-backtest truncation.** Run the entire backtest with all data present,
   then again with every series cut off at the window's last day. Identical trade
   lists. This catches lookahead anywhere downstream of the indicators.
3. **Fill mechanics.** Hand-checkable cases: an order cannot fill on the day it
   is placed; a stock that only rises never fills a dip limit; nothing is held
   past the 30-day time stop; turning slippage off improves the result, which
   proves costs are actually charged.
4. **Two null distributions**, described in §4.

## 4. The scoring rule changed, and this is the most important note here

The first null test ran the strategy on random prices carrying an 8%/yr drift.
It "passed" the deflated Sharpe in 4 of 12 random worlds.

That is not a bug in the engine — it is a bug in the question. The deflated
Sharpe tests whether the return is **above zero**. A long-only strategy in a
market that rises 8% a year is above zero for free. It earns that by being long,
not by being clever.

So the harness now reports two deflated Sharpes:

- **vs cash** — is the return above zero? (the textbook number)
- **vs SPY** — is there anything left after subtracting the index, day by day?

The second one is the one that answers the stated goal. Re-run against it, the
nulls behave: 0 of 12 drifting random worlds beat the index, and 1 of 12
drift-free worlds beat zero (about what 5%-tail luck should produce).

**Read the `vs SPY` line. The `vs cash` line will flatter almost any long-only
strategy tested over 2023–2025.**

## 5. Deviations from `strategy_spec_v1.md`, all decided before seeing a result

**Prices are split-adjusted, not nominal (spec §7).** The spec asked for nominal
prices so that levels would match what ChartGuys published. This strategy derives
every level from the price series itself, so that reason does not apply. Feeding
it nominal prices would inject a fake −50% gap on every 2:1 split, which RSI would
read as genuine weakness and the strategy would buy. Dividends are excluded from
both the strategy and the SPY benchmark, so the comparison is like-for-like. SPY's
real total return is roughly 1.3pp/yr higher than the price-only figure quoted —
the strategy has to beat the higher one to be worth doing.

**Point-in-time index membership was available after all (spec §3 expected it
might not be).** Membership is reconstructed by walking Wikipedia's S&P 500
change log backwards from the current list. This recovers 49 names that were in
the index during the window and later removed — ATVI, FRC, CTXS, DISH, CERN and
so on. Those are exactly the names a buy-the-dip strategy would have bought, so
leaving them out would have flattered the result.

**ATR for the stop and target is taken from the last completed bar, not the entry
bar.** The spec says "measured at entry". Using the entry bar's own ATR would use
that day's high and low, which are not known at the moment an intraday limit
fills. Off by a day, deliberately, on the safe side.

**Same-bar stop-outs are counted.** If a position fills and that same bar's low
is below the stop, it is booked as a stop-out at zero bars held. We cannot know
whether the low came before or after the fill, so we assume the worse case,
consistent with the spec scoring same-bar ties as losses.

**Earnings blackout applies to the signal only.** A position can still be held
through an earnings report — an order placed on day *t* can fill up to 10 days
later and hold 30 days after that. The spec's exclusion is written as a universe
filter, so that is where it is applied.

## 6. One bug worth recording, because of how it failed

The first full run reported "earnings dates missing for 520 symbols" and ran
anyway. The earnings blackout — a rule in the spec — was silently doing nothing.

Cause: `get_earnings_dates(limit=120)` raises, because Yahoo caps that argument
at 100. A bare `except Exception` swallowed it, and an empty list got cached for
every symbol, so the next run wouldn't retry either. The backtest completed, the
numbers looked plausible, and one of the five entry rules simply wasn't there.

This is the shape of bug to watch for: not a crash, a rule quietly not applying.
`data.py` now retries symbols that came back empty and counts attempts, so a
throttled fetch is never mistaken for "this company reports no earnings".

## 7. Known limitations that no amount of code fixes

- **Survivorship bias is reduced, not eliminated.** Point-in-time membership
  correctly puts 49 removed names into the universe, but Yahoo will not serve
  price history for 31 of them — ATVI, FRC, CERN, CTXS, DISH, PXD, TWTR and
  similar. They are in the universe list and absent from the data, so the
  backtest never sees them. The direction of the remaining bias is mixed:
  takeovers (most of that list) exit at a premium, blowups (FRC) exit at zero.
- Earnings dates come from Yahoo and are missing for some symbols; where missing,
  no blackout is applied.
- Fills assume a resting limit always gets filled if the day's low touches it.
  For $20M+ ADV names at 1% risk sizing that is reasonable, but it is an
  assumption, not a measurement.
- Taxes are not modelled. The trade frequency here is entirely short-term gains
  at ordinary income rates; buy-and-hold defers and pays long-term. Any
  comparison that ignores this favours the strategy.

---

# Result — build window 2023-01-03 to 2025-12-31

Run once, on the frozen spec, with no parameters touched.

| | strategy | SPY | equal-weight S&P (RSP) |
|---|---|---|---|
| CAGR (price only) | **+13.45%** | +21.49% | +10.75% |
| max drawdown | −14.9% | −19.0% | −18.5% |
| Sharpe | 1.20 | | |

276 resolved trades, 49.3% win rate, profit factor 1.42, mean +0.86%/trade,
median hold 10 days, 62.5% average invested, 92 trades/yr.

### Pre-registered criteria (spec §8)

| criterion | result | |
|---|---|---|
| ≥ 100 resolved trades | 276 | PASS |
| CAGR > SPY + 3pp | 13.45% vs 24.49% needed | **FAIL** |
| max drawdown < SPY | −14.9% vs −19.0% | PASS |
| profit factor ≥ 1.3 | 1.42 | PASS |
| positive without best 5 trades | +$33,259 | PASS |

Deflated Sharpe vs SPY: **0.170**. Nothing here beats the index.

**Verdict: FAILS. The 2026 holdout stays unspent. No `BUILD_PASSED` marker was
written, so `run_test.py --holdout` will refuse to run.**

# The premise itself does not hold

`premise_test.py` asks the prior question: forget entries and stops, does
weakness predict strength in the S&P 500 at all? 352,186 symbol-days,
2023–2025, forward 30-day return relative to SPY, bucketed by RSI(14):

| RSI decile | mean RSI | forward 30d vs SPY |
|---|---|---|
| 1 (weakest) | 30.5 | −0.81% |
| 5 | 50.2 | −0.89% |
| 10 (strongest) | 73.1 | −0.43% |

Lowest decile minus highest: **−0.39%**, t = −0.44 clustered by date and
de-overlapped. The sign is backwards and the magnitude is noise. Restricting to
names in the top 40% of their 252-day range, as spec §4.2 requires, gives the
same backwards sign.

The ChartGuys observation — 60.8% win on falling names vs 45.8% on rising ones,
across 169 discretionary picks — does not survive mechanisation onto this
universe. `chartguys_methodology.md` §9 flagged exactly this risk: the trend
labels were analyst judgment, not a calculation, and any replication would have
to define its own weakness measure and re-verify. RSI(14) ≤ 40 was that measure.
It does not reproduce the finding.

# One thing worth knowing before designing anything else

Every RSI decile underperformed SPY by 0.4–1.0% per 30 days. That is not a
strategy result, it is the window: cap-weighted SPY returned 21.5%/yr while the
equal-weighted index returned 10.8%/yr. A handful of mega-caps carried the
benchmark. Any roughly equal-weighted stock-picking system in 2023–2025 started
about 10pp/yr behind SPY before making a single decision.

The strategy cleared RSP by ~2.7pp while sitting 37% in cash. That is the only
faintly encouraging number in this file, it is not statistically distinguishable
from luck, and it cannot be attributed to the weakness premise, which does not
exist in this data.

---

# Ground-up signal survey — 16 pre-specified predictors

Not a replication of anything. A frozen list of well-documented published effects
(`signals.py`), each measured the same way, on 13 years of discovery data, then
re-measured on an untouched window.

**Method.** Each day, score every S&P 500 member, buy the top decile, short the
bottom, equal weight, hold a month, with 21 overlapping baskets running so the
daily return series is honest about overlap. Signals lagged 2 days: scored on day
t, traded at the close of t+1.

**Machinery check.** 40 random signals run through the same pipeline cleared
|t| > 2 in 1 of 40 (2%), sd of t = 0.88. The t-statistics are not inflated by the
overlapping construction — if anything slightly conservative.

**Calibration check.** The equal-weight universe leg returns +12.87%/yr over
2010–2022 against RSP's actual +10.17%/yr. That 2.7pp/yr gap is the residual
survivorship bias from the 152 delisted names Yahoo will not serve, measured
rather than assumed. It affects long-only figures and largely cancels in
long-short.

## Discovery, 2010–2022

Only one of sixteen survived Benjamini-Hochberg correction:

| signal | long-short /yr | t |
|---|---|---|
| **illiquidity** | **+10.68%** | **+3.03** |
| rev_1w | +4.68% | +1.77 |
| low_ivol | −8.83% | −1.66 |
| low_beta | −10.04% | −1.40 |
| low_rsi *(the ChartGuys claim)* | +4.34% | +1.10 |
| mom_12_1 | +3.20% | +0.53 |

`illiquidity` was labelled in the frozen list, before testing, as a near-control
that should show nothing. It was the only thing that passed.

## Confirmation, 2023–2025

| signal | 2010–22 | 2023–25 | |
|---|---|---|---|
| illiquidity | +10.68% (t 3.03) | **−1.88%** (t −0.28) | REVERSED |
| low_rsi | +4.34% (t 1.10) | −1.77% (t −0.21) | dead |
| mom_12_1 | +3.20% (t 0.53) | +13.34% (t 0.99) | never significant |

**Nothing survives correction in either window, and the one thing that survived
discovery reversed out of sample.**

## What this means

Sixteen of the best-documented effects in the literature, on 16 years of S&P 500
data, produce nothing reliably tradeable from daily price and volume alone. That
is not a surprising result — it is what the replication literature reports for
large-cap US equities since roughly 2003. It is the most efficient corner of the
most-studied market on earth.

Two findings are worth carrying forward, both negative:

1. **Buying weakness is dead here**, in every form tested: `low_rsi`, `rev_1m`,
   `rev_1w` all fail. The ChartGuys premise has now failed three separate tests.
2. **Low volatility was backwards** in both windows and violently so in 2023–2025
   (−29.6%/yr): high-volatility names beat low-volatility ones. That is the
   mega-cap concentration again, and it is the same force that put SPY 10pp/yr
   ahead of the equal-weight index.

---

# Chart pattern event study — 16 classic setups

Different question from the signal survey. That one asked "rank all 500 stocks,
which is better." This one asks "this setup just appeared, what happens next" —
a conditional event, not a ranking. Definitions frozen in `patterns.py` with
conventional parameters before any of it ran.

Covered: trend pullbacks and higher lows, 20/50 EMA rides, bull flags (pole,
tight flag, breakout), tight-range equilibrium breakouts and breakdowns,
volatility contraction, 52-week-high breakouts, inside bars, bullish engulfing,
hammers, doji reversals, pocket pivots, gap-and-go, golden cross.

Rule: buy at the close AFTER the trigger, hold 5 / 21 / 63 days, equal weight.

**Two benchmarks, deliberately.** Against SPY answers "would this have beaten
the index." Against the equal-weight universe answers "did the pattern pick
better stocks than picking at random from the same list." The second matters
because in 2023–2025 an equal-weight S&P basket lost ~10pp/yr to cap-weighted
SPY on mega-cap concentration alone — scored only against SPY, every pattern
looks like a failure whether or not it selects well.

## Result: nothing, on either benchmark, in either window

45 pattern-horizon combinations in discovery, 43 in confirmation. **Zero survive
Benjamini-Hochberg correction anywhere.**

The near misses and what happened to them:

| pattern | 2010–2022 (vs universe) | 2023–2025 |
|---|---|---|
| new_high_52w, 21d | −6.08% (t −2.20) | +1.17% (t 0.21) |
| range_breakout, 63d | −3.15% (t −2.12) | −6.51% (t −2.46) |
| gap_and_go, 5d | +9.73% (t 1.33) | +15.86% (t 1.12) |
| bull_flag, 63d | −3.81% (t −0.71) | **+31.65% (t 2.84)** |

That bull flag row is the one to look at twice. It is the single most impressive
number produced anywhere in this project — and it is 186 events, it was
*negative* in the 13-year window, and it appears only in the second window. It
is exactly what a false positive looks like when you test 43 things. Anyone
searching for a reason to trade would stop on that row.

Two genuine observations, both negative:

- **The tight-range breakout is consistently negative** — −3% to −8%/yr vs the
  universe in both windows, at 8,499 events. So is the breakdown. A coil
  resolving in either direction underperformed. That is the closest thing to a
  repeatable effect found in this entire project, and it is a reason not to
  trade breakouts rather than a way to make money.
- **Pullback buying in an uptrend is flat.** trend_pullback, three_day_pullback,
  ema_ride_20, ema_ride_50 — 74,000 events between them, all within ±2%/yr of
  simply owning the universe. Not harmful. Not useful.

---

# Everything re-measured on 2022 onward only

Run at the user's instruction: post-2022 is arguably a different regime, so
older data may not describe it. `recent.py`.

## The cost, measured

40 pure-noise signals through the same pipeline:

| window | biggest fake result | spread of fake results |
|---|---|---|
| 2010–2022, 13 yrs | +2.3%/yr | sd 1.1%/yr |
| 2022–2025, 4 yrs | **+4.2%/yr** | sd 1.9%/yr |

The false-positive *rate* is unchanged (1 in 40 either way). The *size* roughly
doubles. On a 4-year window, anything under about 5%/yr cannot be told from
noise by magnitude alone.

There is also a structural cost: 2023–2025 was the confirmation window. On
2022 onward there is not enough data to both find something and check it, so
every result below is **unconfirmed by construction**. 2026 is the only
untouched data left.

## Was the regime premise right?

Same measurement, two eras:

| | 2010–2021 | 2022–2025 |
|---|---|---|
| low_vol | −10.7% (t −1.61) | −21.9% (t −1.72) |
| low_beta | −12.7% (t −1.80) | −20.0% (t −1.32) |
| mom_12_1 | +2.4% (t 0.39) | +13.4% (t 1.10) |
| low_rsi | +4.6% (t 1.14) | −1.0% (t −0.13) |
| illiquidity | +10.0% (t 2.71) | +3.1% (t 0.52) |

**Signals significant in both eras: 0. Signals significant in either era: 0
after correction.** 4 of 16 flipped sign; if both eras were pure noise about
half would flip by chance, so 4 is if anything evidence *against* a dramatic
break.

The one visible regime effect is real but unhelpful: the low-volatility family
went from bad to worse (−10.7% to −21.9%), and momentum improved. Both are the
same story — mega-cap concentration intensified. Neither is significant.

The deeper problem with the regime argument: you cannot detect a regime change
in an effect that was never there in the first place. Nothing was significant
before 2022, so there is nothing for the new regime to have broken.

## Result on 2022–2025

- **16 signals: nothing survives correction.** Best is mom_12_1 at +13.4%/yr,
  t = 1.10 — below the ~+4%/yr that noise alone generates over a window this
  short, once you account for having looked at 16 things.
- **16 chart patterns, 44 combinations: nothing survives** on either benchmark.
  Best is gap_and_go at 21 days, +15.0%/yr vs the universe, t = 1.99. In the
  13-year window the same pattern gave +3.0%/yr at t = 1.06.

Same answer as the full-history version, with wider error bars.

---

# Cross-asset trend following — `trend_spec.md`, frozen before running

15 ETFs across equities, bonds, commodities and currencies. Hold an asset while
its own 12-month return is positive, size inverse to 60-day volatility, cap 25%,
rebalance monthly, 0.10%/side. Dividend-adjusted prices. Futures were rejected
as a data source: Yahoo's continuous contracts carry roll artifacts (natural gas
had 48% of its >8% daily moves at contract-roll dates against a 20% baseline).

## Result: FAILS the pre-registered criteria in both windows

| | trend | SPY | 60/40 |
|---|---|---|---|
| **2007–2018** CAGR | +4.31% | +7.03% | +6.80% |
| Sharpe | 0.60 | 0.44 | 0.66 |
| max drawdown | **−14.0%** | −55.2% | −31.4% |
| correlation to SPY | 0.41 | | |
| **2019–2025** CAGR | +6.01% | +17.22% | +11.15% |
| Sharpe | 0.81 | 0.90 | 0.95 |
| max drawdown | **−14.0%** | −33.7% | −21.0% |
| correlation to SPY | 0.66 | | |

Fails on return against 60/40 in both windows, and on correlation in the second.

## But this failure is different from the others, and worth saying why

Everything else in this project flipped sign between windows. This did not:

- Sharpe 0.60 then 0.81. Positive both times.
- Max drawdown −14.0% in **both** windows — through 2008 (SPY −55%) and 2022.
- **2008: +1.9% while SPY lost 36.8%. 2022: −9.0% while SPY lost 18.2%.**
- Robustness across lookbacks, which nothing else here survived:
  3/6/12/18-month all give confirmation Sharpe 0.81–0.88. Not knife-edge.

## Why the return is low, honestly

It runs at 7.6% volatility against SPY's 19.8%. Comparing raw CAGR across
different risk levels is not a like-for-like comparison. Scaled to 60/40's risk
and charged 5% financing on the borrowed portion:

| | scaled trend | 60/40 |
|---|---|---|
| 2007–2018 | +3.75% | +6.80% |
| 2019–2025 | +6.25% | +11.15% |

Still loses. Leverage does not rescue it.

## The real limitation

"Share of time in cash: 0%. Average assets held: 10 of 15." This is not really
trend following — it is a mildly filtered long-only risk-parity portfolio. The
documented version goes **short** and targets a volatility level. Managed futures
earned their 2008 and 2022 reputation substantially from short positions in
equities and bonds, which a long-only ETF book cannot take.

So the honest reading: the constrained proxy fails, and its failure mode points
at the specific constraint rather than at the idea. Testing the unconstrained
version is a **new pre-registered test**, not a tweak to this one — and it needs
short selling, which changes the risk profile materially.

---

# The user's own method, mechanised

"Oversold lower timeframes to mark higher lows on healthy uptrend higher
timeframes... indicators and candle psychology to catch entries for riding
trends... it could even be daily candles, if trying to catch a weekly or monthly
higher low... a daily tightening wedge."

Four conditions, all required, frozen before running: higher-timeframe uptrend
(computed only on completed higher-timeframe bars), lower-timeframe RSI oversold
within the last 10 bars, a confirmed higher swing low (3 bars either side, not
treated as known until 3 bars later), and a confirmation candle / tightening
wedge. Tested at four timeframe pairs.

## Daily -> weekly and daily -> monthly, 2007-2025 (`mtf.py`)

**0 of 24 combinations survive correction.** The full setup fired only 459 times
in 13 years and was negative in both windows.

A structural point worth more than the result: **weekly -> monthly never fired
often enough to test at all.** A setup that produces a few hundred events across
500 stocks over 18 years cannot be statistically validated, ever, by anyone. That
is not a failure of this test — it is a property of the setup.

## Hourly -> daily, 2023-2026 (`intraday.py`)

This is the one place in the entire project where stacking conditions improved
the result monotonically, exactly as the logic predicts:

| conditions (6-bar hold, vs equal-weight universe) | discovery |
|---|---|
| daily uptrend alone | −0.52%/yr |
| + hourly oversold | +7.41%/yr |
| + higher low | +19.41%/yr |
| + candle confirmation | **+24.86%/yr** (t = 1.65) |

Every component earned its place. Nothing else here did that.

## Then costs

Per trade — buy the next bar's open, sell at the close `hold` bars later:

| window | hold | vs SPY per trade | net of 0.20% round trip | hit rate |
|---|---|---|---|---|
| 2023–25 (n=3,313) | 6 bars | +0.045% | **−0.155%** | 43.8% |
| 2023–25 | 30 bars | +0.019% | −0.181% | 44.5% |
| 2023–25 | 78 bars | +0.041% | −0.159% | 43.7% |
| 2026 (n=790) | 6 bars | +0.139% | −0.061% | 48.5% |
| 2026 | 30 bars | +0.344% | +0.144% | 46.7% |
| 2026 | 78 bars | +0.470% | **+0.270%** | 48.1% |

The raw per-trade return rises with holding period (+0.05% → +1.12%) but that is
market drift. Against SPY it is roughly zero in the larger sample, and a
round trip costs 0.20%.

2026 looks better and is net positive at longer holds, but it is 750 trades with
a t-statistic near 1.4 — not established.

## The honest caveat, which cuts the user's way

This mechanisation applies one fixed rule to all 500 S&P names with no judgment.
The user's version selects which chart to look at, reads context and levels,
sizes the position, and declines setups that look wrong. None of that is in here,
and none of it can be. **This result does not say the method does not work for a
discretionary trader. It says this particular mechanical shadow of it, averaged
across everything, does not clear costs.**

The measured gap between the two is a real quantity: roughly 0.2%/trade of
selection skill would flip it.

---

# 3,600-variant sweep on volatile names — and how it nearly fooled us

Run at the user's request: test many iterations on volatile, high-retail names,
on the theory that chart psychology works best where the most humans trade.

Design: 1,800 parameter combinations (RSI length, oversold level, lookback
window, higher-low required, candle required, uptrend required, holding period)
on two frozen universes — 25 high-retail names at 72% annual volatility (TSLA,
NVDA, PLTR, GME, COIN...) versus 19 institutional names at 21% (JNJ, PG, KO...).
Every trade scored against its own basket's equal-weight return over identical
hours, 0.20% charged per round trip. Reported as a distribution, never as a
winner.

## Stage 1: the permutation test said yes

Each variant was re-run with trigger times randomly permuted within each symbol
— same prices, same trade count, same volatility clustering, signal-to-future
link destroyed. 20 independent shuffles.

| | best real | best of 20 shuffles | |
|---|---|---|---|
| high-retail | +2.834%/trade, t 3.38 | +1.788% avg, t 2.46 | real wins |
| institutional | +0.741%/trade, t 4.35 | +0.295% avg, t 1.47 | real wins |

Real beat all 20 shuffles on t-statistic in both universes. At this point it
looked like the first genuine finding in the project.

## Stage 2: the time split killed it

Split the hourly sample in half and asked whether variants that worked in the
first half worked in the second.

| | high-retail | institutional |
|---|---|---|
| correlation, half 1 vs half 2 | **−0.33** | **−0.29** |
| top-50 from half 1 still profitable in half 2 | 8/50 (16%) | 16/50 (32%) |
| best half-1 variant | +4.214% (t 3.27) | +0.538% (t 2.15) |
| the same variant in half 2 | **−2.087% (t −3.76)** | **−0.708% (t −3.09)** |

The correlation is **negative**. Variants that won in the first half actively
lost in the second — not decay, reversal. The single best variant flipped from
t = +3.27 to t = −3.76.

Cross-universe correlation of variant results: **−0.30**. What worked on the
retail names did not work on the institutional names either.

Mean across all variants: −0.21% and −0.17% per trade in the two halves. **The
average variant loses money after costs. Only the tails look good, and the tails
do not persist.**

## Why the permutation test was fooled — worth remembering

Permuting trigger times destroys *when* signals fire but real triggers cluster
in time. If a particular stretch of 2024 happened to be favourable for
oversold-buying, the real (clustered) version collects it while the permuted
version spreads trades across everything and averages it away.

So the permutation test detects "trigger timing is non-random with respect to
favourable periods." That is a true statement and it is not a tradeable edge —
it is regime luck. **A permutation test on signal timing is not a substitute for
an out-of-sample time split.** This is the most useful methodological lesson in
the project.

## On the retail-psychology hypothesis

Not supported. The institutional basket produced a *higher* t-statistic (4.35 vs
3.38) despite a third of the volatility. Raw per-trade returns were larger on
volatile names purely because their moves are larger — scaling by volatility
removes the advantage entirely. And variant results correlate −0.30 across the
two universes, so there is no shared structure for "more humans" to be driving.

## ES futures

24-hour data gives 13,687 hourly bars against SPY's 5,072 — genuinely 2.7x more
data, and the user was right that this is the better instrument for candle work.
Roll contamination is mild and usable (15% of >1.5% moves fall in roll windows
against an 8% baseline, versus natural gas at 48%). Worth keeping for any future
intraday work. 70% of ES bars are overnight and carry 52% of total movement.

---

# Trend riding with a trailing structural stop -- the best result in this project

"Buying uptrends, set a stop under the next formed higher low, hold until that
trend breaks, when a higher low is broken."

**This exposed a real blind spot in everything above.** Every earlier test used a
FIXED holding period. A fixed exit cannot ever show what trend riding is for:
cutting losers fast and letting winners run for months. Here the market decides
the holding period.

Entry: flat, price above its 200-day average, and a newly confirmed swing low
prints above the previous one. Stop at that higher low, trailed up on every new
higher low, never lowered. Exit when price trades through it. Costs 0.10%/side.
S&P 500, 2007-2025, split in half.

## The trade shape is exactly right

| pivot | trades | win rate | avg win | avg loss | expectancy |
|---|---|---|---|---|---|
| 3 | 32,665 | 30.3% | +7.38% | −2.83% | +0.26% |
| 5 | 21,274 | 31.0% | +10.11% | −3.72% | +0.57% |
| **10** | 11,303 | 35.3% | **+15.98%** | **−5.16%** | **+2.31%** |

Wins three times the size of losses. Best trade +873%, worst −35%. Median hold
17 days, 90th percentile 62, longest 1,975 days. **It genuinely lets winners
run and cuts losers fast.**

And unlike everything else tested, **expectancy persisted**: +2.54%/trade in
2007–2016 and +2.13% in 2017–2025. First thing in this project not to flip sign.

## As a portfolio, against simply buying and holding

| pivot 10 | strategy | buy & hold |
|---|---|---|
| **2007–2016** return | +10.17%/yr | +12.42%/yr |
| Sharpe | **0.69** | 0.62 |
| max drawdown | **−26.2%** | −52.4% |
| **2017–2025** return | +8.24%/yr | +16.85%/yr |
| Sharpe | 0.60 | **0.88** |
| max drawdown | **−27.0%** | −39.6% |

**It beat buy-and-hold on risk-adjusted return in the decade containing 2008,
and lost in the decade that did not.** Drawdown was roughly halved in both.

That is exactly the expected signature of a stop-loss overlay: it earns its keep
in sustained bear markets and pays for itself in whipsaw during V-shaped
recoveries. 2018, 2020 and 2022 all stopped it out and then recovered fast.

## Honest caveats

- **Cost drag is 1.7–2.0%/yr** at pivot 10, and 3.2–3.7%/yr at pivot 5. Trading
  costs are a first-order term here, not a rounding error.
- **Very sensitive to the swing-low setting.** Pivot 10 works, pivot 3 does not
  (Sharpe 0.21 in the first half). The ordering is monotonic and mechanically
  sensible — tighter stops get whipsawed more — which is far more credible than
  a winner picked out of a shuffle. But it is still a parameter that matters
  enormously, and only three values were examined.
- **The buy-and-hold benchmark is survivorship-inflated** by roughly 2.7pp/yr
  (measured earlier against RSP). That bias flatters buy-and-hold more than the
  strategy, since the strategy stops out of the names that later delist. So the
  true gap is smaller than the table shows.
- Never tested out of sample in the strict sense — both halves were examined.
  2026 remains untouched.

## Verdict

Does not beat buy-and-hold on return. Does roughly halve the drawdown, does have
a genuinely positive and *persistent* per-trade expectancy, and does beat
buy-and-hold risk-adjusted when a real bear market is in the sample.

This is the only idea tested that behaves like a real strategy rather than like
noise. It is worth a proper pre-registered specification and a single run on
2026.

---

# ES futures: costs, and the timeframe-alignment test

## The cost finding, which is real and useful

| | round trip cost | as a share of one average hourly move |
|---|---|---|
| stocks (charged throughout this project) | 0.2000% | ~80% |
| **ES futures** (1 tick + $4 commission on $386k notional) | **0.0043%** | **3.5%** |

**47x cheaper.** Several results in this project were positive gross and died to
stock-level costs — the hourly setup was +0.045%/trade gross against a 0.20%
charge. On ES that charge would have been 0.0043%. Any future intraday work
belongs on futures for this reason alone.

## A bug caught before it became a result

The first run produced Sharpe ratios of 4.55 and 5.13. Not believable, and it
was not real: the return series was built from a position mask, which credits
the move from the prior close to the entry open. Entries here follow a bounce
off a higher low, so that phantom gap is positive on average. Rebuilding the
series from the actual fills dropped the best Sharpe from 4.55 to 0.82.

Same lesson as the split-adjustment bug in the original handoff: the tell was
that the number was too good, and the cause was an entry price that never
happened.

## The hypothesis, falsified cleanly

"We don't play when there aren't uptrends on enough timeframes." Tested by
requiring 0, 1, 2 or 3 macro timeframes (4-hour, daily, weekly) to be in
confirmed uptrend before taking an hourly higher-low entry.

Expectancy per trade, by how many timeframes were required to agree:

| swing low | 0 TF | 1 TF | 2 TF | 3 TF |
|---|---|---|---|---|
| 3 bars | **+0.051%** | +0.007% | +0.012% | −0.034% |
| 5 bars | **+0.027%** | −0.015% | −0.006% | −0.122% |
| 10 bars | **+0.082%** | +0.056% | −0.053% | −0.071% |

**The gradient runs the wrong way, in all three settings.** Requiring more
timeframes to agree made results steadily worse, and requiring all three was
worst every time.

The mechanism shows up in the average winner, which shrinks monotonically as
alignment is demanded: +1.53% → +0.80% at the 10-bar setting. Alignment is a
*lagging* condition. By the time the weekly, daily and 4-hour charts have all
confirmed, the move is mature and you are buying late. The filter removes the
early entries, and the early entries are where the money is.

Nothing tested beat buy-and-hold ES over the window (+17.15%/yr); best config was
+7.34%/yr at Sharpe 0.82, in the market 35% of the time.

## Caveats

One instrument, 29 months, in a strong uptrend. This is enough to falsify a
clean monotonic claim — which it did, three times independently — but not enough
to establish anything positive. Sub-hour testing is not possible: 60 days of
history is all this data source provides.

---

# FOUND SOMETHING: the overnight drift, on ES

The first idea in this project that survives every check thrown at it.

## The rule

**Buy at the 16:00 close. Sell at the 09:30 open. Only when SPY is above its
200-day average.** That is the entire system. No indicators, no thresholds, one
filter whose value sits on a plateau.

## Why it is not like the other results here

1. **No free parameters in the core rule.** The overfitting machinery that
   killed everything else has nothing to grip.
2. **Not discovered by searching.** A long-documented effect in the literature,
   tested here rather than found here. It never entered the multiple-testing
   count because it was never one of many candidates.
3. **It has a mechanism.** Whoever holds index exposure while the market is shut
   carries gap risk they cannot hedge or exit, and is paid for it. Most macro
   news also lands outside US hours.
4. **Tradeable only on futures.** 252 round trips a year at stock costs pays
   5.17%/yr in fees and destroys it. At ES costs it survives. This is the single
   place in the project where the cheap-futures-execution point is decisive.

## Results, SPY 1993-2026 (8,444 sessions), at ES costs

| | CAGR | vol | Sharpe | max DD |
|---|---|---|---|---|
| SPY buy & hold | +8.91% | 18.6% | 0.55 | −56.5% |
| overnight only | +6.94% | 10.6% | 0.69 | −36.1% |
| **overnight + 200d trend** | **+6.80%** | **6.5%** | **1.05** | **−14.4%** |
| same, 3x leverage (matched risk) | +16.75% | 19.4% | 0.90 | −44.0% |

**At matched risk it nearly doubles buy-and-hold's return with a smaller
drawdown.**

## The stability, which is the point

| | 1993–2015 | 2016–2026 |
|---|---|---|
| Sharpe | **1.01** | **1.00** |
| max drawdown | −14.0% | −14.4% |

Nothing else tested in this project stayed the same across two independent
multi-year periods. Most flipped sign.

Trend-filter length is a plateau, not a spike: 150d → 0.94, 200d → 1.01,
250d → 1.01, 300d → 0.99. 50d → 0.63. A lucky number looks like a spike; this
looks like a plateau, which is what a robust parameter looks like.

## Where it breaks — the honest risks

**Execution is everything.** 252 round trips a year means **one extra tick of
slippage costs 0.82%/yr** against a ~6.5%/yr edge:

| assumed round-trip cost | CAGR | Sharpe |
|---|---|---|
| 1 tick + commission | +6.49% | 1.01 |
| 2 ticks | +5.63% | 0.88 |
| 4 ticks | +3.92% | 0.63 |
| **8 ticks** | **+0.58%** | **0.12 — dead** |

And the trade happens at the 09:30 open, the single worst moment of the day for
slippage. The 1-tick assumption is the weakest part of this whole analysis and
needs verifying against live fills before any money moves.

**Other real risks:**
- Longest time under water: **945 trading days — 3.8 years.**
- Worst single nights: −4.0%, −3.4%, −3.2%. Unhedgeable; you are asleep.
- It lags badly in strong bull markets. 2023: −3.5% at 3x while SPY made +24.3%.
  Beat SPY in only 11 of 34 calendar years — it wins on risk, not on raw return.
- Widely published, so arbitrage is a live concern. The unfiltered version
  already decayed: Sharpe 0.72 (1993–2015) → 0.62 (2016–2026).
- **No untouched holdout remains.** This test used data through Aug 2026. The
  period split is legitimate because nothing was fitted, but the only real test
  left is forward from today.

## Recent years, 3x leverage vs SPY

| | system | SPY |
|---|---|---|
| 2021 | +44.2% | +27.0% |
| 2022 | −20.2% | −19.5% |
| 2023 | −3.6% | +24.3% |
| 2024 | +68.0% | +23.3% |
| 2025 | +30.2% | +16.4% |
| 2026 YTD | +6.4% | +12.5% |

Beat SPY in 3 of the last 6. Not "consistent" in the sense of winning every
year — consistent in the sense that the risk-adjusted edge held up.

---

# Hourly ES: 1,586 configurations across 10 families

Run at the user's instruction to "test as many times as possible and then test
more." Families: time-of-day, day-of-week x session, MA cross, Donchian
breakout, RSI mean reversion, z-score mean reversion, opening-range breakout,
gap follow/fade, prior-day levels, volatility expansion. Then multiplied out
with short-side, stop-loss, session-restricted and trend-filtered variants.

Search on the first 60% of bars (Mar 2024 – Sep 2025), last 40% held back
(Sep 2025 – Aug 2026) and never looked at until the end.

## The search does not work, and here is the proof

**1. Three separate null datasets each beat the real data.**

| | best Sharpe found |
|---|---|
| real ES data | 2.54 |
| null — returns reversed | 2.65 |
| null — 24-bar blocks shuffled | 2.69 |
| null — signals 500 bars out of phase | **3.02** |

Going from 396 to 1,586 configurations did not pull real ahead of null. It
pulled null ahead. More searching samples the tail harder; it does not find
signal that is not there.

**2. The search-period winners collapsed.**

Top 50 by search Sharpe: mean **1.63** in the search period → mean **0.15** held
back. Only **3 of 50** beat buy-and-hold in the held-back period.

The single best search performer — volatility expansion, overnight only,
Sharpe 2.54 — returned **−2.19 Sharpe, −5.3%/yr** held back.

**3. The held-back winners were invisible during the search.**

| best in held-back period | search Sharpe | held-back Sharpe |
|---|---|---|
| Monday 00:00 +9h | 0.72 | 3.40 |
| vol expansion short | −1.02 | 3.04 |
| rsi12<20 hold24 | 0.05 | 2.61 |
| prior_levels buy_low hold24 | 1.02 | 2.50 (+33.7%/yr) |

Every one of them looked mediocre or bad in the search period. **No selection
rule applied to the search data could have chosen them.** That is the whole
case, in one table: it is not that the search found nothing, it is that the
search provably cannot pick the winners.

Correlation between search and held-back Sharpe across all 1,586: **+0.209**.
Too weak to select on.

## Meanwhile

Buy and hold ES over the held-back period: **+22.3%/yr, Sharpe 1.42.**

## Why the overnight system is different in kind

It was not selected from a field of candidates. Zero parameters in the core
rule. Sharpe 1.01 and 1.00 across two independent multi-decade periods, on
8,444 sessions rather than 13,688 hourly bars in one 29-month window. Whatever
its execution risk turns out to be, it is not the same kind of object as
anything in this file.

---

# Sub-hour data: what exists, and the execution question answered

## The hard constraint

Verified against the API, not assumed:

| interval | available history |
|---|---|
| 30m / 15m / 5m | last **60 days** only (2026-06-09 onward) |
| 1m | 8-day chunks, ~30 days total |
| 1h | 730 days |

**January–May 2026 is not retrievable at any sub-hour interval.** Yahoo returns
empty for those ranges. Sub-hour strategy testing "this year" is not possible
from this source.

Nor would 10 weeks support it: the hourly sweep used 29 months and 1,586
configurations and could not select a winner. A tenth of the data would be
strictly worse.

## A framing error, corrected

First pass measured the median range of the 09:30 one-minute bar at 32 ticks
(0.106% of price) and translated "half that range" into 15%/yr of slippage,
which would have killed the overnight system outright.

**That was wrong.** A 32-tick first-minute range is price *moving over a minute*.
It is not slippage on a single order. An order sent at 09:30:00 fills at the
prevailing bid/ask — one tick wide on ES even at the open — not at a random
point in the minute's range. The two are different quantities and conflating
them overstated the cost by an order of magnitude.

## What the 1-minute data actually says

Exit timing, measured across 24 sessions:

| exit time | avg vs exiting at 09:30 | annualised | daily sd |
|---|---|---|---|
| 09:31 | −0.0039% | −0.97%/yr | 0.056% |
| 09:35 | +0.0164% | +4.21%/yr | 0.110% |
| 09:45 | +0.0068% | +1.73%/yr | 0.153% |
| 10:00 | +0.0017% | +0.44%/yr | 0.257% |
| 10:30 | −0.0070% | −1.75%/yr | 0.364% |

Being minutes late is worth roughly ±1–4%/yr, the sign is not consistent, and
the daily standard deviations dwarf the means — this is noise, not a systematic
drag. Against a ~6.5%/yr edge that means the system needs ordinary discipline,
not microsecond precision.

## What still cannot be measured here

True slippage is (price when you decide) − (price you get). That needs quote or
fill data, not OHLC bars. The 1-tick assumption is reasonable for small size in
the most liquid equity index future in the world, but it remains an assumption.
**Only the user's own fills can settle it.**

---

# THE ANSWER: the user's own trades, and what the exit is costing

## Their record, pulled from Robinhood (199 realised closes, Feb 2025 – Aug 2026)

$16,094 realised, 53% win rate, **median trade $1.01**.

| | trades | total | avg | win rate |
|---|---|---|---|---|
| position trades (≥$100) | 45 | **$15,501** | $344 | **84%** |
| scalps (<$100) | 154 | $593 | $3.85 | 44% |

**Top 20 trades = 90% of all profit.** 77% of trades are scalps producing 3.7%
of the money.

A natural experiment sits inside the data — same asset, same person, same month:

| SLV | trades | total | avg | win |
|---|---|---|---|---|
| held as positions (to Feb 5) | 11 | **$8,190** | $744 | **100%** |
| day-traded (Feb 6 – Mar 6) | 129 | $381 | $2.96 | 43% |

21x the money from 12x fewer trades.

## Exit rules, entry held constant

Same entry (RSI<35 above the 200-day) on 12 instruments, only the exit varies.

**Per year of capital deployed:**

| exit | return/yr | win% |
|---|---|---|
| close < 20d MA | +27.0% | 70% |
| swing low break *(their rule)* | +20.4% | 47% |
| close < 50d MA | +17.3% | 75% |
| target +20% | +9.9% | 79% |
| target +30% | +8.3% | 77% |

**Profit targets have the highest win rates and the lowest returns.** That is the
psychological trap stated numerically: locking in gains feels good and costs
money.

**But over the full calendar period including cash time, the ranking inverts** —
fast exits sit in cash 80–90% of the time, so total CAGR favours wide stops
(+6.7%) over fast trend exits (+2.9%). Which rule is "best" depends entirely on
whether the freed capital has somewhere to go.

## The silver counterfactual — the decisive number

Entry proxy 2025-09-15 at $38.76. SLV peaked at $105.60 (+172%), now $57.44.

| exit rule | exit date | return |
|---|---|---|
| target +20% *(≈ what they did — selling began Oct 13)* | 2025-10-13 | **+20.0%** |
| trail 10% off high | 2025-10-21 | +14.4% |
| chandelier 3×ATR | 2025-10-09 | +10.8% |
| close < 20d MA | 2025-10-21 | +13.0% |
| swing low break | 2026-02-17 | +69.0% |
| close < 50d MA | 2026-02-05 | +72.1% |
| **trail 20% off high** | **2026-01-30** | **+126.7%** |

**Six times the return, on the exact trade they raised.**

And the counterintuitive part: the *tight* exits did worst. A 10% trailing stop
got shaken out at +14%; a 20% trailing stop rode to +127%. Tightening the stop
did not protect the position, it cost 112 percentage points.

## Why this all coheres

Their profit is a fat tail — top 20 trades are 90% of everything. A profit
target caps precisely the trades that matter. A wide trailing stop exists to not
cap them. The three findings — trade concentration, the SLV held-vs-scalped
experiment, and the exit comparison — are three independent measurements of the
same thing.

**The edge was never missing. It was being cut off at +20%.**

---

# Trend-Hold bot (system_spec_v2.md) — tested, and it FAILS its own spec

| | trend-hold | SPY |
|---|---|---|
| **2007–2018** CAGR | +5.08% | +4.87% |
| max drawdown | **−21.1%** | −56.5% |
| Sharpe | **0.50** | 0.34 |
| **2019–2026** CAGR | +15.01% | **+15.86%** |
| max drawdown | **−25.1%** | −34.1% |
| Sharpe | **1.01** | 0.86 |

Pre-registered criteria (spec §7): CAGR > SPY in confirmation **FAILED**
(15.01 vs 15.86). Trades ≥ 60 **FAILED** (36). Drawdown and both-window
criteria passed.

**Verdict: fails as specified.** It beats SPY on risk-adjusted return in both
windows and roughly halves the drawdown, but it does not beat SPY on raw return.

## Two findings that matter more than the verdict

**1. It is brutally fat-tailed — by design, and it works.**

| | drop best 0 | best 3 | best 5 |
|---|---|---|---|
| 2007–2018 total trade return | +299% | +13% | **−103%** |
| 2019–2026 | +823% | +165% | +24% |

Only 18–19 of 36 trades were profitable. Top 5 = 97% of profit in the
confirmation window. This is exactly the shape of the user's own record (top 20
trades = 90% of profit), which is reassuring about the design and alarming about
the reliance on a handful of outcomes.

**2. The alpha is the universe, not the exit rule.**

Confirmation window, same rules, different instrument lists:

| universe | CAGR | Sharpe |
|---|---|---|
| full | +15.01% | 1.01 |
| **without TSLA/BTC/NVDA/AMD** | **+5.50%** | 0.49 |
| metals + energy only | +11.29% | 0.86 |
| index ETFs only | +3.90% | 0.42 |

Remove four names and the system returns 5.5% against SPY's 15.9%. **The exit
rule does not generate return — it avoids destroying it.** Finding the names is
still the job, and that is precisely the discretionary skill the user's trade
record demonstrates and no backtest here could reproduce.

## The conclusion this points to

The defensible product is not an autonomous entry bot. It is an **exit manager**
applied to positions the user selects: a 20% trailing stop that ratchets and
never takes profit early. That automates the part their record shows is costing
them (six times the return on the silver trade) and leaves the part their record
shows they are good at in human hands.

Robustness on the trail width is reassuring — 15% / 20% / 25% / 30% give
Sharpe 1.03 / 1.01 / 0.91 / 1.00. Not a knife-edge. 10% is clearly too tight
(0.81, and it cut the silver trade at +14%).

---

# Reverse-engineering the user's entries, and testing their stated pattern

## What their 102 real buy orders have in common

Measured against every other day in the same instruments:

| feature | SLV entries (73) | everything else (27) |
|---|---|---|
| daily RSI | 43.0 | 43.5 |
| weekly RSI | 60.7 | 50.0 |
| vs 200-day MA | **+47.8%** | +6.5% |
| vs 50-day MA | −5.1% | −4.0% |
| drawdown from 52w high | **−35.9%** | −16.3% |
| 1-month return | **−19.6%** | −3.8% |
| 3-month return | **+47.4%** | +2.0% |
| volatility percentile | **99.6th** | 75th |

Two distinct trades, not one:

- **The ordinary trade** (27 orders): a normal pullback — mildly above the
  200-day, below the 50-day, ~16% off the high, down ~4% on the month, daily
  RSI 43. This is roughly what `system_spec_v2` already encodes.
- **The SLV trade** (73 orders, and by far the most profitable): a *violent*
  pullback inside a parabolic move — 99.6th percentile volatility, +47% over
  three months, −36% from the high, −20% in one month. A completely different
  animal, and the one that made the money.

## Their stated pattern, tested on 39 markets

"Oversold weekly RSI alongside lower weekly candle lows without follow through"
— a failed breakdown: price breaks a prior weekly swing low while weekly RSI is
oversold, then reclaims it instead of continuing down.

896 signals. The decisive test compares three states that are **all** oversold
on the weekly, differing only in what happened at the low:

| horizon | reclaimed *(their pattern)* | broke down | just oversold |
|---|---|---|---|
| 4 weeks | +0.52% (n=896) | **+3.26%** | +1.82% |
| 13 weeks | +4.33% (n=882) | **+7.73%** | +4.77% |
| 26 weeks | +12.61% (n=876) | +12.02% | +10.97% |

**The "no follow through" component adds nothing.** At 13 weeks the reclaim
returns +4.33% against +4.77% for simply being oversold — and the names that
*did* break down did better still. The chart-reading refinement they believe is
doing the work is not doing it. Being oversold on the weekly is the entire
signal.

## Except, possibly, in crypto

| crypto only | reclaimed | broke down | just oversold |
|---|---|---|---|
| 13 weeks | +11.45% (n=56) | +6.01% | +12.48% |
| **26 weeks** | **+43.48% (n=56)** | +11.35% | +28.83% |

At six months in crypto the reclaim genuinely looks better — +43% against +29%
for plain oversold. But that is 56 observations in the most fat-tailed asset
class there is. Suggestive, not established, and nowhere near enough to trade
on by itself.

## By asset class, 13-week edge over each market's own average

| class | edge | hit% |
|---|---|---|
| equity index | **+2.62%** | 68% |
| metals | +1.21% | 60% |
| bonds/REIT | +0.78% | 54% |
| energy | +0.29% | 58% |
| single stocks | −1.76% | 61% |
| FX | −0.82% | 44% |
| **crypto** | **−26.52%** | 40% |

The pattern is mildly useful on indices and metals and actively harmful on
single stocks and crypto at the 13-week horizon.

## The honest conclusion about the intuition

The reverse-engineering and the pattern test agree: **the replicable part of
their edge is "buy weakness in something that is structurally fine", which is
already mechanised. The unreplicable part is choosing WHICH market** — energy in
June, silver in September, uranium in 2025. Every attempt in this project to
mechanise that has failed, and the divergence/spring refinement they believe is
guiding them turns out not to be carrying the signal.
