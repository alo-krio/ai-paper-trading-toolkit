# 3-year backtest: rsi2 (Dip Buyer) and spymom (Power Hour), 2026-11-12

RESEARCH ONLY. This is informational. Nothing in `scripts/bakeoff.py`, `sleeves/`, the book or the scheduled tasks was changed. The bake-off rules stay frozen. The 3-year window follows the owner's standing rule of 2-3 years only. All runs are net of costs at 0.05% per side, and again at 0.10% per side (measured paper fills are about 8 bp per side median). The cost model is the same as `bakeoff.open_pos/close_pos/hval`.

**Window:** sessions 2023-11-13 to 2026-11-11 (752 sessions). The base is the 2023-11-10 close.
**Benchmark:** SPY buy-and-hold, total return (adjusted), **+78.8%**: CAGR +21.5%, Sharpe 1.34, max DD -18.8%.
**Scripts:** `research/bt3y/` (`pull.py`, `common.py`, `rsi2_bt.py`, `rsi2_windows.py`, `spymom_bt.py`, `check_rsi.py`, `tables.py`). Outputs go to `research/bt3y/out/` and data to `research/bt3y/data/`. Other agents' subfolders `orb/`, `runup/` and `main/` sit next to these and are not part of this study.

## Verdicts

- **spymom (Power Hour): will not pass. FAIL on all three legs.** It averages 7.8 trades per 29 sessions. No 29-session window in 3 years reached 40 (max 21, median 7). The gross edge is zero (-0.0001% per trade before costs, direction hit rate 49.5%), so each trade loses about the round-trip cost. Results: -15.2% at 5 bp and -27.8% at 10 bp, with every calendar year negative. Return per unit of exposure is negative.
- **rsi2 (Dip Buyer): unlikely to pass, roughly a 1-in-3 to 1-in-4 shot, and a coin flip on the trade count alone.** Fresh 29-session sleeves started on every second session of the 3-year window, using the replicable full rules:
  - Today's universe (5 bp): 33% pass all three legs.
  - Point-in-time S&P 500 universe (5 bp): 29% pass.
  - At 10 bp: 30% and 23%.
  - Median trades per window: 43 (today's universe) and 40 (S&P 500). That is **before** the headline, supply, M&A and 8-K filters, which can only remove entries. Even the best case sits right on the 40-trade line.
  - Median 29-session net return: +0.6% (today) and +1.4% (S&P 500). SPY's median over the same windows was +2.4%.
  - Over 3 years, the full rules never beat SPY on return per exposure.

## Design issue found (not changed; the rules are frozen)

**The rsi2 drawdown breaker never lets go.** It blocks entries for 5 sessions and then re-checks against the *old* peak. A sleeve sitting in cash cannot recover, so once equity is more than 10% below its peak the sleeve never trades again. In the 3-year run this happened in late July / early August 2024. The full rules then took **zero trades in 2025-2026** (last entry: 2024-08-01 on today's universe, 2024-08-02 on the S&P 500 universe). The code does exactly this (`market_gates`: the peak is never reset, `cb` clears after 5 sessions and immediately re-triggers). Inside the 29-session bake-off this only matters if the sleeve falls 10%. In historical 29-session windows that happened in a small minority of cases: the 10th-percentile window return was -8.7%. If it does happen, rsi2 is finished for the rest of the test. **Flag for after Dec 23:** reset the peak on re-arm, or measure from the equity at lock-out.

Because of this lock, the 3-year "full" line below is mostly 9 months of trading followed by cash. The "full minus breaker" line is the fair 3-year read on the filters.

## rsi2: 3-year results

How the rules were built: the 15:45 entry price and the 15:30 pm-exit price are the daily close, and the 9:45 am-exit price is the daily open. On half days there are no pm exits or entries, as in the README. Daily SIP bars use adjustment=all, which plays the role of the README's dividend-adjusted closes. RSI2 and ATR14 were checked against the extracted `bakeoff.rsi`/`bakeoff.atr` source and match exactly (`check_rsi.py`: max difference 0).

**What each line is:**
- **core:** base screen ($20M ADV, close >= $4, 210+ bars) + RSI2 < 10 + price > 200DMA, lowest RSI2 first, 6 slots at 1/6 each, plus the exits (> 5-day SMA, RSI2 > 70, 5 sessions, 3×ATR stop). No gates and no per-name filters.
- **coregates:** core + the SPY < 200DMA gate + the 10% breaker.
- **full:** every replicable rule: both gates, $10/$50M liquidity, earnings (entry block plus force-exit), cooldown, news-shock, sector ETF < 200DMA, sector 3-day selloff, relative dip, sector cap of 2, ex-dividend ±2, the LITE deal-target list, YTD < -30% from Nov 1, and 60-day correlation > 0.8.

**Universes:**
- **today:** the live `rotate.universe()` list as dumped 2026-10-27 (data/hist/universe.csv). It has survivorship bias, because names that crashed and dropped out are missing.
- **sp500pit:** point-in-time S&P 500 membership (fja05680, includes names later delisted; last snapshot 2026-08-18 carried forward). This one is survivorship-free.

| run | total | CAGR | Sharpe | max DD | trades | /yr | /29 sess | win | payoff | avg net/trade | avg exposure | return/exposure |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| core, today, 5bp | +75.6% | +20.8% | 0.98 | -22.0% | 1282 | 430 | 49.4 | 64% | 0.67 | +0.295% | 81.7% | 0.93 |
| coregates, today, 5bp | +47.4% | +13.9% | 1.47 | -13.2% | 317 | 106 | 12.2 | 69% | 0.79 | +0.771% | 19.7% | 2.40 |
| **full, today, 5bp** | +1.8% | +0.6% | 0.11 | -16.7% | 286 | 96 | 11.0 | 64% | 0.59 | +0.065% | 19.1% | 0.09 |
| full minus breaker, today, 5bp | +17.3% | +5.5% | 0.38 | -21.7% | 1133 | 380 | 43.7 | 60% | 0.71 | +0.111% | 75.0% | 0.23 |
| core, today, 10bp | +41.7% | +12.4% | 0.65 | -25.7% | 1282 | 430 | 49.4 | 63% | 0.65 | +0.195% | 81.7% | 0.51 |
| coregates, today, 10bp | +39.9% | +11.9% | 1.29 | -14.4% | 317 | 106 | 12.2 | 67% | 0.80 | +0.670% | 19.7% | 2.02 |
| **full, today, 10bp** | +1.3% | +0.4% | 0.09 | -14.2% | 282 | 94 | 10.9 | 64% | 0.59 | +0.048% | 18.7% | 0.07 |
| full minus breaker, today, 10bp | -3.0% | -1.0% | 0.04 | -27.9% | 1133 | 380 | 43.7 | 59% | 0.69 | +0.011% | 75.1% | -0.04 |
| core, S&P PIT, 5bp | +41.8% | +12.4% | 0.79 | -23.8% | 1208 | 405 | 46.6 | 63% | 0.69 | +0.194% | 80.6% | 0.52 |
| coregates, S&P PIT, 5bp | +41.2% | +12.3% | 1.22 | -12.1% | 568 | 190 | 21.9 | 66% | 0.74 | +0.379% | 35.6% | 1.16 |
| **full, S&P PIT, 5bp** | +6.4% | +2.1% | 0.33 | -10.7% | 271 | 91 | 10.5 | 64% | 0.63 | +0.155% | 18.0% | 0.35 |
| full minus breaker, S&P PIT, 5bp | +38.9% | +11.6% | 0.82 | -14.7% | 1037 | 348 | 40.0 | 61% | 0.74 | +0.210% | 68.8% | 0.57 |
| core, S&P PIT, 10bp | +15.9% | +5.1% | 0.38 | -31.1% | 1208 | 405 | 46.6 | 62% | 0.67 | +0.094% | 80.6% | 0.20 |
| coregates, S&P PIT, 10bp | +30.4% | +9.3% | 0.99 | -11.3% | 565 | 189 | 21.8 | 65% | 0.72 | +0.296% | 35.3% | 0.86 |
| **full, S&P PIT, 10bp** | +1.7% | +0.6% | 0.11 | -12.0% | 271 | 91 | 10.5 | 63% | 0.61 | +0.055% | 18.0% | 0.09 |
| full minus breaker, S&P PIT, 10bp | +16.8% | +5.3% | 0.43 | -15.6% | 1037 | 348 | 40.0 | 60% | 0.72 | +0.110% | 68.8% | 0.24 |

**How to read these numbers:**
- **Return per exposure:** total return divided by average capital-weighted market-hours exposure, as in `bakeoff.score_new`. To pass, it has to beat SPY's total return over the same span, which is **0.788** here.
- **Over 3 years, only core on today's universe clears 0.788 (0.93), and that is the survivorship-biased universe.** Everything on the survivorship-free S&P universe falls short, and so do all full variants.
- **"coregates" looks good on return per exposure only because the breaker locked it in cash early:** in 2024-07 on today's universe, 2025-03 on S&P. Its trades stop there.
- Exits under full minus breaker, today, 5bp: 747 above the 5-day SMA, 334 time, 25 stop, 17 earnings, 10 RSI2 > 70. Average hold is 3.0 sessions.

**Per year (net, 5 bp; the 2023 stub is Nov 13 to Dec 29):**

| run | 2023 stub | 2024 | 2025 | 2026 YTD |
|---|---|---|---|---|
| SPY | +8.3% | +24.9% | +17.7% | +12.3% |
| core, today | +21.8% (61 trades) | +24.9% (441) | +20.4% (418) | -4.2% (362) |
| full, today | +10.2% (43) | -7.7% (243) | 0 (locked) | 0 (locked) |
| full minus breaker, today | +10.2% (43) | -0.4% (407) | +4.1% (340) | +2.6% (343) |
| core, S&P PIT | +8.5% (52) | +35.8% (433) | -2.6% (397) | -1.2% (326) |
| full, S&P PIT | +6.8% (37) | -0.4% (234) | 0 (locked) | 0 (locked) |
| full minus breaker, S&P PIT | +6.8% (37) | +12.4% (380) | +15.1% (308) | +0.5% (312) |

At 10 bp, every row loses roughly 4-10 points a year when there are 300-440 trades. Full minus breaker on today's universe goes to -6.9% / -1.6% / -3.1% for 2024 / 2025 / 2026. Full tables are in `research/bt3y/out/tables.md`.

**2026 YTD is flat to negative for every rsi2 variant, while SPY is up 12.3%.** The recent regime is the weakest of the three years for this signal.

### What the filters cost

- **Core vs full minus breaker:**
  - On today's universe the replicable filters cut 3-year return from +75.6% to +17.3% (5 bp), and average net per trade from +0.30% to +0.11%. Max DD stays about the same.
  - On the survivorship-free S&P universe they are roughly neutral on return (+41.8% vs +38.9%) but cut max DD (-23.8% to -14.7%) and lift Sharpe slightly (0.79 to 0.82).
  - Much of core's big edge on today's universe is likely survivorship: dips in names that are still in today's list recovered by construction.
- **Leave-one-out (full minus breaker, then also drop one filter; 5 bp; 3-year total return):**

| filter dropped | today universe | S&P PIT |
|---|---|---|
| (none: full minus breaker) | +17.3% | +38.9% |
| SPY 200DMA gate | +18.8% | +34.5% |
| liquidity $10/$50M | +9.1% | +41.1% |
| earnings block + force-exit | +63.6% | +21.2% |
| cooldown | +10.8% | +44.3% |
| news-shock | +33.7% | +36.4% |
| sector ETF 200DMA + 3-day selloff | +54.2% | +36.5% |
| relative dip | +39.6% | +44.6% |
| sector cap 2 | +20.3% | +53.8% |
| ex-dividend ±2 | +21.1% | +30.0% |
| YTD < -30% (Nov-Dec only) | +18.2% | +38.9% |
| correlation > 0.8 | +13.1% | +39.9% |

  Single-filter effects are mostly path noise: the earnings filter is -46 points on one universe and +18 on the other. Only one filter costs return on both universes: dropping relative dip added +22 points (today) and +6 points (S&P). It is also the filter that removes the most trades (+7% and +14% more trades without it, or about 3-6 more per 29 sessions), which matters for the 40 bar. No filter reliably earns its keep.

### rsi2: 29-session pass test (the bake-off's actual question)

A fresh sleeve was started every 2nd session from 2023-11-13 (362 windows). Breaker and peak start fresh, as in the bake-off. Each window was scored on the pre-registered bar.

| rules, universe, cost | pass all 3 | return/exposure > SPY | return > 0 | >= 40 trades | median trades (p90) | median return | beat SPY raw |
|---|---|---|---|---|---|---|---|
| full, today, 5bp | **33%** | 37% | 52% | 74% | 43 (48) | +0.6% | 35% |
| full, S&P PIT, 5bp | **29%** | 44% | 61% | 51% | 40 (44) | +1.4% | 39% |
| full, today, 10bp | **30%** | 34% | 48% | 73% | 43 (47) | -0.1% | 31% |
| full, S&P PIT, 10bp | **23%** | 32% | 56% | 51% | 40 (44) | +0.6% | 32% |
| core, today, 5bp | 46% | 49% | 63% | 98% | 46 (51) | +1.7% | 48% |
| core, today, 10bp | 40% | 43% | 56% | 98% | 46 (51) | +0.8% | 40% |

Seasonal analogs (windows starting about Nov 11-13), full rules, today's universe, 5 bp:
- 2024: -0.7% / +3.3% (43 and 45 trades).
- 2025: -9.4% (breaker hit, 20 trades) / +7.5% (42 trades).
- In other words, it can land on either side of the bar.

The headline, supply, M&A and 8-K filters can't be replicated. They can only remove trades: the live caveat says they "cost trades, by design." **That pushes the 40-trade leg below the 51-74% shown,** so the realistic pass odds are below the 23-33% in the table.

## spymom (Power Hour): 3-year results

How the rules were built: SPY 15-min SIP bars (raw), pulled fresh for 2023-10-01 to 2026-11-11 (782 sessions, 26 bars each).
- First half hour: the 9:30 bar open to the 9:45 bar close. ±0.25% sets the direction, inclusive (edge.IM_TH).
- Confirmation: the 15:00 open to the 15:15 close. Same sign or flat means 100% size; opposite sign means 50%.
- Trade: in at the 15:30 bar open, out at the 15:45 bar close (16:00). Long or short.
- The 7 half days were skipped (2023-11-24, 2024-07-03, 2024-11-29, 2024-12-24, 2025-07-03, 2025-11-28, 2025-12-24; confirmed by after-13:00 volume share < 10%).
- 15-min bars are the same as the bake-off's 5-min endpoints (the 9:55/15:25/15:55 closes equal the 9:45/15:15/15:45 15-min closes).
- FOMC days trade normally, as in the rules.

| cost | total | CAGR | Sharpe | max DD | trades | /yr | /29 sess | win | payoff | avg net/trade | avg exposure | return/exposure |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5bp | -15.2% | -5.4% | -3.13 | -15.2% | 203 | 68 | 7.8 | 32% | 0.76 | -0.100% | 1.6% | -9.2 |
| 10bp | -27.8% | -10.3% | -5.33 | -27.8% | 203 | 68 | 7.8 | 16% | 0.68 | -0.200% | 1.6% | -16.9 |

- **Per year (5 bp):** 2023 stub -0.6% (3 trades), 2024 -2.9% (41), 2025 -6.3% (82), 2026 YTD -6.3% (77). At 10 bp: -0.9% / -5.9% / -12.2% / -11.9%.
- **Signal frequency:** only 27% of sessions have a first half hour of ±0.25% or more (median absolute move 0.13%).
- **Trade breakdown:** 103 longs and 100 shorts, both averaging -0.10% net. 119 trades were full size and 84 half size; both lose the cost.
- **Gross:** -0.0001% per trade. The last-30-minute direction matched the first-30 on 49.5% of signal days.
- **29-session windows (724 rolling):** 0% reach 40 trades, 8% are positive, 0% pass.

This is a pure cost drag on zero edge. The Gao-Han-Li-Zhou effect is not present in SPY over 2023-2026 at this threshold.

## What could not be replicated (skipped)

- **rsi2 entry filters:**
  - Benzinga keyword headlines (6.14).
  - Supply headlines, offerings and S&P deletions (6.15).
  - M&A headlines (6.11). The static LITE list is applied.
  - SEC 8-K items (6.16).
- **rsi2 holding exits:** the headline and 8-K exits (8.3).
- **IPO lockup (6.10):** not modelled, because it is a no-op here. The 210-bar base screen means a name has traded about 300+ calendar days, so an IPO + 180-day lockup can never fall within ±5 sessions.
- **Universe screen:** the $2B market-cap leg of `rotate.universe()` can't be rebuilt historically. The $20M/$50M ADV floors are applied.
- **Price proxies:** daily open and close stand in for the 9:45 / 15:30 / 15:45 IEX prints. Missing-print carry-over is not modelled. spymom uses SIP rather than IEX bars.
- **Earnings report times:** historically almost always "time-not-supplied", so they are treated as pre-market, as the live rules do. The calendar after 2026-10-27 was pulled fresh (data/earnings_ext.csv).
- **Ex-dividend dates:** Alpaca corporate actions as listed today (data/divs.csv).
- **Other simplifications:** the circuit-breaker peak is updated at the open mark and at the entry window. Exposure counts market minutes as in `score_new`. The risk-free rate is 0 in Sharpe.

## Survivorship

- The "today" universe is survivorship-biased (today's ~1,800 live names only). It flatters rsi2, most visibly in core: +75.6% vs +41.8% on point-in-time S&P members.
- The S&P PIT run includes members that were later removed or delisted (pulled by their historical tickers). Sector is unknown for removed names ("Other", using SPY as the sector ETF).
- spymom trades only SPY, so survivorship does not apply.

## Data pulled for this study (research/bt3y/data)

- `daily.parquet`: Alpaca SIP daily bars 2022-06-01 to 2026-11-11, adjustment=all, 1,842 symbols (the live universe + 33 ETFs + every S&P 500 member since 2023-01). Pulled fresh so all adjustments are as of one date. The older store (data/hist) ends 2026-10-26.
- `spy15.parquet`: SPY 15-min SIP bars, raw, 2023-10-02 to 2026-11-11.
- `earnings_ext.csv`: Nasdaq calendar 2026-10-27 to 2026-11-20 (added to data/hist/earnings.csv).
- `divs.csv`: Alpaca cash dividends 2022-06 to 2026-11 for those symbols.

Reproduce with `research/backtest/.venv/bin/python research/bt3y/rsi2_bt.py all`, then the same script with `ablate`, then `rsi2_windows.py full_today_5bp,...`, `spymom_bt.py` and `tables.py`.
