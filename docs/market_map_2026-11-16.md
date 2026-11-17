# Market map results (Nov 16, 2026; PAPER research)

What: a relationship map of the whole market, for ripple checks. All 1,664 liquid US stocks in the bar cache (price
>= $5, 20-day dollar volume >= $20M) are ranked against each other on five kinds of evidence:
- residual return correlation, after SPY and the sector factor, over 1 year and 60 days, plus a market-only residual version;
- catalyst co-move: a shrunk ripple beta and hit rate on the other stock's gap days, from 3,217 events;
- headline co-mention: 14,849 headlines from Apr 29, 2026 onward;
- Nasdaq industry and size;
- the hand-researched brain edges.
For each name there is a top-15 list with a score, a type guess and a reason, plus 110 theme clusters. Docs:
market-brain/MARKET_MAP.md. Command-line tool: `python3 /home/user/workspace/market-brain/market_map.py neighbors TICKER`.

Out-of-sample test: the map was built on data through Jun 30, 2026 and tested on 1,397 catalysts from Jul 1 to Nov 12.
Moves are excess vs SPY, signed in the leader's direction.

| Top-6 list | Day-0 move | Moved >= 2 pts same way | In day's top-5% movers | Next 3d |
|---|---|---|---|---|
| Market map | +2.12 (t 21) | 44% | 19.4% | -0.32 |
| Industry peers (old rule) | +1.15 (t 15) | 33% | 11.8% | -0.27 |
| Random | -0.06 | 20% | 4.8% | -0.02 |

- Paired on the same events, the map moved +0.98 points more (t 11.2) and was better in 62% of events.
- Large-cap leaders (>= $20B): map +2.82 vs peers +1.67.
- Map names outside the industry list carry the gain: +2.10, against +0.88 for the peers the map left out.
- After day 0 the old rules hold. Laggards after a good-news leader drift +0.52 over 3 days (random +0.27). Sympathy followers reverse 1.6. Neighbours of a bad-news leader rebound 1.4.

What changes:
- The 24-hour intraday scanner's ripples() now lists brain edges, then map neighbours. Industry peers are only a fallback.
- The map is the WHO list for ripple checks. brain.py and the industry desks remain the WHY.
- Rebuild weekly. A full rebuild takes about 20 s plus the news increment.

Caveats:
- One year of data, and small co-move samples (shrunk, n shown).
- Market caps and labels are current values.
- The news feed tags one symbol per article, so co-mention is headline name matching from Apr 29 onward, and it is weak evidence so far.
- Megacaps have few strong neighbours.
- Weights were set by hand, with one change after a first test look.
