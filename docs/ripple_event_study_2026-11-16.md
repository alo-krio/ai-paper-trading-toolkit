# Ripple event study: how linked stocks reacted to past catalysts (Nov 16, 2026, PAPER research)

Method: 1,233 large-cap catalysts (>= $20B, |gap| >= 4% on >= 2x volume) over the past ~year of cached daily bars; 6,621 leader-link pairs (705 from the market-brain graph: suppliers, customers, competitors, adjacent, input costs; the rest same-industry peers of similar size). Moves are excess vs SPY, signed so + means the linked stock moved the same way as the leader. "Next" returns start at the catalyst-day close (tradeable). Code: research/ripple_study/study.py; rows: events.csv.

## Findings
| Group | n | Day 0 | Next 1d | Next 3d | Next 5d | Note |
|---|---|---|---|---|---|---|
| All links | 6,621 | +1.30 | +0.03 | -0.08 | -0.19 | most ripple is priced the same day; median follow only 0.09 |
| Laggards (follow < 0.3), leader UP | 2,288 | -0.38 | +0.21 | +0.37 | +0.65 | catch-up drift, t +2.1; small, roughly 0.2-0.5 pts after costs |
| Laggards, leader DOWN | 2,317 | -0.62 | -0.10 | +0.02 | +0.15 | no catch-up on bad news |
| Sympathy followers (follow >= 0.7) | 918 | +7.18 | 0.00 | -1.22 | -2.25 | they REVERSE, t -2.5 |
| Competitors (graph) | 200 | +1.28 | -0.38 | -0.32 | -0.74 | trade as the same factor on day 0, then share-shift logic takes over |
| Suppliers (graph) | 186 | +0.83 | +0.14 | +0.19 | +0.05 | modest follow-through |
| Leader itself | 1,233 | | | -0.39 | | the leader's own gap fades a little |
Mapped graph links did not beat plain industry peers yet (graph laggards next3 -0.04, n=484), so the map's value is in explaining WHY, not yet in timing.

## Case studies
- MU, Nov 5, 2026 (-13 vs SPY): equipment and chip names sold off with it on day 0 (LRCX -12, AMAT -9, TSM -6, INTC -6, ASML -5 in excess terms), then rebounded relative to MU by 9-18 pts over 3 days. MU kept falling. Lesson: a supplier/customer selloff that matches the leader is often an overreaction when its own business did not change.
- MSFT, Jul 30, 2026 (+13.8): AI-capex suppliers jumped on day 0 (NBIS +25, MU +17, GEV/MOD/ORCL/ANET +7); ORCL and ANET kept going (+10, +7 over 3 days), MU reversed (-6.6 next day). AMZN barely moved on day 0, then jumped on its own print the next day (own-earnings confound).
- AVGO, Jun 4, 2026 (-13): ANET fell with it (+5 same-direction), then rebounded 5.7 pts over 3 days. NVDA and TSM barely followed.
- NVO, Feb 23, 2026 (-15.4): LLY (competitor) fell 5.9 with it, then recovered 4.5 over 3 days; the leader itself bounced 6.1.

## Rules this changes (v6.5)
1. Don't chase sympathy. A linked name that already moved >= 70% of the leader is a FADE candidate, not a buy (scan flags it). Buying the oversold sympathy name whose own business didn't change is the better trade, especially after a bad-news leader.
2. Catch-up buys only after GOOD news, on names that have moved < 30% of the leader, with a stated channel; expect small, multi-day drift (3-5 sessions), not an intraday pop.
3. Competitors move with the leader on day 0; the share-shift trade (the other way) shows up over the next days.
4. Watch for own-earnings confounds: a linked name reporting in the next 3 sessions is its own catalyst, not a ripple.
Caveats: one year of data, catalysts are gap proxies (not all earnings), a cached universe, and the graph covers mainly AI/semis, health care, energy and industrials.

