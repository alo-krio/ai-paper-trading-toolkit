# Tooling scan: open-source repos and HF models to help the paper books beat SPY
Date: 2026-10-27 (IST). Research only, no code changed. Paper trading only.

## Bottom line
- Nothing off the shelf, whether a model or an agent framework, has credible, cost-adjusted evidence of beating SPY on 1–5 day US large/mid-cap returns. The best-supported gains come from three things. First, **better testing**: a long history and a real backtest of our exact rules. Second, **better-built simple signals**: residual or industry-adjusted reversal instead of raw RSI2, and earnings/revision event filters. Third, **using ML for risk (volatility), not direction**.
- The biggest unlock is a data one. The new **free Alpaca account serves full-market (SIP) historical bars back to 2016** for anything older than 15 minutes. Our current `data/ohlcv/*.json` has only ~275 sessions per name, which is too short to tell skill from luck.
- Time-series foundation models (Chronos, TimesFM, Moirai, Lag-Llama, TTM) do **not** forecast daily returns meaningfully better than a random walk in independent tests. Their realistic use is volatility forecasting for position size and stop width.
- Multi-agent LLM traders (TradingAgents, ai-hedge-fund, FinMem, FinRobot) show no independent, broad-universe, after-cost evidence. The one rigorous re-test (FINSABER, KDD 2026) found the claimed gains go away.

Sandbox checked today: 2 CPUs, 7 GB RAM, no GPU, and pandas is not installed in the default python. A research harness can live in a separate venv/script without touching the pandas-free main script. 1,800 names × ~2,600 days × float64 is about 37 MB per array, so everything below fits.

---

## Ranked shortlist (11 items)

GitHub stars and last push were read from the GitHub API on 2026-10-27, and HF downloads (last 30 days) from the HF API the same day. "Last push" is the repo's latest push to any branch.

