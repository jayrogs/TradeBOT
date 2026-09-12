# The playbook: both books, the room, and what this desk has actually measured

2026-09-12, written overnight at his request: "make sure you distill trading in the zone and murphys book with all
your knowledge possible."

Three sources, one frame. Murphy (*Technical Analysis of the Financial Markets*) for what to look at. Douglas
(*Trading in the Zone*) for how to think while you look. The Chart Guys room (`TCG_METHOD.md`) for how his mentor
actually trades it. Everything is marked with what this desk has MEASURED, so you can see where the confidence
comes from and where it does not exist yet.

`TA_FOUNDATION.md` is the background. This file is the operating manual.

---

## 1. The one-page version

A trade is four questions, in this order. If any one has no answer, there is no trade.

| | Question | Answered by |
|---|---|---|
| WHERE | Is price at a place the market remembers? | A bigger chart's 12 EMA, a prior swing level, a broken level, an oversold reading, a value edge |
| WHICH WAY | What is the bigger chart doing? | Its trend (higher lows / lower highs) and which side of its 12 EMA price sits on |
| WHEN | What starts it? | A small-chart trigger: an EQ break, a higher low, a backburner bounce, price regaining the small 12 EMA |
| HOW MUCH | Where is it wrong, and is the payoff worth it? | The nearest structure that kills the idea; skip unless the target is ~3x that |

Then: take a partial early so the rest is free, walk the stop under each new higher low, and let the bigger chart
decide when it is over. Take EVERY occurrence, judge in samples of 20, not trade by trade.

---

## 2. The frame (Douglas)

- **Anything can happen.** One participant anywhere can negate the best-looking setup. His illustration: the
  chairman who sold two million bushels through the analyst's "low of the day".
- **You do not need to know what happens next to make money.** The edge is a higher probability, not a forecast.
- **There is a random distribution between wins and losses.** Even with a real edge, the order of wins and losses
  is noise. This is why the result of the last trade must not change the next one.
- **Every moment is unique.** The same pattern is never the same crowd.
- **Consistency is a state, not a streak.** The casino takes every hand, because picking hands destroys the edge
  it measured.
- **Rigid in rules, flexible in expectations.** Most people are the reverse.
- **Predefining risk is not a formality.** If you would not predefine it, you secretly think you know.
- The four fears that cause ~95% of the errors: being wrong, losing money, missing out, leaving money on the table.
  Their symptoms: hesitating, jumping the gun, no stop, refusing the loss, cutting winners, letting a winner become
  a loser, moving a stop closer, oversizing.

**What that means for this desk:** every study takes every occurrence of an edge (no cherry-picking), reports the
sample not the trade, and never treats a result as a prediction.

---

## 3. The setup stack (how everything gets tested here)

Regime -> Context -> Location -> Trigger -> Risk -> Management -> Size. One skeleton, each layer a switch, and the
control must skip exactly what the rule skips. Nothing is tested one flag at a time and called a method.

### Regime (what state is the market in)
Balance (two-sided, rotating, an EQ is balance tightening) or trend (one side in control). Tools that work in one
fail in the other. Era matters: before 2022, first half, second half are three different markets, and a rule that
only works in one is a curve fit.

### Context (which way)
- The bigger chart's structure: higher highs and higher lows, or lower highs and lower lows.
- Which side of the bigger chart's 12 EMA price is on, and whether that EMA is rising or falling.
- The "zoom out" stack: the 12 EMAs above (15m, 1h, 4h, daily). When one is lost, the next takes over as the guide.
- MEASURED HERE: on a 5m/15m EQ, the bigger chart's 12 EMA points the WRONG way for the first poke (44-48% right,
  #26f/#26g) but the RIGHT way for holding a position (the "on the right side of the idea 12 EMA" filter is the
  largest single improvement found so far, currently under verification).

### Location (where it is allowed to happen)
Murphy's rule and Joey's rule agree: without location, a pattern is 50/50. What counts as location:

