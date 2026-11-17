# Market map: who moves with whom (built Nov 16, 2026; PAPER research only, never trades)

Owner: "analyze all of stocks and figure out their relationships to one another. This might help quickly understand all
of the companies we need to do a ripple check for once a catalyst happens."

The market map ranks every liquid US stock against every other one on five kinds of evidence. It stores the top 15
neighbours for each name, with a score, a guess at the relationship type, and a reason you can read. It also groups the
market into 110 theme clusters. Everything is precomputed, so a lookup takes about 0.4 s.

## How to use

```
python3 /home/user/workspace/market-brain/market_map.py neighbors MU [--n 15] [--all]  # who to ripple-check, with evidence
python3 /home/user/workspace/market-brain/market_map.py cluster MU                      # its theme group, members by similarity
python3 /home/user/workspace/market-brain/market_map.py clusters                        # all 110 groups
python3 /home/user/workspace/market-brain/market_map.py stats                           # build date, coverage, data gaps, validation
sh /home/user/workspace/_platform/py.sh /home/user/workspace/market-brain/market_map.py build      # weekly rebuild
python3 /home/user/workspace/market-brain/market_map.py validate                        # re-run the out-of-sample test
```
From Python: `sys.path.insert(0, '/home/user/workspace/market-brain'); import market_map as MM; MM.neighbors('MU', n=10)`
returns a DataFrame. Every hand-researched brain edge is included, plus the top n others. If the result is empty, the
relationship is UNKNOWN, not "no links". The 24-hour intraday scanner's `ripples()` already uses the map (see Integration).

Reading a row (`neighbors MU`): `LRCX 0.48 strong supply chain: supplier | brain: MU customer_of LRCX [high]; mkt-resid corr +0.67; resid corr +0.44 1y / +0.31 60d; moves +0.04x on MU catalysts (n=3, hit 20%)`
- score: from 0 to about 1. Strong is >= 0.40, moderate is 0.25-0.40, and weak is anything lower. Treat a weak link as "check it if there's time".
- brain: the hand-researched edge. It reads as "TICKER relation NEIGHBOR", and the type column describes the neighbour.
- mkt-resid corr: the 1-year correlation of daily returns after removing the stock's SPY beta. Names that share a sector theme score high here.
- resid corr 1y / 60d: the correlation after removing both SPY and the stock's sector factor, so it only counts what the pair shares beyond the sector.
- moves Bx on T catalysts: the shrunk ripple beta. It measures how far this name moved, as a fraction of T's move, on T's gap days. n is the number of events. hit is the share of events where it moved at least 1 of its own daily standard deviations in the same direction (about 12.5% with no link).
- joint articles: headlines tagged with one company that name the other.

## Method (market_map/build.py)

Universe: every stock in the daily-bar cache (`investing-24hour-agent/project/data/ohlcv`) that the Nasdaq screener
lists. ETFs are excluded. A stock needs a last price of at least $5, a 20-day median dollar volume of at least $20M, and
at least 120 days of history. That gave 1,664 names on the Nov 13, 2026 bars, using 252 trading days (Nov 12, 2025 to
Nov 13, 2026). A daily return above 70% in either direction is treated as a split or bad print and marked UNKNOWN.

1. Residual correlation (a)
   - Step 1 regresses each stock on SPY, which gives the market residual. That residual feeds the "mkt-resid corr" column.
   - Step 2 assigns each stock to the SPDR sector ETF (XLK, XLF and so on) whose SPY-neutral return best explains its residual. This choice is data-driven, so Nasdaq's odd sector labels don't matter.
   - The sector factor is the leave-one-out equal-weight mean of that sector group's market residuals. We don't use the cap-weighted ETF itself, because XOM is about 23% of XLE and regressing XOM on XLE would mostly remove XOM.
   - Residuals are standardised and clipped at 4 standard deviations, so one day can't dominate. Correlation uses pairwise overlap, over 1 year and over the last 60 days.
   - In the score, every correlation is shrunk by 2 standard errors (2/sqrt(n): about 0.13 for 1 year and 0.26 for 60 days), so a correlation that could be noise counts for nothing.
2. Catalyst co-move (b)
   - A catalyst is a day with |gap| >= 4%, volume >= 2x the prior 20-day average, and a day move of at least 2% after removing market beta. There were 3,217 events.
   - We dropped 3 macro days. Those had more than 30 catalysts with at least 75% moving the same way. Earnings days have mixed directions and are kept.
   - For each leader and follower pair: beta = Σxy / (Σx² + 5·median x²). This is equivalent to adding 5 pseudo-events with zero follow-through.
   - The hit rate is shrunk toward the 12.5% base rate in the same way.
   - Co-move only enters the score with at least 3 events, and its weight scales with n/(n+5). Most names have only 2-8 catalysts a year, so this evidence is sparse and is shown with n.