### 1. Alpaca market data via alpaca-py (or the raw REST API): the 2016–2026 history unlock
- **URL:** https://github.com/alpacahq/alpaca-py · plan docs: https://docs.alpaca.markets/docs/about-market-data-api
- **What it does:** Official Python SDK for Alpaca trading and data. The free Basic plan gives real-time IEX quotes, 30 websocket symbols, 200 historical calls/min, history **since 2016**, and full-market SIP bars for anything older than 15 minutes (Alpaca forum staff: both plans have the same coverage for data older than 15 min, https://forum.alpaca.markets/t/iex-or-sip-with-a-free-account/17141). Options are an "indicative" feed only. Benzinga news history is available through the news endpoint.
- **Helps:** All three books, mainly the 24-Hour swing book and 14-Day picks.
- **Experiment:** Pull adjusted daily SIP bars for the 1,800-name universe plus SPY, HYG, LQD and sector ETFs for 2016-01 to now. Multi-symbol bar requests mean roughly 20–40 calls per refresh, well under 200/min. Also pull 15-minute bars to rebuild the 9:45/10:00 and 3:30/3:45 ET fills, so the backtest trades at our real decision times, not at the close. Save as compact JSON/npz alongside `data/ohlcv`. The main script can keep using the Nasdaq API; this is only the research store.
- **Cost/compute:** Free. Light CPU. One-time pull of about 1–2 hours with throttling.
- **Maturity:** 1,570 stars, pushed 2026-10-27, Apache-2.0. Official SDK.
- **Evidence quality:** N/A (it's data). **Caveat:** survivorship bias. Today's 1,800-name universe leaves out names that were delisted, acquired or fell below $2B. I did **not** verify whether Alpaca serves bars for delisted symbols. Check `GET /v2/assets?status=inactive` first. If it doesn't, every backtest will be optimistic (more so for longs) and must be read that way.

### 2. vectorbt: fast vectorized backtests of our exact setups on 1,800 names
- **URL:** https://github.com/polakowo/vectorbt
- **What it does:** NumPy/Numba portfolio simulation over wide price matrices. It handles thousands of symbols × parameter grids in seconds to minutes and supports stop-loss, trailing-stop and time-exit orders natively (`Portfolio.from_signals` with `sl_stop`, `tsl_stop`, plus custom exits).
- **Helps:** 24-Hour swing book, and the 14-Day picks entry rules.
- **Experiment:** Re-implement the v2 rules as boolean entry matrices: RSI2 pullback in an uptrend, 20-day volume breakout, bounce and breakdown shorts in downtrends, the beta ≥ 1 long filter, the 0.7–1.0 beta band for 14-Day picks, -4% stop, a trailing stop armed after +4%, and a 5-session time stop. Run 2016–2026 with 5 and 10 bps per side, plus short borrow of about 1% a year on general-collateral names. Report CAGR, Sharpe, max drawdown and **% of 20-day windows beating SPY**, by setup and by risk-dial state. Then do a *small* walk-forward sweep: RSI2 threshold, stop %, time stop 3/5/7. Fit on 2016–2021, test on 2022–2026, and keep the grid tiny to avoid curve-fitting.
- **Cost/compute:** Free. pip install vectorbt (pulls pandas + numba) into a separate venv. CPU-only is fine on 2 cores and 7 GB.
- **Maturity:** 9,553 stars, pushed 2026-10-23. License shows as NOASSERTION on GitHub; per the project, it's Apache-2.0 with the Commons Clause, which is fine for personal research but means no reselling. (The paid "vectorbt PRO" is a separate product and isn't needed.)
- **Evidence quality:** It's a tool, so there's no alpha claim. It's widely used. Watch-outs: by default it fills at bar prices, so model our 15-minute decision prices explicitly, and stops are checked on OHLC bars, so intraday ordering is ambiguous.

### 3. alphalens-reloaded: signal IC and quantile tests at 1/3/5/10/14-day horizons
- **URL:** https://github.com/stefan-jansen/alphalens-reloaded
- **What it does:** Takes any per-stock daily score and gives rank IC by horizon, quantile return spreads, turnover and IC decay, with sector breakdowns.
- **Helps:** All books. It's the gate every new signal must pass before it touches a trade.
- **Experiment:** Feed it, at forward horizons of 1, 3, 5, 10 and 14 days:
  - (a) raw RSI2;
  - (b) 5-day return residualized to market + sector (item 4);
  - (c) 20-day volume-breakout strength;
  - (d) earnings surprise % and 4-week estimate revisions (item 5);
  - (e) our logged Perplexity news score and the Kronos side scores once 20+ days exist;
  - (f) short-volume ratio (item 8).
  A signal earns a slot only if mean rank IC is positive with t > 2 over 2016–2026 **and** in the 2022–2026 sub-period, and the top-minus-bottom quintile spread beats the round-trip cost of 10–20 bps.
- **Cost/compute:** Free, pandas-based, CPU.
- **Maturity:** 677 stars, pushed 2026-10-27, Apache-2.0. Maintained by Stefan Jansen (ML4T).
- **Evidence quality:** N/A, it's a tool. It is the standard factor-IC methodology.

### 4. Residual / industry-adjusted short-term reversal (method + small reference code)
- **Code templates:** https://github.com/Itaru-Shin/short-term-reversal-study (MIT, 0 stars, single-commit study, but clean and honest), and the `STreversal` predictor in https://github.com/OpenSourceAP/CrossSection (1,071 stars, pushed 2026-10-26, GPL-2.0).
- **What it is:** Our RSI2-pullback long is a reversal trade. Evidence says *raw* reversal in US large caps is dead after costs, but the *residual* part (return left after removing market/industry moves) still works:
  - The Itaru-Shin study (2018–2025; 89 mega-caps and a 353-name S&P subset; 5-day losers vs winners) found raw reversal IC t = 0.45, net Sharpe -0.65 at 5 bps. All gross profit came from high-VIX days, mainly COVID 2020. Ken French ST_Rev Sharpe in 2018–25 was 0.35 (t ≈ 1.0).
  - Short-term residual reversal (Blitz et al., JFM 2013) is profitable after costs in large caps after 1990, while conventional reversal was near zero: https://www.sciencedirect.com/science/article/abs/pii/S1386418112000468
  - "Short-term reversal persists globally—if properly measured" (Economics Letters, 2026): standard reversal goes negative after costs, industry-adjusted stays positive: https://www.sciencedirect.com/science/article/pii/S0165176526003095
  - NBER w35840 "Asymmetric Reversals" (2026): reversal sits in the residual component, while the systematic component shows short-term momentum: https://www.nber.org/system/files/working_papers/w35840/w35840.pdf
- **Helps:** 24-Hour swing book (RSI2 longs and bounce shorts), and 14-Day pullback picks.
- **Experiment:** Compute each stock's 5-day return minus beta × SPY return minus its sector-ETF excess return (rolling 60-day betas). Rank by residual instead of RSI2, keeping the uptrend filter. In vectorbt (item 2), compare three variants: raw RSI2, residual-ranked, and residual-ranked + risk-dial gating, where we lean in on wide-credit/weak-breadth stress days. That matches the finding that profits cluster in high-VIX regimes.
- **Cost/compute:** Pure arithmetic on daily bars. Can be written without pandas, so it can go into the main script if it wins.
- **Evidence quality:** **Moderate.** Several peer-reviewed papers agree, but the effect is small and has decayed. At our 10–20 bps round trip it may only pay in stress regimes. Treat it as a ranking upgrade, not a new strategy.

### 5. Earnings and analyst-revision event filters (free Nasdaq endpoints we already use, plus PEAD evidence)
- **Sources (verified working today, same `api.nasdaq.com` host as our bars):**
  - `/api/company/{SYM}/earnings-surprise`: last 4 quarters, EPS vs consensus, % surprise, report date
  - `/api/analyst/{SYM}/earnings-forecast`: consensus/high/low and **number of up/down revisions in the last 4 weeks**
  - `/api/calendar/earnings?date=YYYY-MM-DD`: daily calendar with timing (before or after hours)
  - `/api/analyst/{SYM}/ratings`
  - `/api/quote/{SYM}/short-interest?assetClass=stocks`: bi-monthly short interest and days-to-cover
- **Helps:** 24-Hour swing book (event risk and short selection) and 14-Day picks (quality filter). Also useful context for the 3–6 month book.
- **Experiment:**
  - (a) **Earnings blackout:** in vectorbt, compare "no new longs within 2 sessions before a report" against the current rules. Our -4% stop doesn't protect against overnight earnings gaps.
  - (b) **Post-miss short tilt:** large-cap evidence is asymmetric. Misses keep drifting down and beats barely drift up (finlab 2016–2026 top-500: beats +0.41% at 20 days, misses -1.63%, https://finlab.finance/en/blog/us-earnings-surprise-strategy). So test favoring breakdown shorts in names that missed in the last 10 sessions.
  - (c) **Revision filter for 14-Day picks:** require net up-revisions ≥ 0 over 4 weeks. Test with alphalens at a 14-day horizon.
  - **Point-in-time caveat:** the Nasdaq endpoints only show current/recent values, so history must be logged forward daily from now (cheap: one call per name per week) or rebuilt from Alpaca/Benzinga earnings headlines. The blackout test (a) needs only historical report dates.
- **Cost/compute:** Free. Calls are already in our stack.
- **Evidence quality:** **Weak to moderate, and mixed.** In large caps, PEAD is "low-amplitude, not vanished":
  - CAR[+2,+20] t-stats fell to about 2.65 in 2019–21 (UCP thesis: https://repositorio.ucp.pt/server/api/core/bitstreams/c9033501-675d-4fda-a389-c1b18a4ffc6a/content).
  - A 2025 paper claims a post-2020 resurgence (http://arc.hhs.se/download.aspx?MediumId=6317), while another finds no reliable 20-day drift in 2025–26 large caps (SSRN 7137218).
  - The blackout (a) is risk control and likely the most robust piece. (b) and (c) are only hypotheses until our own IC test passes.

### 6. Lopez-Lira–Tang headline scoring on Alpaca/Benzinga news, with ProsusAI/FinBERT as a free baseline
- **URLs:** FinBERT model https://huggingface.co/ProsusAI/finbert · repo https://github.com/ProsusAI/finBERT · paper (JFE 2025 version) https://arxiv.org/abs/2304.07619
- **What it does:** FinBERT is a 110M-parameter BERT that labels financial text positive/negative/neutral, fast on CPU (about 20–50 headlines/s on 2 cores). The Lopez-Lira–Tang protocol asks an LLM, for each headline, whether it's good or bad news for the stock (YES/NO/UNKNOWN). It then trades next-day open to close and finds the signal works for about 2 days, strongest for small caps and negative news.
- **Does it beat our Perplexity scoring?** The evidence says **FinBERT will not beat an LLM scorer**:
  - In Lopez-Lira–Tang, FinBERT marked 75% of overnight news neutral, and its drift strategy had a negative Sharpe (-0.33), while GPT-4 scores predicted next-day drift.
  - Fine-tuned small models can match zero-shot GPT on *labelling accuracy* (https://arxiv.org/html/2409.11408v1), but labelling accuracy isn't return prediction.
  - The authors also report that "strategy returns decline as LLM adoption rises."
  - So: **keep Perplexity**, and use FinBERT only as a zero-cost control so we know whether Perplexity adds anything.
- **Helps:** 24-Hour swing book (news veto/boost at both windows) and 14-Day picks (news check).
- **Experiment:** Pull Benzinga headlines from Alpaca for each candidate for the 18 hours before each decision window. Score each headline three ways: FinBERT, Perplexity sonar (current prompt), and the Lopez-Lira YES/NO prompt on sonar. Log all three as SIDE tests next to the existing `SIDE news` line. After 20+ sessions, and also on a 2024–2026 Benzinga backfill, compare rank IC vs next-session and next-3-session excess return. **Backfill caveat:** an LLM may have seen post-headline prices in training, so only backfill after the model's knowledge cutoff, or trust only forward logs.
- **Cost/compute:** FinBERT is free on CPU (~440 MB download, needs torch-cpu). The Perplexity cost is what we already pay; the extra prompt variant roughly doubles calls on candidates only.
- **Maturity:** FinBERT repo 2,265 stars, pushed 2026-10-12, Apache-2.0; HF model 3.9M downloads/month.
- **Evidence quality:** **Moderate** that LLM headline scores predict 1–2 day returns, peer-reviewed. **Weak** that it survives our costs in large caps: the effect is strongest in small caps, which we exclude below $2B, and it is decaying.

### 7. Chronos-2 / Chronos-Bolt (and TimesFM-2.5) for VOLATILITY, not direction
- **URLs:** https://github.com/amazon-science/chronos-forecasting · https://huggingface.co/amazon/chronos-2 · https://huggingface.co/amazon/chronos-bolt-small · https://github.com/google-research/timesfm · https://huggingface.co/google/timesfm-2.5-200m-pytorch
- **What it does:** Pretrained zero-shot forecasters. Chronos-Bolt is CPU-friendly; the project says it's up to 250× faster than the original Chronos. Chronos-2 supports covariates.
- **Evidence on daily returns (negative):**
  - "Re(Visiting) TSFMs in Finance" (34 years, 94 countries): zero-shot Chronos-large out-of-sample R² is -1.37% with ~51% direction accuracy; TimesFM-500M R² is -2.80% with <50% accuracy; both lose to CatBoost/LightGBM (https://arxiv.org/abs/2511.18578).
  - "Pretrained TSFMs for Financial Return Forecasting" (June 2026; TimesFM-2.5, Moirai-2.0, Chronos-2 and others on 5 US large caps): gains over a random walk are "small and sparse." Diebold-Mariano is significant in only 2 of the stock-model cases (https://arxiv.org/abs/2606.27100).
  - The Chronos project's own site summarizes return forecasting as "rarely beats a random walk."
- **Why still listed:** Volatility is predictable, and our own `SIDE kronos_vol` showed rank IC +0.49 on its first day (1 day only, no meaning yet).
- **Helps:** 24-Hour swing book (position sizing and stop width), maybe the risk dial.
- **Experiment:** Each night, forecast 5-day realized volatility for all 1,800 names with chronos-bolt-small on log-|return| or squared-return series. Benchmark against **EWMA(λ=0.94) and 20-day ATR**, which are free and the bar to beat. Only if Chronos beats ATR on QLIKE/rank IC over 60+ days, test vol-scaled sizing (equal risk per position) and an ATR-multiple stop instead of a flat -4% in vectorbt. Expect ATR to be hard to beat; if it is, drop the model.
- **Cost/compute:** chronos-bolt-small (~48M params) should handle 1,800 series in minutes on 2 CPUs (estimated, not timed here). Chronos-2 and TimesFM-2.5 (200M) are slower but still workable nightly.
- **Maturity:** chronos-forecasting 6,195 stars, pushed 2026-10-05, Apache-2.0; chronos-2 has 13.3M HF downloads/month. timesfm 34,791 stars, pushed 2026-09-30, Apache-2.0. Google has also announced TimesFM-3 (https://research.google/blog/timesfm-3-a-zero-shot-foundation-model-for-multivariate-forecasting).
- **Evidence quality:** **Strong negative** for return direction. **Plausible but unproven** for adding to ATR-style volatility.

### 8. FINRA short-sale volume and short interest (free) for short-book risk control
- **URLs:** Daily Reg SHO short volume files https://www.finra.org/finra-data/browse-catalog/short-sale-volume-data/daily-short-sale-volume-files (cdn.finra.org/equity/regsho/daily/*.txt) · Query API https://developer.finra.org/catalog · bi-monthly short interest https://www.finra.org/finra-data/browse-catalog/equity-short-interest/files (also on the Nasdaq short-interest endpoint above)
- **What it does:** Free (non-commercial) daily off-exchange short volume by symbol, and twice-monthly short interest with days-to-cover.
- **Helps:** 24-Hour swing book shorts, mainly.
- **Experiment:**
  - (a) **Squeeze guard:** skip breakdown/bounce shorts where days-to-cover is above about 5 or short interest is above ~15% of float. Backtest the change in short-leg drawdown in vectorbt.
  - (b) Alphalens IC of the 5-day change in short-volume ratio at 1–5 day horizons.
- **Cost/compute:** Free. Small text files.
- **Maturity:** Official regulator data.
- **Evidence quality:** (a) is risk control with sound logic. (b) is **weak**: FINRA files cover only off-exchange prints, so the "short volume ratio" mixes market-maker hedging with real shorting and is noisy. Expect little IC.

### 9. Qlib: Alpha158 features + LightGBM cross-sectional ranker (stretch goal)
- **URL:** https://github.com/microsoft/qlib
- **What it does:** End-to-end quant research platform: data layer, 158 price/volume features (Alpha158), LightGBM/GBDT and deep models, rolling retraining, backtest and analysis.
- **Helps:** 24-Hour swing book and 14-Day picks, as a *ranker* inside the candidate list rather than a new strategy.
- **Experiment:** Load the item-1 Alpaca history into Qlib format. Train LightGBM on Alpha158 to predict 5-day and 14-day market-excess returns with rolling yearly retraining, 2016–2026. Use its score only to **rank the setup candidates our rules already pick** (top-N of the RSI2 and breakout hits), and compare against picking by RSI2 depth or volume ratio. The Re(Visiting) paper is a useful pointer: gradient-boosted trees on features beat foundation models on daily returns, so this is the strongest "ML" baseline we could run.
- **Cost/compute:** Free. LightGBM CPU training on ~4M rows × 158 features is roughly minutes per fold on 2 cores (estimated). Qlib setup is the heaviest of anything here: data conversion and its own config system.
- **Maturity:** 49,745 stars, pushed 2026-10-22, MIT. Its published benchmarks are mostly China A-shares (CSI300).
- **Evidence quality:** **Weak for our use.** The published IC figures are on Chinese markets and gross of costs. US large-cap daily ML returns are much thinner. Adopt only after items 1–4.

### 10. FINSABER: bias-aware backtest framework and benchmark from the LLM-trading critique
- **URL:** https://github.com/waylonli/FINSABER/ · paper (KDD 2026) https://arxiv.org/abs/2505.07078
- **What it does:** Backtesting package (FINSABER-2) built to test trading strategies, including LLM agents, with survivorship-, look-ahead- and data-snooping-bias controls over about 20 years and 100+ symbols.
- **Helps:** Our method for any LLM-in-the-loop test, such as the Perplexity decision layer and the AI CALL side test.
- **Experiment:** Don't adopt the framework wholesale. Copy its test protocol for any LLM signal: post-knowledge-cutoff data only, broad universe, report by market regime (bull vs bear), and always against buy-and-hold. Its finding that LLM strategies are "overly conservative in bull markets... overly aggressive in bear markets" matches what to watch for in our AI CALL line.
- **Cost/compute:** Free, CPU (LLM calls aside).
- **Maturity:** Stars not retrieved (GitHub API rate limit). Academic repo tied to a peer-reviewed paper.
- **Evidence quality:** **Strong** as a negative result about LLM traders.

### 11. pandas-ta-classic / TA-Lib: indicator libraries for the research harness only
- **URLs:** https://github.com/xgboosted/pandas-ta-classic (460 stars, pushed 2026-10-23, MIT) · https://github.com/TA-Lib/ta-lib-python (12,336 stars, pushed 2026-10-26, BSD-2-Clause)
- **What it does:** Vetted RSI/ATR/ADX and similar indicators, used to cross-check our hand-rolled pandas-free RSI2/ATR so the backtest and the live script compute identical values.
- **Note:** The original `twopirllc/pandas-ta` is gone from GitHub. Its PyPI history was wiped and replaced by releases under a new maintainer, with provenance questioned (https://github.com/TradeMaster-NTU/TradeMaster/issues/236; https://discuss.python.org/t/stop-allowing-deleting-things-from-pypi/17227/118). **Do not `pip install pandas-ta`**; use pandas-ta-classic or TA-Lib.
- **Evidence quality:** N/A (utility). Low priority, ranked last because our indicators are simple.

---

## Skip list (one-line reasons)
- **TradingAgents** (TauricResearch, 116,818 stars, Apache-2.0): the paper's evaluation covers Jan 1–Mar 29, 2024 on 3 tickers (AAPL, GOOGL, AMZN), and I found no independent after-cost replication. It's also very expensive in LLM calls per ticker per day, impossible across 1,800 names.
- **virattt/ai-hedge-fund** (64,283 stars, MIT): educational demo with persona agents; no independent broad-universe evidence (Perplexity sonar-pro check, 2026-10-27).
- **FinRobot** (8,316 stars) and **FinMem** (967 stars, last push Aug 2024): FINSABER shows FinMem/FinAgent-style gains go away over 20 years and 100+ symbols, and both underperform simple baselines.
- **FinGPT** (21,475 stars, MIT): the sentiment models are 7B–13B LoRA adapters (e.g. fingpt-sentiment_llama2-13b_lora, 0 HF downloads last month), so not CPU-practical. Benchmarks measure labelling accuracy, not returns, and Perplexity already covers this.
- **Lag-Llama** (1,601 stars, last push June 2025): stale, and an older-generation TSFM that is weaker than Chronos-2/TimesFM-2.5, which already fail on returns.
- **Moirai-2.0 / uni2ts** (1,616 stars) and **IBM TTM / granite-tsfm** (917 stars) for return prediction: same random-walk finding (arXiv 2606.27100). Only revisit as vol forecasters if Chronos shows value.
- **Kronos** (shiyu-coder, 43,903 stars, MIT): already being side-tested. Its paper's excess-return claims are on its own benchmark. Keep the vol side test running to the planned mid-Nov decision; don't expand it.
- **TimesFM for returns:** see item 7. Fine for vol, not direction.
- **zipline-reloaded** (1,987 stars): event-driven, needs a data "bundle" ingest, and is slow for 1,800 names × parameter sweeps. vectorbt does the same job faster.
- **QuantConnect Lean** (22,260 stars): C#/Docker engine; free US equity data lives in their cloud, and local data is paid or DIY. Too heavy for a CPU sandbox research loop.
- **backtesting.py** (9,150 stars, AGPL-3.0): single-instrument by design, can't do cross-sectional 1,800-name portfolios.
- **bt** (3,010 stars, MIT): portfolio weight/rebalance framework, poor fit for per-trade stops, trailing stops and time stops.
- **nautilus_trader** (30,929 stars, LGPL-3.0): production-grade event engine for intraday/HFT, overkill for 2 decision windows a day.
- **OpenBB** (now openbq-org/OpenBB, 74,777 stars): a data-aggregation wrapper. Its free providers add nothing over Nasdaq + Alpaca + SEC + FINRA, and the license changed.
- **yfinance** (25,621 stars): unofficial scraping with Yahoo ToS issues and breaks often; Alpaca history replaces it.
- **Free options-flow data:** no credible free source exists. Alpaca's free options feed is "indicative" quotes, not prints/flow. Skip until a paid feed is justified.
- **FinRL / RL traders:** weak, mostly in-sample evidence, and heavy tuning.
- **ORB intraday:** already tested negative on our scoreboard (62 days, PF 0.86), consistent with expectations. Don't revisit.
- **Chen-Zimmermann OpenSourceAP as a data source:** most of its ~200 signals are monthly/fundamental, and the portfolio code needs CRSP/WRDS. Use it only as a reference for exact signal definitions (STreversal, EarningsSurprise, AnalystRevision).

---

## Top 3 to adopt first, in order
1. **Alpaca 2016–2026 history pull (item 1).** Nothing else can be judged on ~275 sessions. First check whether delisted symbols are served, since that decides how much to discount every backtest.
2. **vectorbt replica of the live v2 rules (item 2), with costs and short borrow.** This answers the main question directly: do our current setups beat SPY over 10 years, in which regimes, and which setup carries the book? Expect to cut at least one setup.
3. **alphalens-reloaded signal gate (item 3), first run on the residual-reversal swap (item 4) and the earnings blackout / post-miss tilt (item 5).** These are the cheapest, best-evidenced ways to improve the RSI2 and short legs, and they need no new paid data or GPU.

After those: run the news three-way side test (item 6) and the Chronos-vs-ATR volatility test (item 7) in parallel as logged-only SIDE lines, with the same ~20-session decision rule we use for Kronos.

## Honest caveats on all of the above
- Any backtest on today's universe has survivorship bias. Shorts are hurt by it less than longs, but the long book looks better than it really is.
- Our round-trip cost assumption (10–20 bps incl. spread at 9:45/3:45 ET) is the main killer of short-horizon edges; the reversal literature shows the sign flips between 5 and 10 bps.
- With 2 decision windows, ~10 positions and 5-day holds, even a true edge needs months of live paper data to separate from noise. "Beat SPY 50% of days" after 2 days means nothing yet.
- No item here was installed or run. Compute estimates for Chronos and LightGBM are estimates, not timings.

## Sources consulted (key)
- TSFMs in finance: https://arxiv.org/abs/2511.18578 · https://arxiv.org/abs/2606.27100 · https://chronos-ts.ai/
- LLM traders: https://arxiv.org/abs/2505.07078 · https://arxiv.org/html/2412.20138v1 · FINSABER repo https://github.com/waylonli/FINSABER/
- News/LLM vs FinBERT: https://arxiv.org/abs/2304.07619 · https://arxiv.org/abs/2412.19245 · https://arxiv.org/html/2409.11408v1
- Reversal: https://github.com/Itaru-Shin/short-term-reversal-study · https://www.sciencedirect.com/science/article/abs/pii/S1386418112000468 · https://www.sciencedirect.com/science/article/pii/S0165176526003095 · https://www.nber.org/system/files/working_papers/w35840/w35840.pdf · https://www.sciencedirect.com/science/article/abs/pii/S0378426611002263
- PEAD: https://finlab.finance/en/blog/us-earnings-surprise-strategy · http://arc.hhs.se/download.aspx?MediumId=6317 · https://github.com/dylan-jeon/earnings-surprise-analysis · https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7137218
- Alpaca data plan: https://docs.alpaca.markets/docs/about-market-data-api · https://forum.alpaca.markets/t/iex-or-sip-with-a-free-account/17141
- FINRA: https://www.finra.org/finra-data/browse-catalog/short-sale-volume · https://developer.finra.org/catalog
- pandas-ta status: https://github.com/xgboosted/pandas-ta-classic/issues/30 · https://github.com/TradeMaster-NTU/TradeMaster/issues/236
- Repo stats: GitHub REST API and HF API, queried 2026-10-27 (raw output in work/gh.txt).
