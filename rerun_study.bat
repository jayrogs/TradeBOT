@echo off
cd /d "%~dp0"
python studies\backburner_study.py > logs\backburner_study_v2.log 2>&1
python studies\split_events.py > logs\split_events.log 2>&1
python studies\name_scorecard.py > logs\name_scorecard_v2.log 2>&1
python pics_cases.py > logs\pics_cases_v2.log 2>&1
echo done > logs\rerun_study.done
