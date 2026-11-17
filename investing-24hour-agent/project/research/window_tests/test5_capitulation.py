"""TEST 5: Breitstein 'right side of the V' capitulation, morning-window version. PAPER research only.
Universe: eligible names, top-500 by prior-20d $vol, D close > $20. Setup on D (all known at D close): 3+ down closes in a row
(incl. D), D close < 20d mean - 2 SD (20 closes incl. D), D volume >= 2x prior-20d avg volume.
Entries: (a) D+1 10:00; (b) D+1 10:00 only if 10:00 price > high of the 9:50-9:55 bar AND > D+1 9:30 open; (c) D close (official close
used as proxy for 15:55). Exits: D+1, D+2, D+5 official close. Cost 20 bps round trip. Sample 2020-2026 for (a)/(b); (c) 2016-2026.
Beta: 120d daily beta vs SPY (prior data), terciles across the top-500 universe on D."""
import pandas as pd, numpy as np, sys
sys.path.insert(0, '.'); from wt_lib import *
P = load_panel(); SP = load_spy()['SPY']
P = P.sort_values(['symbol', 'date']); g = P.groupby('symbol')
P['ret'] = g.c.pct_change()
P['down3'] = g.ret.transform(lambda r: (r < 0).astype(int).rolling(3).sum()) == 3
P['m20'] = g.c.transform(lambda c: c.rolling(20).mean()); P['s20'] = g.c.transform(lambda c: c.rolling(20).std())
P['spyr'] = P.date.map(SP.ret)
def beta(x):
    cv = x.ret.rolling(120, min_periods=80).cov(x.spyr); vv = x.spyr.rolling(120, min_periods=80).var()
    return (cv / vv).shift(1)
P['beta'] = g.apply(beta).reset_index(level=0, drop=True)
for k in ['date', 'fo', 'p10', 'h950', 'c']: P['n1_' + k] = g[k].shift(-1)
P['c2'] = g.c.shift(-2); P['c5'] = g.c.shift(-5)
U = P[P.elig & P.top500].copy()
U['bt'] = U.groupby('date').beta.transform(lambda b: pd.qcut(b.rank(method='first'), 3, labels=['low', 'mid', 'high']) if b.notna().sum() > 30 else np.nan)
E = U[U.down3 & (U.c < U.m20 - 2 * U.s20) & (U.v >= 2 * U.vol20) & (U.c > 20)].copy()
E['per'] = period(E.date)
E.to_csv('test5_events.csv', index=False, columns=['symbol', 'date', 'c', 'm20', 's20', 'v', 'vol20', 'beta', 'bt', 'n1_fo', 'n1_p10', 'n1_h950', 'n1_c', 'c2', 'c5'])
COST = 20.0; rows = []
spy_c = SP.c; spy_p10 = SP.p10
def spy_ret(d, entry, k):  # SPY over the same window
    i = SP.index.get_loc(d); ent = SP.c.iloc[i] if entry == 'c' else SP.p10.iloc[i + 1]
    return (SP.c.iloc[i + k] / ent - 1) * 1e4 if i + k < len(SP) else np.nan
for ent in ['(a) D+1 10:00', '(b) D+1 10:00 turn', '(c) D close']:
    x = E.copy()
    if ent.startswith('(a)') or ent.startswith('(b)'):
        x = x[x.second & x.n1_p10.notna()]; x['ep'] = x.n1_p10
        if ent.startswith('(b)'): x = x[(x.n1_p10 > x.n1_h950) & (x.n1_p10 > x.n1_fo)]
        sp_ent = 'p10'
    else:
        x['ep'] = x.c; sp_ent = 'c'
    for ex, col, k in [('D+1 close', 'n1_c', 1), ('D+2 close', 'c2', 2), ('D+5 close', 'c5', 5)]:
        y = x[x[col].notna()].copy(); y['r'] = (y[col] / y.ep - 1) * 1e4 - COST
        y['spy'] = [spy_ret(d, sp_ent, k) for d in y.date]; y['ex'] = y.r - y.spy
        for split, grp in [('all', None), ('beta', 'bt')]:
            for key, z in ([('all', y)] if grp is None else list(y.groupby(grp))):
                for per in ['IS', 'OOS']:
                    w = z[z.per == per]
                    if len(w) < 5: rows.append(dict(entry=ent, exit=ex, split=key, period=per, n=len(w))); continue
                    rows.append(dict(entry=ent, exit=ex, split=key, period=per, n=len(w), days=w.date.nunique(), hit=round((w.r > 0).mean() * 100, 1), mean_net_bps=round(w.r.mean(), 1),
                                     t=round(w.r.mean() / w.r.std() * np.sqrt(len(w)), 2), spy_same_bps=round(w.spy.mean(), 1), excess_bps=round(w.ex.mean(), 1),
                                     excess_t_clustered=round(w.groupby('date').ex.mean().mean() / w.groupby('date').ex.mean().std() * np.sqrt(w.date.nunique()), 2)))
R = pd.DataFrame(rows).reindex(columns=['entry','exit','split','period','n','days','hit','mean_net_bps','t','spy_same_bps','excess_bps','excess_t_clustered']); R.to_csv('test5_results.csv', index=False)
pd.set_option('display.width', 250, 'display.max_rows', 500); print(R.to_string(index=False)); print('events', len(E), E.groupby('per').size().to_dict())
