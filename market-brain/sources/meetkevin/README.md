# Meet Kevin feed (shared source for all three books)

What: Kevin Paffrath's YouTube channels (main + clips, several uploads a day) and his "Daily Digest" email (Kevin@meetkevin.com, your Gmail).
Files: videos.csv (every upload seen), emails_raw.json (digest bodies, first ~2.5k chars), calls.csv (his explicit calls), calls_scored.csv, latest.md (rolling notes, newest on top).
Refresh: the "Meet Kevin feed" automation runs every weekday at 7:30 AM ET, before the 24H premarket digest.

## How the books may use it
1. NARRATIVE AND CALENDAR. He is fast on retail-facing narratives (Jensen/Nvidia board, Fed hike pricing, Iran deal, Trump trades) and names dates (e.g. Nvidia general counsel House testimony Dec 2). Use him to find what to check, then verify with primary sources. Never trade on his claim alone.
2. CROWD SENTIMENT. He has a very large retail audience. His calls describe where the retail dip-buying money is leaning. Treat his strong conviction as positioning information, not edge.
3. DISAGREEMENTS ARE THE SIGNAL. Where he differs from the market (e.g. Nov 17: he puts Jensen's return at ~40% vs Polymarket 11%), log it in data/anticipate/forecasts.csv as a "kevin" forecast and score it. Our Polymarket backtest found the market calibrated; his number has to earn its weight.
4. NOT FOR: buy decisions by itself, price lines/"breakout" levels as triggers (24H rule: no technical triggers), or as a substitute for the filing, transcript or data.

## Track record (scored 2026-11-17, calls Oct 2 - Nov 15, entry = next open)
28 explicit calls, 28 of 28 bullish (no shorts or sells). 5-day excess vs QQQ +0.47% (hit 50%); to date excess +1.16% (hit 57%); raw 5-day mean -1.1% while the market fell.
Best: LLY Oct 26 (+20% vs QQQ), AAPL Oct 2 (+18%), AMD Nov 4 under-$520 line (+15%), TLT floor calls (+7 to +9%), MSFT target hit.
Worst: NBIS "about to break out" Oct 8 (-40% vs QQQ, -53% max drawdown), NVDA "0.65 PEG cheap" Oct 20 (-21%), ENPH floor (-15%), MRVL dip (-13%).
Read: no reliable short-term edge beyond QQQ; permanently bullish; his best calls were quality/defensive (LLY, AAPL, TLT) and his worst were high-beta AI dips. Re-score weekly; change the weight only when n >= 50 and the hit rate moves.
