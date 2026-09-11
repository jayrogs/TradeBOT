"""pull_focus.py -- fetch the intraday (Alpaca) and daily (Yahoo) history for
a few named stocks that the tier1 scan missed (NVDA, TSLA, NFLX, PLTR were not
in cache/tier1.csv at all -- only their tokenised OKX versions).

    pythonw pull_focus.py --log logs/pull_focus.log NVDA TSLA NFLX PLTR
"""
import os
import subprocess
import sys
import time

import pandas as pd
import yfinance as yf

syms = [a for a in sys.argv[1:] if not a.startswith("--") and a != "logs/pull_focus.log" and not a.endswith(".log")]
log = None
for i, a in enumerate(sys.argv):
    if a == "--log" and i + 1 < len(sys.argv):
        log = sys.argv[i + 1]
        sys.stdout = sys.stderr = open(log, "w", buffering=1, encoding="utf-8", errors="replace")
t0 = time.time()
procs = []
for tf in ("1h", "15m", "5m"):
    procs.append(subprocess.Popen([sys.executable, "backfill_stocks.py", "--tf", tf, "--since", "2021-01-01"] + syms,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)))
out_dir = os.path.join("history", "stocks")
d = yf.download(syms, interval="1d", period="10y", progress=False, auto_adjust=False, group_by="ticker", threads=True)
for s in syms:
    try:
        x = d[s].dropna(how="all")
        x = x[["Open", "High", "Low", "Close", "Volume"]]
        x.index.name = "Date"
        x.to_csv(os.path.join(out_dir, "%s_1d.csv.gz" % s), compression="gzip")
        print("  %s daily: %d bars" % (s, len(x)), flush=True)
    except Exception as ex:
        print("  %s daily failed: %s" % (s, ex), flush=True)
for p in procs:
    o, _ = p.communicate()
    print(o[-600:], flush=True)
print("  done in %.0fs" % (time.time() - t0), flush=True)
if log:
    open(os.path.splitext(log)[0] + ".done", "w").write("done")
