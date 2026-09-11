"""queue_stocks.py -- after the top-300 stock pull finishes, pull the next
tier (top 600) on every timeframe. Runs detached; logs to logs/bf600_*.log.
"""

import os
import subprocess
import sys
import time

os.chdir(os.path.dirname(os.path.abspath(__file__)))
MARK = os.path.join("logs", "bf300_1d.log")
while True:
    try:
        if "done:" in open(MARK, encoding="utf-8", errors="ignore").read():
            break
    except OSError:
        pass
    time.sleep(120)
for tf in ("1h", "15m", "5m", "1d"):
    with open(os.path.join("logs", "bf600_%s.log" % tf), "w") as fh:
        subprocess.run([sys.executable, "-u", "backfill_stocks.py", "--top", "600", "--tf", tf],
                       stdout=fh, stderr=subprocess.STDOUT)
print("done", flush=True)
