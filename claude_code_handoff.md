# Project Handoff — Trading Strategy Research

Paste this into Claude Code as your first message, with these files in the folder:

- `harness.py` — the testing engine
- `run_test.py` — press-go script
- `chartguys_methodology.md` — analysis of a vendor's system
- `strategy_spec_v1.md` — a written-in-advance strategy plan
- `chartguys_all_picks.csv` — 291 vendor picks, parsed
- `cg2_trades_top.csv` — outcomes we recomputed for those picks

---

## Paste from here down

I'm building and testing stock trading strategies. A previous session did the
research; the files in this folder are the output. Read `harness.py` and
`strategy_spec_v1.md` first — they explain the approach.

**Where things stand:** the testing machinery is built and verified. It has been
fed pure random data (no real edge possible) and correctly reported "not
significant," so it can be trusted to reject nonsense. What has NOT been done is
running it on real market data. That's step one.

**What I want from you:** run `python run_test.py`, get it working, then help me
try better strategies. The strategy lives in one function called
`weakness_reversion` at the bottom of `harness.py`. Everything else stays put.

**The goal:** beat buying-and-holding SPY, after trading costs and after tax.
That's a genuinely hard bar and most professionals miss it. If we can't clear it,
the correct answer is to buy the index, and I'd rather find that out than be told
a comfortable story.

---

## Rules I want you to hold me to

These exist because it is extremely easy to build something that looks brilliant
on past data and earns nothing going forward. Please push back on me when I break
them — I would rather be argued with than agreed with.

**1. Simple beats complicated.** Every extra indicator or rule is another dial to
turn, and more dials means more ways to accidentally fit random noise. If a
strategy needs more than about four rules, be suspicious of it. Strategies that
survive decades are boring and short.

**2. The deflated Sharpe number is the one that matters.** It asks: given how many
versions we tried, could this result have happened by luck? Below 0.95 means yes,
it could. Ignore a good-looking return with a bad deflated Sharpe. This has been
demonstrated on this exact machinery — random noise produced a stretch returning
+18% with a great-looking score, and the deflated number correctly called it
worthless.

**3. Never change a rule because of what recently happened.** If I say "let's
adjust this, it did badly last quarter," that's me fitting to noise. Tell me no.

**4. If it fails, we say it failed.** Do not tune a strategy until it passes.
Tuning until it passes is the single most common way people fool themselves.

**5. Assume trading costs are real.** Slippage stays in every test. Do not turn it
off to make a curve look better.

**6. Watch for lookahead.** The most common backtest bug is accidentally using
information that wasn't available yet. If a result looks amazing, suspect this
first. A real one bit us already: stock split adjustments made old prices look 10x
too cheap and turned a break-even system into a fake +31% a year. Check for that
class of error before believing anything.

---

## Background on why the strategy is what it is

The current strategy — buy the most beaten-down stocks in the list, only while the
overall market is healthy — comes from one finding in `chartguys_methodology.md`.
A vendor's 169 real trades showed that stocks *falling* short-term at pick time
did much better than stocks rising: 60.8% win rate versus 45.8%. That survived a
check for whether it was just a selection artifact, and it held up across three
separate sub-groups.

Treat it as a starting hypothesis, not a fact. It came from one vendor's
discretionary picks and may not survive a mechanical version.

Everything else in that document is unverified and should not be built on. About
fifteen different splits of the data were tried, and with fifteen tries there was
a 58% chance of finding something impressive purely by accident.

---

## Immediate tasks

1. Get `run_test.py` running. It downloads prices the first time, which is slow.
   Expect the first result to lose to SPY — that's the honest starting point.
2. Check the whole pipeline for lookahead bugs before trusting any output.
3. Then let's try variations, one at a time, checking the deflated Sharpe each time.

Please tell me plainly when something doesn't work or when an idea of mine is bad.
Explain things in plain language — skip the jargon, or define it the first time.
