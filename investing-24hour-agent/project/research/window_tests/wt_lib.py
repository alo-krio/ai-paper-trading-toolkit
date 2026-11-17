"""Shared loaders/stats for window_tests analyses. PAPER research only."""
import pandas as pd, numpy as np, glob, os
H = os.path.dirname(os.path.abspath(__file__)); C = H + '/cache'
IS_END = '2022-12-31'; OOS_END = '2026-11-13'
def period(d): return np.where(d <= IS_END, 'IS', 'OOS')
def load_panel():
    P = pd.read_parquet(C + '/panel.parquet')
    fs = glob.glob(C + '/second/*.parquet')
    S = pd.concat([pd.read_parquet(f).assign(date=os.path.basename(f)[:10]) for f in fs])
    S = S.astype({k: float for k in ['o', 'h', 'l', 'c', 'v']}); S['hm'] = pd.to_datetime(S.t, utc=True).dt.tz_convert('America/New_York').dt.strftime('%H:%M')
    W = S.pivot_table(index=['S', 'date'], columns='hm', values='c')
    Hh = S[S.hm == '09:50'].set_index(['S', 'date']).h.rename('h950')
    W = pd.DataFrame({'p10': W.get('09:55'), 'p1015': W.get('10:10'), 'p1530': W.get('15:25')}).join(Hh)
    W.index.names = ['symbol', 'date']; W = W.reset_index()
    P = P.merge(W, on=['symbol', 'date'], how='left').sort_values(['symbol', 'date'])
    g = P.groupby('symbol')
    P['n10'] = g.p10.shift(-1)
    P['nd'] = g.date.shift(-1)
    P['second'] = P.date >= min(os.path.basename(f)[:10] for f in fs)
    return P
def load_spy():
    E = pd.read_parquet(C + '/etf5.parquet'); D = pd.read_parquet(C + '/daily.parquet')
    out = {}
    for sym in ['SPY', 'QQQ']:
        e = E[E.symbol == sym].pivot_table(index='date', columns='hm', values='c')
        o = E[(E.symbol == sym) & (E.hm == '09:30')].set_index('date').o
        d = D[D.symbol == sym].set_index('date').sort_index()
        f = pd.DataFrame(index=d.index); f['o'] = o; f['c'] = d.c; f['pc'] = d.c.shift(1)
        f['p935'] = e['09:30']; f['p10'] = e['09:55']; f['p1015'] = e['10:10']; f['p1500'] = e['14:55']; f['p1530'] = e['15:25']
        f['n10'] = f.p10.shift(-1); f['nc'] = f.c.shift(-1); f['nc2'] = f.c.shift(-2); f['nc5'] = f.c.shift(-5)
        tr = np.maximum(d.h, f.pc) - np.minimum(d.l, f.pc); f['atrp'] = (tr / f.pc).rolling(14).mean().shift(1)
        f['ret'] = d.c.pct_change()
        out[sym] = f
    return out
def summ(daily, traded, label):
    """daily: net bps series (0 when flat). returns dict"""
    t = daily[traded]
    if len(t) < 5: return dict(label=label, days=int(len(t)))
    return dict(label=label, days=int(len(t)), hit=round((t > 0).mean() * 100, 1), mean_bps=round(t.mean(), 2),
                t=round(t.mean() / t.std() * np.sqrt(len(t)), 2), sharpe=round(daily.mean() / daily.std() * np.sqrt(252), 2) if daily.std() > 0 else np.nan)
