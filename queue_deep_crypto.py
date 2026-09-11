"""queue_deep_crypto.py -- after the all-names 5m Coinbase pull finishes, take
the ten majors' 15m history back 8 years (free; Coinbase reaches to listing).
Runs detached; logs to logs/backfill_crypto_deep.log.
"""

import os
import subprocess
import sys
import time

os.chdir(os.path.dirname(os.path.abspath(__file__)))
MARK = os.path.join("logs", "backfill_crypto_5m_all.log")
while True:
    try:
        if "  done" in open(MARK, encoding="utf-8", errors="ignore").read():
            break
    except OSError:
        pass
    time.sleep(300)
majors = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "LINK", "AVAX", "LTC", "SUI"]
with open(os.path.join("logs", "backfill_crypto_deep.log"), "w") as fh:
    subprocess.run([sys.executable, "-u", "backfill_crypto_intraday.py", "--tf", "15m",
                    "--years", "8", "--names"] + majors, stdout=fh, stderr=subprocess.STDOUT)
print("done", flush=True)
