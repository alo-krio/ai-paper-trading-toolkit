# AI paper-trading research toolkit

Tools an AI agent uses to run research-driven **paper** trading books: a whole-market relationship map, a "ripple" toolkit for news that spreads across linked companies, an anticipation engine that compares prediction-market odds with our own forecasts, intraday opportunity boards, free news/halt/crowd-chatter feeds, a creator-call scorer, and the backtests that decided which ideas to keep.

> **Paper trading and research only.** Nothing here is investment advice, and nothing places real trades. Several studies in this repo exist precisely because popular strategies failed out of sample.

See [TOOLS.md](TOOLS.md) for the full inventory.

## What's interesting here
- **Market map** (`market-brain/market_map.py`): ~1,650 US stocks linked by co-movement, shared news and industry; its top-6 neighbors moved almost twice as much as plain industry peers on catalyst days.
- **Ripple event study** (`investing-24hour-agent/project/research/ripple_study/`): which linked stocks follow a leader's news, which fade, and why the actual headline matters.
- **Anticipation engine** (`scripts/anticipate.py`): event calendar + Polymarket odds + our own probability, logged and Brier-scored. Backtest on 1,498 resolved earnings markets: odds are calibrated; the surprise, not the odds level, drives the reaction.
- **Window tests** (`research/window_tests/`): five well-known day-trading ideas tested in a two-window (10:00 / 3:30 ET) setup, net of costs, 2023-2026 out of sample. All five failed, which is the point.
- **Feeds** (`market-brain/sources/feeds.py`): Nasdaq halts, a headline relay and Reddit mention spikes, with failed fetches reported as UNKNOWN.

## Setup
```bash
git clone <this repo> && cd ai-paper-trading-toolkit
python3 tools/set_root.py "$(pwd)"          # rewrite hard-coded paths to your clone
pip install -r requirements.txt
export APCA_DATA_KEY_ID=...  APCA_DATA_SECRET_KEY=...    # Alpaca market data (a free paper account works)
export PERPLEXITY_API_KEY=...                             # optional: LLM headline classification
export FIRECRAWL_API_KEY=...                              # optional: Polymarket via Firecrawl Alexandria
export SEC_USER_AGENT="Your Name you@example.com"         # required by SEC EDGAR
sh _platform/py.sh market-brain/market_map.py build
python3 market-brain/market_map.py neighbors NVDA
```
Most scripts write their outputs (data/, book/, shadow/) next to themselves; those folders are git-ignored.

## Layout
```
_platform/                      py.sh (runs Python with your env keys), alex.sh (Firecrawl), DATA_SOURCES.md
market-brain/                   market map, ripple toolkit, research memory, desks, world pulse, sources/feeds
investing-24hour-agent/project/ scripts/ (the two-window trader's tools) and research/ (studies)
docs/                           write-ups
tools/set_root.py               path rewrite after cloning
```

## License
MIT. Data you pull through these tools stays subject to each provider's terms.
