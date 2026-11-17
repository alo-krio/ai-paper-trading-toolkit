"""Pass 1: first 5-minute bar (9:30-9:35 ET, SIP, split-adj) for the whole market_map universe, every weekday
2015-12-01..2026-11-13 -> cache/first/YYYY-MM-DD.parquet (resumable). One request per day. Data only."""
import pandas as pd, sys, os, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from dl_common import *
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
NY = ZoneInfo('America/New_York'); os.makedirs(CACHE + '/first', exist_ok=True)
t = pd.read_csv(UNIV).ticker.tolist()
def utc(d, hm):
    h, m = map(int, hm.split(':')); return dt.datetime(d.year, d.month, d.day, h, m, tzinfo=NY).astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def day(d):
    f = f'{CACHE}/first/{d}.parquet'
    if os.path.exists(f): return 0
    rows = bars_all(symbols=','.join(t), timeframe='5Min', start=utc(d, '09:30'), end=utc(d, '09:34'), feed='sip', adjustment='split')
    df = pd.DataFrame(rows, columns=['S', 't', 'o', 'h', 'l', 'c', 'v']); df.to_parquet(f, index=False); return len(df)
days = [d for d in pd.bdate_range(sys.argv[1] if len(sys.argv) > 1 else '2015-12-01', '2026-11-13').date][::-1]
n = 0; import time; t0 = time.time()
with ThreadPoolExecutor(8) as ex:
    for i, r in enumerate(ex.map(day, days)):
        n += r
        if i % 50 == 0: print(i, len(days), n, round(time.time() - t0), flush=True)
print('done', n)
