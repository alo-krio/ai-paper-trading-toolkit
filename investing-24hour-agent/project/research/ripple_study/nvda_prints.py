import os,json,urllib.request,datetime as dt
H={'APCA-API-KEY-ID':os.environ['APCA_DATA_KEY_ID'],'APCA-API-SECRET-KEY':os.environ['APCA_DATA_SECRET_KEY']}
T=['NVDA','SPY','SMH','TSM','MU','AVGO','AMD','VRT','SMCI','DELL','ANET','CRWV','ORCL','MSFT','META','CEG','ETN']
def bars(s):
  u=f'https://data.alpaca.markets/v2/stocks/bars?symbols={s}&timeframe=1Day&start=2024-11-01&end=2026-11-16&feed=sip&adjustment=all&limit=10000'
  out={};tok=None
  while True:
    r=json.load(urllib.request.urlopen(urllib.request.Request(u+(f'&page_token={tok}' if tok else ''),headers=H)))
    for k,v in r['bars'].items(): out.setdefault(k,[]).extend(v)
    tok=r.get('next_page_token')
    if not tok: return out
B=bars(','.join(T))
C={k:{b['t'][:10]:(b['o'],b['c']) for b in v} for k,v in B.items()}
days=sorted(C['SPY'])
prints=['2024-11-20','2025-02-26','2025-05-28','2025-08-27','2025-11-19','2026-02-25','2026-05-20','2026-08-26']
rows=[]
for p in prints:
  i=days.index(p); d0=days[i]; d1=days[i+1]; d2=days[i+2]
  def r(t,a,b): 
    try: return C[t][b][1]/C[t][a][1]-1
    except KeyError: return None
  spy1=r('SPY',d0,d1); spy2=r('SPY',d0,d2)
  row={'print':p}
  for t in T:
    if t=='SPY':continue
    x1=r(t,d0,d1); x2=r(t,d0,d2)
    row[t]=(None if x1 is None else round((x1-spy1)*100,1), None if x2 is None else round((x2-spy2)*100,1))
  rows.append(row)
json.dump(rows,open('/tmp/nvda_rip.json','w'))
for row in rows: print(row['print'],' '.join(f"{t}:{row[t][0]}/{row[t][1]}" for t in T if t!='SPY'))