| Location | Status on this desk |
|---|---|
| A bigger chart's 12 EMA | measured, helps: +0.04 to +0.09% a trade on EQ entries |
| Previous swing support/resistance | measured, ~nothing as coded (the last pivot alone) |
| A BROKEN level, now the other side (role reversal) | measured 2026-09-12: small but positive on breaks (+0.05 to +0.07%) |
| 38-62% retracement of the last leg | measured 2026-09-12: nothing, except on backburner entries |
| Oversold / overbought on the bigger chart | measured, mixed; helps with a runner, hurts with a fixed target |
| Value area edges (VAH/VAL/POC) | NOT BUILT: needs volume-at-price, we have bars only |
| Gaps as support/resistance | not tested |
| Level weight by time spent / volume traded / recency | not tested |

### Trigger (what starts it, on the small chart)
EQ break, higher low inside an EQ, plain higher low, backburner bounce (RSI 30 and back over), price regaining the
small 12 EMA. MEASURED: on their own, none of them pays on 5m/15m after costs. With context and location they
range from break-even to the one positive corner under verification.

### Risk (where it is wrong)
- The stop goes just past the structure that kills the idea -- the NEAREST one, not the furthest. (The 2026-09-11
  bug: using the far hourly swing made every trade risk 5x what it aimed at.)
- Volatility sets the distance: too close and noise takes you out, too far and the loss is not worth the
  information.
- Floor the risk so it is several times the round-trip cost. On crypto at 0.2% a round trip, a 0.3% stop is a
  coin flip against friction.
- Skip the trade when the target is not at least ~2-3x the risk. Murphy says 3:1; Douglas says with 3:1 a sub-50%
  win rate still pays.
- A stop does not fill at the stop price. It sells the next open, and gaps go through it.

### Management (his, and the books')
- Take a partial early. Douglas: a third as soon as the market gives a little, a second third at a level, stop to
  entry -- "risk-free opportunity". Murphy: a trading unit and a trending unit. Jay: "locking in some partial to
  have security ... once it makes the move in your favor, just sell everything."
- The rest: walk the stop under each new higher low on the idea chart, or hold it on a 12 EMA a size below, and
  zoom out when that one is lost.
- No discretionary cuts. Stop or target, not feeling.
- MEASURED HERE: management changes outcomes more than entry does. On his own 26 marked EQs, partials cut the
  average loss by 5x (worst trade -10.5% to -1.6%).

### Size (the part this desk has never built)
Murphy: at most ~5% of equity at risk on one trade, 10-15% committed to one market, 20-25% to one group. Add only
to winners, in smaller size, never to losers, and move the stop to breakeven when you add. Raise size after an
equity DIP, not after a winning streak. Nothing on this desk sizes anything yet -- only `portfolio.py` touches it.

---

## 4. The math that decides it

- Expectancy = (win rate x average win) - (loss rate x average loss). That is the edge; nothing else is.
- Win rate alone means nothing. 25% wins needs ~4:1; 60% wins can live on 1:1. Murphy: the best futures traders
  are right on ~40% of trades.
- R is the unit: every result in multiples of the risk taken. Percent hides the shape.
- Variance: at a 35% win rate, ten losses in a row is normal. Size for the streak or you will not trade the system.
- Sample of 20: judge blocks of twenty trades in time order, not single trades. How many blocks made money is the
  number a human actually lives.
- Costs scale with frequency. 1,500 trades a year at +0.1% is a cost story, not a strategy.
- Sequence risk: the same trades in a different order give very different equity paths. Judge the worst path.

---

## 5. The daily routine (the room's, worth copying)

1. Start on the big charts: monthly/weekly for context, daily for the decision, intraday only to fine-tune.
2. Write each name as a level in waiting: "anything over X is a daily higher low, anything under Y is an hourly
   lower high."
3. Say the most likely scenario out loud, and what would disprove it.
4. Only then look for a trigger on the small chart, at a location, in the direction of the big chart.
5. Most days have nothing. "If we have ho-hum balancing action, best to just sit on your hands."

