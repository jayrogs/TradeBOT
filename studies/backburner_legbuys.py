"""backburner_legbuys.py -- WHAT EACH BUY EARNS, STOCKS VS CRYPTO (2026-09-23). His question: "How does buying more of the dip
going lower not more helpful for stocks? Is it just cause of losers being worse?" -- and then: "very important behavior
difference between sectors", so it lives here and in CLAUDE.md #45, not in scratch.

Every page trade with orders resting at RSI 30, 25 and 20 (equal dollars, the page's cancel/stop/exits). Each buy's own
return per dollar, split by how deep the dip went. Every share sells at the same prices, so buy i returns
(position price / fill i) x (1 + position return + cost) - 1 - cost.

    python studies/backburner_legbuys.py
Writes validation/backburner_legbuys.json
"""
import json, io, os
import concurrent.futures as cf, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import backburner_study as S, trend_ride as R, pics_backburner_tcg as PB

def w(a):
    sym,kind=a; out=[]
    try:
        cost=PB.COST.get(kind,0.05)
        for r in PB.trades_for(sym,kind,dict(PB.STOP,bids=[25,20])):
            E=r["entry"]; c=cost*(1.5 if r["half_at"] is not None else 1.0); g=1+(r["pct"]+c)/100
            legs=[100*(E/fx*g-1-c/100) for fx in r["fills"]]
            out.append((0 if kind in("stock","etf") else 1, len(r["fills"]), legs[0],
                        legs[1] if len(legs)>1 else np.nan, legs[2] if len(legs)>2 else np.nan,
                        100*(r["fills"][0]/min(r["fills"])-1)))
    except Exception: pass
    return out

if __name__=="__main__":
    names=R._by_size([(s,k) for s,k in S.universe() if k in("stock","etf","crypto") and s not in PB.T.SUSPECT])
    R.quiet_workers(); rows=[]
    with cf.ProcessPoolExecutor(8) as ex:
        for o in ex.map(w,names,chunksize=2): rows+=o
    f=pd.DataFrame(rows,columns=["crypto","fills","r30","r25","r20","depth"])
    res={}
    for lab,g in (("STOCKS + ETFs",f[f.crypto==0]),("CRYPTO",f[f.crypto==1])):
        res[lab]={}
        print("\n"+lab)
        print("  %-40s %5s %8s %8s %6s %9s %9s"%("","n","per $","middle","won","avg win","avg loss"))
        def line(name,x):
            x=x.dropna(); 
            if len(x)<10: return
            print("  %-40s %5d %+7.2f%% %+7.2f%% %5.0f%% %+8.2f%% %+8.2f%%"%(name,len(x),x.mean(),x.median(),100*(x>0).mean(),x[x>0].mean(),x[x<=0].mean()))
            res[lab][name]=dict(n=int(len(x)),per_dollar=float(x.mean()),middle=float(x.median()),won=float((x>0).mean()),
                                avg_win=float(x[x>0].mean()),avg_loss=float(x[x<=0].mean()))
        line("30 buy, trades that stopped there",g[g.fills==1].r30)
        line("30 buy, trades that went on to 25",g[g.fills>=2].r30)
        line("25 buy",g.r25)
        line("30 buy, trades that went on to 20",g[g.fills==3].r30)
        line("20 buy",g.r20)
        print("  share of trades reaching 25: %.0f%%   reaching 20: %.0f%%"%(100*(g.fills>=2).mean(),100*(g.fills==3).mean()))
    res["all dollars"]={"STOCKS + ETFs": float(np.nanmean(np.r_[f[f.crypto==0].r30, f[f.crypto==0].r25.dropna(), f[f.crypto==0].r20.dropna()])),
                        "CRYPTO": float(np.nanmean(np.r_[f[f.crypto==1].r30, f[f.crypto==1].r25.dropna(), f[f.crypto==1].r20.dropna()]))}
    json.dump(dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), table=res),
              io.open(os.path.join("validation","backburner_legbuys.json"),"w",encoding="utf-8"), indent=1)
