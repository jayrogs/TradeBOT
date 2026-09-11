"""After the crypto top-up: trend behaviour, trend ride, trail variants; full then focus. pythonw rerun_all_trend.py"""
import subprocess, sys, os, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
jobs = [["studies/trend_names.py", "--procs", "20", "--log", "logs/trend_names.log"],
        ["studies/trend_names.py", "--focus", "--procs", "20", "--log", "logs/trend_names_focus.log"],
        ["studies/trend_ride.py", "--procs", "20", "--log", "logs/trend_ride.log"],
        ["studies/trend_ride.py", "--focus", "--procs", "20", "--log", "logs/trend_ride_focus.log"],
        ["studies/trend_ride.py", "--variants", "--procs", "20", "--log", "logs/trend_ride_trail.log"],
        ["studies/trend_ride.py", "--variants", "--focus", "--procs", "20", "--log", "logs/trend_ride_trail_focus.log"]]
with open("logs/rerun_all_trend.log", "a") as f:
    for j in jobs:
        t0 = time.time(); f.write("%s start %s\n" % (time.strftime("%H:%M:%S"), " ".join(j))); f.flush()
        r = subprocess.run([sys.executable] + j, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        f.write("%s done rc=%s in %ds\n" % (time.strftime("%H:%M:%S"), r.returncode, time.time() - t0)); f.flush()
    f.write("ALL DONE\n")
