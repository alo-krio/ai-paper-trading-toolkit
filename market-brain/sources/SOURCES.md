# Information sources for the three paper books (from the owner's Day Trading Resource Guide, Nov 17, 2026)

| Guide item | What we use | Status |
|---|---|---|
| Economic calendar (Forex Factory) | anticipate.py calendar (Forex Factory feed) | live |
| CME FedWatch | Polymarket Fed markets in anticipate.py odds; FedWatch page is not machine-readable for us | proxy |
| Trading halts (Nasdaq Trader) | `python3 feeds.py halts --today` (all US listings, T1/T2 news halts, LULD pauses) | live, new |
| SEC EDGAR 8-K/S-1/offerings | rsi2/bakeoff 8-K checks; EDGAR full-text via curl with SEC_USER_AGENT | live |
| Real-time news (Benzinga Pro) | Alpaca news API is Benzinga-sourced (one symbol per article): intraday_scan.py, premarket.py | live |
| Squawk / headline relay (FinancialJuice, @DeItaone) | `python3 feeds.py headlines --min 120` (FinancialJuice RSS; rate-limits hard, cached 2 min; X accounts not accessible) | live, new, flaky |
| Options flow (Unusual Whales) | not available (paid); skip | none |
| Earnings calendar | anticipate.py calendar + finance tools | live |
| Creators | Meet Kevin feed (sources/meetkevin) scored; day-trading YouTubers not ingested: their small-cap gap-and-go style has no independent evidence and doesn't fit two fixed windows | partial |
| Reddit crowd attention (r/wallstreetbets, r/stocks, ...) | `python3 feeds.py chatter --log` (ApeWisdom mention counts + 24h spikes), logged each 24H window to chatter/snapshots.csv for a later test | live, new |
| r/RealDayTrading methods | Real Relative Strength vs SPY and 'wait 45 minutes' under test (window_tests Test 3-4); 15 tips mostly already in our rules (no averaging down, flat into earnings without edge, size so no single trade causes anxiety) | testing |
| Practitioner frameworks (Lance Breitstein capitulation, SMB 'stocks in play') | Window tests 2 and 5; if they hold, they refine the B_flush and catalyst plays | testing |
| Strategy evidence | research/window_tests/REPORT.md (Nov 17): intraday momentum (close window), stocks-in-play ORB (morning window), waiting-30-min test | running |

Rules: relays and creators are VERIFY until a primary source confirms. Failed feeds are UNKNOWN, never "no news".

## Why we watch chatter, and how
Research on r/wallstreetbets: following its buy/sell recommendations produced no alpha at horizons from 1 day to 1 year; the forum is mostly REACTIVE (bullish posts cluster at price peaks, then returns reverse); positions opened at peak WSB attention averaged -8.5%. Kevin's 28 calls showed no edge vs QQQ either.
So: chatter tells us WHAT the crowd is fixated on (narratives, fear, euphoria) and WHERE retail money is crowded. Uses: (1) a name at peak chatter after a run is chase/fade risk; (2) despair chatter on a boring large cap with no real news is a capitulation candidate (Breitstein rubric), never a buy until it turns; (3) narrative map for the tape thesis. Never a buy reason by itself.
