#!/usr/bin/env python3
"""Whole-market relationship map CLI (PAPER research only; never trades). Reads precomputed files in market_map/.

  python3 market_map.py neighbors TICKER [--n 15] [--all]   ranked neighbours with evidence (brain edges always shown)
  python3 market_map.py cluster TICKER                       the ticker's theme cluster and its closest members
  python3 market_map.py clusters                              list all clusters
  python3 market_map.py stats                                 build date, coverage, data gaps, validation headline
  python3 market_map.py build [--no-news]                     weekly rebuild (refresh news cache, then recompute map)
  python3 market_map.py validate                              re-run the out-of-sample test (train <= 2026-06-30)
Library: import market_map as MM; MM.neighbors('NVDA', n=10) -> DataFrame (empty if the map is missing / ticker unknown).
build should be run with credentials for the news refresh:
  sh /home/user/workspace/_platform/py.sh /home/user/workspace/market-brain/market_map.py build
Without credentials it uses the cached news only (days not fetched are UNKNOWN, reported in stats)."""
import os, sys, json, time
HERE = os.path.dirname(os.path.abspath(__file__)); MD = os.path.join(HERE, 'market_map')
sys.path.insert(0, MD)
_NB = None


def _load():
    global _NB
    if _NB is None:
        import pandas as pd
        f = MD + '/neighbors.parquet'
        _NB = pd.read_parquet(f) if os.path.exists(f) else (pd.read_csv(MD + '/neighbors.csv') if os.path.exists(MD + '/neighbors.csv') else None)
    return _NB


def meta():
    try: return json.load(open(MD + '/meta.json'))
    except Exception: return {}


def neighbors(t, n=15, include_weak=True):
    import pandas as pd
    NB = _load()
    if NB is None: return pd.DataFrame()
    s = NB[NB.ticker == t.upper()].sort_values('score', ascending=False)
    brain = s[s.brain_rel != '']
    rest = s[s.brain_rel == ''] if include_weak else s[(s.brain_rel == '') & ~s.weak]
    # every hand-researched brain edge, plus the top-n other neighbours
    return pd.concat([brain, rest.head(n)]).sort_values('score', ascending=False) if len(s) else s


def print_neighbors(t, n=15, show_all=False):
    m = meta(); s = neighbors(t, n=10 ** 6 if show_all else n)
    if not m: print("market map not built: run  python3 market_map.py build"); return
    if s.empty:
        print(f"{t.upper()}: not in the liquid universe of the {m.get('asof')} map (price >= $5, 20d $vol >= $20M, cached bars). "
              f"Relationship UNKNOWN here; check brain.py ripple {t.upper()} for hand-researched edges."); return
    print(f"{t.upper()} neighbours (map as of {m.get('asof')}; score 0-1; strong >= 0.40, moderate >= 0.25; brain edges always listed)")
    print(f"{'#':>2} {'name':6s} {'score':>5s} {'str':8s} {'type':32s} reason")
    for r in s.itertuples():
        print(f"{r.rank:>2} {r.neighbor:6s} {r.score:5.2f} {r.strength:8s} {r.type[:32]:32s} {r.reason}")
    print("Notes: resid corr = daily return correlation after SPY and sector (1y and 60d, shrunk by 2 standard errors in the score). "
          "'moves Bx on T catalysts' = shrunk ripple beta of this name on T's gap days (n events, hit = moved >= 1 own-sd the same way; ~12.5% with no link). "
          "Co-mention counts are from Benzinga since Apr 29, 2026 only.")


def cluster(t):
    import pandas as pd
    if not os.path.exists(MD + '/clusters.csv'): print("market map not built"); return
    CL = pd.read_csv(MD + '/clusters.csv'); r = CL[CL.ticker == t.upper()]
    if r.empty: print(f"{t.upper()}: not in the map universe (UNKNOWN)"); return
    c = r.iloc[0]; mem = CL[CL.cluster == c.cluster].sort_values('sim_to_cluster', ascending=False)
    print(f"{t.upper()} -> cluster {c.cluster}: {c.cluster_name}  ({c.cluster_size} names, mean similarity {c.intra_sim:.2f}; {t.upper()} {c.sim_to_cluster:.2f} to the group)")
    if str(c.get('nearest_theme', '') or '') not in ('', 'nan'):
        print(f"   LOOSE group = names without a strong common factor; nearest real theme: {c.nearest_theme}. Use neighbors {t.upper()} instead.")
    for x in mem.itertuples():
        print(f"   {x.ticker:6s} sim {x.sim_to_cluster:+.2f}  ${x.mcap_b:,.0f}B  {str(x.industry)[:45]}")


def list_clusters():
    import pandas as pd
    CL = pd.read_csv(MD + '/clusters.csv')
    for c, g in CL.groupby('cluster'):
        print(f"{c:4d} n={len(g):3d} sim {g.intra_sim.iloc[0]:.2f}  {g.cluster_name.iloc[0]}")


def stats():
    m = meta()
    if not m: print("market map not built"); return
    nw = m.get('news', {})
    print(f"built {m['built']} | price data {m['first_day']}..{m['asof']} ({m['days']} days) | universe {m['universe']} liquid stocks | "
          f"catalyst events {m['catalyst_events']} | brain edges in universe {m.get('brain_edges_in_universe')} | build {m['seconds']}s")
    print(f"news: {nw.get('days_cached')} day files {nw.get('first')}..{nw.get('last')}, {nw.get('joint_articles')} multi-ticker articles used; "
          f"failed days (UNKNOWN): {nw.get('failed_days') or 'none'}")
    NB = _load()
    if NB is not None:
        print(f"neighbour rows {len(NB)} | strength: {NB.strength.value_counts().to_dict()} | types: {NB.type.value_counts().to_dict()}")
    v = MD + '/validation/results.json'
    if os.path.exists(v):
        r = json.load(open(v)); a = r['all leaders']
        print(f"validation (train <= {r['coverage']['train_end']}, test {r['coverage']['test_first']}..{r['coverage']['test_last']}, {r['coverage']['events']} events): "
              f"day-0 signed move MAP {a['MAP']['day0']:+.2f} vs industry PEER {a['PEER']['day0']:+.2f} vs random {a['RANDOM']['day0']:+.2f}; "
              f"top-5% movers MAP {a['MAP']['top5pct']}% vs PEER {a['PEER']['top5pct']}% (random 5%)")
    import datetime as dt
    age = (dt.date.today() - dt.date.fromisoformat(m['asof'])).days
    if age > 10: print(f"WARNING: map price data is {age} days old; rebuild (weekly).")


def build(no_news=False):
    t0 = time.time()
    if not no_news:
        try:
            import news_fetch as NF
            st = NF.update(verbose=True)
            print(f"news cache: {st['days_have']}/{st['days_total']} days; failed (UNKNOWN): {st['failed'] or 'none'}")
        except Exception as e:
            print("DATA WARNING: news refresh failed (run via _platform/py.sh for credentials); using cached news only:", repr(e)[:160])
    import build as B
    B.build()
    print(f"total {time.time()-t0:.0f}s"); stats()


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit()
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else d
    cmd = a[0]
    if cmd in ('neighbors', 'neighbours', 'n'): print_neighbors(a[1], int(opt('--n', 15)), '--all' in a)
    elif cmd == 'cluster': cluster(a[1])
    elif cmd == 'clusters': list_clusters()
    elif cmd == 'stats': stats()
    elif cmd == 'build': build('--no-news' in a)
    elif cmd == 'validate':
        import validate; validate.main()
    else: print(__doc__)
