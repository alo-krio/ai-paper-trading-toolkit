"""Ripple event study (Main 24h, Nov 16 2026). PAPER research only.
Catalyst = large-cap (>= $20B) day with |gap| >= 4% on relvol >= 2 (earnings/news proxy), past ~1 year of cached daily bars.
Linked names = brain graph edges (supplier/customer/competitor/adjacent, with sensitivity) + same-industry peers (Nasdaq
screener industry, 0.2-5x market cap, top 6). For each linked name: day-0 excess vs SPY (in leader's direction),
follow ratio, and the NEXT 1/3/5-day excess in the leader's direction (signed so + = moved the same way as the leader)."""
import json, glob, os, sqlite3, sys, numpy as np, pandas as pd
P = '/home/user/workspace/investing-24hour-agent/project'
sys.path.insert(0, P + '/scripts'); sys.path.insert(0, '/home/user/workspace/market-brain')
import brain, prices as PR
fr = []
for f in glob.glob(P + '/data/ohlcv/*.json'):
    r = json.load(open(f))
    if len(r) < 120: continue
    d = pd.DataFrame(r, columns=['date', 'o', 'h', 'l', 'c', 'v']); d['t'] = os.path.basename(f)[:-5]; fr.append(d)
D = pd.concat(fr); D['date'] = pd.to_datetime(D['date']); D = D.sort_values(['t', 'date']); g = D.groupby('t')
D['pc'] = g.c.shift(1); D['r0'] = D.c / D.pc - 1; D['gap'] = D.o / D.pc - 1
for k in (1, 3, 5): D[f'f{k}'] = g.c.shift(-k) / D.c - 1
D['rv'] = D.v / g.v.transform(lambda s: s.rolling(20).mean()).shift(1)
spy = D[D.t == 'SPY'].set_index('date')
for k in ('r0', 'f1', 'f3', 'f5'): D['x' + k] = D[k] - spy[k].reindex(D.date).values
body = brain.cached_get("https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&download=true", 24 * 3600,
                        kind="nasdaq", fetch=lambda u, h: json.dumps(PR._curl(["-H", "Accept: application/json", u])).encode())
ind = {}
for r in json.loads(body)["data"]["rows"]:
    try: ind[r["symbol"]] = (r.get("industry") or "", float(str(r.get("marketCap") or 0).replace(",", "") or 0))
    except Exception: pass
c = sqlite3.connect('/home/user/workspace/market-brain/brain.db')
E = c.execute("SELECT source,target,relation,sensitivity FROM edges").fetchall()
have = set(D.t)
X = D.set_index(['t', 'date'])
cat = D[(D.t != 'SPY') & (D.gap.abs() >= .04) & (D.rv >= 2) & D.t.map(lambda t: ind.get(t, ('', 0))[1] >= 2e10)]
rows = []
for L in cat.itertuples():
    sgn = np.sign(L.xr0) or 1
    links = {}
    for s_, t_, rel, sen in E:
        if s_ == L.t and t_ in have: links[t_] = ('graph:' + rel, sen)
        elif t_ == L.t and s_ in have: links[s_] = ('graph:' + {'supplier_to': 'customer_of', 'customer_of': 'supplier_to'}.get(rel, rel), sen)
    li, lm = ind.get(L.t, ('', 0))
    peers = sorted([t for t, (i, m) in ind.items() if i == li and t != L.t and t in have and 0.2 * lm <= m <= 5 * lm], key=lambda t: -ind[t][1])[:6]
    for t in peers: links.setdefault(t, ('peer', 'peer'))
    for t, (rel, sen) in links.items():
        try: y = X.loc[(t, L.date)]
        except KeyError: continue
        if pd.isna(y.xr0) or pd.isna(y.xf3): continue
        rows.append(dict(leader=L.t, date=L.date.date(), lead_x0=100 * L.xr0, rel=rel, sen=sen, t=t, x0=100 * sgn * y.xr0,
                         follow=(y.xr0 / L.xr0) if L.xr0 else np.nan, n1=100 * sgn * y.xf1, n3=100 * sgn * y.xf3, n5=100 * sgn * y.xf5 if not pd.isna(y.xf5) else np.nan,
                         lead_n3=100 * sgn * L.xf3 if not pd.isna(L.xf3) else np.nan))
R = pd.DataFrame(rows); R.to_csv(P + '/research/ripple_study/events.csv', index=False)
print(f"catalysts {cat.shape[0]} | leader-link pairs {len(R)} | graph pairs {(R.rel.str.startswith('graph')).sum()}")
def show(name, m):
    s = R[m]
    if len(s) < 5: print(f"{name}: n={len(s)} (too few)"); return
    byd = s.groupby(['leader', 'date']).n3.mean()
    t = byd.mean() / (byd.std() / np.sqrt(len(byd))) if len(byd) > 2 else 0
    print(f"{name:44s} n={len(s):5d} events={len(byd):4d} | day0 {s.x0.mean():+.2f} follow {s.follow.median():+.2f} | next1 {s.n1.mean():+.2f} next3 {s.n3.mean():+.2f} next5 {s.n5.mean():+.2f} | hit3 {100*(s.n3>0).mean():.0f}% t(events) {t:+.1f}")
print("\nSigned so + = linked name moves the SAME way as the leader. 'next' = AFTER the catalyst day close (tradeable).")
show('ALL links', R.t.notna())
for rel in sorted(R.rel.unique()): show(rel, R.rel == rel)
show('graph high sensitivity', R.sen == 'high')
show('LAGGARDS (follow < 0.3)', R.follow < .3)
show('LAGGARDS, leader UP', (R.follow < .3) & (R.lead_x0 > 0))
show('LAGGARDS, leader DOWN', (R.follow < .3) & (R.lead_x0 < 0))
show('FOLLOWERS (follow >= 0.7)', R.follow >= .7)
show('OVERSHOOTERS (follow >= 1.5)', R.follow >= 1.5)
show('graph LAGGARDS', (R.follow < .3) & R.rel.str.startswith('graph'))
show('peer LAGGARDS', (R.follow < .3) & (R.rel == 'peer'))
print("\nLeader itself after the catalyst day (signed): next3", round(R.drop_duplicates(['leader', 'date']).lead_n3.mean(), 2))
