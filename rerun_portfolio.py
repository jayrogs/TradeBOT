"""Rebuild the portfolio trades (now including the repaired forex pairs), then rank the names.
pythonw rerun_portfolio.py"""
import os, subprocess, sys, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
jobs = [["studies/portfolio.py", "--with-forex", "--procs", "20", "--log", "logs/portfolio.log"],
        ["studies/portfolio_names.py", "--procs", "20", "--log", "logs/portfolio_names.log"]]
with open("logs/rerun_portfolio.log", "w", buffering=1) as f:
    for j in jobs:
        t0 = time.time(); f.write("%s start %s\n" % (time.strftime("%H:%M:%S"), j[0]))
        r = subprocess.run([sys.executable] + j, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        f.write("%s done rc=%s in %ds\n" % (time.strftime("%H:%M:%S"), r.returncode, time.time() - t0))
    f.write("ALL DONE\n")
