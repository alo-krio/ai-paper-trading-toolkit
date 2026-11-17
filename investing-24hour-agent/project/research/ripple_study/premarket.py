import json, glob, os, numpy as np, pandas as pd
P='/home/user/workspace/investing-24hour-agent/project'
fr=[]
for f in glob.glob(P+'/data/ohlcv/*.json'):
    r=json.load(open(f))
    if len(r)<120: continue
    d=pd.DataFrame(r,columns=['date','o','h','l','c','v']); d['t']=os.path.basename(f)[:-5]; fr.append(d)
D=pd.concat(fr); D=D.sort_values(['t','date']); D['pc']=D.groupby('t').c.shift(1)
D['gapr']=D.o/D.pc-1; D['ocr']=D.c/D.o-1
S=D[D.t=='SPY'].set_index('date')
X=D.set_index(['t','date'])
E=pd.read_csv(P+'/research/ripple_study/events.csv'); E['date']=E.date.astype(str)
try:
    C=pd.read_csv(P+'/research/ripple_study/events_classified.csv'); C['date']=C.date.astype(str)
    E=E.merge(C[['leader','date','t','scope','trig2']],on=['leader','date','t'],how='left')
except Exception: E['scope']=np.nan
rows=[]
for e in E.itertuples():
    try: y=X.loc[(e.t,e.date)]; l=X.loc[(e.leader,e.date)]; s=S.loc[e.date]
    except KeyError: continue
    sg=np.sign(l.c/l.pc-1-(s.c/s.pc-1)) or 1
    rows.append(dict(scope=e.scope,trig=e.trig2,follow=e.follow,lead_gap=100*sg*(l.gapr-s.gapr),lead_oc=100*sg*(l.ocr-s.ocr),
                     gap=100*sg*(y.gapr-s.gapr),oc=100*sg*(y.ocr-s.ocr),n3=e.n3))
R=pd.DataFrame(rows)
R['kind']=np.where(R.follow>=0.7,'follower',np.where(R.follow<0.3,'laggard','partial'))
def st(n,s): print(f"{n:40s} n={len(s):5d} | leader: pre-open {s.lead_gap.mean():+.2f} session {s.lead_oc.mean():+.2f} | linked: pre-open {s.gap.mean():+.2f} session(open->close) {s.oc.mean():+.2f} next3 {s.n3.mean():+.2f} | share of linked day-0 move before the bell {100*s.gap.mean()/(s.gap.mean()+s.oc.mean()) if (s.gap.mean()+s.oc.mean()) else float('nan'):.0f}%")
print('signed + = same direction as leader; excess vs SPY; pre-open = prior close -> 9:30 open (after-hours + pre-market)')
st('ALL links',R)
for k in ('follower','laggard'): st('  '+k,R[R.kind==k])
for k,s in R.dropna(subset=['scope']).groupby('scope'): st('scope '+k,s)
# leader gaps big but linked open small: does linked open->close follow?
m=(R.lead_gap.abs()>=4)&(R.gap.abs()<0.5); st('leader pre-open>=4, linked pre-open <0.5',R[m])
m=(R.lead_gap>=4)&(R.gap<0.5); st('  leader UP pre-open, linked flat at open',R[(R.lead_gap>=4)&(R.gap.abs()<0.5)])
# leader fades or extends after the open
st('leader extends after open (lead_oc>0)',R[R.lead_oc>0]); st('leader fades after open (lead_oc<0)',R[R.lead_oc<0])
R.to_csv(P+'/research/ripple_study/premarket_split.csv',index=False)
