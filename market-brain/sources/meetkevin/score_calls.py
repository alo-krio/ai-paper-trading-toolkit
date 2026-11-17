import os,json,csv,urllib.request,datetime as dt
H={'APCA-API-KEY-ID':os.environ['APCA_DATA_KEY_ID'],'APCA-API-SECRET-KEY':os.environ['APCA_DATA_SECRET_KEY']}
rows=list(csv.DictReader(open('calls.csv')))
END=(dt.date.today()-dt.timedelta(days=1)).isoformat()
rows=[r for r in rows if r['ticker'] not in ('BTC','SPACEX','ANTHROPIC')]
T=sorted({r['ticker'] for r in rows}|{'QQQ','SPY'})
u=f"https://data.alpaca.markets/v2/stocks/bars?symbols={','.join(T)}&timeframe=1Day&start=2026-09-25&end={END}&feed=sip&adjustment=all&limit=10000"
B={};tok=None
while True:
  r=json.load(urllib.request.urlopen(urllib.request.Request(u+(f'&page_token={tok}' if tok else ''),headers=H)))
  for k,v in r['bars'].items(): B.setdefault(k,[]).extend(v)
  tok=r.get('next_page_token')
  if not tok: break
P={k:{b['t'][:10]:b for b in v} for k,v in B.items()}
days=sorted(P['SPY'])
out=[]
for r in rows:
  t=r['ticker']
  if t not in P: print('no data',t); continue
  nxt=[d for d in days if d>r['date']]
  if not nxt: continue
  d0=nxt[0]; e=P[t][d0]['o']; q0=P['QQQ'][d0]['o']
  def ret(n):
    if len(nxt)<=n: return None
    d=nxt[n]; return (P[t][d]['c']/e-1)*100, (P[t][d]['c']/e-1-(P['QQQ'][d]['c']/q0-1))*100
  last=days[-1]; tot=(P[t][last]['c']/e-1)*100; ex=tot-(P['QQQ'][last]['c']/q0-1)*100
  r5=ret(4)
  mn=min(P[t][d]['l'] for d in nxt)/e*100-100
  out.append(dict(r,entry_day=d0,entry=round(e,2),ret5=None if not r5 else round(r5[0],2),xs5=None if not r5 else round(r5[1],2),ret_now=round(tot,2),xs_now=round(ex,2),max_dd=round(mn,2)))
w=csv.DictWriter(open('calls_scored.csv','w'),fieldnames=list(out[0].keys()));w.writeheader();w.writerows(out)
for o in out: print(o['date'],o['ticker'],o['kind'],o['entry'],o['ret5'],o['xs5'],o['ret_now'],o['xs_now'],o['max_dd'])
import statistics as s
x5=[o['xs5'] for o in out if o['xs5'] is not None]; xn=[o['xs_now'] for o in out]
print('n',len(out),'5d excess vs QQQ mean',round(s.mean(x5),2),'hit',round(sum(v>0 for v in x5)/len(x5),2),'| to date mean',round(s.mean(xn),2),'hit',round(sum(v>0 for v in xn)/len(xn),2))
print('5d raw mean',round(s.mean([o['ret5'] for o in out if o['ret5'] is not None]),2))
