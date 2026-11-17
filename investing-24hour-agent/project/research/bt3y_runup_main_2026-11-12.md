# 3-year backtest: Earnings Run-Up sleeve and Main 24h book (v4.4), Nov 2023 to Nov 2026 (RESEARCH ONLY)
Built 2026-11-12. This was informational only. Nothing under `scripts/`, `sleeves/`, `book/`, `control/` or the scheduled tasks was touched, `data/runup_release_times.json` was only read, and no orders were placed. Costs are per side on traded value. 5 bp is the bake-off rule; 10 bp is a stress case at our measured paper fills (median ~8 bp/side).

## Plain verdicts
- **Earnings Run-Up: the edge per trade looks real over 3 years, but passing its own bar in a 29-session window is roughly a 1-in-4 shot. The binding constraint is the trade count, not the edge.**
  - Over 3 years, net 5 bp: +53.9% total, +15.6% CAGR, Sharpe 1.57, max DD -10.4% at only ~23% average exposure.
  - 220 trades, average net +1.02%, average excess vs QQQ **+0.93% per trade** (t 2.7). At 10 bp: +0.83% (t 2.4).
  - Every calendar year had positive average excess. Taking every report unfiltered earns about nothing vs QQQ (+0.14%, week-clustered t -0.4), so the filters are doing the work.
  - The problem is the count. It averages 8.5 trades per 29 sessions, but in rolling 29-session windows the median is 6. Only 41% of windows reach 8 closed trades, and **25% pass both parts of the bar** (≥ 8 trades and positive excess).
  - The same Nov 12 to Dec 23 window in 2023, 2024 and 2025 gave 7, 5 and 8 trades, with positive excess each time.
  - **Likely verdict at Dec 23: FAIL on the trade count (≥ 8) more often than not, even though the per-trade read will probably be positive.** If it falls short only on the count, treat that as "inconclusive, keep running," not as evidence against it. That is a judgment call, not a rule change.
- **Main 24h book (v4.4): does not beat SPY over the last 3 years, and is collapsing in 2026. It would likely FAIL the bake-off bar (about 1 in 5 windows pass).**
  - Re-run from flat on Nov 13, 2023 (close fills, 5 bp): +32.7% total vs SPY +80.3%, CAGR +10.1% vs +22.2%, Sharpe 0.46 vs 1.39, max DD -39% vs -19%, beta 1.14.
  - At 10 bp: +11.9% total (+3.9%/yr).
  - 2026 to Oct 26: **-33.8% vs SPY +13.1%**.
  - Return per unit of exposure (+11.5%/yr) is about half of SPY's +22.2%.
  - In rolling 29-session windows it clears all three pass conditions 19% of the time (close, 5 bp) to 30% (15m, 5 bp). The 40-trade minimum alone is met in 64-73% of windows.

---

## (1) Earnings Run-Up (sleeve 5)
**Rules:** as in sleeves/README.md section 5 and `scripts/bakeoff.py` `runup()`, re-implemented on daily bars in `research/bt3y/runup/runup_bt.py`:
- **Entry:** 5 sessions before the last pre-report close. A lead of 4 is used after a half day, and 6 before one. No entries on half days.
- **Filters:**
  - Same-sector peers that reported in the last 10 sessions: average reaction > 0, with at least 2 peers.
  - Price above the 50DMA (49 prior closes plus price).
  - 20-day return ≥ QQQ's.
  - 10-day return ≤ +8%.
  - Beat in ≥ 3 of the last 4 quarters.
  - SPY prior close > 200DMA.
  - Price ≥ $10 and ADV ≥ $50M.
- **Book:** ranked by peer read-through, then RS. Max 5 positions at min(20% of equity, cash), max 2 per sector.
- **Exits:** at the last pre-report close. Stop at 2×ATR14, checked at the open and the close. Hold half through the report if beats are 4/4, peers ≥ +2% and the gain is ≤ +5%; that half exits at the next open.
- **Not replicated:** the headline and 8-K filters (no history). They only remove trades, so the live sleeve should trade a little less than this.

