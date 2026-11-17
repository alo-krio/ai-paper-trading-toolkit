# Extra data sources (Firecrawl Alexandria), all books
Added Nov 13, 2026 with the owner's OK ("use it where needed to make yourself more informed"). Data sources only: never a rule change, never a gate bypass.

Call: `sh /home/user/workspace/_platform/alex.sh <provider> <capability> '<options JSON>' [out.json]` (prints a `credits:` line).
Budget: Firecrawl plan ~1,000 credits per cycle (resets the 11th). Check remaining first when planning paid calls:
`curl -s -H "Authorization: Bearer $FIRECRAWL_API_KEY" https://api.firecrawl.dev/v2/team/credit-usage`
Credits policy (owner, Nov 13): use credits freely wherever they make a run better informed; the owner will top up as needed. Still keep a 150-credit reserve so fc.sh page fallbacks never fail. When remaining credits drop under ~250, say so in one line in that run's report so the owner can add more (don't ration silently).

## Defaults (cheap, 5 credits per call)
| Need | Provider / capability | Options | When |
|---|---|---|---|
| Economic calendar (data/events.md) | forexfactory-com / economic-calendar/list_events | {"currencies":["USD","CAD"],"date":"YYYY-MM-DD","impacts":["high","medium"],"view":"week"} | 14-Day 8:45 run, when events.md is rebuilt (Mondays); use `datetime_utc` converted to ET (time_label is not ET) |
| Fed odds per meeting | cmegroup-com / fomc-rate-probabilities/fedwatch_meetings | {} | 8:45 on Mondays and every day of an FOMC week; 3-6M weekly check (macro view: our odds vs market) |
| Valuation fallback (forward P/E etc.) | stockanalysis-com / securities/stock_statistics | {"symbol":"LLY"} | Only when the free stockanalysis.com page fetch fails (fields: peForward, pe, ps...) |
| Earnings history (beat 3/4 checks) | stockanalysis-com / securities/earnings | {"symbol":"..."} | 24H v4.3 earnings decision; 3-6M earnings gate (fix A), when free sources are thin |
| Structured company/topic news (AI summary, sentiment, event tags, grouped by event) | akta / news/search (2 credits) | {"primary_company":"nvidia.com","start_date":"YYYY-MM-DD","limit":5,"group_articles":true} or {"query":"crude oil supply","start_date":"...","limit":10,"group_articles":true} | Main cheap news layer: 14-Day 3:15 finalists (1 call each); 24H holdings verdicts and candidates (1 call each, max ~6 per window); 3-6M holdings with possible news (fix E lines) and fix F read-through topics; ripple maps (query by topic). Input only: the Perplexity Decider check stays the red-flag veto. Use the company's website domain. |
| What the market is reading | cnbc-com / news/most_popular {"tag":"Markets"}; cnbc-com / news/search_news {"query":"stocks today","sort":"date","page_size":5} | | 14-Day 4:45 debrief "the why" (market-wrap source); 8:45 pre-market top stories |
| Fed speeches and statements | federalreserve-gov / central-bank-communications/speeches {"from":"YYYY-MM-DD","speaker":"Warsh"}; .../press_releases; .../fomc_meetings | | When a Fed speaker or FOMC event is on the day's calendar; 3-6M monthly macro view |

## Higher-cost (30-45 credits per call), use when it adds information
- benzinga / calendar/consensus-ratings, analyst ratings (30): confirm analyst moves behind a catalyst (upgrades, PT raises, consensus) for finalists, candidates and holdings.
- benzinga / news/wiims "Why Is It Moving" (45): the reason behind big movers and names in play, especially in the 24H windows and the 4:45 top-movers section.
- benzinga / unusual options activity (45) and M&A (15): when a story hinges on positioning or a deal.
No fixed daily cap; skip only when free sources already answer the question.
Not used (redundant or off-topic): GlobeNewswire, Nasdaq.com news (Akta and Alpaca cover them), Trends, university/space/gaming/state-politics feeds. Substack (5) only when the owner shares a Substack link (shared-link skill).
Free alternatives first: Alpaca news (24H, Benzinga headlines), news_check, Nasdaq API analyst targets, web search/fetch.

Discovery of other providers is free: https://alexandria.firecrawl.dev/skills.md (POST /v2/search with sources ["alexandria"]). Don't pay to probe.
