# What I hold as background: technical analysis and trade psychology

2026-09-12. His words: "is there a way i can get you to understand trade psychology and technical analysis
fundamentals? because youre acting like only the things we talk about exist for the most part."

He is right about the symptom. I have been testing his sentences as isolated switches on fast charts, which is not
how any of this works. This file is the general body I hold as background, written down so HE CAN CORRECT IT.
Strike out what is wrong, add what is missing, and it becomes part of the rules.

Nothing in here is a result. Results live in CLAUDE.md. This is the frame the results get judged in.

---

## 1. What a chart is

- Price is the record of an auction. It moves between BALANCE (two-sided, value being agreed, prices rotate) and
  TREND / IMBALANCE (one side in control, prices travel). An EQ is balance that is tightening; a trend is imbalance
  with pauses. Most tools work in one state and fail in the other, which is why a rule tested across everything
  usually reads as nothing.
- A chart size is a lens on the same auction, not a different market. Structure on a big chart outranks structure on
  a small one; the small chart's job is timing and risk, not opinion.
- Time of day and session matter. The open, the close, the overnight and the lunch lull have different behaviour.
  Mixing them is mixing populations.

## 2. Structure

- The language: higher highs / higher lows = uptrend; lower highs / lower lows = downtrend; anything else is
  transition or balance. A trend ends when the sequence breaks, not when an indicator says so.
- Swing points are where risk is defined. A stop belongs just past the point that makes the idea wrong, not at a
  round number or a fixed percentage.
- Prior pivots become reference levels. Old support acting as resistance (and the reverse) is the cleanest evidence
  that control changed hands.
- Consolidation shapes (flags, wedges, triangles, EQs) are pauses inside a move. They inherit the direction of what
  came before them more often than not, but only at LOCATION; in open space they are close to a coin flip.

## 3. Location and confluence

- A setup is worth more where several independent things line up: a bigger chart's moving average, a prior swing
  level, a value area edge, a round-number / gap area, an oversold reading. "Confluence" is not magic; it is the
  same level being remembered by different participants.
- The corollary matters more: the same pattern without location is noise. Most published pattern statistics fail
  because they ignore this.

## 4. Moving averages

- A moving average is a moving reference for "the status quo", not a signal. The 12 EMA in this room, the 21, the
  50, the 200 elsewhere: what makes them work is that enough people watch them to make them a location.
- Price riding one is trend persistence; repeated closes through one is a change of control. Slope matters as much
  as side.
- They lag by construction. They tell you what has been true, so they are for CONTEXT and for TRAILING, not for
  prediction.

## 5. Volume, liquidity, participation

- Volume confirms or questions a move: a break on thin volume is a candidate for a fakeout; a rotation on heavy
  volume at an edge is often the actual turn.
