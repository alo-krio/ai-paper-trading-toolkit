# Combo fix study: what would improve the weak stretch? Earnings Run-Up + Dip Buyer (rsi2), Nov 13 2023 to Nov 11 2026 (RESEARCH ONLY)

## Pre-registration (written 2026-11-13 09:03 ET, before any variant was run; nothing added or tuned afterwards)
Base: the primary combo of `research/bt3y_combo_2026-11-13.md` (combined $100k, Run-Up first call on capital, rsi2 "full minus breaker" on the point-in-time S&P 500, fixed re-arming 10% breaker blocking rsi2 entries only). Sessions 2023-11-13 to 2026-11-11 (base = 2023-11-10 close); earlier data only as indicator warm-up. Code: `research/bt3y/combo/combo_fix_bt.py` (imports `combo_bt.py`, `runup_bt.py`, `rsi2_bt.py` unmodified; the session loop is copied from `combo_bt.run` with switches added).

### Variants (exactly these; run at 10 bp/side = primary, and 5 bp/side)
- **V0 baseline**: the existing primary combo, reproduced. Must match +65.7% at 10 bp within ~0.2 pts, else stop and report.
- **V1 regime filter**: rsi2 may only open new positions when SPY's prior close is above its 200-day simple moving average; exits unchanged.
  - **Note written before running:** reading `combo_bt.py` / `rsi2_bt.py` shows the rsi2 rule set already contains this exact gate (`spy_gate`: no rsi2 entries when SPY's prior close < mean of the prior 200 closes), and it is on in V0. V1 is therefore expected to be identical to V0. It is run as specified anyway (implemented as an extra, redundant check) so the result is on record; it is not replaced by a different filter.
- **V2 half-size Dip Buyer**: rsi2 slot = 1/12 of combined equity instead of 1/6 (max 6 positions unchanged; the "skip below half a slot" rule scales with the slot).
- **V3 cash reserve for Run-Up**: reserve R = min(20% x V x (5 - open Run-Up positions), 40% x V), V = combined equity at the 15:45 proxy, open Run-Up count taken after that session's Run-Up entries. Implementation: each rsi2 entry amount = min(slot, free - R); the entry is skipped if that is below half a slot. So rsi2 entries never take free cash below R. (Simplest faithful version; rsi2 positions already held are never sold to restore the reserve.)
- **V4 idle cash in SPY**: after all entries at the 15:45 proxy (session close), all remaining cash is held in SPY. Entries are funded from cash first, then by selling SPY at the same close. Cost is charged on the net SPY change per session at the same per-side rate. Free cash for every sizing/skip rule = cash + SPY liquidation value. Equity, breaker and drawdown include SPY. Exits during a session go to cash and are swept into SPY at that session's close. Exposure reported two ways: strategy-only (Run-Up + rsi2, as V0) and including SPY (SPY weight x 390 minutes per session held close to close).
- **V5 = V1 + V3. V6 = V1 + V3 + V4.** In V6, the reserve R can sit in SPY (free = cash + SPY).

### Judging (same bar as the combo study)
- (a) total return / average exposure > SPY total return over the same span; (b) total return > 0; (c) max drawdown (session closes) smaller in magnitude than SPY's over the same span (-18.8% on the full period).
- For V4/V6, check (a) uses the **including-SPY exposure** (the conservative one); the strategy-only figure is reported alongside.
- Reported per variant: the full period, each calendar year (2023 stub, 2024, 2025, 2026 YTD) and the 6-month holdout (sessions 2026-05-12 to 2026-11-11), all sliced from one continuous run.
- **The honest read is the anchored walk-forward, not the full-period table.**

### Anchored walk-forward (10 bp primary; 5 bp also reported)
- Blocks: 6-month blocks starting at the first session on or after the 12th of May/Nov: B1 2023-11-13, B2 2024-05-13, B3 2024-11-12, B4 2025-05-12, B5 2025-11-12, B6 2026-05-12 (B6 = the holdout), each running to the session before the next block (B6 to 2026-11-11).
- For each block B3..B6: using only sessions from 2023-11-13 to the day before the block, compute each variant's return/exposure and max DD (from its continuous run, sliced) and SPY's max DD over the same prior span. Eligible = max DD smaller in magnitude than SPY's. Choose the eligible variant with the highest return/exposure (V4/V6 use including-SPY exposure). If none is eligible, choose the variant with the shallowest prior max DD. Ties go to the lower variant number.
- Out-of-sample: record the chosen variant's return in that block (sliced from its continuous run, so it inherits that variant's open positions at the block start; a real switch would inherit the previous variant's book: stated caveat). Stitch B3..B6 into one equity curve; report total return, max DD, return/exposure (session-weighted average exposure of the chosen variants) vs SPY over B3..B6, and the same three checks.

### Untested ideas (listed, not run)
- A stricter or different regime filter for rsi2 (e.g. SPY above its 50-day, or a volatility filter such as VIX below a level), since V1 duplicates the gate already in place.
- Pausing rsi2 after N consecutive losing trades; capping rsi2 per-trade loss tighter than the ATR stop.
- Reserving cash only for Run-Up candidates already passing filters the day before (the combo study's other noted alternative).

---

# Results (run 2026-11-13 ~09:10 ET, after the pre-registration above)

## Verdict
- **Holdout:** no variant fixes it. All seven fail check (c) on May 12 to Nov 11 2026 (best is V2 at -9.8% vs SPY's -5.9%). Every variant passes (a) and (b) there.
- **Full period:** all seven pass the bar at both 10 bp and 5 bp. That table is in-sample and is not the honest read.
- **Walk-forward (the honest read), 10 bp:** **+16.1%** over Nov 12 2024 to Nov 11 2026, against SPY's +29.8%. Max DD -13.5% vs SPY -18.8%. Return/exposure 0.304 vs SPY 0.298. It passes all three checks, but (a) wins by only 2%, so call it a tie with SPY per unit of exposure, at about half of SPY's absolute return. The selection rule picked V3 twice and V2 twice. On the same span the fixed V0 made +23.7% and V2 made +26.8%, so the choosing step itself lost money: V3 dropped 6.7% in B4 while SPY gained 21.7%.
- **Recommendation for a January 2027 live test: V2 (Dip Buyer at half size, 1/12 slots), if the combo goes ahead at all.** It is the only change that helped consistently, not just on one path:
  - It has the shallowest drawdown on every slice and at both costs: full period -9.8% (10 bp) and -9.0% (5 bp), vs V0's -14.1% and -17.9%.
  - It has the best Sharpe (1.35 and 1.67) and best return/exposure among the non-SPY variants (1.10 and 1.46). Its breaker never tripped.
  - Its holdout drawdown is the best, though it still fails (c).
  - The walk-forward chose it from prior data alone for the last two blocks. It made +5.1% and +11.5% there.
  - The cost: the Dip Buyer adds little. Its 3-year contribution falls to +5.0% at 10 bp. It still lost 9.1% of equity in 2026 (V0: -10.7%), because smaller slots meant more trades and no breaker trips. V2's drawdown gain comes mostly from risking less in rsi2, with Run-Up doing the earning (+56.8%).
- **Not recommended:**
  - **V1:** identical to V0. The 200-day SPY gate was already in the rules, as flagged in the pre-registration.
  - **V3 and V5:** these are identical, because V1 is a no-op. They fixed what they targeted: Run-Up skips fell from 114 to 63. But total return fell to +51.6%, 2025 was -0.6% with a -13.5% drawdown, and the walk-forward was hurt by picking V3.
  - **V4 and V6:** these raise total return (+81.1% and +85.2%) only by holding SPY, and drawdowns deepen (-15.5%; V6 -18.3%, about equal to SPY's). Counting the SPY exposure, return/exposure is 0.913 and 0.909, below V2. That is a leveraged-to-SPY version of the same thing, not a fix.
- **Observation (not a variant, not judged):** Run-Up alone (combo study, 10 bp) still beats every variant on return/exposure (1.69). It is also the only configuration that passed the holdout. The Dip Buyer leg remains the weak link in every configuration tried.

## Full period (sessions 2023-11-13 to 2026-11-11, 752 sessions), 10 bp/side (primary), rsi2 on point-in-time S&P 500
| Variant | Total | CAGR | Sharpe | Max DD | Avg exposure: strategy / incl. SPY | Return/exposure: strategy / incl. SPY | Trades per 29 sessions (Run-Up, rsi2) | Run-Up cash skips | Contribution: Run-Up / rsi2 / idle SPY | Bar a/b/c |
|---|---|---|---|---|---|---|---|---|---|---|
| **V0 baseline** | **+65.7%** | +18.4% | 1.13 | -14.1% | 74.7% | 0.879 | 38.4 (7.4, 31.0) | 114 | +47.6% / +18.0% / – | PASS (Y/Y/Y) |
| V1 regime | +65.7% | +18.4% | 1.13 | -14.1% | 74.7% | 0.879 | 38.4 (7.4, 31.0) | 114 | +47.6% / +18.0% / – | PASS |
| **V2 half-size rsi2** | **+61.7%** | +17.5% | **1.35** | **-9.8%** | 56.1% | **1.101** | 43.8 (7.9, 36.0) | 124 | +56.8% / +5.0% / – | PASS |
| V3 Run-Up reserve | +51.6% | +15.0% | 1.14 | -14.2% | 53.7% | 0.961 | 25.4 (8.3, 17.1) | 63 | +45.0% / +6.6% / – | PASS |
| V4 idle cash in SPY | +81.1% | +22.0% | 1.13 | -15.5% | 74.8% / 88.8% | 1.085 / 0.913 | 38.5 (7.4, 31.0) | 107 | +51.2% / +18.6% / +11.3% | PASS |
| V5 = V1+V3 | +51.6% | +15.0% | 1.14 | -14.2% | 53.7% | 0.961 | 25.4 (8.3, 17.1) | 63 | +45.0% / +6.6% / – | PASS |
| V6 = V1+V3+V4 | +85.2% | +22.9% | 1.21 | -18.3% | 53.7% / 93.7% | 1.587 / 0.909 | 25.4 (8.3, 17.1) | 62 | +50.5% / +1.4% / +33.2% | PASS (c by 0.5 pt) |
| SPY | +78.8% | +21.5% | 1.34 | -18.8% | 100% | 0.788 | | | | |

Idle-SPY contribution is the residual: total minus the two sleeves' closed trades and open marks. Breaker trips at 10 bp: V0/V1 2026-04-27 and 2026-10-13; V2 none; V3/V5 2025-08-08 and 2026-11-05; V4 2025-04-04 and 2026-10-13; V6 2025-04-03, 2025-11-20 and 2026-10-28.

### 5 bp/side
| Variant | Total | CAGR | Sharpe | Max DD | Exposure strat / incl. SPY | Ret/exp strat / incl. SPY | Run-Up skips | Contribution RU / rsi2 / SPY | Bar |
|---|---|---|---|---|---|---|---|---|---|
| V0 / V1 | +81.6% | +22.1% | 1.31 | -17.9% | 74.8% | 1.091 | 121 | +58.7% / +22.9% / – | PASS |
| **V2** | **+81.8%** | +22.2% | **1.67** | **-9.0%** | 56.1% | **1.459** | 124 | +66.2% / +15.6% / – | PASS |
| V3 / V5 | +64.0% | +18.0% | 1.34 | -14.4% | 53.4% | 1.198 | 63 | +52.7% / +11.3% / – | PASS |
| V4 | +105.2% | +27.2% | 1.34 | -18.1% | 74.8% / 88.8% | 1.407 / 1.185 | 121 | +63.6% / +22.4% / +19.3% | PASS |
| V6 | +113.7% | +29.0% | 1.48 | -18.0% | 53.7% / 93.6% | 2.117 / 1.214 | 63 | +61.1% / +13.6% / +39.0% | PASS |
| SPY | +78.8% | +21.5% | 1.34 | -18.8% | 100% | 0.788 | | | |

## Per calendar year, 10 bp (return / max DD / avg exposure incl. SPY / rsi2 contribution as % of equity at the year's start, closed trades)
| Variant | 2023 (from Nov 13) | 2024 | 2025 | 2026 (to Nov 11) |
|---|---|---|---|---|
| V0 / V1 | +6.9% / -2.4% / 60% / +5.0% | +24.3% / -7.3% / 81% / +12.6% | +9.1% / -6.6% / 68% / +11.1% | +14.3% / -14.1% / 77% / -10.7% |
| **V2** | +5.2% / -2.0% / 46% / +2.0% | +22.4% / -7.0% / 61% / +7.7% | +8.3% / -7.5% / 49% / +5.8% | **+16.0% / -9.8%** / 59% / -9.1% |
| V3 / V5 | +7.6% / -1.8% / 47% / +4.5% | +20.8% / -4.6% / 57% / +5.8% | -0.6% / -13.5% / 48% / +0.1% | +17.4% / -11.6% / 57% / -3.3% |
| V4 | +8.3% / -2.5% / 88% / +5.0% | +22.9% / -7.3% / 88% / +12.7% | +15.3% / -15.3% / 90% / +11.7% | +18.0% / -15.5% / 89% / -10.5% |
| V6 | +10.6% / -2.2% / 91% / +4.6% | +28.9% / -6.5% / 93% / +5.7% | +5.4% / -18.3% / 94% / -2.3% | +23.2% / -15.0% / 94% / -4.5% |
| SPY | +8.3% | +24.9% | +17.7% | +12.3% |

At 5 bp: V0 2026 is +11.2% with -17.9% DD (rsi2 -15.7%). V2 2026 is +20.2% with -9.0% DD (rsi2 -6.7%). V3 2025 is -0.5% with -14.3% DD. No variant beats SPY in 2025 at either cost except V4 at 5 bp (+22.3%).

## Holdout (sessions 2026-05-12 to 2026-11-11, sliced from each continuous run)
| Variant (10 bp) | Total | Sharpe | Max DD | Exposure strat / incl. | Ret/exp strat / incl. | Contribution RU / rsi2 | Bar | 5 bp: total / max DD / bar |
|---|---|---|---|---|---|---|---|---|
| V0 / V1 | +12.1% | 1.15 | -14.1% | 80.4% | 0.150 | +13.6% / -3.4% | FAIL (Y/Y/N) | +8.9% / -17.9% / FAIL (c) |
| **V2** | +11.5% | **1.41** | **-9.8%** | 61.0% | **0.188** | +13.5% / -2.0% | FAIL (Y/Y/N) | +13.9% / -9.0% / FAIL (c) |
| V3 / V5 | +8.6% | 1.05 | -11.6% | 58.9% | 0.146 | +9.3% / -0.7% | FAIL (Y/Y/N) | +10.9% / -11.1% / FAIL (c) |
| V4 | +10.3% | 0.97 | -15.5% | 80.4% / 88.1% | 0.128 / 0.117 | +13.6% / -3.4% | FAIL (Y/Y/N) | +9.0% / -18.1% / FAIL (c) |
| V6 | +7.9% | 0.82 | -15.0% | 59.0% / 94.2% | 0.134 / 0.084 | +9.2% / -1.5% | FAIL (Y/Y/N) | +11.7% / -12.1% / FAIL (c) |
| SPY | +3.3% | 0.52 | -5.9% | 100% | 0.033 | | | |

## Anchored walk-forward (the honest read)
Blocks B1 2023-11-13, B2 2024-05-13, B3 2024-11-12, B4 2025-05-12, B5 2025-11-12, B6 2026-05-12 to 2026-11-11. The choice for each block uses only data from 2023-11-13 to the day before it (anchored). Prior max DD was compared with SPY's over that same prior span. The return/exposure figure uses exposure including SPY.

10 bp (primary):
| Block | Prior data: return/exposure / max DD (SPY prior DD) | Chosen | Out-of-sample: return / max DD / exposure | SPY: return / max DD |
|---|---|---|---|---|
| B3 Nov 12 2024 to May 9 2025 | V0 0.43/-7.3%, V2 0.45/-7.0%, **V3 0.54/-4.6%**, V4 0.42/-7.3%, V6 0.51/-6.2% (SPY -8.4%) | V3 (tie with V5 → lower number) | **+6.1%** / -5.5% / 39% | -5.1% / -18.8% |
| B4 May 12 to Nov 11 2025 | V0 0.52/-7.3%, V2 0.71/-7.0%, **V3 0.75/-5.5%**, V4 0.45/-15.3%, V6 0.54/-18.3% (SPY -18.8%) | V3 | **-6.7%** / -7.5% / 54% | +21.7% / -3.0% |
| B5 Nov 12 2025 to May 11 2026 | V0 0.60/-7.3%, **V2 0.70/-7.3%**, V3 0.57/-11.0%, V4 0.59/-15.3%, V6 0.54/-18.3% | V2 | **+5.1%** / -7.7% / 57% | +8.9% / -8.9% |
| B6 May 12 to Nov 11 2026 (= holdout) | V0 0.65/-10.0%, **V2 0.82/-7.7%**, V3 0.75/-14.2%, V4 0.72/-15.3%, V6 0.76/-18.3% | V2 | **+11.5%** / -9.8% / 61% | +3.3% / -5.9% |

| Stitched B3 to B6 (501 sessions) | Total | CAGR | Sharpe | Max DD | Avg exposure | Return/exposure | Bar a/b/c |
|---|---|---|---|---|---|---|---|
| **Walk-forward, 10 bp** | **+16.1%** | +7.8% | 0.63 | **-13.5%** | 53.0% | **0.304** | PASS (Y/Y/Y): (a) 0.304 vs 0.298, a 2% margin |
| Walk-forward, 5 bp (same picks) | +20.9% | +10.0% | 0.78 | -14.1% | 52.6% | 0.398 | PASS |
| SPY, same span | +29.8% | +14.0% | | -18.8% | 100% | 0.298 | |
| Reference, not a strategy (hindsight-fixed over the same span, 10 bp) | V0 +23.7%, DD -14.1%, R/E 0.327; **V2 +26.8%, DD -9.8%, R/E 0.499**; V3 +15.8%; V4 +32.4%, DD -15.5%, R/E 0.364 (incl. SPY); V6 +25.7%, DD -18.3%, R/E 0.272 | | | | | | |

Read: picking a variant from past results did worse than just holding V0, mainly because V3 looked best on a short early history and then lost 6.7% in a block where SPY rose 21.7%. Two blocks out of four lost to SPY (B4, B5). The walk-forward lands at about half of SPY's return with a shallower drawdown. Per unit of exposure it ties SPY, which is not evidence of an edge.

## Caveats
- Daily bars stand in for the 9:45 / 15:30 / 15:45 prints, as in both source studies. The headline, supply, M&A and 8-K filters are not replicated for either sleeve.
- **2026 had already been seen** before these variants were written. The variants target the known 2026 problems (the Dip Buyer's losses and the Run-Up cash skips), so even the holdout and B5/B6 are not clean out-of-sample tests.
- **Seven variants (five distinct) × two costs were tested, so there is some data-mining risk.** Picking the best full-period row would overstate the result. The walk-forward is the guard, and it shows the choosing step losing ground to a fixed choice.
- The walk-forward slices each variant's continuous run, so a chosen variant inherits its own open positions at the block start. A real switch would inherit the previous variant's book.
- V4/V6 assume SPY can be traded at the close with the same per-side cost and that sweeps cost only the net change. SPY's actual spread is far tighter, so this is conservative on cost. But V4/V6 returns are mostly SPY beta.
- Path sensitivity remains high. V0's max DD moves from -14.1% to -17.9% between 10 bp and 5 bp. V2 is the least path-sensitive (-9.8% / -9.0%).
- Run-Up uses today's Nasdaq-100 list (survivorship), as in the combo study.

## Files
- `research/bt3y/combo/combo_fix_bt.py`: `run_fix()`, a copy of `combo_bt.run` with switches (generated by exact string substitution from `combo_bt.py`'s source). `python3 combo_fix_bt.py [bps] [variants]` runs the variants. `python3 combo_fix_bt.py wf` runs the walk-forward. V0 reproduces the combo study exactly (+65.66%, -14.1%, 114 skips).
- `research/bt3y/combo/out_fix/`: `fix.json` (full and holdout summaries with per-year breakdowns, all variants and costs), `wf.json`, `wf_eq_{10,5}bp.csv`, and per run `eq_*.csv`, `trades_*.csv`, `expmin_*.csv` (strategy and SPY minutes) and `res_*.pkl`.
- Imported unmodified: `combo_bt.py`, `runup/runup_bt.py`, `rsi2_bt.py`, `common.py`. Nothing in scripts/, sleeves/, book/ or the scheduled tasks was touched. No brokerage was used. (The sandbox's python3 was missing numpy/pandas/pyarrow, so they were pip-installed. No project files changed.)
