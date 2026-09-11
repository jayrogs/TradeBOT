# Cross-Asset Trend Following — spec v1

**Status: PRE-REGISTERED. Frozen before any backtest is run.** Written 2026-08-18.

Everything below is chosen from reasoning and from published convention, not from
fitting. Discovery 2007–2018. Confirmation 2019–2025. 2026 untouched.

---

## 1. Why this and not more stock work

Three findings from this project point here:

1. Every **cross-sectional** test failed — 16 ranking signals, 16 chart patterns,
   0 survivors. The only thing that helped anything was the regime gate, which is
   a **time-series** trend rule.
2. 500 S&P stocks are one bet. They are 60–80% correlated with SPY, which is why
   nothing built from them could get away from SPY. Bonds, gold, oil, agriculture
   and currencies are far less correlated with each other. More independent bets
   is the only reliable way to raise a Sharpe ratio.
3. Trend following has an economic story rather than a pattern story: hedgers pay
   speculators to carry risk. It is documented across asset classes back to the
   19th century, which is a very different evidence base from a chart shape.

## 2. Instruments

ETFs, not futures. Yahoo's continuous futures contracts contain roll artifacts —
natural gas shows 48% of its >8% daily moves clustered at contract-roll dates
against a 20% baseline. Those are fake returns, the same class of error as the
split-adjustment bug that faked +31%/yr earlier in this project.

ETFs are honestly tradeable and carry their roll costs inside the price. The
trade-off is real: no leverage, higher fees, and contango drag in commodity
funds. This tests whether the idea works, not the best possible implementation.

14 funds, four asset classes:

| class | funds |
|---|---|
| equity | SPY, QQQ, IWM, EFA, EEM |
| fixed income | TLT, IEF, LQD, HYG |
| commodity | GLD, SLV, DBC, DBA |
| currency / real assets | UUP, VNQ |

Dividend-adjusted prices throughout, for the strategy and both benchmarks. Bond
ETFs pay most of their return as income; excluding it would misstate everything.

## 3. The rule

One signal. Chosen now, not to be touched:

- **Hold an asset if its own trailing 12-month (252 trading day) return is
  positive. Otherwise hold cash.**

That is the whole entry and exit. No stops, no targets, no filters.

## 4. Sizing

- Weight each held asset **inversely to its 60-day realised volatility**, so a
  bond fund and an oil fund contribute comparable risk
- Weights normalised across held assets; unheld capital sits in cash earning zero
- Cap any single asset at **25%** of the portfolio
- **Rebalance monthly**, on the last trading day

## 5. Costs

- **0.10% per side** on turnover, same as every other test in this project
- Cash earns 0%, which understates the strategy in high-rate years — deliberately
  on the conservative side

## 6. Benchmarks

Judged against three things, because "beat SPY" is not the only useful question
for something meant to diversify:

1. **SPY** — the bar from the original project
2. **60/40** — 60% SPY, 40% IEF, rebalanced monthly
3. **Correlation to SPY** — the actual point of the exercise

## 7. Success criteria — DEFINED NOW

Measured on discovery 2007–2018, then required to repeat on 2019–2025:

| metric | minimum |
|---|---|
| Sharpe ratio | ≥ 0.60 |
| max drawdown | < half of SPY's |
| correlation to SPY | < 0.60 |
| CAGR | ≥ 60/40 portfolio |
| result repeats in confirmation window | same sign, Sharpe ≥ 0.40 |

Deliberately *not* "beat SPY's return". A diversifier that returns less than SPY
with a third of the drawdown and low correlation is doing its job. Demanding it
beat a cap-weighted equity index on raw return is the same category error that
made the first strategy look worse than it was.

## 8. Robustness, not selection

The 3-month and 6-month lookbacks will also be reported. They are **not**
candidates — the 12-month version is the one being judged. They are there to show
whether the result is knife-edge dependent on one number. If 12 months works and
3 and 6 months are catastrophic, that is a warning, not a menu.

## 9. If it fails

We say it failed. No tuning, same as before.