- Where volume traded (value areas, point of control) marks the prices the market accepted. Breaks away from value
  travel; moves back into value rotate. (Lamont's lens. The desk has bars only, so this needs building.)
- Liquidity decides whether an edge survives: spread, slippage, and how much size the book can absorb. An edge
  smaller than the round-trip cost does not exist.

## 6. The math that decides everything

- Expectancy = (win rate x average win) - (loss rate x average loss). Nothing else is "the edge".
- Win rate alone is meaningless, and so is reward-to-risk alone. They trade against each other: a 25% win rate needs
  ~4:1; a 60% win rate can live on 1:1.
- Variance is not optional. With a 35% win rate, ten losses in a row happens regularly. The system must be sized so
  that streak is survivable, or it will not be traded.
- Costs compound with frequency. A rule that makes +0.1% a trade and trades 1,500 times a year is a cost story
  before it is a strategy story.
- Position sizing is where most of the realised difference between traders lives: fixed fractional risk per trade,
  reduced size in bad conditions, and a hard daily/weekly loss limit.
- Sequence risk: the same trades in a different order produce very different equity paths. Judge a system on its
  worst path, not its average.

## 7. Trade psychology, as it actually bites

- Loss aversion: losses hurt about twice as much as equivalent gains feel good. That is why partials exist: taking
  something off converts an uncertain outcome into a certain one and makes the rest holdable. It usually costs a
  little expectancy and buys a lot of adherence. A plan that is followed beats a better plan that is abandoned.
- Recency and tilt: after two or three losses people either freeze or size up. Both destroy edges that were real.
- Confirmation bias: the reason to write the plan down BEFORE the entry, including where it is wrong.
- Sunk cost: moving a stop "just this once" is the single most common account killer.
- FOMO and the fear of missing the runner: this is what turns a mechanical partial into a discretionary hold.
- Boredom trading: most days have no setup. "Sit on your hands" is a rule, not an attitude.
- What this means for me: HIS CONSTRAINTS ARE REQUIREMENTS, NOT NOISE. If he says he wants a partial for security,
  the job is to find the best system that takes a partial, not to argue the expectancy of holding.

## 8. Regimes and time

- Everything is regime-dependent: 2020-2021 is not 2022 is not 2024. Any rule must be checked in separate eras and
  in both directions (long and short), or it is a curve fit on the era that dominated the sample.
- Trends in one asset class are not trends in another: crypto is 24/7 and news-driven, futures have sessions and
  rollovers, stocks have earnings and gaps, forex is macro-driven.
- Events (earnings, CPI, FOMC, expiry) change the distribution. A system that ignores them owns their risk anyway.

## 9. How a test should be built (my job)

- One trade skeleton, then switches. Never compare two things that differ in more than one way.
- Look-ahead is the default failure: the read must use the bar BEFORE the fill, the fill must be the next open, and
  a stop that gaps must fill at the gap, not the stop price.
- Population must be identical when comparing rules (the control has to skip what the rule skips).
- Report expectancy, win rate, average win vs average loss, worst losing streak, worst dip, time in trade and trades
  per year: enough for a human to know whether it is holdable.
- Multiple testing: dozens of switches means some look good by chance. What survives must survive out of sample, in
  every era, and on both sides.
- Draw the trades. Every number gets a picture before it gets a conclusion (the levels bug of 2026-09-11 was
  invisible in the averages and obvious in the first chart).

## 10. What I do NOT know and should not pretend

- Order flow, the tape, the book: not in the data.
- Options positioning, gamma, dealer hedging flows: not in the data, and a real driver of index behaviour.
- News and narrative: not in the data.
- His execution: real fills, real spreads at his size, his platform's behaviour. Assumed, not measured.
- What HE sees on a chart. That is why his gradings and markings matter more than my averages.

---

## The stack, as I will test it from now on

Every test is one setup, built in this order, and every layer is optional so its value can be measured:

1. **Regime / universe** -- which names, which conditions, which era.
2. **Context** -- what the bigger chart is doing (trend, balance, side of its 12 EMA).
3. **Location** -- where the setup sits (bigger 12 EMA, prior level, value edge, oversold).
4. **Trigger** -- the small-chart event that starts it (EQ break, higher low, backburner, 12 EMA regain).
5. **Risk** -- where it is wrong, how far that is, and whether the reward justifies it.
6. **Management** -- partial, stop movement, runner, time stop, session close.
7. **Size** -- fixed fractional, with limits; and the equity path that results.

Correct anything here that is wrong, Jay, and add what I have missed. This file wins over my assumptions.

---

## 11. Mark Douglas, *Trading in the Zone* (read in full, 2026-09-12, at his request)

The book's claim: better analysis is not what separates consistent winners. A mind-set is. What it means for
this desk, in his terms and mine:

**The five fundamental truths**
1. Anything can happen.
2. You don't need to know what is going to happen next to make money.
3. There is a random distribution between wins and losses for any given edge.
4. An edge is nothing more than a higher probability of one thing over another.
5. Every moment in the market is unique.

**The seven principles of consistency** (his checklist for "I am a consistent winner")
objectively identify edges; predefine the risk of every trade; completely accept that risk; act on the edge without
hesitation; pay yourself as the market makes money available; monitor your own errors; never violate these.

**The casino frame.** A casino has a ~4.5% edge at blackjack and makes money because it takes EVERY hand, over a
large sample. Picking and choosing which signals to take destroys the edge you measured. His exercise: define an
edge with no discretion, then take the next 20 occurrences, all of them, no deviation. Judge the SAMPLE, not the
trade.

**What he says about the things we argue about here**
- SCALING OUT IS CORRECT, and for the reason Jay gives. Douglas takes a third off as soon as the market gives a
  little, then a second third at a level, moving the stop to the entry: "risk-free opportunity". He calls the feeling
  of that state the point of the exercise. So Jay's "partial for security" is the textbook, not a concession, and my
  job is to find the best system that takes a partial.
- REWARD TO RISK ~3:1 makes a sub-50% win rate profitable. That is the shape to aim at, and it is why my
  "target at least as far as the stop" filter was too weak a bar.
- ONE TIMEFRAME FOR THE TRADE. "All your entry and exit signals have to be based in the same time frame"; other
  charts are FILTERS (his example: only take 30-minute support trades in the direction of the daily trend). Our EQ
  trade currently enters on the 5m and takes its stop from the hourly, which mixes the two. That is testable:
  same-timeframe risk with the hourly as a filter, against what we have now.
- THE STOP COMES FROM STRUCTURE, not from a dollar amount you are comfortable with: "let the market structure
  determine where this optimum point is".
- THE ERRORS HE LISTS are the ones to detect in the live log: hesitating, jumping the gun, no predefined risk,
  refusing the loss, cutting winners early, letting a winner become a loser, moving the stop closer, oversizing.
- "Rigid in our rules and flexible in our expectations." The typical trader is the reverse.

**What this changes in the studies, concretely**
1. Results get reported in R (multiples of the risk taken) as well as percent. R is the unit the whole framework
   speaks in.
2. Every rule gets a SAMPLE-OF-20 view: split its trades into blocks of 20 in time order and report how many blocks
   made money and the spread. That is what a human actually lives through.
3. No variant without a predefined stop gets reported as a real trade.
4. A trade is defined in ONE chart size; bigger charts enter as filters, and if a rule needs the bigger chart for its
   risk, that is a different trade and gets labelled as one.

(Note: the extracted text of the book lives in `scratch/` and is gitignored -- it is copyrighted and does not go to
GitHub.)

---

## 12. John Murphy, *Technical Analysis of the Financial Markets* (2026-09-12, his "gold standard")

Read: the trend chapter, support and resistance, moving averages, money management and trading tactics, and the
final checklist. What matters here is less the vocabulary (we have it) than the parts of it this desk has never
touched.

**His three parts of a trade, in order:** price forecasting (what to do), timing (when), money management (how
much). We have only ever worked on the first two. The third has had one study (`portfolio.py`) and no rules.

**Money management, his numbers**
- Risk at most ~5% of equity on any one trade; commit at most 10-15% to one market; at most 20-25% to one group.
- Reward-to-risk at least 3:1 on a trade worth taking. The best traders are right on ~40% of trades and win anyway.
- Trade MULTIPLE UNITS, split into a "trading" portion (taken off at the first objective / overbought / resistance)
  and a "trending" portion (loose stop, given room, produces the big wins). This is exactly Jay's partial-plus-rest,
  written in 1986.
- Pyramiding: each add smaller than the last, only add to winners, never to losers, and move the stop to breakeven.
- Increase size after a DIP in equity, not after a winning streak. (Against instinct, and the opposite of tilt.)
- Never move a stop away; stops belong beyond a valid support or resistance level, with volatility setting the
  distance: too close and noise takes you out, too far and the loss is not worth the information.

**Timing tactics (the "when")**
- Breakouts: anticipate, take the break, or buy the pullback -- or split the position across all three.
- A tight trendline break is an early entry or exit signal.
- Support and resistance are the best tools for entry and for stop placement.
- 40-60% retracements of the prior leg are the buying zone in an uptrend (selling zone in a downtrend).
- Gaps act as support and resistance; buy the dip into the upper end of a gap, stop below it.
- Work long chart to short: monthly/weekly for context, daily for the decision, intraday only to fine-tune.
  (Same shape as the TCG room and as Douglas's "other timeframes as filters".)

**What makes a level matter** (his three measures, none of which our code uses): how much TIME price spent there,
how much VOLUME traded there, and how RECENT it was. Plus role reversal: once a level is decisively penetrated,
resistance becomes support and support becomes resistance.

### What this desk has never tested, in his own list

| Murphy's tool | Status here |
|---|---|
| 40-60% retracement as the entry zone | never tested |
| Role reversal (broken resistance as support) | never tested |
| Level significance by time spent / volume / recency | never tested; our levels are just the last pivot |
| Volume confirming a break or a turn | NEVER TESTED, and we have the volume data |
| Gaps as support/resistance | never tested |
| Trendline breaks (as opposed to pivot breaks) | never tested |
| Oscillator divergence | never tested |
| 3:1 reward-to-risk as a hard filter | partly (the far-line filter, #26e) |
| Trading unit vs trending unit | partly (partial + runner) |
| Sizing, equity path, adding after drawdowns | only `portfolio.py`; no rules |

That table is the research queue. The first four are the cheapest and the most likely to matter, and volume is the
embarrassing one: every study on this desk so far has ignored the volume column entirely.
