"""Extended-hours ripple test: for catalysts (Apr-Nov 2026) use SIP 30-min bars from the prior 4 PM to 10 AM.
Leader after-hours move (4 PM -> 8 PM close) and pre-market (4 AM -> 9:00). Linked names: what moves 8 PM -> 9:00 AM,
9:00 -> 9:30 open, 9:30 -> 10:00. Question: once the leader has moved after hours, is there ripple left to capture from a
9:00 pre-market entry (or 8 PM), or is it priced by then?"""
import sys, time, numpy as np, pandas as pd, datetime as dt
P='/home/user/workspace/investing-24hour-agent/project'; sys.path.insert(0,P+'/scripts'); import alpaca_data as A
E=pd.read_csv(P+'/research/ripple_study/events_classified.csv'); E['date']=E.date.astype(str)
def off(d): x=dt.date.fromisoformat(d); return 4 if dt.date(2026,3,8)<=x<dt.date(2026,11,1) else 5
def utc(d,hh,mm): return (dt.datetime.fromisoformat(d)+dt.timedelta(hours=hh+off(d),minutes=mm)).strftime('%Y-%m-%dT%H:%M:%SZ')
def prevday(d):
    x=dt.date.fromisoformat(d)-dt.timedelta(days=1)
    while x.weekday()>=5: x-=dt.timedelta(days=1)
    return str(x)
out=[]
for i,((L,d),g) in enumerate(E.groupby(['leader','date'])):
    p=prevday(d); syms=[L,'SPY']+list(g.t.unique())[:20]
    try: b=A.get('/v2/stocks/bars',symbols=','.join(syms),timeframe='30Min',start=utc(p,15,30),end=utc(d,10,0),feed='sip',limit=10000).get('bars',{})
    except Exception: time.sleep(1); continue
    def at(s,day,hh,mm,field='c'):
        t=utc(day,hh,mm); v=[x for x in b.get(s,[]) if x['t']==t]; return v[0][field] if v else None
    def last_before(s,day,hh,mm):
        t=utc(day,hh,mm); v=[x for x in b.get(s,[]) if x['t']<t]; return v[-1]['c'] if v else None
    pts=lambda s:(at(s,p,15,30),last_before(s,d,0,0),last_before(s,d,9,0),at(s,d,9,30,'o'),at(s,d,9,30))
    lp=pts(L); sp=pts('SPY')
    if None in lp: continue
    c4,pm8,am9,o930,p10=lp
    lead_ah=100*(pm8/c4-1); lead_pre=100*(am9/c4-1)
    for r in g.itertuples():
        q=pts(r.t)
        if None in q: continue
        sg=np.sign(lead_pre) or 1
        out.append(dict(leader=L,date=d,t=r.t,scope=r.scope,lead_ah=sg*lead_ah,lead_pre=sg*lead_pre,
            ah=100*sg*(q[1]/q[0]-1), night=100*sg*(q[2]/q[1]-1), pre_to_open=100*sg*(q[3]/q[2]-1), first30=100*sg*(q[4]/q[3]-1),
            from9_to10=100*sg*(q[4]/q[2]-1), n3=r.n3*np.sign(r.lead_x0)*sg))
    if i%100==0: print(i,flush=True)
R=pd.DataFrame(out); R.to_csv(P+'/research/ripple_study/extended.csv',index=False)
print("signed by the leader's move from 4 PM to 9 AM (known pre-market); raw returns, not SPY-adjusted (SPY overnight is small)")
def st(n,s): print(f"{n:44s} n={len(s):5d} | leader AH {s.lead_ah.mean():+.2f} 4PM->9AM {s.lead_pre.mean():+.2f} | linked: 4->8PM {s.ah.mean():+.2f} 8PM->9AM {s.night.mean():+.2f} 9->9:30 {s.pre_to_open.mean():+.2f} 9:30->10 {s.first30.mean():+.2f} | 9AM->10AM {s.from9_to10.mean():+.2f} hit {100*(s.from9_to10>0).mean():.0f}% next3 {s.n3.mean():+.2f}")
st('ALL',R)
st('leader moved >= 4% by 9 AM',R[R.lead_pre>=4])
st('  ...and linked flat by 9 AM (|4PM->9AM| < 0.5)',R[(R.lead_pre>=4)&((R.ah+R.night).abs()<0.5)])
st('  ...and linked already moved >= 2 by 9 AM',R[(R.lead_pre>=4)&((R.ah+R.night)>=2)])
for sc in ('company_specific','mixed','industry_signal'): st('scope '+sc+', leader >= 4',R[(R.scope==sc)&(R.lead_pre>=4)])
