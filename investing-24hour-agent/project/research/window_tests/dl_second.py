"""Pass 2 (per day, newest first, 2019-01-02..2026-11-13): 5-min bars 9:50, 9:55 (9:50 high for Test 5; 9:55 close = 10:00 price), 10:10 (close = 10:15 price) and the
15:25 bar (close = 15:30 price) for: top-500 eligible names by prior-20d $vol  U  in-play candidates (top-40 RVOL, or RVOL>=2 & |gap|>=2%)
of that day U the previous day's candidates (for next-day 10:00 exits). Candidates use only prior days + first 5 min.
-> cache/second/YYYY-MM-DD.parquet. Data only."""
import pandas as pd, sys, os, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from dl_common import *
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
NY = ZoneInfo('America/New_York'); os.makedirs(CACHE + '/second', exist_ok=True)
P = pd.read_parquet(CACHE + '/panel.parquet', columns=['symbol', 'date', 'elig', 'top500', 'rvol', 'gap'])
P = P[P.elig]
P['rr'] = P.groupby('date').rvol.rank(ascending=False)
P['cand'] = (P.rr <= 40) | ((P.rvol >= 2) & (P.gap.abs() >= 0.02))
days = sorted(P.date.unique()); days = [d for d in days if d >= sys.argv[1]] if len(sys.argv) > 1 else [d for d in days if d >= '2019-01-02']
S = {d: set(x.symbol[x.top500 | x.cand]) for d, x in P.groupby('date')}
CA = {d: set(x.symbol[x.cand]) for d, x in P.groupby('date')}
alld = sorted(S); prev = {alld[i]: alld[i - 1] for i in range(1, len(alld))}
def utc(d, hm):
    d = dt.date.fromisoformat(d); h, m = map(int, hm.split(':')); return dt.datetime(d.year, d.month, d.day, h, m, tzinfo=NY).astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def day(d):
    f = f'{CACHE}/second/{d}.parquet'
    if os.path.exists(f): return 0
    syms = sorted(S[d] | CA.get(prev.get(d), set()))
    rows = []
    try:
      for a, b in [('09:50', '09:59'), ('10:10', '10:14'), ('15:25', '15:29')]:  # 3 contiguous windows (~1 page each)
        rows += bars_all(symbols=','.join(syms), timeframe='5Min', start=utc(d, a), end=utc(d, b), feed='sip', adjustment='split')
    except Exception as ex:
        print('FAIL', d, ex, flush=True); return 0
    df = pd.DataFrame(rows, columns=['S', 't', 'o', 'h', 'l', 'c', 'v']); df.to_parquet(f, index=False); return len(df)
n = 0; import time; t0 = time.time()
with ThreadPoolExecutor(8) as ex:
    for i, r in enumerate(ex.map(day, days[::-1])):
        n += r
        if i % 50 == 0: print(i, len(days), n, round(time.time() - t0), flush=True)
print('done', n)
