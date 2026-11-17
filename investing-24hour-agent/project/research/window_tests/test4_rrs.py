"""TEST 4: Real Relative Strength (r/RealDayTrading). PAPER research only.
RRS_T = (r_stock - r_SPY * ATR_stock/ATR_SPY) / ATR_stock with r measured from the 9:30 open to time T.
ATR: prior-14-day DAILY ATR as % of price (cheaper than 50h of 5-min bars). Scaling daily ATR to an intraday horizon by sqrt(time)
multiplies both ATRs by the same factor, so the cross-sectional ranking is identical; we state RRS in daily-ATR units.
Universe: eligible names ranked top-500 by prior-20d $vol (dynamic, no look-ahead). Sample 2020-01-02..2026-11-13 (IS 2020-22).
Cost 10 bps/side (20 round trip); SPY comparison over the same window, no cost."""
import pandas as pd, numpy as np, sys
sys.path.insert(0, '.'); from wt_lib import *
P = load_panel(); SP = load_spy()['SPY']
P = P[P.elig & P.second].copy(); P['per'] = period(P.date)
for k in ['o', 'p10', 'p1015', 'p1530', 'c', 'n10', 'nc', 'atrp']: P['spy_' + k] = P.date.map(SP[k] if k != 'nc' else SP['nc'])
def rrs(pt, spt): return ((P[pt] / P.fo - 1) - (P[spt] / P.spy_o - 1) * P.atrp / P.spy_atrp) / P.atrp
P['rrs10'] = rrs('p10', 'spy_p10'); P['rrs1015'] = rrs('p1015', 'spy_p1015'); P['rrs1530'] = rrs('p1530', 'spy_p1530')
U = P[P.top500].copy()
COST = 20.0; rows = []
alld = pd.Index(sorted(P.date.unique()))
def run(name, sig, entry, exit, sp_entry, sp_exit, daymask=None):
    x = U[U[sig].notna() & U[entry].notna() & U[exit].notna()].copy()
    if daymask is not None: x = x[x.date.isin(daymask)]
    x['rk'] = x.groupby('date')[sig].rank(ascending=False); x['rb'] = x.groupby('date')[sig].rank()
    x['r'] = (x[exit] / x[entry] - 1) * 1e4 - COST
    sp = (SP[sp_exit] / SP[sp_entry] - 1) * 1e4
    for leg, m in [('top10', x.rk <= 10), ('bottom10', x.rb <= 10), ('all500 (avg)', x.rk > 0)]:
        d = x[m].groupby('date').r.mean()
        for per in ['IS', 'OOS']:
            days = alld[period(alld) == per] if daymask is None else pd.Index(sorted(set(daymask))).intersection(alld[period(alld) == per])
            dd = d.reindex(days); tr = dd.notna()
            s = summ(dd.fillna(0), tr, '')
            rows.append(dict(test=name, leg=leg, period=per, **{k: v for k, v in s.items() if k != 'label'},
                             spy_same_window_bps=round(sp.reindex(days)[tr].mean(), 2), excess_vs_spy_bps=round((dd[tr] - sp.reindex(days)[tr]).mean(), 2),
                             excess_t=round((dd[tr] - sp.reindex(days)[tr]).mean() / (dd[tr] - sp.reindex(days)[tr]).std() * np.sqrt(tr.sum()), 2)))
run('4a RRS 9:30-10:00, buy 10:00 -> close', 'rrs10', 'p10', 'c', 'p10', 'c')
run('4a RRS 9:30-10:00, buy 10:00 -> next close', 'rrs10', 'p10', 'nc', 'p10', 'nc')
run('4a RRS 9:30-10:15, buy 10:15 -> close', 'rrs1015', 'p1015', 'c', 'p1015', 'c')
run('4a RRS 9:30-10:15, buy 10:15 -> next close', 'rrs1015', 'p1015', 'nc', 'p1015', 'nc')
run('4b RRS 9:30-15:30, buy 15:30 -> next 10:00', 'rrs1530', 'p1530', 'n10', 'p1530', 'n10')
run('4b RRS 9:30-15:30, buy 15:30 -> next close', 'rrs1530', 'p1530', 'nc', 'p1530', 'nc')
down = SP.index[SP.p1530 < SP.o]
run('4c SPY down 9:30-15:30: buy 15:30 -> next 10:00', 'rrs1530', 'p1530', 'n10', 'p1530', 'n10', down)
run('4c SPY down 9:30-15:30: buy 15:30 -> next close', 'rrs1530', 'p1530', 'nc', 'p1530', 'nc', down)
down50 = SP.index[(SP.p1530 / SP.o - 1) < -0.005]
run('4c SPY down >0.5% 9:30-15:30: buy 15:30 -> next 10:00', 'rrs1530', 'p1530', 'n10', 'p1530', 'n10', down50)
run('4c SPY down >0.5% 9:30-15:30: buy 15:30 -> next close', 'rrs1530', 'p1530', 'nc', 'p1530', 'nc', down50)
R = pd.DataFrame(rows).reindex(columns=['test','leg','period','days','hit','mean_bps','t','sharpe','spy_same_window_bps','excess_vs_spy_bps','excess_t']); R.to_csv('test4_results.csv', index=False)
pd.set_option('display.width', 250, 'display.max_rows', 500); print(R.to_string(index=False))
# 4d: in-play (Test 2 set A) x RRS sign at 10:00; trade in first-candle direction at 10:00 -> close
A = pd.read_parquet('cache/inplay_A.parquet')[['symbol', 'date']]
X = A.merge(P, on=['symbol', 'date']); X = X[X.p10.notna() & X.rrs10.notna()]
X['r'] = X.dir * (X.c / X.p10 - 1) * 1e4 - COST; X['rl'] = (X.c / X.p10 - 1) * 1e4 - COST
o = []
for (per, dr, rs), y in X.groupby(['per', X.dir.map({1: 'long-dir', -1: 'short-dir'}), np.where(X.rrs10 > 0, 'RRS>0', 'RRS<=0')]):
    o.append(dict(period=per, first_candle=dr, rrs=rs, n=len(y), mean_net_bps_in_dir=round(y.r.mean(), 2), t=round(y.r.mean() / y.r.std() * np.sqrt(len(y)), 2), hit=round((y.r > 0).mean() * 100, 1), long_only_net_bps=round(y.rl.mean(), 2)))
O = pd.DataFrame(o); O.to_csv('test4d_inplay_x_rrs.csv', index=False); print(O.to_string(index=False))
