# Window tests: published intraday edges vs our two windows (24H book, PAPER only)

Date: 2026-11-17. In-sample (IS) = 2016-2022, out-of-sample (OOS) = 2023-01-03 to 2026-11-13. OOS decides.
Costs: 5 bps/side SPY/QQQ (10 bps round trip), 10 bps/side single stocks (20 bps round trip). All returns below are NET unless marked gross.
Data: Alpaca SIP, split-adjusted. Scripts, CSVs and cache are in `research/window_tests/`.

## Bottom line

None of the five ideas survives costs out of sample in our windows (one 7-month news-conditioned cell is flagged for shadow only, see item 6 below). The book should not add any of them as a trading rule.
The gross edges are tiny. Intraday momentum on SPY is about 0 bps. Stocks in play bought at 10:00 make +0 to +9 bps gross. The cost hurdle is 10 to 20 bps.
The only things that look like real signal are small. They are (i) the long side of extreme-RVOL names at 9:35, which we can't trade, and (ii) a weak RRS ranking effect for 15:30 to next-day holds. Neither clears costs on its own.

## Scope changes (budget)

- The Alpaca data API is capped at 200 requests/min, and that limit was the bottleneck. I fetched only the bars each test needs, not full 5-min histories:
  - the 9:30 5-min bar for all 1,664 market_map names on every day from 2016 to 2026 (RVOL, gap, first-candle direction, 9:35 price);
  - the 9:50, 9:55, 10:10 and 15:25 5-min bars (10:00 / 10:15 / 15:30 prices, plus the 9:50 bar high) for the top-500 names by prior-20d $ volume, plus that day's in-play candidates (top-40 RVOL, or RVOL ≥ 2 with |gap| ≥ 2%), plus the previous day's candidates.
  - **Those second-pass prices cover only 2020-01-02 onward.** So every test that needs a 10:00 / 10:15 / 15:30 / next-day-10:00 price has an IS period of **2020-2022**, not 2016-2022. Test 1 (SPY/QQQ, full 5-min) and Test 2's 9:35 entry with a close exit use the full 2016-2022 IS period.
- Test 1 uses no shortlisting (full SPY/QQQ 5-min data). Test 2 uses the full universe for RVOL, so RVOL ranks are exact rather than built from a daily-bar shortlist.
- "15:30 price" = close of the 15:25-15:30 bar. "10:00" = close of the 9:55 bar. "10:15" = close of the 10:10 bar. "9:35" = close of the first 5-min bar. "Close" = the official daily close (auction).
- News split: the Alpaca/Benzinga news API on this account **returns no articles before about 2026-04-28**. I checked: 0 hits for all of Jan-2024 to Mar-2026 across 14k in-play names. So the Test 2 news split covers only 2026-04-29 → 2026-11-13 (136 days), and the Test 5 news/no-news split was **skipped** because there's no history.

## Caveats (read before using any number)

1. **Survivorship.** The universe is today's market_map, i.e. 1,664 names that are liquid as of 2026-11-13. Names that delisted or shrank before then are missing. Daily eligibility (prev close > $5, prior-20d avg $vol > $20M, prior-14d RVOL) uses only past data. Membership itself still embeds the future, which biases long-side results upward, most of all in 2016-2019. Since long-side results are already negative, this bias only strengthens the "no" verdicts.
2. There are no stops, no leverage and no ATR filter. The ORB paper (Zarattini-Barbon-Aziz) gets much of its edge from a tight stop (10% of ATR) plus position sizing. Without intraday paths for 2016-2026 we test hold-to-exit only. This is the version our window-based book can actually run.
3. The 9:35 entry assumes a fill at the first-bar close. That is optimistic and only a reference point; we don't trade at 9:35.
4. Portfolio t-stats use daily portfolio returns. Event tests (Test 5) report a date-clustered t for excess vs SPY, because events bunch on selloff days.
5. The RRS ATR is the **prior-14-day daily ATR (% of price)**, not 50 hours of 5-min ATR. Scaling both ATRs by the same sqrt-time factor doesn't change the cross-sectional ranking, so the top-10 / bottom-10 sets are identical. Only the units of RRS differ.

