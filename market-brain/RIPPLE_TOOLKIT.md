# Ripple toolkit: shared by all three books (Nov 16, 2026)
PAPER ONLY. Information, never an order. Built for Main 24h, shared with the 14-Day and 3-6 Month books.

## Tools
| Tool | Command (from any book's project/ folder) | What it gives |
|---|---|---|
| Live scan with ripples | `sh /home/user/workspace/_platform/py.sh /home/user/workspace/investing-24hour-agent/project/scripts/intraday_scan.py scan` (market hours; ~10 s) | Boards (CATALYST, MOMENTUM, OVERSOLD, OVERBOUGHT, REPORTS TONIGHT) and a RIPPLES block: each leader's headlines, then linked names with how far they followed (LAG / FADE / lag?) |
| Overnight digest | `... intraday_scan.py premarket` (9:15-9:45 ET; SIP bars ~15 min delayed) | After-hours and pre-market movers, reporters, headlines, ripples |
| Board scoring | `... intraday_scan.py score` | How each board did from scan price to close and next close vs SPY |
| Brain ripple (mapped links) | `python3 /home/user/workspace/market-brain/brain.py ripple TICKER` | Hand-researched suppliers, customers, competitors, adjacent, with sensitivity and notes |
| Market map (all stocks) | `python3 /home/user/workspace/market-brain/market_map.py neighbors TICKER` (being built Nov 16; see MARKET_MAP.md when present) | Statistical neighbours for every liquid stock (residual correlation, catalyst co-move, news co-mention, industry) |
| 3-6M wrappers | `python3 scripts/ripple.py TICKER` (3-6M project) | Same graph plus desk notes |
| Event study | `/home/user/workspace/investing-24hour-agent/project/research/ripple_study/REPORT.md` | Cause and effect from 1,233 past catalysts |

## What the study says (use it in every book)
1. Find the TRIGGER first: read the leader's actual headlines and classify SCOPE: industry signal (demand, pricing, capex, costs, regulation that applies to others), company-specific, or mixed. Unknown trigger = no ripple conclusion.
2. Most ripple is priced the same day, and two thirds of it before the 9:30 open (catalysts land after hours / pre-market).
3. Company-specific news: linked names that moved in sympathy (>= 70% of the leader) give it back over 3-5 days (-1.5 / -2.9 pts, t -2.5). Laggards correctly don't move.
4. Mixed or industry-signal GOOD news: linked laggards drift +0.45 over 3 days, +0.6 over 5 (e.g. AMZN capex raise Jul 31: suppliers +0.6 on day 0, +4.1 over 3 days).
5. Analyst-call and guidance-raise-only ripples fade. M&A: peers keep re-rating (+0.9 / +1.5). Misses and guidance cuts: names that fell in sympathy without their own bad news rebound (MU Nov 5: LRCX/AMAT rebounded 14-18 pts relative in 3 days). Regulation/policy diffuses slowly (check day 2-3).
6. Intraday: the tradeable ripple is a leader that gapped up and HOLDS its gap through ~10:00 with a linked name still lagging (+0.22 to 3:30, +0.32 over 3 days). Names that already ran in the first 30 minutes have nothing left.

## How each book uses it
- Main 24h (intraday to a few days): rules v6.4-v6.7 in its notes/rules.md; scan every window, premarket digest at 9:45.
- 14-Day (10-session hold): the multi-day findings fit best. Use the scan (or premarket digest) in the 3:15 run on catalyst days. Good 14-day ripple entries: (a) laggards after GOOD industry/mixed news, entered day 0-1, (b) quality names that sold off in sympathy with a company-specific or bad-news leader while their own business didn't change (rebound over 3-5 days, within the 10-session hold), (c) M&A peers. Never buy a sympathy name that already moved >= 70% of the leader on good news. Write the link, trigger, scope and channel in the pick's 14-day test (CARRY = ripple) and log it in picks/ripple_shadow.csv as before (Amendment J).
- 3-6 Month (judgement, fundamentals): ripple is about whether the news changes a linked company's BUSINESS (orders, pricing, costs, share) over quarters, not about the day-0 price. Industry-signal news (capex raises, pricing, regulation) is a reason to re-underwrite linked holdings and candidates (desk read); company-specific news that drags a holding or candidate in sympathy is a potential add/entry if the business didn't change (the MU Nov 5 pattern). Use the scan's RIPPLES block and market_map neighbours to find who is exposed, then the desks and primary sources to size the effect. Never trade on a sympathy move alone.
