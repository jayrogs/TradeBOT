"""Twenty exit managers, full universe then focus. pythonw rerun_exits.py"""
import subprocess, sys, os, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
jobs = [["studies/trend_ride.py", "--exits", "--procs", "20", "--log", "logs/trend_ride_exits.log"],
        ["studies/trend_ride.py", "--exits", "--focus", "--procs", "20", "--log", "logs/trend_ride_exits_focus.log"]]
with open("logs/rerun_exits.log", "a") as f:
    for j in jobs:
        t0 = time.time(); f.write("%s start %s\n" % (time.strftime("%H:%M:%S"), " ".join(j))); f.flush()
        r = subprocess.run([sys.executable] + j, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        f.write("%s done rc=%s in %ds\n" % (time.strftime("%H:%M:%S"), r.returncode, time.time() - t0)); f.flush()
    f.write("ALL DONE\n")