---

## TEST 1 - Market intraday momentum (Gao-Han-Li-Zhou 2018), CLOSE window

Signal r1 = prev close → 10:00. The classic variant is r1 + r12 (r12 = 15:00 → 15:30). Trade at 15:30 by sign. Net of 10 bps round trip. "Sharpe" is annualized on the daily series, with 0 on flat days. Full table: `test1_results.csv`.

| Sym | Signal | Trade | IS n / hit / net bps / t / Sharpe | OOS n / hit / net bps / t / Sharpe | OOS gross bps |
|---|---|---|---|---|---|
| SPY | r1 | LS 15:30→close | 1753 / 25.2% / -11.2 / -14.3 / -5.4 | 969 / 26.5% / -9.4 / -13.2 / -6.7 | +0.6 |
| SPY | r1 | Long-only 15:30→close | 952 / 23.5% / -11.9 / -11.9 / -4.4 | 553 / 26.8% / -9.1 / -10.4 / -5.1 | +0.9 |
| SPY | r1 | LS 15:30→next 10:00 | 1753 / 37.6% / -13.7 / -7.1 / -2.7 | 968 / 42.9% / -8.1 / -3.9 / -2.0 | +1.9 |
| SPY | r1 | Long-only 15:30→next 10:00 | 952 / 40.7% / -11.1 / -4.9 / -1.9 | 553 / 47.6% / -3.3 / -1.3 / -0.7 | +6.7 |
| SPY | r1+r12 | LS 15:30→close | 1757 / 25.2% / -10.8 / -13.7 / -5.2 | 969 / 26.3% / -10.2 / -14.2 / -7.3 | -0.2 |
| QQQ | r1 | LS 15:30→close | 1751 / 29.8% / -9.7 / -10.7 / -4.1 | 967 / 28.7% / -10.4 / -12.2 / -6.2 | -0.4 |
| QQQ | r1 | Long-only 15:30→next 10:00 | 963 / 45.0% / -7.7 / -2.7 / -1.0 | 540 / 48.5% / -3.1 / -0.9 / -0.4 | +6.9 |
| QQQ | r1+r12 | LS 15:30→close | 1752 / 29.9% / -9.6 / -10.6 / -4.0 | 968 / 29.6% / -9.6 / -11.3 / -5.8 | +0.4 |
| SPY | (none) | Always long 15:30→close | -10.7 | -9.6 | +0.4 |

