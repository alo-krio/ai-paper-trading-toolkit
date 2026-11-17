# Pre-earnings run-up: Nasdaq-100, reports from Nov 11, 2025 to Nov 10, 2026 (research only, no trades)

**Question:** Should we buy N sessions before a report, sell at the last close before it, and hold through only when we have conviction?

## Verdict
1. **Best entry lead time: about 5 sessions. The edge is small and not proven.** Before costs are adjusted for the market, N=20 gives the biggest total excess (+1.75% vs QQQ), and N=5 gives the most per day held (+0.105%/day). Today's NDX members beat QQQ on any random day, though. After subtracting that drift, the event edge is +0.35% at N=5 (+0.07%/day) and +0.68% at N=20. With week-clustered t-stats of 0.9 and 1.2, neither is significant. The 10-year history for the same names shows **no edge after the drift control** (+0.05% at N=5, +0.01% at N=20).
2. **Holding through does not pay.** The average reaction is about zero (+0.05%; median −0.61%; 46% positive). The average absolute move is 7.1%, and the 5th percentile is −14.5%. Holding through leaves the mean unchanged and widens the left tail (N=5: 5th percentile −11.7% → −18.1%). Neither conviction filter helps. The top run-up tercile has a negative reaction at N=5 (−0.68%) and a positive one at N=20 (+1.09%); the corr is +0.08, so the sign is not stable. Four beats in the last four quarters gave −0.23% vs +0.09% for the rest.
3. **It beats QQQ only because of which stocks were picked, not because of the earnings timing.** Over the 12 months, QQQ returned +11.2%. The N=5 sell-before book returned +23.6% and the N=20 book +39.2%. Simply holding an equal weight of today's NDX names returned **+31.2%**, with lower vol (19%) and a smaller drawdown (−9.6%). The N=5 book had 30% vol and a −29% drawdown. The N=20 book is invested every day, so it is close to that same basket.

## Compact table (run-up vs QQQ, net of 0.10% round trip, n=387)
| N | raw mean | xQQQ mean | xQQQ %pos | xQQQ t (week-clust.) | same names' baseline | event − baseline | per day | 10y event − baseline |
|---|---|---|---|---|---|---|---|---|
| 1 | −0.09% | −0.03% | 48% | −1.52 | −0.04% | +0.01% | +0.009% | +0.03% |
| 2 | +0.32% | +0.16% | 48% | −0.16 | +0.01% | +0.15% | +0.073% | +0.01% |
| 3 | +0.38% | +0.11% | 49% | −0.29 | +0.07% | +0.04% | +0.014% | +0.05% |
| **5** | +0.64% | +0.53% | 51% | 0.91 | +0.18% | **+0.35%** | **+0.070%** | +0.05% |
| 7 | +0.86% | +0.63% | 53% | 0.90 | +0.28% | +0.35% | +0.050% | +0.09% |
| 10 | +1.01% | +1.03% | 52% | 1.90 | +0.44% | +0.59% | +0.059% | +0.02% |
| 15 | +1.68% | +1.29% | 53% | 0.46 | +0.75% | +0.55% | +0.036% | −0.02% |
| 20 | +3.16% | +1.75% | 52% | 1.16 | +1.07% | +0.68% | +0.034% | +0.01% |

**Reaction** (from the last pre-report close): to the open, mean −0.13%, median 0.00%, 50% positive, |move| 5.9%, 5th percentile −11.9%. To the close, mean +0.05%, median −0.61%, 46% positive, |move| 7.1%, 5th percentile −14.5%, 95th percentile +16.6%.

