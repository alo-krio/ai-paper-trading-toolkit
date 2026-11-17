"""Test 2 news split: in-play set A names with/without a Benzinga headline tagged to the symbol from 16:00 ET prior day to 9:35 ET.
Uses cache/news_inplay.csv; effective sample 2026-04-29..2026-11-13 (news feed empty earlier). Net 20 bps round trip, per-name trades. PAPER research only."""
import pandas as pd, numpy as np
A = pd.read_parquet('cache/inplay_A.parquet'); N = pd.read_csv('cache/news_inplay.csv')
N = N[N.n_news.notna() & (N.date >= '2026-04-29')]  # Alpaca news returns nothing before ~2026-04-28 on this account (checked: 0 hits Jan-2024..Mar-2026)
X = A.merge(N[['symbol', 'date', 'n_news']], on=['symbol', 'date'])
X['news'] = np.where(X.n_news > 0, 'news', 'no news')
rows = []
for (nw, side), y in X.groupby(['news', X.dir.map({1: 'long-dir', -1: 'short-dir'})]):
    for lab, e in [('9:35', 'fc'), ('10:00', 'p10')]:
        z = y[y[e].notna()]; r = z.dir * (z.c / z[e] - 1) * 1e4 - 20
        rows.append(dict(news=nw, first_candle=side, entry=lab, exit='close', n=len(z), days=z.date.nunique(), net_bps=round(r.mean(), 1), t=round(r.mean() / r.std() * np.sqrt(len(z)), 2), hit=round((r > 0).mean() * 100, 1)))
R = pd.DataFrame(rows); R.to_csv('test2_news_split.csv', index=False); print(R.to_string(index=False))
print('sample', X.date.min(), X.date.max(), len(X), 'share with news', round((X.n_news > 0).mean(), 3))
