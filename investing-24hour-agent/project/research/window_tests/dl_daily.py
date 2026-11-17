"""Daily split-adjusted SIP bars 2015-10-01..2026-11-14 for market_map universe + SPY,QQQ -> cache/daily.parquet"""
import pandas as pd, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from dl_common import *
from concurrent.futures import ThreadPoolExecutor
t = pd.read_csv(UNIV).ticker.tolist() + ['SPY', 'QQQ']
ch = [t[i:i+50] for i in range(0, len(t), 50)]
def f(c):
    return bars_all(symbols=','.join(c), timeframe='1Day', start='2015-10-01', end='2026-11-14', feed='sip', adjustment='split')
rows = []
with ThreadPoolExecutor(3) as ex:
    for i, r in enumerate(ex.map(f, ch)): rows += r; print(i, len(ch), len(rows), flush=True)
d = pd.DataFrame(rows); d['date'] = d.t.str[:10]
d = d.rename(columns={'S': 'symbol'})[['symbol', 'date', 'o', 'h', 'l', 'c', 'v', 'vw']]
d.to_parquet(CACHE + '/daily.parquet', index=False); print(d.shape)
