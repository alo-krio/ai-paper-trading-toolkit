# Overnight Momentum backtest (2026-11-12) | PAPER/RESEARCH ONLY

Nothing traded. No book, sleeve, scheduled task or bakeoff.py was touched. Window follows the standing rule (last 3 years only).

## Verdict (plain)
**No live sleeve as specified.** The overnight effect in momentum names is real and large *gross* (top-10 12-1 momentum earned ~17.7 bp per night, a 48.8% CAGR from the close-to-open leg alone, while the open-to-close leg of the same names was roughly flat at -0.4% CAGR). But the trade is only "overnight" if every name is sold at the open and bought back at the close every day. That costs 10 bp of the whole book per night, about **25% a year**. At the stated 0.05% per side, the version you can actually execute nets **15.8% CAGR, Sharpe 0.64, max drawdown -34.7%**. That is worse than simply holding SPY (21.5% CAGR, Sharpe 1.34, max drawdown -18.8%) on every measure.

The headline "cost only on names that change" number (46.3% CAGR, Sharpe 1.41) is **not an executable overnight strategy**. If you don't sell a continuing name at 9:45, you hold it intraday, so you are really running the close-to-close momentum book. That book returns about the same (45.8% CAGR after costs) but with a -49% drawdown and a Sharpe of 1.06. That is a plain momentum sleeve, not an overnight edge.

What would change the verdict: the edge breaks even at about 8.8 bp per side. At realistic MOC/MOO-auction costs for large S&P names (1 to 2 bp per side), it nets 35 to 42% CAGR with a Sharpe of 1.1 to 1.3 (table below). So the deciding fact is your **real** per-side cost at 9:45 and 3:45 on Alpaca. That needs to be measured on paper fills before any sleeve, along with the gap between the open-auction price and 9:45 (not modelled here). If paper fills show 2 bp per side or less, (C) is the variant to shadow first.

## Setup
- **Data:** `data/hist/wide_daily.npz` (Alpaca SIP daily, `adjustment=all`, so splits and dividends are adjusted the same way for opens and closes). It ends 2026-10-26, so it was extended to 2026-11-11 with a fresh pull of the same feed and adjustment (`research/overnight_momentum/tail.parquet`, 520 current S&P members plus SPY). Older history was rescaled to the new adjustment basis for the 69 symbols whose basis changed on the overlap.
- **Universe:** point-in-time S&P 500 membership (fja05680), *including names later removed or delisted*. This means there is **little survivorship bias**. 99.98% of members had data on each day, and no picked name was missing its next open. Caveat: the membership file's last snapshot is 2026-08-18, so any index changes after that are not reflected.
- **Window:** decisions from 2023-11-13 to 2026-11-10 at the close, exits from 2023-11-14 to 2026-11-11 at the open. That is 751 sessions (2.995 years).
- **Signal at close t:** 12-1 momentum = C[t-21]/C[t-252] - 1. Filters: close >= $10 and 20-day average dollar volume >= $50M (median of 493 eligible names per day).
- **Rules:** top 10, equal weight at 10% each. Enter at close t (proxy for 3:45) and exit at the open of t+1 (proxy for 9:45).
- **Variants:**
  - (A) top-10 12-1 momentum.
  - (B) 60-day beta to SPY >= 1.5 *and* 12-1 momentum > 0, then the top 10 by momentum. This is the simpler of the two options (median of 45 qualifying names, so the book was always full).
  - (C) the same as A, but only when SPY's close is above its 200-day moving average (invested 92.8% of days).
- **Costs:** 0.05% per side.
  - "Changes only" charges 0.05% × sum|Δw| (both the buys and the sells of names that change).
  - "Full round-trip" charges 0.10% × exposure every night.
- **Sharpe:** daily, annualised with √252, risk-free rate 0. Win rate and average are per invested day.

## Main results (whole window, net unless labelled gross)
| Series | CAGR | Total | Sharpe | Max DD | % days inv | Win/day | Avg/night |
|---|---|---|---|---|---|---|---|
| **A** overnight, cost on changes only (spec, not executable) | 46.3% | 212.8% | 1.41 | -30.6% | 100% | 57.7% | 17.0 bp |
| **A** overnight, full daily round-trip (executable) | 15.8% | 55.2% | 0.64 | -34.7% | 100% | 54.1% | 7.7 bp |
| A overnight gross | 48.8% | 228.6% | 1.46 | -30.4% | 100% | 58.5% | 17.7 bp |
| A intraday leg gross (open to close, same picks) | -0.4% | -1.1% | 0.16 | -37.7% | 100% | 52.2% | 2.3 bp |
| A close-to-close gross | 48.2% | 225.1% | 1.10 | -48.8% | 100% | 57.1% | 19.9 bp |
| A close-to-close, cost on changes (hold-through) | 45.8% | 209.4% | 1.06 | -49.1% | 100% | 57.1% | 19.2 bp |
| **B** overnight, cost on changes only | 39.6% | 171.6% | 1.21 | -28.8% | 100% | 57.9% | 15.3 bp |
| **B** overnight, full daily round-trip | 10.7% | 35.7% | 0.48 | -33.1% | 100% | 54.3% | 6.1 bp |
| B intraday leg gross | -1.4% | -4.1% | 0.14 | -39.7% | 100% | 52.2% | 2.1 bp |
| B close-to-close gross | 40.1% | 174.7% | 0.95 | -49.2% | 100% | 56.9% | 18.0 bp |
| **C** overnight, cost on changes only | 46.0% | 210.5% | 1.47 | -30.6% | 92.8% | 58.2% | 18.1 bp |
| **C** overnight, full daily round-trip | 17.5% | 62.2% | 0.71 | -34.7% | 92.8% | 54.8% | 8.7 bp |
| C intraday leg gross | -11.0% | -29.6% | -0.22 | -45.5% | 92.8% | 51.4% | -2.9 bp |
| C close-to-close gross | 32.0% | 129.9% | 0.87 | -48.8% | 92.8% | 56.2% | 15.9 bp |
| SPY buy-and-hold | 21.5% | 79.0% | 1.34 | -18.8% | 100% | 56.7% | 8.2 bp |
| SPY overnight-only gross | 15.6% | 54.6% | 1.56 | -15.9% | 100% | 59.4% | 6.0 bp |
| SPY overnight-only, 0.1%/night | -10.0% | -27.1% | -1.05 | -29.7% | 100% | 48.3% | -4.0 bp |
| SPY intraday-only gross | 5.0% | 15.8% | 0.44 | -13.1% | 100% | 53.3% | 2.3 bp |