## Method
- **Universe:** 101 current Nasdaq-100 names from api.nasdaq.com/api/quote/list-type/nasdaq100 (pulled Nov 11, 2026). FER had no calendar rows, which left 387 events across 100 names.
- **Report dates:** the Nasdaq calendar (`data/hist/earnings.csv` through Oct 27, 2026, plus fresh calls to `api.nasdaq.com/api/calendar/earnings?date=` for Oct 28 to Nov 11). The Nasdaq calendar showed `time-not-supplied` even for recent dates.
- **Report timing (BMO/AMC):** I got this from the **Alpaca/Benzinga news timestamp of the results headline** (e.g. "Apple Q4 EPS $2.10 Beats…", 16:30 ET). That gave 256 AMC and 126 BMO events. For the 5 unknowns (CCEP Feb 13, CEG Feb 17, PANW Feb 12, ROP Jan 27, TXN Jan 27), I used the conservative anchor from the brief: the close 2 sessions before the report date, with the reaction measured to the close the session after the report date. Every matched headline fell on the Nasdaq calendar date.
- **Last pre-report close:** the close of the report day for AMC, and the prior close for BMO. The reaction is measured to the next open and close.
- **Prices:** Alpaca SIP daily bars (adjustment=all), Mar 2025 to Nov 10, 2026. The partial Nov 11 bar is excluded. The 10-year check uses `data/hist/wide_daily.npz`.
- **Regime:** QQQ above or below its 50DMA at the entry close. **Halves:** split at May 11, 2026.
- **Beat history:** the count of positive `surprise_pct` over the prior 4 Nasdaq-calendar reports (at least 3 needed).
- **Portfolio sim:** an equal-weight book of all open trades, in cash when none are open, with costs charged half at entry and half at exit.

## Robustness (run-up xQQQ, net)
| N | H1 (Nov–May) | H2 (May–Nov) | QQQ>50DMA | QQQ<50DMA |
|---|---|---|---|---|
| 2 | +0.40% (t 1.3) | −0.07% (t −0.2) | −0.06% | +0.36% |
| 5 | +0.50% (t 1.1) | +0.55% (t 1.1) | +0.24% | +0.86% (t 1.6) |
| 10 | +0.17% (t 0.3) | +1.86% (t 3.1) | +0.62% | +1.92% (t 2.5) |
| 20 | +1.51% (t 1.1) | +1.98% (t 2.1) | +2.76% (t 2.8) | −0.55% |

- **N=5 is the only lead time that is positive and roughly equal in both halves.** The longer leads swing with the half-year and the regime.
- **N=10 and above mostly rode H2 and uptrends.** That is market and stock drift, not earnings.
- **The reaction flipped sign between halves:** +1.19% in H1 and −1.05% in H2. That is one more reason not to hold through.

## Caveats
- **Small sample:** 12 months and 387 events, with reports bunched into 4 seasons. The week-clustered t-stats are the honest ones, and none is above 2.
- **Survivorship:** both samples use today's NDX members. They include names added because they rallied, such as ALAB and CRWV. That flatters any long-only rule, which is why the baseline columns matter.
- **10-year check:** the timing is unknown there, so it uses the close 2 sessions before the report date. The 12-month result recomputed with that same anchor is +0.39% at N=5 and +1.54% at N=20.
- **Lead times:** no tuning beyond the N grid. The verdict's N=5 is the per-day maximum before the baseline (after the baseline, N=2 is a near-tie at +0.073%/day). It is not a fitted parameter.

## Files
- `research/earnings_runup/fetch.py` pulls the data (NDX list, Nasdaq calendar, Alpaca SIP bars, Benzinga release times). It only makes GET requests.
- `research/earnings_runup/events.py` builds the event list.
- `research/earnings_runup/analyze.py` runs the full study, takes about 3 seconds, and writes `out/results.md`. Run it with `research/backtest/.venv/bin/python research/earnings_runup/analyze.py`.
- `research/earnings_runup/data/`:
  - `ndx.csv`
  - `cal_new.csv`
  - `events.csv`
  - `news_times.csv` (release timestamp and headline per event)
  - `bars.csv`
  - `ndx_cal_all.csv`
- `research/earnings_runup/out/`:
  - `results.md` (full tables)
  - `events_enriched.csv` (per-event run-ups and reactions)
  - `runup_grid.csv`