### Results (Nov 13, 2023 to Nov 11, 2026; 752 sessions)
| | net 5 bp/side | net 10 bp/side | SPY | QQQ |
|---|---|---|---|---|
| Total return | **+53.9%** | +47.3% | +78.8% | +85.6% |
| CAGR | +15.6% | +13.9% | +21.5% | |
| Sharpe (daily) | 1.57 | 1.41 | 1.34 | |
| Max drawdown | -10.4% | -10.8% | -18.8% | |
| Average exposure | 23% | 23% | 100% | |
| Return ÷ avg exposure (total) | +233% | +204% | +78.8% | |
| Closed round trips | 220 (73.7/yr) | 220 | | |
| Implied per 29 sessions (average) | 8.5 | 8.5 | | |
| Win % | 55.9% | 54.5% | | |
| Average net per trade | +1.02% (median +0.81%) | +0.92% | | |
| **Average excess vs QQQ per trade** | **+0.93%** (median +0.53%, 56% positive, t 2.70) | **+0.83%** (t 2.41) | | |
| Payoff (avg win ÷ avg loss) | 1.40 | 1.40 | | |
| Hold-through trades / stops | 46 / 23 | 46 / 23 | | |

### Per year (5 bp; 10 bp in brackets)
| Year | Trades | Return | SPY | Sharpe | Max DD | Avg net/trade | Avg excess vs QQQ/trade |
|---|---|---|---|---|---|---|---|
| 2023 (from Nov 13) | 8 | +3.5% (+3.3%) | +8.3% | 4.44 | -0.9% | +1.80% | +0.35% (+0.25%) |
| 2024 | 84 | +14.0% (+12.1%) | +24.9% | 1.48 | -5.1% | +0.84% | +0.83% (+0.73%) |
| 2025 | 59 | +4.4% (+3.2%) | +17.7% | 0.53 | -10.4% | +0.41% | +0.24% (+0.14%) |
| 2026 (to Nov 11) | 69 | +24.9% (+23.1%) | +12.3% | 2.45 | -5.3% | +1.66% | +1.70% (+1.60%) |

### Bake-off-sized windows (runup's own bar: ≥ 8 closed round trips AND average excess vs QQQ > 0)
- **Same calendar window in past years** (entries Nov 12 to Dec 23, closed trades; 5 bp):
  - 2023: 7 trades, +0.20% excess.
  - 2024: 5 trades, +0.58%.
  - 2025: 8 trades, +1.05%.
  - Only 2025 would have passed.
- **All rolling 29-session windows** (723; trades entered and exited inside the window):

| Read | Median trades | Windows with ≥ 8 trades | Windows with excess > 0 | Windows that pass |
|---|---|---|---|---|
| 5 bp | 6 | 41% | 60% | **25%** |
| 10 bp | 6 | 41% | 58% | 25% |
| 5 bp, S&P-only universe | 5 | 37% | 57% | 25% |

### Unfiltered baseline (take every liquid report: enter 5 sessions before L, exit at L, no stop, no caps)
| | 5 bp | 10 bp |
|---|---|---|
| Trades | 5,921 (~1,980/yr) | 5,921 |
| Win % | 54.4% | 53.3% |
| Average net per trade | +0.44% | +0.34% |
| Average excess vs QQQ | **+0.14%** (week-clustered t -0.39) | +0.04% (t -0.90) |
| Excess by year | 2024 +0.63%, 2025 -0.70%, 2026 +0.50% | |

The unfiltered run-up is roughly QQQ plus noise, which matches the Nov 11 study. The filtered book's +0.93% per trade is the selection: peers, trend, RS, beats and the market gate.

### Robustness and caveats (runup)
- **Survivorship:**
  - S&P 500 membership is point-in-time (`data/hist/sp500_hist_components.csv`; snapshot ends 2026-08-18 and is carried forward).
  - **Nasdaq-100 is today's list** (no history), so names added because they rallied are included.
  - Only 4 trades were Nasdaq-100-only names, but they averaged +6.7% (ALAB, ARM and others).
  - **S&P-only rerun:** +39.0% total, CAGR +11.7%, Sharpe 1.32, 208 trades, average excess **+0.77%** (t 2.32). At 10 bp: +0.67% (t 2.02). The edge survives with a smaller size.
- **Concentration:**
  - Dropping the best 5 trades cuts the average net to +0.56%; dropping the best 10 cuts it to +0.32%.
  - The best trades include DELL +30%, APP +19%, MRVL +19%, ALAB +18% and ARM +17%.
  - The edge is real but fat-tailed, so a 29-session sample is noisy.
