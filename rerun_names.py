"""Re-run the trend behaviour study, full universe then the focus list. pythonw rerun_names.py"""
import subprocess, sys, os, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
jobs = [["studies/trend_names.py", "--procs", "20", "--log", "logs/trend_names.log"],
        ["studies/trend_names.py", "--focus", "--procs", "20", "--log", "logs/trend_names_focus.log"]]
with open("logs/rerun_names.log", "a") as f:
    for j in jobs:
        t0 = time.time(); f.write("%s start %s\n" % (time.strftime("%H:%M:%S"), " ".join(j))); f.flush()
        r = subprocess.run([sys.executable] + j, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        f.write("%s done rc=%s in %ds\n" % (time.strftime("%H:%M:%S"), r.returncode, time.time() - t0)); f.flush()
    f.write("ALL DONE\n")
