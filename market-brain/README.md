Market brain: shared memory for the paper-trading desk (owner, Nov 16, 2026). PAPER ONLY. Library + CLI.

Owner: "set it up in a way where we don't need to keep running ripple or keep pulling the same information. Think of
building some sort of brain, vector database or cache to help you recall information you might have already discovered."

One SQLite file (brain.db) with four layers:
  1. DOCS    every research note, thesis, report, brief, industry-desk file and insight line across the three books,
             chunked, entity-tagged and indexed twice: full text (FTS5/BM25) and vectors (local model2vec embeddings,
             no API). Ingest is incremental (only changed files are re-read).
  2. FACTS   short sourced claims ("AVGO has ~$43B of AI-lab backstops", source, date, expiry). Added by agents after
             research; recalled before research. Expired facts are shown as STALE, not deleted.
  3. CACHE   raw HTTP responses (Nasdaq analyst data, SEC filings, news RSS...) with a TTL per source, so scripts never
             pull the same thing twice within its freshness window. Also per-ticker snapshots so briefs show only
             what changed since last time.
  4. GRAPH   the industry desks' ripple graph (data/ripple_graph/*.csv imported on change) and a ripple cache keyed by
             the graph version, so neighbourhoods are computed once per graph change, not per question.

CLI (python3 /home/user/workspace/market-brain/brain.py ...):
  ingest                      index new/changed files (cheap; run at the end of every routine)
  recall "query" [--entity T] [--k 8] [--days N]   hybrid search over docs + facts, freshness shown
  facts T [--all]             current facts about an entity (--all includes stale/superseded)
  fact --entity T --topic X --claim "..." --source URL [--date YYYY-MM-DD] [--ttl DAYS] [--by NAME]
  ripple T [--hops 2]         cached ripple neighbourhood (recomputed only if the graph changed)
  exposure                    for every holding: the 2-hop set of names whose news touches it (cached)
  stale [--days 45]           facts past expiry and graph rows older than N days
  stats
Library: import brain; brain.cached_get(url, ttl_s, headers) ; brain.snapshot_diff(ticker, kind, dict) ;
         brain.recall(q) ; brain.add_fact(...) ; brain.seen(key) / brain.mark_seen(keys)


MARKET MAP (added Nov 16, 2026; details in MARKET_MAP.md). Whole-market relationship map for ripple checks: every liquid
US stock (~1,660) ranked against every other on residual return correlation, catalyst co-move, Benzinga co-mention,
industry and the hand-researched graph edges above. Precomputed; lookups are instant.
  python3 /home/user/workspace/market-brain/market_map.py neighbors NVDA [--n 15] [--all]   who to ripple-check, with evidence
  python3 /home/user/workspace/market-brain/market_map.py cluster MU                         its theme group
  python3 /home/user/workspace/market-brain/market_map.py stats                              build date, coverage, validation
  sh /home/user/workspace/_platform/py.sh /home/user/workspace/market-brain/market_map.py build   weekly rebuild (Sat/Sun)
From Python (any book):  sys.path.insert(0, '/home/user/workspace/market-brain'); import market_map as MM
                         MM.neighbors('NVDA', n=10)  -> DataFrame (brain edges always included; empty = UNKNOWN, not "no links")
Use brain.py ripple T for the WHY (hand-researched channel), market_map.py neighbors T for the WHO (who actually moves).
The 24h intraday scanner's ripples() already uses it (brain edges first, then map neighbours, industry peers as fallback).
