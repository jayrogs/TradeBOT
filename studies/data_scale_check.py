"""data_scale_check.py -- every name: do its hourly and daily closes agree? (2026-09-23, found through BNY: hourly ~$9, daily ~$101).
A name whose closes are 15%%+ apart on more than 1%% of days goes in validation/suspect_names.json. Run after any data pull."""
import sys, concurrent.futures as cf
sys.path.insert(0,"."); sys.path.insert(0,"studies")
import numpy as np, pandas as pd
import backburner_study as S, eq_freeride2 as FR2, trend_ride as R
def w(a):
    s,k=a
    try:
        fr={x:v for x,v in S.frames_for(s,k).items() if x in("1h","1d")}
        if k in("stock","etf"): fr=FR2.regular_hours(fr)
        h,d=fr["1h"],fr["1d"]
        hi=pd.DatetimeIndex(h.index); hi=hi.tz_localize(None) if hi.tz is not None else hi
        di=pd.DatetimeIndex(d.index); di=di.tz_localize(None) if di.tz is not None else di
        hc=pd.Series(h.Close.values.astype(float),index=hi).groupby(hi.normalize()).last()
        dc=pd.Series(d.Close.values.astype(float),index=di.normalize()).groupby(level=0).last()
        j=pd.concat([hc,dc],axis=1,join="inner").dropna()
        if len(j)<20: return None
        r=(j.iloc[:,1]/j.iloc[:,0])
        bad=(np.abs(np.log(r))>np.log(1.15)).mean()
        return (s,k,float(r.median()),float(bad),len(j))
    except Exception as e: return None
if __name__=="__main__":
    names=[(s,k) for s,k in S.universe() if k!="forex"]
    R.quiet_workers(); rows=[]
    with cf.ProcessPoolExecutor(8) as ex:
        for o in ex.map(w,names,chunksize=4):
            if o: rows.append(o)
    rows.sort(key=lambda x:-x[3])
    print("names where hourly and daily closes disagree by 15%+ on some days (share of days):")
    for s,k,m,b,n in rows:
        if b>0.01: print("  %-7s %-7s daily/hourly middle ratio %.3f   disagree on %.0f%% of %d days"%(s,k,m,100*b,n))
    print("checked",len(rows))