3. News co-mention (c)
   - Source: every article from the Alpaca news endpoint, Apr 29, 2026 to now. That is 198 day files and 279k unique headlines through Nov 13, paged by date range rather than per pair. The cache lives in market_map/news/, one gzip file per UTC day.
   - Important: the feed (source "fiscal.ai") tags each article with exactly one symbol, so co-mention from symbol lists isn't possible.
   - Co-mention here means a headline tagged A that names company B. Company names come from the Nasdaq screener, and the longest match wins.
   - Aliases that map to two companies are dropped, for example "Apple" (AAPL and APLE) and "Applied" (AMAT and AAOI).
   - Aliases are also dropped when fewer than 30% of the headlines containing them are tagged with their own company, for example "Target" in "Price Target", or "AI".
   - The full window gave 14,849 co-mention headlines. A pair needs at least 3 joint headlines. The strength measure is the cosine joint / sqrt(n_A·n_B).
4. Industry and size (d): same Nasdaq industry, same sector, and market-cap ratio, from the screener (24-hour cache in brain.db).
5. Brain edges (e): all rows of brain.db `edges`, in both directions, with supplier and customer flipped. Edges are kept with their sensitivity, and both ends must be in the universe. That came to 230 directed links. They are always listed, even when their statistics are weak.

Score = 0.25·sector-residual corr + 0.15·market-residual corr + 0.08·60-day corr + 0.17·co-move beta + 0.05·co-move hit
+ 0.12·co-mention + 0.10·same industry (0.03 for same sector only) + 0.08·brain edge. Each part is scaled to [0, 1] after
shrinkage. These weights were set by hand, then changed once: after the first test pass, market-residual correlation was
added, because on its own it did as well as the full map. That is mild test-set influence, so treat the weights as
reasonable, not optimised.

Relationship type (a guess, in this order):
- A brain relation wins if there is one.
- Same industry plus strong correlation or co-move gives "peer/competitor".
- Strong co-mention with weaker correlation gives "co-mentioned (deal/partner/news link)".
- Strong co-move with low correlation gives "catalyst read-through".
- Correlation alone gives "same factor/theme".
- Same industry with weak statistics gives "industry peer (label only)".

Clusters (clusters.csv): Ward hierarchical clustering on a similarity of 0.5·sector-residual corr + 0.35·market-residual corr
+ 0.15·symmetric co-move, cut into 110 groups (about 15 names each). Each group is named after its two most common Nasdaq
industries and its three largest members. Groups with mean similarity under 0.08 are marked LOOSE (3 groups) and those
under 0.15 MIXED (7 groups). Names in LOOSE groups get a `nearest_theme`. Some megacaps have no strong group: NVDA, AAPL
and TSLA are mostly their own factor, so use `neighbors` for them, not `cluster`.

## Validation (market_map/validate.py; market_map/validation/REPORT.md)

The map was rebuilt using only data through Jun 30, 2026: prices, catalysts, and news from Apr 29 to Jun 30, giving 1,623
names. It was then tested on every catalyst from Jul 1 to Nov 12, 2026: 1,397 events with the same definition and macro
filter. For each event we compared the top 6 map neighbours with the top 6 same-Nasdaq-industry peers. The peers are the
old scanner and event-study rule: 0.2-5x market cap, largest first. We also compared 6 random liquid names. Moves are
excess vs SPY, signed so + means the same direction as the leader.

| Top-6 list | n pairs | Day-0 move | t | Median follow | Same direction | Moved >= 2 pts same way | In day's top-5% movers | Next 1d | Next 3d |
|---|---|---|---|---|---|---|---|---|---|
| Market map | 8,381 | +2.12 | 21.2 | 0.14 | 68% | 44% | 19.4% | +0.07 | -0.32 |
| Industry peers | 7,168 | +1.15 | 15.3 | 0.07 | 62% | 33% | 11.8% | -0.02 | -0.27 |
| Random names | 8,381 | -0.06 | -1.5 | 0.00 | 49% | 20% | 4.8% | -0.04 | -0.02 |
| Map, leaders >= $20B | 2,855 | +2.82 | 15.8 | 0.22 | 73% | 49% | 23.2% | -0.19 | -0.76 |
| Peers, leaders >= $20B | 2,307 | +1.67 | 12.2 | 0.13 | 66% | 38% | 13.7% | -0.07 | -0.49 |

- Paired over the same 1,333 events, map lists moved 0.98 points more on day 0 (t 11.2). The map list was better in 62% of events, and its top-5% hit rate was 7.6 points higher.
- What the map adds: map names that are not industry peers moved +2.10 on day 0 with a 19.1% top-5% rate. Industry peers that the map dropped moved only +0.88, with 9.6%. Map ranks 1-3 moved +2.40 and ranks 4-6 moved +1.84, so the order carries information.
- Evidence on its own:
  - Sector-residual correlation: +1.98.
  - Market-residual correlation: +2.14.
  - Co-move: +1.19 overall and +2.33 for large-cap leaders. It only covers the 365 events whose leader had at least 3 training catalysts.
  - News co-mention: +0.77, n = 481. It is weak because the training window had only 2 months of news.
  - Removing the industry bonus barely changes the result (+2.06).
