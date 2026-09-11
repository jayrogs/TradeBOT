"""Waits for the Polygon pull to finish, then re-runs every study on the all-hours stock data.
pythonw rerun_after_polygon.py"""
import subprocess, sys, os, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
LOG = "logs/rerun_after_polygon.log"
def say(m):
    open(LOG, "a").write("%s %s\n" % (time.strftime("%H:%M:%S"), m))
say("waiting for the pull")
while True:
    try:
        if "done 604 names" in open("logs/polygon.log").read() or "done " in open("logs/polygon.log").read().splitlines()[-1]:
            break
    except Exception:
        pass
    time.sleep(30)
say("pull finished; studies start")
jobs = [["studies/trend_names.py", "--procs", "20", "--log", "logs/trend_names.log"],
        ["studies/trend_names.py", "--focus", "--procs", "20", "--log", "logs/trend_names_focus.log"],
        ["studies/trend_ride.py", "--procs", "20", "--log", "logs/trend_ride.log"],
        ["studies/trend_ride.py", "--focus", "--procs", "20", "--log", "logs/trend_ride_focus.log"],
        ["studies/trend_ride.py", "--variants", "--procs", "20", "--log", "logs/trend_ride_trail.log"],
        ["studies/trend_ride.py", "--variants", "--focus", "--procs", "20", "--log", "logs/trend_ride_trail_focus.log"],
        ["studies/backburner_study.py", "--procs", "20", "--log", "logs/backburner_study_allhours.log"],
        ["studies/name_scorecard.py", "--log", "logs/name_scorecard.log"],
        ["studies/split_events.py"]]
for j in jobs:
    t0 = time.time(); say("start " + " ".join(j))
    r = subprocess.run([sys.executable] + j, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    say("done rc=%s in %ds" % (r.returncode, time.time() - t0))
say("ALL DONE")
