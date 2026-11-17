"""TEST 1: market intraday momentum (Gao-Han-Li-Zhou 2018) on SPY/QQQ in our CLOSE window. PAPER research only.
Prices: prev official close (daily bar), 10:00 = close of 9:55 5m bar, 15:00/15:30 = closes of 14:55/15:25 bars,
close = official daily close, next-day 10:00 = next day's 9:55 bar close. Cost 5 bps/side (10 bps round trip)."""
import pandas as pd, numpy as np, os
H = os.path.dirname(os.path.abspath(__file__)); C = H + '/cache'
E = pd.read_parquet(C + '/etf5.parquet'); D = pd.read_parquet(C + '/daily.parquet')
COST = 10.0
def stats(x, traded):
    """x: daily net-return series in bps (0 on flat days); traded: bool mask"""
    t = x[traded]
    if len(t) < 5: return dict(n=len(t))
    return dict(n=int(len(t)), hit=round((t > 0).mean() * 100, 1), mean_bps=round(t.mean(), 2), t=round(t.mean() / t.std() * np.sqrt(len(t)), 2),
                sharpe=round(x.mean() / x.std() * np.sqrt(252), 2) if x.std() > 0 else np.nan, tot_pct=round(t.sum() / 100, 1))
rows = []
for sym in ['SPY', 'QQQ']:
    e = E[E.symbol == sym].pivot_table(index='date', columns='hm', values='c')
    d = D[D.symbol == sym].set_index('date').sort_index()
    f = pd.DataFrame(index=d.index); f['pc'] = d.c.shift(1); f['c'] = d.c
    for k, hm in [('p10', '09:55'), ('p1500', '14:55'), ('p1530', '15:25')]: f[k] = e[hm].reindex(f.index)
    f['n10'] = f.p10.shift(-1)
    f['r1'] = f.p10 / f.pc - 1; f['r12'] = f.p1530 / f.p1500 - 1
    f['last'] = (f.c / f.p1530 - 1) * 1e4; f['ovn'] = (f.n10 / f.p1530 - 1) * 1e4
    rv = np.log(d.c).diff().rolling(20).std().shift(1)  # prior-20d realized vol, known before today
    f['hv'] = rv > rv.rolling(252, min_periods=120).quantile(2 / 3)
    f = f.dropna(subset=['pc', 'p10', 'p1500', 'p1530', 'c'])
    f = f[(f.index >= '2016-01-01') & (f.index <= '2026-11-13')]
    f['per'] = np.where(f.index <= '2022-12-31', 'IS 2016-22', 'OOS 2023-26')
    for sig in ['r1', 'r1+r12']:
        s = f.r1 if sig == 'r1' else f.r1 + f.r12
        thr = s.abs().rolling(252, min_periods=120).quantile(0.7).shift(1)  # trailing-1y 70th pct, no look-ahead
        for cond in ['all', 'top30%|sig|', 'highvol']:
            m = pd.Series(True, index=f.index) if cond == 'all' else ((s.abs() > thr) if cond.startswith('top') else f.hv)
            for var, ret, longonly in [('LS 15:30->close', 'last', False), ('Long-only 15:30->close', 'last', True), ('LS 15:30->next10:00', 'ovn', False), ('Long-only 15:30->next10:00', 'ovn', True)]:
                pos = np.sign(s).where(m, 0)
                if longonly: pos = pos.clip(lower=0)
                gross = pos * f[ret]; net = gross - COST * (pos != 0)
                for per in ['IS 2016-22', 'OOS 2023-26']:
                    k = (f.per == per) & f[ret].notna()
                    st = stats(net[k].fillna(0), (pos[k] != 0)); st['gross_bps'] = round(gross[k][pos[k] != 0].mean(), 2)
                    rows.append(dict(sym=sym, signal=sig, cond=cond, trade=var, period=per, **st))
    # baseline: always long the last 30 min, and predictive regression slope
    for per in ['IS 2016-22', 'OOS 2023-26']:
        k = f.per == per; x = f.r1[k] * 1e4; y = f['last'][k]
        b = np.polyfit(x, y, 1)[0]; corr = np.corrcoef(x, y)[0, 1]
        rows.append(dict(sym=sym, signal='r1', cond='regression', trade=f'slope={b:.4f} corr={corr:.3f} R2={corr**2*100:.2f}%', period=per, n=int(k.sum())))
        net = y - COST; rows.append(dict(sym=sym, signal='none', cond='all', trade='Always long 15:30->close', period=per, **stats(net, pd.Series(True, index=net.index)), gross_bps=round(y.mean(), 2)))
R = pd.DataFrame(rows); R.to_csv(H + '/test1_results.csv', index=False)
pd.set_option('display.width', 250, 'display.max_rows', 500)
print(R.to_string(index=False))
