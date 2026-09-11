# Trend-Hold System — spec v2

**Status: PRE-REGISTERED.** Written 2026-08-19, before this version was backtested.

Every rule below is fixed by an argument, not by a search. Where a number came
from evidence already seen in this project, that is stated openly so the reader
can discount it.

---

## 1. What this is built on

Three independent measurements from the user's own 199 realised trades and from
backtests on 12–30 years of daily data:

1. **Profit is a fat tail.** Top 20 trades = 90% of all profit. Any rule that
   caps winners amputates the entire edge.
2. **Holding beat trading the same asset.** SLV held as positions: 11 trades,
   $8,190, 100% win. SLV day-traded, same month: 129 trades, $381, 43% win.
3. **Wide exits beat targets.** Same entry across 12 instruments, exit varied:
   profit targets returned +8–10%/yr of deployed capital at ~78% win rates;
   trend-change exits returned +17–27% at lower win rates. On the actual silver
   move, a +20% target returned +20% while a 20% trailing stop returned +127%.

**The design goal is therefore not a better entry. It is an exit that does not
cut off the trades that pay for everything.**

## 2. Universe

Liquid, trending-capable instruments of the kind the user already trades —
metals, miners, energy, broad index ETFs, large-cap equities. Fixed list, no
screening, no discretion:

    metals/miners   GLD SLV GDX UUUU PLG
    energy          XLE CVX XOM USO
    index           SPY QQQ IWM DIA
    sectors         XLF XLK XLV XLI XLU XLP
    equities        AAPL MSFT NVDA TSLA AMD JPM
    other           TLT EEM EFA VNQ BTC-USD

Requirements: price > $5, 20-day average dollar volume > $10M.

## 3. Entry — deliberately simple

All must be true on a completed daily close:

1. **Uptrend:** close > 200-day simple moving average
2. **Weakness:** RSI(14) < 35

Buy at the next open. That is the whole entry. It is a mechanical approximation
of "buy the dip in something that is trending up", which the user's record shows
they already do well.

No attempt is made to replicate their instrument-selection skill. That is
discretionary and is the part a bot cannot reproduce.

## 4. Exit — the actual point of the system

**Trailing stop 20% below the highest CLOSE since entry.** Starts at entry −20%
and only ever ratchets up. No profit target. No time limit.

Rationale, and the honest caveat: 20% was not optimised, but it is the width
that rode the silver move in a test I had already seen. Treat it as informed by
prior data. The 50-day moving-average break performed comparably (+72% vs +127%
on silver, +17.3%/yr vs similar) and is reported alongside as a robustness check
rather than a competing candidate.

Why wide: on the silver trade a 10% trailing stop exited at +14%, a 20% stop at
+127%. Normal pullbacks inside a real trend are larger than most traders'
stomachs. A stop tight enough to feel safe is tight enough to guarantee you miss
the trades that matter.

## 5. Position sizing

- Equal dollar weight, **12.5% of equity per position**
- Maximum **8 concurrent positions** (so up to 100% invested)
- No leverage, no pyramiding, no averaging down
- If more than 8 signals fire on one day, take the lowest RSI first

Rationale for equal weight rather than risk-parity: with a single 20% stop on
every position, equal dollar weight already equalises risk.

## 6. Costs

0.05% per side. Generous for liquid ETFs and large caps; the user pays zero
commission and crosses a spread of roughly 0.01–0.05%.

## 7. Success criteria — DEFINED NOW

Search window 2007–2018, confirmation 2019–2026, judged on the confirmation
window:

| metric | minimum |
|---|---|
| CAGR | > SPY buy-and-hold over the same window |
| max drawdown | < SPY max drawdown |
| resolved trades | ≥ 60 |
| result holds in both windows | same sign, CAGR > 0 in each |

**If it fails on the confirmation window, it failed.** No tuning.

## 8. What this system is NOT

- It does not replicate the user's sector-selection skill, which is where a
  large part of their real edge lives.
- It is long-only. It will sit in cash through bear markets and will not short.
- It will have a low win rate and long flat periods. That is the cost of not
  capping winners, and it is the entire design.
- **It has no untouched holdout left after this run.** The only honest test
  remaining is forward, on live or paper fills.
