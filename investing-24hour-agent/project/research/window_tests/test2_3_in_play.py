"""TEST 2 (stocks-in-play ORB adapted to our morning window) and TEST 3 (does waiting help?). PAPER research only.
In play: eligible (prev close > $5, prior-20d avg $vol > $20M), RVOL = first-5-min vol / mean first-5-min vol of prior 14 sessions.
 set A = top-20 RVOL per day (RVOL > 1), set B = RVOL >= 2 and |gap| >= 2%. Direction = sign(first 5-min close - open), dojis dropped.
Entries 9:35 (first-bar close), 10:00 (9:55 bar close), 10:00-confirmed (10:00 price beyond 9:35 price in trade direction), 10:15.
Exits: official close; next-day 10:00. Equal weight per day; cost 10 bps/side; flat days = 0."""
import pandas as pd, numpy as np, sys
sys.path.insert(0, '.'); from wt_lib import *
P = load_panel(); SP = load_spy()['SPY']
P = P[P.elig & (P.dir != 0)].copy()
P['per'] = period(P.date)
P['rr'] = P.groupby('date').rvol.rank(ascending=False)
A = P[(P.rr <= 20) & (P.rvol > 1)].copy(); B = P[(P.rvol >= 2) & (P.gap.abs() >= 0.02)].copy()
COST = 20.0
ENTRY = {'9:35': 'fc', '10:00': 'p10', '10:00conf': 'p10', '10:15': 'p1015'}
SPYE = {'fc': 'p935', 'p10': 'p10', 'p1015': 'p1015'}
alldays = pd.Index(sorted(P.date.unique()))
rows = []
def port(S, entry, exit, side, start):
    e = ENTRY[entry]; x = S[S.date >= start].copy()
    if exit == 'n10': x = x[x.second & x.n10.notna()]
    x = x[x[e].notna() & x[exit].notna()]
    if entry == '10:00conf': x = x[x.dir * (x.p10 - x.fc) > 0]
    if side == 'long': x = x[x.dir > 0]
    x['r'] = x.dir * (x[exit] / x[e] - 1) * 1e4 - COST
    d = x.groupby('date').r.mean()
    sp = (SP['c' if exit == 'c' else 'n10'] / SP[SPYE[e]] - 1) * 1e4
    return d, sp, x
for setname, S in [('A top20 RVOL', A), ('B RVOL>=2 & |gap|>=2%', B)]:
    for entry in ENTRY:
        for exit in ['c', 'n10']:
            for side in ['long-short', 'long']:
                for start in ['2016-01-01', '2020-01-02']:
                    if (entry != '9:35' or exit == 'n10') and start == '2016-01-01': continue
                    d, sp, x = port(S, entry, exit, side, start)
                    for per in ['IS', 'OOS']:
                        days = alldays[(alldays >= start) & (period(alldays) == per)]
                        if exit == 'n10' or entry != '9:35': days = days[days >= '2020-01-02']
                        dd = d.reindex(days).fillna(0); tr = d.reindex(days).notna()
                        s = summ(dd, tr, '')
                        ex = (d.reindex(days)[tr] - sp.reindex(days)[tr]).mean() if side == 'long' else np.nan
                        rows.append(dict(set=setname, entry=entry, exit='close' if exit == 'c' else 'next 10:00', side=side, sample_start=start[:4], period=per,
                                         names_per_day=round(x[x.date.isin(days)].groupby('date').size().mean(), 1), **{k: v for k, v in s.items() if k != 'label'},
                                         spy_same_window_bps=round(sp.reindex(days)[tr].mean(), 2), excess_vs_spy_bps=round(ex, 2)))
R = pd.DataFrame(rows); R.to_csv('test2_results.csv', index=False)
pd.set_option('display.width', 250, 'display.max_rows', 500); print(R.to_string(index=False))
# RVOL deciles (all eligible stock-days, cross-sectional decile per day), signed by first-candle direction, gross & net
P['dec'] = P.groupby('date').rvol.transform(lambda v: pd.qcut(v.rank(method='first'), 10, labels=False) + 1)
dr = []
for (per, dec), x in P.groupby(['per', 'dec']):
    r935 = x.dir * (x.c / x.fc - 1) * 1e4; y = x[x.second & x.p10.notna()]; r10 = y.dir * (y.c / y.p10 - 1) * 1e4
    dr.append(dict(period=per, rvol_decile=dec, n=len(x), med_rvol=round(x.rvol.median(), 2), signed_935_close_gross=round(r935.mean(), 2), hit_935=round((r935 > COST).mean() * 100, 1),
                   n_2020=len(y), signed_1000_close_gross=round(r10.mean(), 2), net_1000_close=round(r10.mean() - COST, 2)))
DR = pd.DataFrame(dr); DR.to_csv('test2_rvol_deciles.csv', index=False); print(DR.to_string(index=False))
# top-percentile buckets within decile 10
P['rpct'] = P.groupby('date').rvol.rank(pct=True)
tp = []
for per in ['IS', 'OOS']:
    for lo, hi in [(0.9, 0.95), (0.95, 0.99), (0.99, 1.01)]:
        x = P[(P.per == per) & (P.rpct > lo) & (P.rpct <= hi)]; y = x[x.second & x.p10.notna()]
        tp.append(dict(period=per, bucket=f'{lo}-{min(hi,1)}', n=len(x), s935=round((x.dir * (x.c / x.fc - 1) * 1e4).mean(), 2), s1000=round((y.dir * (y.c / y.p10 - 1) * 1e4).mean(), 2)))
print(pd.DataFrame(tp).to_string(index=False)); pd.DataFrame(tp).to_csv('test2_rvol_top_buckets.csv', index=False)
A.to_parquet('cache/inplay_A.parquet', index=False)