- **Report timing:**
  - Benzinga results-headline timestamps (Alpaca news, the same patterns as `research/earnings_runup/fetch.py`) were matched directly for 1,242 of the 6,712 reports.
  - The Alpaca rate limit was shared with other jobs today. So for 5,262 reports I applied each company's usual timing: the modal Benzinga AMC/BMO over its matched quarters, used only when ≥ 75% consistent.
  - Leave-one-out, that habit matched the actual headline timing **96%** of the time.
  - 208 reports had neither and use the 2-sessions-before rule (7 trades).
  - Trades on direct timing averaged +0.48%, and on habit timing +1.22%. That gap is mostly a time split: direct matches are concentrated in the last year's NDX names.
  - Using the habit is not look-ahead in spirit (live uses the calendar's time), but it uses all quarters, including later ones.
- **Prices:** the 3:45 entry and 15:30 exit are proxied by the daily close, and the 9:45 stop/hold-through exit by the open (Alpaca SIP daily bars, adjustment=all). Real 15:30/9:45 fills will differ a little.
- **Report dates** are the realized Nasdaq calendar dates. Live uses the calendar 5 sessions ahead, and a few dates move.
- **Beat history** comes from the Nasdaq calendar surprise % (`data/hist/earnings.csv` + `research/earnings_runup/data/cal_new.csv`), not the earnings-surprise API. Quarters without a surprise value are skipped.
- **Filter hit rates:** 6,009 candidates were evaluated. First blocks: peers too few 2,067, peer read-through 1,546, below 50DMA 713, SPY < 200DMA 494, weak RS 355, chasing 164, beat history 122, liquidity 64. 477 passed all filters, and caps and slots trimmed them to 222 entries.
- **Open at the end:** 2 positions (WSM and TJX, entered Nov 10, reporting Nov 18) are excluded from the trade stats but marked in the equity curve.

---

## (2) Main 24h book (v4.4)
**Engine:** `research/backtest/v5test.py` with `BASE`, run unmodified. That file is the `replicate.py` copy whose BASE equals the live v4.4 settings in `scripts/rotate.py`:
- 6 slots, longs only, pullback setups, beta ≥ 1.5.
- Trail +4%/60%, 5-session time stop, gap-take.
- Regime de-risk and the earnings gate.

**Runs:** close fills (exits at open/close, entries at the close) and 15m fills (9:45 / 3:30 exits, 3:45 entries; hybrid where `fills.parquet` lacks the bar).

**Two reads:**
- **fresh:** re-run with start = 2023-11-13, starting flat.
- **sliced:** the existing 2016-26 equity curve cut to the window.

**The price store ends 2026-10-26**, so this window stops 12 sessions short of Nov 11 (740 sessions). Script: `research/bt3y/main/run_main.py`.

### Headline (fresh re-run, Nov 13, 2023 to Oct 26, 2026)
| | close 5 bp | close 10 bp | 15m 5 bp | 15m 10 bp | SPY |
|---|---|---|---|---|---|
| Total return | +32.7% | +11.9% | +14.6% | -4.4% | +80.3% |
| CAGR | **+10.1%** | +3.9% | +4.7% | -1.5% | +22.2% |
| Sharpe | 0.46 | 0.28 | 0.31 | 0.11 | 1.39 |
| Max DD | -39.0% | -41.9% | -39.0% | -40.4% | -18.8% |
| Beta / alpha per yr | 1.14 / -9.3% | 1.14 / -15.1% | 1.08 / -13.3% | 1.08 / -19.4% | |
| Overnight leg (cum) | +84.4% | +84.1% | +71.9% | +71.9% | +51.1% |
| Day leg (cum) | -28.0% | -39.2% | -33.3% | -44.4% | +19.2% |
| Gross exposure overnight / day | 0.97 / 0.79 | 0.97 / 0.79 | 0.97 / 0.76 | 0.97 / 0.76 | 1 / 1 |
| CAGR ÷ avg exposure | +11.5% | +4.4% | +5.5% | -1.8% | +22.2% |
| Trades / hit | 1,042 / 54% | 1,041 / 53% | 1,113 / 58% | 1,113 / 56% | |

The sliced read (the full-history curve cut to the window) is close for close fills: +29.0% / +8.9% at 5 / 10 bp. It is better for 15m (+56.0% / +31.2%; CAGR +16.3% / +9.7%). The 15m gap between fresh and sliced is path noise plus the partial 15-min fill coverage (fresh paths need bars that were never fetched and fall back to open/close). **Even the best cell (15m sliced, 5 bp, +16.3%/yr, Sharpe 0.63) trails SPY.**

### Per year (fresh, close fills, 5 bp; 10 bp in brackets)
| Year | Book | SPY | Sharpe | Max DD | Overnight leg | Day leg | Beta | CAGR ÷ expo |
|---|---|---|---|---|---|---|---|---|
| 2023 (from Nov 13) | +19.0% (+18.3%) | +8.4% | 5.81 | -3.7% | +6.8% | +11.4% | 2.09 | n/m (7 weeks) |
| 2024 | +39.3% (+32.3%) | +24.9% | 1.32 | -20.7% | +26.0% | +10.3% | 1.55 | +43.4% |
| 2025 | +21.0% (+14.1%) | +17.7% | 0.77 | -21.0% | +40.7% | -14.9% | 0.78 | +24.6% |
| 2026 (to Oct 26) | **-33.8%** (-37.3%) | +13.1% | -1.09 | -39.0% | -4.8% | -31.1% | 1.58 | -45.6% |

15m fills, 5 bp (fresh): 2024 +12.0%, 2025 +12.8%, 2026 -23.4%. Sliced: 2024 +36.5%, 2025 +29.1%, 2026 -27.8%.

**Reading:**
- The overnight leg still carries the book (+84% cumulative vs SPY's +51%), and the day leg still bleeds (-28% vs SPY +19%).
- 2024 and 2025 beat SPY in close mode (2024 with a beta of 1.55).
- 2026 is a severe breakdown: even the overnight leg is negative, and the day leg is -31%. That matches the live book's weak run. At ~8-10 bp fills it is worse again.

### Bake-off-sized windows (pass = return ÷ avg exposure > SPY AND return > 0 AND ≥ 40 closed trades)
| Run | Median trades / 29 sessions | ≥ 40 trades | Beats SPY per exposure | Return > 0 | **All three** |
|---|---|---|---|---|---|
| close 5 bp | 42 | 64% | 40% | 53% | **19%** |
| close 10 bp | 42 | 64% | 37% | 49% | 16% |
| 15m 5 bp | 43 | 73% | 46% | 56% | 30% |
| 15m 10 bp | 43 | 73% | 42% | 52% | 27% |

### Caveats (main)
- **Survivorship is controlled** through `wide_daily.npz` (S&P point-in-time plus delisted names), as in REPORT_v5.md.
- **The live news, catalyst and "why-now" judgment layer** of v4.4 is not in the replica; the mechanical rules are.
- **15m results rest on partial 15-min fill coverage.** Treat close mode as the cleaner read.

---

## Files (all under research/bt3y/)
**`runup/`:**
- `fetch3y.py`: data pulls, GET only.
- `runup_bt.py`: the backtest. `RU_SP_ONLY=1` gives the S&P-only rerun.
- `window_check.py`: rolling windows plus the habit-accuracy check.
- `data/`:
  - `universe.csv`, `sp500_snapshots.csv`, `events.csv`, `cal_fwd.csv`
  - `bars.parquet`: SIP daily 2022-06 to 2026-11-11, 593 symbols.
  - `times_part*.csv`: Benzinga timing.
- `out/`:
  - `runup_3y.json`, `runup_3y_sp_only.json`, `window_check.json`
  - `trades_{5,10}bp*.csv`, `eq_{5,10}bp*.csv`, `unfiltered_trades_*.csv`
  - `cands.csv`: every candidate with its blocks.

**`main/`:**
- `run_main.py`, `window_check.py`
- `out/main_3y.json`, `out/eq_fresh_*.csv`, `out/trades_fresh_*.csv`, `out/window_check.json`

Other jobs are writing in research/bt3y/ (`orb/`, `data/`, `pull.py`, `rsi2_bt.py`, `out/spymom*`, `out/rsi2*`). They are not part of this report.