- Predictive regression of the last-30-min return on r1: SPY corr **-0.039 IS / -0.020 OOS**, QQQ **+0.092 IS / -0.017 OOS**. The effect is essentially gone after 2016 (the paper's sample ends in 2013).
- Conditioning doesn't help. With |signal| above its trailing-1y 70th percentile, SPY LS OOS = -11.7 bps (gross -1.7) and QQQ = -11.1. On high-vol days (prior-20d realized vol in the top tercile of the trailing year), SPY LS OOS = -9.8 (gross +0.3) and QQQ = -10.9 (gross -0.9). The best IS cell was QQQ high-vol at +4.5 bps gross, which flipped to -0.9 bps gross OOS.
- The "long-only 15:30 → next 10:00" positive gross (+6.7 SPY OOS) is just the overnight/early-morning drift of holding SPY. It isn't a momentum effect, since "always long" earns about the same. At 10 bps round trip it's still negative.

**Verdict: reject.** The gross edge is about 0, and costs make every variant lose 8-14 bps per trade in both periods.

## TEST 2 - Stocks in play (Zarattini-Barbon-Aziz), adapted to the MORNING window

Eligible: prev close > $5, prior-20d avg $vol > $20M, RVOL = 9:30-9:35 volume / mean of the prior 14 sessions' 9:30-9:35 volume (at least 10 sessions). Direction = sign of the first 5-min candle; dojis are dropped.
Set A = top-20 RVOL per day (RVOL > 1). Set B = RVOL ≥ 2 and |gap| ≥ 2%. Each set is equal-weighted per day, with flat days = 0. Net of 20 bps round trip.
"Excess" = long-only portfolio minus SPY over the same window, on traded days. IS = 2016-22 for the 9:35→close rows and 2020-22 for all others. Full table: `test2_results.csv`.

| Set | Entry → exit | Side | IS net bps (t) | OOS net bps (t) | OOS hit | OOS Sharpe | OOS excess vs SPY |
|---|---|---|---|---|---|---|---|
| A | 9:35 → close (paper ref.) | L/S | -16.9 (-8.9) | -13.3 (-4.3) | 42.2% | -2.2 | |
| A | 9:35 → close | Long | -13.9 (-3.9) | -5.1 (-1.0) | 48.3% | -0.5 | -7.6 |
| A | 10:00 → close | L/S | -15.4 (-5.5) | -14.0 (-5.4) | 41.4% | -2.8 | |
| A | 10:00 → close | Long | -16.1 (-2.6) | -11.6 (-2.6) | 46.1% | -1.3 | -13.7 |
| A | 10:00 confirmed → close | L/S | -21.5 (-4.9) | -13.6 (-3.4) | 43.7% | -1.8 | |
| A | 10:00 confirmed → close | Long | -22.5 (-3.2) | -7.5 (-1.2) | 46.5% | -0.6 | -10.2 |
| A | 10:00 → next 10:00 | L/S | -15.8 (-3.4) | -16.6 (-4.5) | 43.6% | -2.3 | |
| A | 10:00 → next 10:00 | Long | -7.5 (-0.8) | -10.3 (-1.8) | 47.6% | -0.9 | -17.7 |
| B | 9:35 → close | L/S | -10.3 (-3.6) | -11.3 (-3.8) | 43.1% | -2.0 | |
| B | 9:35 → next 10:00 | Long | +9.0 (0.8) | +5.1 (0.8) | 49.8% | +0.4 | -3.0 |
| B | 10:00 → close | L/S | -8.8 (-2.6) | -12.8 (-5.3) | 40.0% | -2.7 | |
| B | 10:00 → close | Long | -8.9 (-1.2) | -12.3 (-2.7) | 45.4% | -1.4 | -14.3 |
| B | 10:00 → next 10:00 | Long | +6.5 (0.6) | -0.2 (-0.0) | 47.4% | -0.0 | -7.8 |
| B | 10:00 confirmed → next 10:00 | Long | -9.6 (-0.8) | +2.5 (0.3) | 47.1% | +0.2 | -5.0 |

Names per day: about 20 for A (about 10 on the long side) and about 40 for B in OOS (about 20 long).

RVOL deciles. Cross-sectional decile per day, signed by first-candle direction, gross bps (`test2_rvol_deciles.csv`, `test2_rvol_top_buckets.csv`):

| RVOL bucket | IS 9:35→close gross | OOS 9:35→close gross | IS 10:00→close gross (2020-22) | OOS 10:00→close gross |
|---|---|---|---|---|
| Decile 1 (lowest, med RVOL 0.28) | -9.0 | -8.0 | -1.3 | -0.5 |
| Decile 5 | -3.2 | -2.7 | +0.7 | +0.7 |
| Decile 10 (med 2.4-2.6) | -0.3 | -1.6 | +3.0 | +0.5 |
| Top 1% of RVOL | **+8.5** | **+9.2** | +6.2 | +8.7 |

Note: the 10:00 deciles use only names in the second-pass set (top-500 + candidates), so they cover fewer names than the 9:35 deciles.

- The paper's monotone RVOL effect does show up, but only in the top ~1% (about 15 names/day). There it is a stable +8 to +9 bps gross in both periods, which is less than half the 20 bps round-trip cost.
- The "continuation" sits on the long side. Set A long-only 9:35→close is +14.9 bps gross OOS (+3.9 IS), against SPY's +2.6. Shorts lose.

**News split (Benzinga via Alpaca, set A, 2026-04-29 → 2026-11-13 only: 136 days, 2,780 name-days, 56% with a headline from 16:00 prior day to 9:35).** Net bps per name-trade, exit at close (`test2_news_split.csv`). The t-stats are per name, not clustered by date, so they overstate significance.

| Headline? | First candle | 9:35 entry net (t) | 10:00 entry net (t) | n |
|---|---|---|---|---|
| News | Up → long | **+34.8 (2.1)** | **+11.5 (0.9)** | 802 |
| News | Down → short | -1.8 (-0.1) | -4.0 (-0.3) | 758 |
| No news | Up → long | -0.9 (-0.1) | -5.1 (-0.5) | 626 |
| No news | Down → short | -27.4 (-2.3) | -20.1 (-2.0) | 594 |

Within 7 months, news-driven in-play longs continue and no-news names don't, matching the paper's catalyst story. This is the one cell that is net positive at 10:00. The sample is too short to act on, there is no IS period, and 2026 has been a strong tape.

**Verdict: reject for our window.** No variant entered at 10:00 has positive OOS net excess vs SPY.

## TEST 3 - Does waiting help? (in-play sets, exit at close, 2020-2026 sample)

Net bps per day (`test3_results.csv`). "Wait cost" = 10:00 or 10:15 entry minus 9:35 entry.

| Set | Side | Period | 9:35 | 10:00 | 10:15 | Wait cost 10:00 | Wait cost 10:15 |
|---|---|---|---|---|---|---|---|
| A top-20 RVOL | Long | IS 2020-22 | -16.1 | -16.1 | -15.9 | -0.0 | +0.2 |
| A top-20 RVOL | Long | OOS | -5.1 | -11.6 | -11.5 | **-6.5** | **-6.4** |
| A top-20 RVOL | L/S | IS | -16.7 | -15.4 | -15.6 | +1.2 | +1.1 |
| A top-20 RVOL | L/S | OOS | -13.3 | -14.0 | -16.5 | -0.8 | -3.3 |
| B RVOL≥2 & gap≥2% | Long | IS | -7.4 | -8.9 | -7.5 | -1.5 | -0.1 |
| B RVOL≥2 & gap≥2% | Long | OOS | -7.3 | -12.3 | -11.9 | **-5.0** | **-4.6** |
| B RVOL≥2 & gap≥2% | L/S | IS | -10.2 | -8.8 | -8.1 | +1.4 | +2.1 |
| B RVOL≥2 & gap≥2% | L/S | OOS | -11.3 | -12.8 | -13.2 | -1.4 | -1.9 |

- In OOS, waiting **hurts** the long side by about 5-6.5 bps. A good part of the long in-play drift happens between 9:35 and 10:00. Waiting doesn't reduce adverse selection enough to make up for it.
- For long-short, waiting is roughly neutral: +1 to +2 bps IS and -1 to -3 bps OOS.
- The "10:00 only if still beyond the 9:35 close" confirmation filter halves the number of names. In OOS it brings set A long back to -7.5 (from -11.6), but IS was worse (-22.5). That's not robust.
- The r/RealDayTrading advice to skip the first 30 minutes doesn't create an edge. All entry times are negative net. For a trend-following long book, waiting costs a few bps.

## TEST 4 - Real Relative Strength (r/RealDayTrading)

RRS_T = (r_stock − r_SPY · ATR_stock / ATR_SPY) / ATR_stock, with returns from the 9:30 open to T. The ATR is the prior-14-day daily ATR, as explained in caveat 5.
Universe = top-500 eligible names by prior-20d $vol, chosen fresh each day. Equal-weight top-10 / bottom-10, long only, net of 20 bps round trip. Sample: 2020-2026 (IS 2020-22). Full table: `test4_results.csv`.

| Test | Leg | IS net (t) | IS excess vs SPY (t) | OOS net (t) | OOS excess vs SPY (t) |
|---|---|---|---|---|---|
| 4a RRS 9:30-10:00, buy 10:00 → close | top-10 | -22.4 (-4.3) | -22.9 (-6.4) | -21.1 (-5.9) | -23.2 (-8.3) |
|  | bottom-10 | -20.1 | -20.7 | -23.8 | -25.9 |
| 4a buy 10:00 → next close | top-10 | -11.2 (-1.3) | -14.8 (-2.5) | -17.6 (-2.9) | -27.2 (-5.7) |
|  | bottom-10 | -21.1 | -24.7 | -16.9 | -26.4 |
| 4a RRS 9:30-10:15 ("wait 45 min"), buy 10:15 → close | top-10 | -21.4 (-4.4) | -22.2 | -19.9 (-6.1) | -22.1 (-8.6) |
| 4a buy 10:15 → next close | top-10 | -8.8 (-1.0) | -12.6 | -13.8 (-2.3) | -23.4 (-4.9) |
| 4b RRS 9:30-15:30, buy 15:30 → next 10:00 | top-10 | **-2.0 (-0.3)** | -3.8 (-0.8) | **-9.8 (-2.4)** | -15.7 (-4.3) |
|  | bottom-10 | -27.2 | -29.0 | -17.3 | -23.1 |
|  | all 500 | -16.4 | -18.2 | -15.0 | -20.8 |
| 4b buy 15:30 → next close | top-10 | -7.1 (-0.9) | -9.5 | -15.9 (-3.2) | -23.8 (-5.6) |
|  | bottom-10 | -27.0 | -29.4 | -10.2 | -18.1 |
| 4c SPY down 9:30→15:30, buy 15:30 → next 10:00 | top-10 | -8.4 (-0.8) | -3.4 (-0.4) | -10.9 (-1.8) | -16.6 (-3.1) |
| 4c SPY down 9:30→15:30, buy 15:30 → next close | top-10 | -13.3 | -14.2 | -13.9 | -24.2 (-4.0) |
| 4c SPY down > 0.5%, buy 15:30 → next close | top-10 | -16.0 | -25.2 | -2.0 | -24.7 (-2.7) |
|  | bottom-10 | -7.1 | -16.3 | +10.7 | -12.0 |

4d - in-play set A × RRS sign at 10:00, traded in first-candle direction 10:00 → close, net bps per name-trade (`test4d_inplay_x_rrs.csv`):

| First candle | RRS | IS n / net (t) | OOS n / net (t) |
|---|---|---|---|
| Up (long) | RRS > 0 | 5642 / -16.0 (-3.6) | 7649 / **-9.7** (-2.8) |
| Up (long) | RRS ≤ 0 | 2069 / -16.9 (-2.5) | 2278 / -13.2 (-2.0) |
| Down (short) | RRS ≤ 0 | 5370 / -13.5 (-2.8) | 7130 / -16.0 (-3.6) |
| Down (short) | RRS > 0 | 1919 / -18.0 (-2.7) | 2165 / -24.4 (-3.7) |

- **4a (morning): reject.** Top-10 RRS at 10:00 or 10:15 does no better than bottom-10 or the average name. Gross 10:00→close is about -1 bps, so the result is just the cost.
- **4b (close): weak ranking signal, not a buy signal.** For 15:30 → next-day 10:00, top-10 RRS beats bottom-10 by **+25 bps IS / +7.5 bps OOS** and beats the average top-500 name by +14 / +5 bps. Gross top-10 is +18 IS / +10 OOS, but SPY over the same window was +1.8 / +5.8, so OOS excess net = **-15.7 (t -4.3)**. Ranking information decays out of sample and is too small to pay single-stock costs against SPY.
- **4c: the "held up while SPY dropped → rebound" claim fails.** On SPY-down days, top-10 RRS bought at 15:30 underperforms SPY over the next morning (OOS -16.6 bps, t -3.1). On SPY down > 0.5% days, the **weak** names (bottom-10) rebound more by the next close (+10.7 vs -2.0 OOS). That is reversal, the opposite of the claim, though n = 174 days and t < 1.
- **4d:** within in-play names, agreement between the first candle and RRS loses less (long with RRS > 0 is -9.7 OOS vs -13.2 with RRS ≤ 0; short with RRS ≤ 0 is -16.0 vs -24.4). The differences are 3-8 bps, all legs are net negative, and IS differences are near 0.

## TEST 5 - "Right side of the V" capitulation (Breitstein), MORNING window

Setup on D: 3+ down closes, D close < 20d mean − 2 SD, D volume ≥ 2× prior-20d average, D close > $20, top-500 by $vol. 4,506 events (2,937 IS 2016-22, 1,569 OOS).
Entries: (a) D+1 10:00; (b) D+1 10:00 only if above both the 9:50-9:55 bar high and the D+1 open (the "turn"); (c) D close (official close as a proxy for 15:55). Events are long, net of 20 bps round trip. Excess = vs SPY over the same window. t(excess) is date-clustered. IS for (a)/(b) is 2020-22. Full table: `test5_results.csv`, events: `test5_events.csv`.

| Entry | Exit | IS n / net bps / excess (t_cl) | OOS n / net bps / excess (t_cl) |
|---|---|---|---|
| (a) D+1 10:00 | D+1 close | 1434 / +58.8 / +2.4 (0.1) | 1568 / -19.7 / **-15.9 (-2.6)** |
| (a) | D+2 close | 1434 / +17.6 / -0.1 (-0.8) | 1567 / +9.3 / -21.2 (-1.3) |
| (a) | D+5 close | 1434 / +13.3 / -1.5 (0.3) | 1566 / +38.6 / -16.2 (-1.3) |
| (b) 10:00 turn | D+1 close | 202 / +26.1 / +20.0 (0.7) | 227 / -37.6 / **-39.0 (-2.9)** |
| (b) | D+2 close | 202 / +8.0 / +14.5 (0.4) | 227 / -42.5 / -75.7 (-2.7) |
| (b) | D+5 close | 202 / +108 / +42.7 (0.5) | 226 / +33.3 / -45.9 (-1.2) |
| (c) D close | D+1 close | 2937 / +12.0 / -5.7 (-1.6) | 1569 / -8.1 / -24.6 (-1.6) |
| (c) | D+2 close | 2937 / +2.3 / -9.5 (-2.3) | 1568 / +22.5 / -29.2 (-1.1) |
| (c) | D+5 close | 2937 / +23.2 / -6.9 (-1.1) | 1567 / +52.3 / -23.4 (-1.1) |

Beta split (120d beta vs SPY, terciles within top-500 on D), excess vs SPY:

| Entry → exit | Low-beta ("boring") IS / OOS | High-beta IS / OOS |
|---|---|---|
| (a) 10:00 → D+1 close | -9.1 / **-34.4 (t -3.3)** | +21.3 / +13.4 (t 0.8) |
| (a) 10:00 → D+5 close | +26.6 / -49.4 (t -2.2) | -27.4 / +17.2 (t -0.4) |
| (c) D close → D+5 close | +10.5 / -47.0 (t -1.6) | -27.2 / +32.0 (t -0.5) |

- Raw returns after capitulations are positive at 5 days, but SPY did as well or better in the same windows. These events cluster on market selloffs, and it's the market that rebounds, not the stock relative to the market.
- Waiting for the "turn" (b) makes OOS worse (-39 bps excess on D+1, t -2.9).
- "Boring large caps revert best" is contradicted OOS: low-beta capitulations underperform SPY by 34-49 bps. High-beta has mildly positive OOS excess, but IS was negative and t < 1.
- **Verdict: reject.** If we want the rebound, SPY exposure on capitulation days is the cheaper version. That would need its own test.

---

## What this means for our two windows

All decisions use OOS 2023-01 → 2026-11-13, net of our cost assumptions.

1. **CLOSE window: don't add an SPY/QQQ intraday-momentum trade.** Every variant loses 8-14 bps per trade OOS (e.g. SPY r1 LS 15:30→close -9.4 bps, t -13.2, Sharpe -6.7). The gross effect is about 0 (corr -0.02), with or without high-vol or strong-signal conditioning. No rule change.
2. **MORNING window: don't add a stocks-in-play / ORB sleeve at 10:00.** Best 10:00 version is set B long 10:00 → next 10:00 at -0.2 bps OOS, -7.8 vs SPY. Top-20 RVOL long 10:00→close is -11.6 bps/day (excess -13.7). The paper's edge needs 9:35 entries plus stops, and we can't run either.
3. **Don't delay entries "to let the first 30 minutes settle" for momentum longs.** Moving an in-play long entry from 9:35 to 10:00 or 10:15 cost 5-6.5 bps OOS. Since our window opens at 10:00 regardless, this mostly argues against chasing gappers at 10:00. A morning rule that buys "today's movers" pays about 20 bps of cost for about 0-9 bps of gross drift.
4. **RRS: use only as a soft overnight-hold filter, in shadow first.** It is not a buy signal. 15:30 top-10 RRS beat bottom-10 by +7.5 bps OOS (+25 IS) to next 10:00, but excess vs SPY was -15.7 bps (t -4.3). Testable shadow rule: *"At the CLOSE window, when choosing which single-stock names to carry overnight, drop names in the bottom decile of 9:30→15:30 RRS."* The expected benefit is small (bottom-10 vs all-500 OOS: -2.3 bps; IS: -10.8 bps). Log it for 3 months before adopting. The "held up on a red day → buy for the rebound" variant (4c) failed (-16.6 bps vs SPY OOS, t -3.1). Don't use it.
5. **Capitulation "right side of the V": no rule.** OOS excess vs SPY is negative for every entry and exit. The confirmation "turn" makes it worse, and "boring large caps" are the worst subset. Possible follow-up, not tested here: an SPY-only rebound trade on days with many capitulation events.
6. **Shadow-only hypothesis from the news split.** *"MORNING window: buy at 10:00 the top-20 RVOL names whose first 5-min candle is up AND that have a Benzinga headline since 16:00 the prior day; exit at the close."* Backing: +11.5 bps/name net, t 0.9, 136 days, OOS-only 2026-04 → 11, no IS available. Run it as a logged shadow sleeve and judge it on its own forward record. Don't trade it on this evidence.
7. **General guardrail.** With 20 bps round-trip single-stock costs, any new intraday or overnight single-stock rule needs at least about 25 bps per trade of gross OOS edge **vs SPY over the same window** before it's worth a shadow test. Nothing tested here gets close. The largest stable gross effect was the top-1% RVOL continuation at +9 bps.

## Files

- Scripts: `dl_common.py`, `dl_daily.py`, `dl_etf5.py`, `dl_first.py`, `build_panel.py`, `dl_second.py`, `dl_news.py`, `wt_lib.py`, `test1_intraday_momentum.py`, `test2_3_in_play.py`, `test3_table.py`, `test4_rrs.py`, `test5_capitulation.py`, `news_split.py`.
- Results: `test1_results.csv`, `test2_results.csv`, `test2_rvol_deciles.csv`, `test2_rvol_top_buckets.csv`, `test3_results.csv`, `test4_results.csv`, `test4d_inplay_x_rrs.csv`, `test5_results.csv`, `test5_events.csv`, `test2_news_split.csv`.
- Cache (about 0.75 GB): `cache/daily.parquet`, `cache/etf5.parquet`, `cache/first/`, `cache/second/`, `cache/panel.parquet`.
