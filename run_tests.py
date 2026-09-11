"""run_tests.py -- the whole battery, one command, fail-fast summary."""
import subprocess
import sys

SUITES = ["test_trend.py", "test_approved.py", "test_rider.py",
          "test_harden.py", "test_livelog.py", "test_structure.py"]
bad = []
for t in SUITES:
    r = subprocess.run([sys.executable, t], capture_output=True, text=True)
    tail = (r.stdout.strip().splitlines() or ["(no output)"])[-1]
    print("%-22s %s   %s" % (t, "PASS" if r.returncode == 0 else "FAIL", tail))
    if r.returncode:
        bad.append(t)
# a one-line stamp the dashboard (/) shows
try:
    import os
    import time
    os.makedirs("logs", exist_ok=True)
    with open(os.path.join("logs", "tests_last.txt"), "w") as fh:
        fh.write("%s  %d/%d suites pass%s" % (
            time.strftime("%Y-%m-%d %H:%M"), len(SUITES) - len(bad), len(SUITES),
            ("  FAIL: " + ", ".join(bad)) if bad else ""))
except OSError:
    pass
sys.exit(1 if bad else 0)
