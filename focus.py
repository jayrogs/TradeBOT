"""focus.py -- the names we are refining on (2026-09-06, his call: "20 major
stocks, top 10 futures, and 10 best crypto names" before touching the long
tail). Edit the lists here; every study and chart page that takes --focus
reads them.

    python focus.py          # prints the list and which files exist
"""

import os

STOCKS = ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AMD", "AVGO", "MU",
          "NFLX", "LLY", "JPM", "V", "COST", "ORCL", "TSM", "PLTR", "COIN", "MSTR"]
FUTURES = ["ES_F", "NQ_F", "RTY_F", "YM_F", "CL_F", "GC_F", "SI_F", "NG_F", "ZN_F", "6E_F"]
# the majors he trades on Kraken/Coinbase plus the names the scorecard likes
CRYPTO = ["BTC", "ETH", "SOL", "XRP", "AAVE", "INJ", "LINK", "AVAX", "DOGE", "HYPE"]


def names():
    """[(symbol, kind)] in the order stocks, futures, crypto."""
    return ([(s, "stock") for s in STOCKS] + [(s, "futures") for s in FUTURES]
            + [(s, "crypto") for s in CRYPTO])


def have(sym, kind):
    folder = {"stock": os.path.join("history", "stocks"), "futures": os.path.join("history", "futures"),
              "crypto": "history"}[kind]
    return os.path.exists(os.path.join(folder, "%s_1h.csv.gz" % sym))


if __name__ == "__main__":
    for s, k in names():
        print("  %-8s %-8s %s" % (s, k, "ok" if have(s, k) else "MISSING"))