Murphy's checklist, condensed: overall market and sector direction; weekly/monthly; the three trends; support and
resistance; trendlines; volume confirming; retracements; gaps; reversal and continuation patterns; moving averages;
oscillators and divergence; then -- buy or sell, how many units, how much risked, where the stop, what order type.

---

## 6. What this desk has measured (the honest scoreboard)

| Claim | Verdict here |
|---|---|
| Trend riding: buy the second higher low, structural exit | Works on 1h and up (daily +1.11% a trade), flat on 5m/15m (#17) |
| Looser stops make more per trade | True to a point, and they give it back in dips; wide ones lost before 2022 (#23, #25) |
| Fast-chart EQ as a trade on its own | None of MY versions cleared costs (#26c-#26l). Each round found a bug in my code, not in the method, so this is a statement about my implementations |
| EQ direction from the daily 50 EMA | My reading of it was a coin flip on 5m/15m (#26f); he said the daily is too far out for a 5m trade and he was right |
| EQ direction from the bigger chart's 12 EMA, for the FIRST POKE | My reading came out backwards (44-48%); the same input used as a POSITION filter is the strongest thing found so far |
| His rule: hourly uptrend or above the hourly 12 EMA, EQ making the hourly's higher low | My first coding of it added nothing on the poke; as a position filter it separates clearly (#26n), and it is the base of the corner under verification |
| Partial for security | Cuts the average loss ~5x on his own marks; textbook in both books |
| Which names to trade: the ones that move | The only name trait that carried out of sample (+83% a year vs +40%) (#30, #32) |
| Volume confirmation | POSITIVE on breaks (+0.07 to +0.15% a trade). My version only reads the entry bar against its own 20-bar average; volume AT THE LEVEL and volume through the break are not built yet |
| Relative strength (ratio charts) | MY VERSION showed nothing. It is a daily ratio against one benchmark with one reading; Joey uses 2-day, weekly and monthly ratios and reads them at the low end of balance. Not a verdict on the method |
| Role reversal (broken level) | POSITIVE on breaks (+0.05 to +0.07%). My version takes the last broken pivot only, with no weight for how hard it was broken or how much traded there |
| 38-62% retracement zone | POSITIVE on backburner entries; flat elsewhere in MY version, which measures the leg from the last two pivots only |

**Under verification tonight:** the backburner bounce (RSI 30 and back over) with the stop walked under the idea
chart's higher lows, filtered to the right side of that chart's 12 EMA. +0.84% a trade on 18,396 focus-list trades
against +0.00% without the filter. Being checked across eras, markets, charts, sides, blocks of 20, and drawn as
charts before anything is claimed.

---

## 7. What is still untested (the queue)

1. Level weight by time spent, volume traded, recency.
2. Gaps as support and resistance.
3. Trendline breaks (we only use pivot breaks).
4. Oscillator divergence.
5. Value areas (needs a volume-at-price build from 5m bars).
6. Position sizing and the equity path: fixed fractional risk, limits, adding after drawdowns.
7. Events: earnings, CPI, FOMC, expiry.
8. His real costs: spread and slippage at his size, which decides whether anything on the 1h survives at all.

---

## 8. How a negative gets reported (his rule, 2026-09-12)

"i need an actual analysis thats not just jumping to conclusions based on your poor understanding of something. if
youre making shit up on your own, it better be with positive results, and not just so you can say something doesnt
work."

So: I do not get to say a method fails. I get to say MY IMPLEMENTATION of it produced X, name the weakness in that
implementation, and show a chart. Before anything is called dead it needs at least two honest implementations, a
picture, and his eyes. Effort goes into making a rule work, not into proving it does not.

## 9. The rules I keep breaking (so they are written where I will see them)

- Draw the trade before reporting a number. The 5x-risk bug was invisible in averages and obvious in the first
  chart.
- Read at the bar BEFORE the fill. Every look-ahead I have shipped was a flag read on the entry bar's close.
- Never cache into a shared object without proving the numbers are identical afterwards.
- Time one name before launching 809.
- The control must skip exactly what the rule skips.
- His constraints are requirements, not noise.
