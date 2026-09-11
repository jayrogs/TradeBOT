# AI Trading Project

A Flask trading desk (http://localhost:5001) that reads charts the way its owner reads them:
swing pivots (HH / HL / LH / LL), trends built from those pivots, backburners (RSI at or under 30 on a
running name), trend rides, and EQs (a series of higher lows and lower highs tightening). Every method is
turned into a study over ~800 names (stocks, ETFs, crypto, futures; 5 minute to weekly charts), and every
study gets a page of drawn example trades that the owner grades by eye before any verdict.

## Read these first

- `CLAUDE.md`: the rules for working on this project, the owner's vocabulary, and every settled finding
  with its numbers (numbered sections). It is the source of truth.
- `PROJECT_STATE.md`: the long-form history.
- `REVIEW.md`: what each dashboard page is for.

## Layout

| where | what |
|---|---|
| `server.py`, `run_server.ps1` | the desk (Flask). Pages live in `static/`, served without a /static prefix |
| `structure.py`, `panel.py` | the pivot and trend engine every study uses |
| `studies/*.py` | the studies. Run as `pythonw studies/<name>.py --procs 20 --log logs/<name>.log` |
| `validation/*.json` | study results the pages read (only the small ones are in git) |
| `pics_*.py` | draw example trades for each study, measured for overlapping text before saving |
| `check_pages.py` | the gate: every page loads, every file a page reads exists and holds real numbers |
| `tradingview/*.pine` | the same pivot/trend logic as TradingView indicators |
| `focus.py` | the focus list (20 stocks, 10 futures, 10 crypto) |

## Not in this repository

- **Market data** (`history/`, `cache/`, about 5 GB): rebuilt with the backfill scripts
  (`backfill_polygon.py` for stocks, `backfill_dukascopy.py` for forex).
- **API keys** (`livelog/*.json`): never committed.
- **Large study output and chart pictures** (`validation/` beyond the small result files, `logs/`, `*.csv`).
