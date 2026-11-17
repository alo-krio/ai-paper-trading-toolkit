"""Build the daily stock panel (no look-ahead): eligibility, RVOL, gap, first-candle direction, ATR, top-500 flag.
Inputs cache/daily.parquet + cache/first/*.parquet. Output cache/panel.parquet. PAPER research only."""
import pandas as pd, numpy as np, glob, os
H = os.path.dirname(os.path.abspath(__file__)); C = H + '/cache'
D = pd.read_parquet(C + '/daily.parquet').sort_values(['symbol', 'date'])
F = pd.concat([pd.read_parquet(f).assign(date=os.path.basename(f)[:10]) for f in glob.glob(C + '/first/*.parquet')])
F = F.astype({k: float for k in ['o', 'h', 'l', 'c', 'v']}); F = F.rename(columns={'S': 'symbol', 'o': 'fo', 'c': 'fc', 'v': 'fv', 'h': 'fh', 'l': 'fl'})[['symbol', 'date', 'fo', 'fh', 'fl', 'fc', 'fv']]
P = D.merge(F, on=['symbol', 'date'], how='left')
g = P.groupby('symbol')
P['pc'] = g.c.shift(1)
P['dv20'] = g.apply(lambda x: (x.c * x.v).rolling(20, min_periods=15).mean().shift(1)).reset_index(level=0, drop=True)
P['vol20'] = g.v.transform(lambda x: x.rolling(20, min_periods=15).mean().shift(1))
tr = np.maximum(P.h, P.pc) - np.minimum(P.l, P.pc)
P['atrp'] = (tr / P.pc).groupby(P.symbol).transform(lambda x: x.rolling(14, min_periods=10).mean().shift(1))  # prior-14d ATR as % of price
# RVOL: first-5-min volume vs mean over prior 14 sessions that had a first bar
P['fv14'] = g.fv.transform(lambda x: x.rolling(14, min_periods=10).mean().shift(1))
P['rvol'] = P.fv / P.fv14
P['gap'] = P.fo / P.pc - 1
P['dir'] = np.sign(P.fc - P.fo)
P['nc'] = g.c.shift(-1)  # next-day official close (exit only)
P['elig'] = (P.pc > 5) & (P.dv20 > 20e6) & P.rvol.notna() & P.fo.notna()
P['dvrank'] = P[P.elig].groupby('date').dv20.rank(ascending=False)
P['top500'] = P.dvrank <= 500
P = P[P.date >= '2016-01-01']
P.to_parquet(C + '/panel.parquet', index=False)
print(P.shape, P.elig.sum(), P.groupby('date').elig.sum().describe())
