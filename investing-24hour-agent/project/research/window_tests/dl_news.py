"""Alpaca (Benzinga) news flags. PAPER research only.
 (1) Test 2 in-play set A names, 2024-01-02..2026-11-13: any headline tagged with the symbol from 16:00 ET prior session to 9:35 ET.
 (2) Test 5 capitulation events (all years with news coverage, 2019+): any headline tagged with the symbol from 16:00 ET D-1 to 16:00 ET D.
One batched request per day (plus pages). -> cache/news_inplay.csv, cache/news_capit.csv"""
import pandas as pd, numpy as np, sys, os, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from dl_common import *
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
NY = ZoneInfo('America/New_York')
P = pd.read_parquet(CACHE + '/panel.parquet', columns=['symbol', 'date', 'elig', 'rvol', 'dir'])
days = sorted(P.date.unique()); prev = {days[i]: days[i - 1] for i in range(1, len(days))}
P = P[P.elig & (P.dir != 0)]; P['rr'] = P.groupby('date').rvol.rank(ascending=False)
A = P[(P.rr <= 20) & (P.rvol > 1) & (P.date >= '2024-01-02')]
def utc(d, hm):
    d = dt.date.fromisoformat(d); h, m = map(int, hm.split(':')); return dt.datetime(d.year, d.month, d.day, h, m, tzinfo=NY).astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def news(syms, s, e):
    out = []; tok = None
    while True:
        q = dict(symbols=','.join(syms), start=s, end=e, limit=50, sort='asc')
        if tok: q['page_token'] = tok
        j = get('/v1beta1/news', **q); out += j.get('news', []); tok = j.get('next_page_token')
        if not tok: return out
def flag(task):
    d, syms, s_hm, e_hm = task
    try: n = news(syms, utc(prev[d], '16:00'), utc(d, e_hm))
    except Exception as ex:
        return [dict(symbol=s, date=d, n_news=np.nan, first_headline='ERR ' + str(ex)[:60]) for s in syms]
    cnt = {s: 0 for s in syms}; hl = {s: '' for s in syms}
    for a in n:
        for s in a.get('symbols', []):
            if s in cnt:
                cnt[s] += 1
                if not hl[s]: hl[s] = a['headline'][:160]
    return [dict(symbol=s, date=d, n_news=cnt[s], first_headline=hl[s]) for s in syms]
def run(groups, e_hm, outf):
    tasks = [(d, sorted(x.symbol), '16:00', e_hm) for d, x in groups]
    rows = []
    with ThreadPoolExecutor(6) as ex:
        for i, r in enumerate(ex.map(flag, tasks)):
            rows += r
            if i % 100 == 0: print(outf, i, len(tasks), flush=True)
    pd.DataFrame(rows).to_csv(outf, index=False)
if 'capit' in sys.argv:
    E = pd.read_csv(os.path.dirname(CACHE) + '/test5_events.csv'); E = E[E.date >= '2020-01-02']
    run(E.groupby('date'), '16:00', CACHE + '/news_capit.csv')
else:
    run(A.groupby('date'), '09:35', CACHE + '/news_inplay.csv')