**Turnover cost drag per year:**

| Variant | Changes only | Full daily round-trip |
|---|---|---|
| A | 1.65% | 25.1% |
| B | 1.89% | 25.1% |
| C | 1.58% | 23.3% |

**Overnight vs intraday split (A):** the overnight leg is about 89% of the close-to-close sum of daily returns (C: 118%, because the intraday leg was negative). Overnight-only also cuts the max drawdown from about -49% to about -30%. The losses of momentum names are concentrated intraday.

## Per year (net; 2023 is the stub from Nov 13 to Dec 31)
| Series | 2023 stub | 2024 | 2025 | 2026 YTD |
|---|---|---|---|---|
| A overnight, changes-only cost | 2.3% | 59.1% | 36.8% | 40.5% |
| A overnight, full round-trip | -0.5% | 26.0% | 8.3% | 14.3% |
| A intraday leg gross | 6.3% | -17.6% | 8.5% | 4.1% |
| A close-to-close gross | 9.2% | 33.8% | 50.9% | 47.4% |
| B overnight, changes-only cost | 4.4% | 40.2% | 32.9% | 39.7% |
| B overnight, full round-trip | 1.5% | 11.1% | 5.8% | 13.6% |
| C overnight, changes-only cost | 2.3% | 59.1% | 45.3% | 31.3% |
| C overnight, full round-trip | -0.5% | 26.0% | 19.8% | 8.1% |
| SPY buy-and-hold | 8.4% | 24.9% | 17.7% | 12.3% |
| SPY overnight-only gross | 3.2% | 23.8% | 8.3% | 11.7% |

(Per-year Sharpe and drawdown for every series are in `research/overnight_momentum/results.json`.)

## Cost sensitivity, executable full daily round-trip (the only lever that matters)
| Per side | A CAGR / Sharpe | B CAGR / Sharpe | C CAGR / Sharpe |
|---|---|---|---|
| 1 bp | 41.5% / 1.30 | 35.3% / 1.11 | 41.6% / 1.36 |
| 2 bp | 34.6% / 1.13 | 28.7% / 0.95 | 35.1% / 1.20 |
| 3 bp | 28.0% / 0.97 | 22.4% / 0.80 | 29.0% / 1.03 |
| 5 bp (spec) | 15.8% / 0.64 | 10.7% / 0.48 | 17.5% / 0.71 |

## Robustness notes
- **Fat tails, but not a fluke.** The median night for A is +20 bp, so the edge is broad. Gross CAGR still drops from 48.8% to 30.0% without the best 5 nights, 17.3% without the best 10, and about 1% without the best 20 (out of 751). The best night was +10.9% on 2026-07-29. Big nights are mostly earnings gaps, which this strategy is deliberately exposed to.
- **Concentrated in one theme.** The most-held names across 751 sessions were PLTR 340, WDC 323, NVDA 314, VST 305, MU 292, STX 271, AVGO 214, NRG 213, HWM 209 and AXON 191. That is AI hardware, memory and power. Three years is a single momentum regime, and that regime has been kind to this cluster.
- **B (high beta) was worse than A on every line.** C (the SPY > 200DMA filter) added a little Sharpe overnight but hurt in 2026 YTD. Neither is a clear improvement, and no tuning was done beyond the three specified variants.
- **Fill proxies:** the official open and close stand in for 9:45 and 3:45. A real share of the overnight return prints in the opening auction and the first 15 minutes. Selling at 9:45 instead of the open could add to or subtract from returns, and this backtest cannot tell which. `data/hist/fills.parquet` has 9:45 and 15:45 prices only for pairs from earlier backtests. Pulling them for these picks (`pull_history.py fills`) is the next check if this goes further.
- **Simplifications:** equal weight is reset each close (the rebalancing cost of weight drift is ignored), and there are no borrow or short legs.

## Round trips over 29 sessions (the 40-trade bar)
| Variant | Changes only: avg new names per session | Changes only: round trips per 29 sessions | Last 29 sessions | Full daily round-trip |
|---|---|---|---|---|
| A | 0.66 | ~19 | 16 entries + 16 exits | 10 × 29 = **290** (580 orders) |
| B | 0.76 | ~22 | 17 + 17 | 290 |
| C | 0.64 | ~18 | 16 + 16 | ≤290 |

The executable overnight version clears a 40-trade bar easily. The hold-through version (~19 round trips, ~38 orders) only clears it if each side counts as a trade.

## Files
- `research/overnight_momentum/backtest.py`: the backtest (run with `research/backtest/.venv/bin/python`)
- `research/overnight_momentum/pull_tail.py`: the data-only tail pull (2026-09-01 to now, current members + SPY)
- `research/overnight_momentum/tail.parquet`: the tail bars
- `research/overnight_momentum/results.json`: every metric, including per-year Sharpe and drawdown
- `research/overnight_momentum/daily_{A,B,C}.csv`: per-session picks, legs, turnover and net returns
