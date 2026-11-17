# Tool inventory

Every tool in this repo, what it does and how to run it. All of it is research and paper trading only: nothing here places real trades.

Run Python through `_platform/py.sh` when a tool needs market data (it checks your API keys are set). Paths assume the layout in this repo; run `python3 tools/set_root.py "$(pwd)"` once after cloning.

## Shared market brain (`market-brain/`)

| Tool | What it does | Run |
|---|---|---|
| `market_map.py` | Whole-market relationship map for ~1,650 US stocks: co-movement, shared news, industry links, clusters. Answers "who moves with X?" | `py.sh market-brain/market_map.py build`, then `neighbors NVDA`, `cluster NVDA`, `stats`, `validate` |
| `MARKET_MAP.md` | Method, weights and validation of the map (top-6 map names moved +2.12 vs +1.15 for plain industry peers on catalyst days) | read |
| `RIPPLE_TOOLKIT.md` | How to trade "ripples": when news on one company moves suppliers, customers, competitors. Rules from the event study | read |
| `brain.py` | Shared research memory (SQLite + embeddings): store facts with sources, recall before re-researching | `brain.py fact ...`, `brain.py recall "question"` |
| `desks.py` | Registry and prompt template for on-demand research "desks" (an AI helper per industry or event) | `desks.py list`, `desks.py create <slug> --kind event` |
| `pulse.py` | World pulse: what is moving in markets and the news, and which desks are needed | `pulse.py --top 12` |
| `sources/feeds.py` | Free fast feeds: Nasdaq trading halts, FinancialJuice headline relay, Reddit crowd chatter (ApeWisdom) with mention spikes | `feeds.py halts --today`, `feeds.py headlines --min 120`, `feeds.py chatter --log` |
| `sources/SOURCES.md` | Registry of information sources, what each is good for, and the evidence on social-media chatter | read |
| `sources/meetkevin/ingest.py` | Pulls new uploads from a YouTube creator's RSS feeds (example: Meet Kevin) | `python3 ingest.py new` |
| `sources/meetkevin/score_calls.py` | Scores a creator's explicit stock calls against QQQ (next-open entry, 5-day and to-date excess, drawdown) | `py.sh score_calls.py` |

## 24-hour reactive trader (`investing-24hour-agent/project/scripts/`)

A paper book that trades in two windows (about 10:00 and 3:30 ET) with short holds.

| Tool | What it does |
|---|---|
| `intraday_scan.py` | Boards for each window: CATALYST, MOMENTUM, OVERSOLD, OVERBOUGHT, REPORTS TONIGHT, and a RIPPLES block (leader headline, linked names, lagging vs already-followed) |
| `anticipate.py` | Anticipation engine: event calendar, Polymarket odds, our own probability, edge and expected value per event; forecast ledger and Brier scoring; backtest of odds vs stock reactions |
| `plays.py` | Playbook learning engine: logs every signal for each named play (traded or not) and scores it at 1/3/5 days, so plays earn or lose weight |
| `rotate.py` | The paper book engine: mark, review, sell, buy; conviction-based sizing; risk levels; JSON "why" records for every buy |
| `trade_review.py` | Grades every closed trade: return, excess vs SPY, best high and close after entry, what a target would have captured |
| `story_score.py` | Joins closed trades to their buy reason to learn which kinds of stories work |
| `postmortem.py` | Daily post-mortem on any day the book lags the market |
| `scoreboard.py` | One scoreboard from all logs |
| `screen.py` | Nightly S&P 500 and sector ETF screen with breadth |
| `macro_check.py`, `news_check.py`, `pplx_decide.py` | Ask an LLM (Perplexity) to classify macro and company headlines: about this company? good or bad? first-order? |
| `alpaca_data.py`, `prices.py`, `ohlcv.py` | Market data helpers (Alpaca IEX/SIP, Nasdaq), with explicit DATA WARNINGs: a failed fetch is UNKNOWN, never evidence |
| `mirror_plan.py`, `alpaca_mirror.py` | Plan the orders that make an Alpaca PAPER account match the book |
| `bakeoff.py`, `edge.py`, `orb.py`, `orb_gap_shadow.py`, `runup_spy_shadow.py`, `sidelog.py`, `aicall.py` | Shadow tests and a multi-sleeve bake-off of mechanical strategies (logged, never traded) |
| `morning.py`, `nightly.py` | Morning red-flag check and cheap nightly numbers |

## Research (`investing-24hour-agent/project/research/`)

| Study | Question | Headline result |
|---|---|---|
| `ripple_study/` | How do linked stocks react to a big company's catalyst, and does the actual news matter? | Sympathy followers fade; laggards drift only after good news; about two-thirds of the ripple happens before the open |
| `window_tests/` | Do five published day-trading ideas work in a 10:00 / 3:30 two-window setup, net of costs, out of sample (2023-2026)? | No. Intraday momentum, stocks-in-play at 10:00, waiting 30-45 min, relative-strength buys and capitulation reversals all fail OOS |
| `earnings_runup/` | Do Nasdaq-100 stocks run up into earnings? | See report |
| `overnight_momentum/` | Does buying strong closers for the overnight gap work? | See report |
| `bt3y_*.md`, `v5_replay.py` | Three-year backtests of the bake-off sleeves and a rule replay | See reports |

## Docs (`docs/`)

Write-ups of the anticipation engine, the market map, the ripple event study and the window tests.

## Not included (on purpose)

Live book state, trade ledgers, account data, cached market data, private emails and anything personal. Credentials are read only from environment variables.