- After the catalyst day:
  - Map neighbours give back a little over 3 days (-0.32, t -2.3). That matches the ripple study, where most of the ripple is priced on day 0.
  - Leader UP: map laggards (follow < 0.3) drifted +0.52 over 3 days (t 3.1), against +0.33 for peer laggards and +0.27 for random names. So about +0.25 beyond drift.
  - Leader DOWN: map neighbours rebounded 1.37 relative to the leader's direction over 3 days, against 1.04 for peers and 0.29 for random names.
  - Map followers that moved >= 70% of the leader reversed 1.63 over 3 days, against 1.77 for peers. Keep the FADE rule.

Bottom line: the map finds the names that actually react on day 0 about twice as well as plain industry peers, and it
explains why. That fixes the ripple study's finding that "mapped graph links did not beat industry peers". After day 0,
the behaviour is the same as before: catch-up only after good news, fade the sympathy movers, small edges.

## Caveats

- One year of daily bars. Co-move samples are small (n is usually 3-8), which is why they're shrunk and shown with n. Pairs whose co-move n is under 3 show "co-move n=k (too few)" and get no co-move credit.
- Market caps and industry labels are today's values, so peer selection and size ratios have mild look-ahead, for both lists. The universe is the liquid names in the cached bars (about 1,660 of about 7,000 listed). Anything else is UNKNOWN.
- Day-0 correlation partly reflects shared factor moves, not only "news read-through". That is fine for "who will move", but it doesn't tell you the channel. Use brain.py and the industry desks for the WHY.
- News: one symbol per article, so co-mention is headline name matching. It misses tickers named only in the body and catches some false matches. It covers Apr 29, 2026 onward only. Days the fetcher couldn't complete are listed as failed in `stats` and treated as UNKNOWN, not as zero co-mentions. The current cache has 0 failed days.
- Megacaps are their own factor. NVDA, AAPL, AMZN and TSLA have few strong neighbours, because once their own sector factor is removed little shared movement is left. The brain edges matter most for them.
- Weights were set by hand, with one change after seeing test results (see Method). Results are directions, not proof, and the edge after costs on any one trade is small.

## Rebuild schedule

Run weekly, for example Saturday morning ET:
`sh /home/user/workspace/_platform/py.sh /home/user/workspace/market-brain/market_map.py build`
- It first pages the news days not yet cached, plus the last 2 days, at about 4 requests a second (about 10-30 s per day). Then it rebuilds from the bar cache. The full rebuild takes about 12 s, or about 20 s plus 2-3 min of news for a week.
- The first-time news backfill of 203 days took about 40 min.
- Refresh the daily-bar cache before this, using the usual warm routine, so the map's `asof` is current. `stats` warns if the map is more than 10 days old.
- Without credentials, build uses cached news only and says so.
- Re-run `validate` after any method change. Long-running fetches can lose the credential proxy session. Failed days are retried on the next run, never written as empty.

## Integration

- `investing-24hour-agent/project/scripts/intraday_scan.py` ripples(): brain edges are always listed first. Then come up to 8 map neighbours (`map <type> s<score>: <reason>`).
- Same-industry peers are used only if the map is missing or the leader isn't in it. That fallback was tested.
- LAG marks a graph edge or a strong map link (score >= 0.40). "lag?" marks a moderate or weak map link or a label-only peer. FADE and the existing rules are unchanged.
- Duplicate board tags are now de-duplicated. A backup of the original file is intraday_scan.py.bak_mapbuild_2026-11-16.
- Other books: see the MARKET MAP section of market-brain/README.md.

## Files

| File | What |
|---|---|
| `market_map.py` | Command-line tool and library (`neighbors`, `cluster`, `meta`) |
| `market_map/build.py` | Evidence, score, neighbours, clusters. `build(asof=...)` uses only data up to `asof` |
| `market_map/news_fetch.py` | Incremental news day cache (`market_map/news/*.json.gz`, `_status.json`) |
| `market_map/validate.py` | Out-of-sample test. Writes `validation/REPORT.md`, `results.json`, `pairs.parquet`, and `train_map/` |
| `market_map/neighbors.parquet` / `.csv` | 25,097 rows: ticker, rank, neighbor, score, strength, type, reason, corr_1y, corr_mkt_1y, corr_60d, n_1y, n_60d, comove_beta, comove_hit, comove_n, comove_in_beta, comove_in_n, news_joint, news_cos, same_industry, same_sector, size_ratio, brain_rel, brain_sens, n_evidence, weak |
| `market_map/clusters.csv` | ticker, cluster, cluster_name, cluster_size, intra_sim, sim_to_cluster, industry, sector, mcap_b, factor_etf, nearest_theme |
| `market_map/meta.json` | Build time, data window, universe, events, news coverage, failed days, weights, parameters |
