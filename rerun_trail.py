"""Trail-width variants of the trend ride, full universe then the focus list. pythonw rerun_trail.py"""
import subprocess, sys, os, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
jobs = [["studies/trend_ride.py", "--variants", "--procs", "20", "--log", "logs/trend_ride_trail.log"],
        ["studies/trend_ride.py", "--variants", "--focus", "--procs", "20", "--log", "logs/trend_ride_trail_focus.log"]]
with open("logs/rerun_trail.log", "a") as f:
    for j in jobs:
        t0 = time.time(); f.write("%s start %s\n" % (time.strftime("%H:%M:%S"), " ".join(j))); f.flush()
        r = subprocess.run([sys.executable] + j, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        f.write("%s done rc=%s in %ds\n" % (time.strftime("%H:%M:%S"), r.returncode, time.time() - t0)); f.flush()
    f.write("ALL DONE\n")
