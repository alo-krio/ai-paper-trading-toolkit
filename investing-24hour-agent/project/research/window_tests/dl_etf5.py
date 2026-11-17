"""SPY/QQQ 5-min SIP bars 2015-11-01..2026-11-14 (regular hours kept) -> cache/etf5.parquet"""
import pandas as pd, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from dl_common import *
rows = []
for y in range(2015, 2027):
    rows += bars_all(symbols='SPY,QQQ', timeframe='5Min', start=f'{y}-01-01' if y > 2015 else '2015-11-01', end=f'{y+1}-01-01' if y < 2026 else '2026-11-14', feed='sip', adjustment='split')
    print(y, len(rows), flush=True)
d = pd.DataFrame(rows).rename(columns={'S': 'symbol'})
d['ts'] = pd.to_datetime(d.t, utc=True).dt.tz_convert('America/New_York')
d = d[(d.ts.dt.time >= pd.Timestamp('09:30').time()) & (d.ts.dt.time < pd.Timestamp('16:00').time())]
d['date'] = d.ts.dt.strftime('%Y-%m-%d'); d['hm'] = d.ts.dt.strftime('%H:%M')
d[['symbol', 'date', 'hm', 'o', 'h', 'l', 'c', 'v']].to_parquet(CACHE + '/etf5.parquet', index=False); print(d.shape)
