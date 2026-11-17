"""For catalysts with news (Apr-Nov 2026): SIP 30-min bars for the leader and its links on the catalyst day.
Question for our windows: does the leader's 9:30-10:00 behaviour (holding/extending vs fading its gap) predict the linked
names' 10:00 -> 15:30 move (what a 10:00 buy / 3:30 sell captures), and the 10:00 -> next 3 days?"""
import sys, json, time, numpy as np, pandas as pd, datetime as dt
P='/home/user/workspace/investing-24hour-agent/project'; sys.path.insert(0,P+'/scripts'); import alpaca_data as A
E=pd.read_csv(P+'/research/ripple_study/events_classified.csv'); E['date']=E.date.astype(str)
def et(d,hh,mm):  # ET -> UTC (EDT before Nov 2, 2026; EST after)
    off=4 if dt.date.fromisoformat(d) < dt.date(2026,11,1) and dt.date.fromisoformat(d) >= dt.date(2026,3,8) else 5
    return (dt.datetime.fromisoformat(d)+dt.timedelta(hours=hh+off,minutes=mm)).strftime('%Y-%m-%dT%H:%M:%SZ')
out=[]
for i,((L,d),g) in enumerate(E.groupby(['leader','date'])):
    syms=[L,'SPY']+list(g.t.unique())[:20]
    try: b=A.get('/v2/stocks/bars',symbols=','.join(syms),timeframe='30Min',start=et(d,9,30),end=et(d,16,0),feed='sip',limit=10000).get('bars',{})
    except Exception as e: time.sleep(1); continue
    def px(s,hh,mm):
        t=et(d,hh,mm); v=[x for x in b.get(s,[]) if x['t']==t]; return v[0] if v else None
    def p10(s): x=px(s,9,30); return x['c'] if x else None   # close of 9:30-10:00 bar = ~10:00 price
    def o(s): x=px(s,9,30); return x['o'] if x else None
    def p1530(s): x=px(s,15,0); return x['c'] if x else None  # close of 15:00-15:30 bar
    if not all([o(L),p10(L),o('SPY'),p10('SPY'),p1530('SPY')]): continue
    spy_930=p10('SPY')/o('SPY')-1; spy_day=p1530('SPY')/p10('SPY')-1
    lead_930=(p10(L)/o(L)-1)-spy_930; lead_rest=(p1530(L)/p10(L)-1)-spy_day if p1530(L) else np.nan
    for r in g.itertuples():
        if not (o(r.t) and p10(r.t) and p1530(r.t)): continue
        sg=np.sign(r.lead_x0) or 1
        out.append(dict(leader=L,date=d,t=r.t,scope=r.scope,trig=r.trig2,follow=r.follow,sg=sg,
            lead_930=100*sg*lead_930, lead_rest=100*sg*lead_rest, link_930=100*sg*((p10(r.t)/o(r.t)-1)-spy_930),
            link_rest=100*sg*((p1530(r.t)/p10(r.t)-1)-spy_day), n3=r.n3))
    if i%100==0: print(i,flush=True)
R=pd.DataFrame(out); R.to_csv(P+'/research/ripple_study/intraday_path.csv',index=False)
def st(n,s):
    byd=s.groupby(['leader','date']).link_rest.mean(); t=byd.mean()/(byd.std()/np.sqrt(len(byd))) if len(byd)>2 else 0
    print(f"{n:52s} n={len(s):5d} ev={len(byd):3d} | leader 9:30-10 {s.lead_930.mean():+.2f} rest {s.lead_rest.mean():+.2f} | linked 9:30-10 {s.link_930.mean():+.2f} 10:00->15:30 {s.link_rest.mean():+.2f} (t {t:+.1f}) next3 {s.n3.mean():+.2f}")
print('signed + = same direction as the leader\'s day move; excess vs SPY')
st('ALL',R)
st('leader HOLDS/extends gap in first 30 min',R[R.lead_930>0]); st('leader FADES gap in first 30 min',R[R.lead_930<0])
for sc in ('company_specific','mixed','industry_signal'):
    s=R[R.scope==sc]; st(f'{sc}: leader holds',s[s.lead_930>0]); st(f'{sc}: leader fades',s[s.lead_930<0])
st('linked lagging at 10:00 (link_930 < 0.3*lead_930... approx <0.3) & leader holds',R[(R.lead_930>0)&(R.link_930<0.3)])
st('linked already ran 9:30-10 (>1) ',R[R.link_930>1])
