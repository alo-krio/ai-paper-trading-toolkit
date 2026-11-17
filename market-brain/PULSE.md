World pulse: what is moving in markets and the world, where to look, and which desks are needed (owner, Nov 16, 2026).
PAPER ONLY. Information only: never a trade signal.

Owner: "you should have the proactivity and ability to call upon new helpers as broad market news evolves. This also
means that you need to have a pulse of what's going on in the world to know where to look and what new helpers you
might need. Build a system around that."

Each run:
 1. TAPE: every US-listed stock from the Nasdaq screener in one call (price change, market cap, sector, industry):
    market-cap-weighted sector and industry moves, big-cap movers (>= $10B, |move| >= 4%), breadth; plus cross-asset
    ETF proxies (rates, credit, dollar, oil, gold, bitcoin, small caps, vol) via the book's price module.
 2. NEWS: broad feeds (CNBC top/markets/economy/tech/world/politics, MarketWatch, FT markets) + Google News queries on
    macro themes. Everything goes through the brain cache (3h), so repeat runs are cheap.
 3. TOPICS: headlines are embedded and clustered into topics; each topic gets entities, sources, novelty (share of
    headlines never seen before), market link (moves of its entities/industries), book reach (ripple links to holdings
    and candidates) and a heat score. Topics are stored daily, so the pulse knows what is NEW, RISING or FADING.
 4. COVERAGE: each hot topic is matched against the desk registry (desks.py). Output: COVERED by <desk> /
    UNCOVERED (suggested desk with a create command). Also flags industries moving hard that no desk watches.
Output: /home/user/workspace/investing-3-6month-agent/project/data/pulse/YYYY-MM-DD-HHMM.md (ingested by the brain).
Usage: python3 /home/user/workspace/market-brain/pulse.py [--top 12] [--no-tape]

