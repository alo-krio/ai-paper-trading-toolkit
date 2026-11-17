# Anticipation Engine — build + first live run (2026-11-16)

Paper only. No orders placed, no brokerage touched (Alpaca used for read-only market data).

## Built
- `investing-24hour-agent/project/scripts/anticipate.py` — commands: calendar, odds, edge, sheet, log, score, backtest.
- Playbook: `investing-24hour-agent/project/notes/ANTICIPATION.md`.
- Data: `project/data/anticipate/` — `sheets/sheet_2026-11-17.{md,csv,json}`, `polymarket_snapshots.csv` (1,133 markets),
  `forecasts.csv` (9 seeded forecasts), `backtest/{REPORT.md,events.csv,params.json}`, `credits.csv`, caches.
- No existing workspace files were modified.

## Backtest (closed Polymarket earnings-beat markets)
- n = 1,498 usable (1,606 fetched; 101 without odds history), entries 2025-09-23 → 2026-11-13. Base beat rate 73.2%.
- Calibration: Polymarket Brier 0.147 vs 0.196 for a constant; buckets line up (0.41→0.47, 0.78→0.82, 0.90→0.90).
- Odds level vs 2-day excess reaction: slope +0.24%/unit, t 0.23 → no signal. p ≥ 0.85: +0.35% (t 0.95).
  The 0.50-0.70 bucket shows +1.36% (t 2.2), likely chance given multiple buckets.
- Outcome surprise (result − odds): +4.49% per unit, t 7.1. Beats +1.27% (44% still fell), misses −2.14%; high-odds misses (0.85-0.95) −5.3%.
- Final-3-day odds change: predicts outcome (t 6.0; flat-odds beat rate 0.80, falling ≥ 5 pts 0.60), not the reaction (t 0.12).
- Run-up >5% with p ≥ 0.7: n = 230, beat 0.90, +1.77% (10-day run-up slope t 1.94, weak).
- Tradeable subset (px ≥ $5, ADV ≥ $20M, n = 1,348): same picture (surprise slope +3.8%, t 6.1; level t −0.01).
- Caveats: thin markets (median volume ≈ $5k), overlapping dates, strike = consensus at creation, daily closes,
  no costs, survivorship, multiple testing. This supports "Polymarket is a good probability source", NOT "buy beats".

## Tomorrow's sheet (Tue 2026-11-17) — highlights
- NVDA (AMC 11/17): PM P(EPS > $2.53) 83% (thin: liq ≈ $1.1k); consensus ≈ $2.47-2.49; beat 12/12, model 87%, ours 85% →
  NO EDGE, stay flat into the print, trade the reaction/ripples. Stock −24.6% vs SPY over 20 d; options imply ±8.4% vs
  4.5% average past move (rich). First print since Jensen Huang's exit (PM: rejoin by Dec 31 at 11%). Ripples: TSM, MU, VRT, AVGO, ORCL.
- HD (BMO 11/17, past entry window): PM 31% (−15 pts in 24h) vs model 56% → BASE-RATE GAP, but falling late odds
  historically mean a lower beat rate; reaction-only. MOG-A (BMO 11/20): PM 70% vs model 87%, ours 73% → no edge yet.
- Model UNKNOWN (GAAP strike / consensus mismatch): PANW, DLB, WSM, WWD, GRAB.
- Fed Dec 9: FedWatch 25 bp hike 95.5% vs PM 91.5% (−4.0), 50 bp 4.5% vs 5.1%; no tradeable gap.
- Anthropic IPO (ANT, Nasdaq calendar 11/19, $70-78): PM closing mkt cap < $1.25T 35% (+13 pts 24h); AMZN/GOOGL soft vs SPY.
- Flags to verify: "new US sanctions on China by Nov 30" 85% (+76 pts 24h) with KWEB/FXI quiet; US-Iran ceasefire odds +13-16 pts;
  WTI ↑$90 in Nov 38% (−38). Shutdown by Dec 12 ≈ 40%.
- Macro: retail sales 11/17 8:30; FOMC minutes 11/18 14:00; claims/Philly 11/19; core PCE/GDP 11/25.
- Net: no pre-print bet on the sheet clears the edge bar. Default action: flat into binaries; watch reactions.

## Credits
Firecrawl/Alexandria paid ≈ 70 credits today (55 logged in credits.csv + 15 manual probes); ≈ 897 of 1,000 left (resets Dec 11). Polymarket calls cost 0.

## Caveats
- Polymarket earnings books are thin; one trade can move a price 10+ pts. The 24h change flags are noisy.
- ODDS MOVED flags need a headline check before any trade (the market may be priced in futures or elsewhere).
- Consensus differs across sources (Nasdaq vs stockanalysis); strikes set at creation can be stale.
- Forecast ledger has 0 resolved forecasts; calibration claims about OUR model start after ≥ 30 resolve.