## Part 2: what the news actually was (added Nov 16, 2026)
The first pass used price gaps only. Part 2 attaches the real trigger: Benzinga headlines for each leader (prior 4 PM to the catalyst day's 4 PM ET; research/ripple_study/news.py), read and classified by an LLM into a trigger type and a SCOPE: industry signal (demand, pricing, capex, costs or regulation that applies to others), company-specific, or mixed. Headline coverage only exists from Apr 2026, so 564 of the 1,233 catalysts have news (2,950 links); earlier events are UNKNOWN, not "no news". Files: catalysts_classified.csv (trigger, scope, channel, headlines), events_classified.csv.

| Scope / trigger | Who | n | Day 0 | Next 3d | Next 5d | Read |
|---|---|---|---|---|---|---|
| Company-specific news | sympathy followers (>= 70%) | 246 | +6.43 | -1.46 | -2.87 | t -2.5: the market read through news that wasn't about them, then undid it |
| Company-specific news | laggards | 1,252 | -0.45 | -0.07 | -0.05 | nothing to catch up: correctly ignored |
| Mixed (company + industry info), leader UP | laggards | 388 | -0.06 | +0.45 | +0.60 | the catch-up trade lives here (t 1.3) |
| Industry signal | sympathy followers | 27 | +10.5 | -4.4 | -8.1 | even real industry news gets over-extrapolated on day 0 (small n) |
| Analyst call on the leader | all links | 282 | +2.15 | -1.24 | -1.54 | ripple from one analyst note fades (t -1.8) |
| Deal / M&A | all links | 194 | +1.24 | +0.93 | +1.47 | peers keep re-rating (takeover read-through) |
| Guidance raise only | all links | 103 | +0.68 | -0.82 | -1.85 | peers fade |
| Earnings miss / guidance cut | all links | 594 | +0.5 to +0.8 | -0.6 to -1.0 | -0.7 | peers that fell in sympathy rebound |
| Regulatory / policy | all links | 103 | -0.35 | +0.82 | +0.63 | slow, delayed diffusion |

Case studies with the trigger:
- AMZN, Jul 31, 2026 (+14.6): "Amazon increases 2026 capital expenditure forecast to $220B", "$20B increase in technology and AI spending" (industry signal: capex). Its 15 linked suppliers moved only +0.6 on the day, then +4.1 over the next 3 days. That's slow diffusion of a real industry signal: the cleanest catch-up example.
- MU, Nov 5, 2026 (-13): "Micron halts work on planned Taiwan chip plant amid labor dispute", after "Micron shares decline amid concerns over data-center infrastructure policy". The plant halt matters for one fab's tool orders, small against LRCX/AMAT revenue, yet they fell 9-12% with MU and then rebounded 14-18 pts relative within 3 days. Overreaction to news that was mostly about MU.
- MSFT, Jul 30 (+13.8): beat-and-raise with strong cloud growth (mixed: demand signal for AI suppliers). Suppliers that already jumped (NBIS +25, MU +17) gave some back or went flat; ORCL and ANET kept running.
- AVGO, Jun 4 (-13): Q2 beat but guidance seen as weak, plus multi-GW AI deals (mixed). ANET fell in sympathy, then recovered 5.7.
- PCG, Aug 31 (-19.8): California wildfire-liability bill (regulatory, industry signal for utilities). Peers barely moved on the day and stayed flat (-0.3): the market judged it PG&E-specific.
Caveats: Benzinga coverage from Apr 2026 only, headline-level classification, small cells for some triggers; directions, not proof.

## Part 3: after-hours and pre-market (added Nov 16, 2026)
Most catalysts land outside the session (earnings after the close or before the open). Splitting each day into before-the-bell and during-the-session (daily bars, 1,233 catalysts; then SIP 30-minute extended-hours bars for the 502 Apr-Nov events with news):
- Leaders: about +7.7 pts (vs SPY, in the move's direction) happens between the prior close and the 9:30 open, only +1.7 during the session. By 8 PM the leader is already about +3.5%, by 9 AM about +8.5%.
- Linked names: 68% of their day-0 ripple is also priced before the bell, but slowly: about +0.3% from 4 to 8 PM and +0.5% from 8 PM to 9 AM, then +0.3% from 9 to 10 AM (hit 56%), and they give back about 0.2 over the next 3 days. For industry-signal news the 9-10 AM leg is larger (+0.5). After-hours and pre-market spreads in mid caps would eat most of that, so extended-hours trading is not our edge.
- After 10:00 (what our window captures), signed by the leader's gap direction (no look-ahead): linked names add +0.13 (t 2.4) to 3:30, roughly break-even after costs. The usable cell: the leader gapped UP and HOLDS its gap in the first 30 minutes, and the linked name is still lagging at 10:00: +0.22 to 3:30 (t 2.6), +0.32 over 3 days. Linked names that already ran in the first 30 minutes: nothing left (-0.07, then -0.39 over 3 days).
Files: premarket.py / premarket_split.csv, intraday_path.py / intraday_path_gapsigned.csv, extended.py / extended.csv.
