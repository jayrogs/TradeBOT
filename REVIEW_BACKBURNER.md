# The backburner, checked twice, explained plainly

2026-09-15. Two full passes over everything from the last three days. Written so that nothing needs a
dictionary. Where a number changed, the old one is shown crossed out so you can see what moved.

---

## Part 1 — What the trade is

A **backburner** is your word for buying something that just got hit hard.

Here is the exact recipe the computer tested:

1. Look at the **daily chart** — one candle per day.
2. The **RSI** — a 0-to-100 dial that says how beaten-up a stock is — reads **30 or lower**.
3. Today the stock **opened lower than yesterday's lowest price**. There is a gap on the chart. Someone panicked
   overnight. We call this the **fear gap**.
4. **Buy.** If it keeps falling, **buy more** — up to five times, a little lower each time, as long as the dial stays
   at 30 or under. Your price is the average of what you paid.
5. Put a **stop** (the "I was wrong, get me out" price) just under the lowest thing you bought.
6. When it bounces up by the same distance as your stop is below, **sell half**. Keep the rest with a stop that
   follows the price up. Sell the rest when that stop is hit.

That is the whole thing.

---

## Part 2 — What is a good result, in plain words

- **R** means "how many times your stop-distance you made." If your stop was $1 below your buy, and you made $2,
  that is +2R. If you lost the $1, that is −1R. It lets a $5 stock and a $500 stock be compared.
- **The control** is the same trade started on a random day instead of on a backburner day. If the backburner
  is not better than random, it is not worth anything.
- **A drawdown** is how far the account fell from its best day to its worst day after that. −28% means at the
  worst moment you were down 28% from your high.
- **Slots** are how many trades you can hold at once. Ten slots means ten positions, each about a tenth of your
  money.

---

## Part 3 — What the computer found (the good part)

**Buying once loses. Buying more as it falls wins.**

| how you buy the dip | R |
|---|---|
| buy once and stop | **−0.06R** (worse than random) |
| buy up to five times as it falls | **+0.35R** |

This was checked two ways: it is not just that the stop is wider, and no trades were quietly dropped. Your rule
"scale into it" is the whole edge.

**The fear gap makes it much better.**

| | R |
|---|---|
| any backburner | +0.35R |
| backburner **with** a fear gap | **+0.65R** |
| a random day | +0.12R |

It worked in 10 out of 10 years. This is the strongest single thing found in the whole project.

**On the daily chart it works. On the 5-minute chart, whether the market is healthy stops mattering.** The
big-picture dips are the ones that pay.

---

## Part 4 — What was wrong, and got fixed

### 1. The account was using borrowed money (the big one)

The first "how much does this make a year" number was **+40%**. It was fake.

Why: if your stop is 4% below your buy and you want to risk 1% of your account, you have to buy a position worth
26% of your account. Ten of those is 260% of your account. You do not have 260%. The computer was pretending you
did.

Fixed: a real cash account. You can only spend what you have.

| 10 slots | before | now |
|---|---|---|
| a year | ~~+40%~~ | **+17%** |

### 2. Twenty-three stocks had broken data

A stock split (one share becomes two, the price halves) was not adjusted in 23 names. The computer saw a fake
one-day crash or a fake one-day doubling. One of them, QXO, was carrying a fake +107% "trade" with a 240% day
inside it. All 23 are out. It cost 4% of the profit.

### 3. The pictures and the numbers were two different trades

The charts said "sell half at 1× the stop." The study was secretly selling half at a different price (the weekly
average line) when that was further away. 34 of 59 trades disagreed. Fixed so they are the same trade, and there
is now a test that fails if they ever drift apart again.

### 4. The drawdown was measured wrong

The account was only checked on days something **sold**. But in March 2020 you were holding ten falling
positions for days. Checked every day, like SPY is:

| | drawdown |
|---|---|
| first number (only on sell days) | ~~−17%~~ |
| **real, checked every day** | **−28%** |
| SPY, the same years | −34% |

The worst day was 2020-03-23. Same day as SPY's worst.

### 5. "The daily chart is best" was not proved

The daily was compared to the hourly by raw R. But each chart has its own random-day control, and against those,
the **4-hour chart has a bigger edge** (+0.71R over random vs the daily's +0.53R). Only the daily was run through
the account. So "daily is best" is a guess for now, and the page says so.

---

## Part 5 — What was checked and was fine

| the question | the answer |
|---|---|
| Does the computer peek at tomorrow's prices? | No. Every rule uses only what you could see at that moment. |
| Is the "open" a price you could really buy at? | Yes. On 300 of 300 days it was the real 9:30 open. |
| Are the biggest winners real? | Yes. They are the March 2020 crash bottom: TSLA, DKNG, BX, SCCO. |
| Do the fast maths and the slow maths agree? | Yes. 91 trades checked, 0 disagreements. |
| How long is money tied up? | Middle trade 24 days. One in ten over four months. |
| Does buying a name you already hold matter? | No. Blocking it: same result. |
| Does trading cost matter? | Barely. Each extra 0.10% of cost takes 3% of the average trade. |

---

## Part 6 — What cannot be fixed on this computer

**The list of stocks is today's list.** Every company that crashed, hit 30, gapped down, and then **died** is not
in the data. A buy-the-crash rule is the one kind of rule that this makes look better than it is.

We can put a fence around it:

| which stocks | 10 slots, a year |
|---|---|
| all of them | +17% — the most it could be |
| **only ETFs** (baskets of stocks; these do not die) | **+11% — the least it could be** |
| SPY, just holding it | +13% |

The truth is between +11% and +17%. Fixing this needs a paid list of dead companies.

---

## Part 7 — So what is it actually worth?

In plain words, with a cash account and ten slots:

- **About +17% a year, maybe as low as +11%.** SPY did +13%.
- **Worst fall: −28%.** SPY's was −34%.
- **It made money in all 10 years. It beat SPY in only 4 of them.**
- **Where it shines: bad years.** 2018: +8% while SPY lost 6%. 2022: +13% while SPY lost 20%.
- **Where it lags: good years.** It sat in cash waiting for crashes while SPY just went up.
- **2020 was a letdown:** +2%. All ten slots were full of early-March losers when the real bottom fired.

A few big winners carry it: the top 5% of trades make about two-thirds of the profit. You have to take every
trade to catch the few that pay.

**Honest one-line summary:** a real but modest trade that is worth having in a bear market, is roughly a wash
with the index in a bull market, and whose true value sits somewhere between "a bit worse than SPY" and "a bit
better than SPY with a gentler worst day."

---

## Part 8 — What to do next, in order

1. **Look at the sixteen pictures on /scalein and grade them.** Nothing above counts until you have seen the
   trades and said whether they look like something you would take.
2. **Run the 4-hour chart through the account.** It might be the better version.
3. **Get the list of dead companies**, if this is ever going to be traded with real money. It is the one thing
   that could cut the number in half.
