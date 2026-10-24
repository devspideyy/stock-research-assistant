# Recommendations, strategy experiments and playback

This release adds useful research decisions and richer experiments. It remains a
research prototype, not an industry-validated recommendation service. Real data,
corporate-action accounting, execution realism and prospective evaluation are still
needed. No broker orders or automatic model calls were added.

## Stock research cases

Use **Assess selected stock** in Overview, or open **Stock ideas**. The latter can
assess the active dataset, the five fictional demo scenarios, or 1–10 daily OHLCV
CSV files. Batch imports require a daily-bar declaration and a decision time for
date-only evidence. Scans are explicit actions, make no authenticated requests,
and clear when their inputs change. Catalogue identifiers contain no price history
and cannot be ranked on their own.

Each card records its instrument, source scope, cutoff, recommendation, price
regime, opposing cases, strategy hypotheses, missing evidence and invalidations.
Cards can be saved to the existing evidence history or exported. History and demo
cards retain their labels; they are not current recommendations.
Daily interval declarations and plausible date spacing are checked before rating.
The evidence also retains the native executable and request hashes for reproducibility.

### Explainable scores, policy `price-evidence-v1`

| Factor | Maximum points | Bullish / bearish evidence |
| --- | --- | --- |
| Prior range break | 30 | Close above the previous 20-bar high / below its low |
| Prior price structure | 30 | Both high and low rise / fall between two prior ten-bar windows |
| 20-bar displacement | 15 | Return above / below one current ATR-to-close ratio |
| Candle-volume participation proxy | 15 | Relative volume ≥ 1.2 with positive / negative close-to-close change |
| SMA20 context | 10 | Close above / below SMA20 |

Reference ranges exclude the current candle. The C++ engine calculates the inputs;
Python applies the disclosed policy. A bullish-minus-bearish gap of at least 25
points gives a bullish watch; at most −25 gives a bearish case, otherwise mixed.
The 3% ATR/close volatility flag is another manually chosen threshold.

These are correlated, manually weighted hypotheses, not independent votes or
calibrated probabilities. Neutral factors award neither side points. Missing
factors remain unavailable and reduce the scorable weight; scores are not scaled
up to hide missing data. Invalid or insufficient histories receive no rating.
News meaning, valuation, benchmark/sector strength, liquidity and suitability are
not rated. Their absence remains visible. `R1` records the derived assessment in
the same evidence record as the underlying `P2`, `P3`, `V1` and `I1` facts.

Bullish means an observation worth investigating. Bearish means caution about new
long positions in this long-only project. It does not enable short selling.

## Five strategy hypotheses

- **Price + volume:** a prior-range breakout with the configured volume threshold.
- **Trend pullback:** higher prior highs/lows, positive 20-bar return, an up-close
  within 1.5 ATR below the prior high and relative volume of at least 0.8.
- **Range reversion:** mixed prior structure, absolute 20-bar return no larger than
  2 ATR/close, and an up-close in the bottom 20% of the prior range.
- **Indicator baseline:** close above SMA20, exit below it.
- **Buy and hold:** passive comparison from the next evaluation open.

Pullbacks exit below the prior low; range reversion exits on midpoint recovery or
support failure. Strategy stops remain close-based signals executed next observed
open. All active hypotheses use the configured fixed stop; buy-and-hold has no
strategy stop. All strategies retain whole shares, entry allocation limits and
costs on both sides. The in-app strategy table contains the rules and failure cases.

Default evaluation uses the final 30% of observations. The first evaluation bar
starts in cash; earlier bars warm up causal features only. The first possible fill
is the next evaluation open. No parameter fitting, optimiser or automatic
winner-selection is run. Once inspected or used for tuning, this period is no
longer an untouched holdout. A full-history mode is explicitly exploratory.

New metrics include closed-trade win rate, net realised P&L, fees, profit factor
and CAGR in the native output. Closed-trade P&L deducts entry and exit commission;
fill prices include configured slippage. Open positions are marked to market, so
realised P&L can differ from total equity return. Profit factor is missing when
there are no losses, rather than reported as a finite or guaranteed gain.

## Replay and Monte Carlo distribution

Backtest equity curves and Monte Carlo paths have **Play**, **Pause** and a
checkpoint scrubber. The chart annotation shows the actual replay date/step.
Playback reads completed results; it does not advance the market clock, rerun the
engine or call an API. Charts initially show the completed run and only animate
when Play is pressed. The toggle enables a static view.

Replay is limited to 36 frames and 300 displayed points per trace to bound browser
payloads. The final point is preserved, scales are fixed and no interpolated
financial observations are invented. Metrics and exports use all observations.
The simulation's 20-bin terminal histogram counts every generated path; a flat
distribution uses one bin. Paths and percentile bands remain conditional on model
assumptions, and do not represent a confidence interval for actual future prices.
The simulation describes one invested wealth process from stock returns, not the
selected active strategy or a diversified portfolio.

## What to do next

1. Obtain permitted real daily histories with dated corporate actions, a benchmark
   and source/publication metadata. Use these to audit the new cases and rules.
2. Implement corporate-action accounting and dated Indian charges, then add
   liquidity/lot/circuit and gap scenarios before judging net performance.
3. Freeze policies and evaluation windows; compare against benchmarks on a genuine
   untouched period and prospectively logged paper observations. Compare single
   versus multiple LLM roles on identical evidence and call budgets.
4. Connect an authorised broker feed and validate instrument identity, timestamps,
   reconnect behaviour and market-session freshness before enabling current alerts.

Only after these steps should production reliability and recommendation quality
be assessed. Feature count and passing software tests do not establish profitability.

## Verification for this release

The full Python suite passes 259 tests, including native integration and Streamlit
workflows. The nine existing C++ test groups also pass. Added fixtures cover known
bullish/bearish cases, missing-volume and daily-interval gates, native provenance,
holdout timing, causal pullback fills, range exits, both-side fees, histogram totals,
bounded replay and preservation of terminal values. Both replay controls were checked
in the browser. No authenticated financial-data or model call was needed.

## References and interpretation

- [CME support and resistance](https://www.cmegroup.com/education/courses/technical-analysis/support-and-resistance)
  describes the underlying concept; it does not validate this project's weights.
- [CFA Institute: Backtesting & Simulation](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/backtesting-and-simulation)
  discusses evaluation, assumptions, pitfalls and complementary scenario analysis.
- [QuantConnect walk-forward documentation](https://www.quantconnect.com/docs/v2/writing-algorithms/optimization/walk-forward-optimization)
  distinguishes rolling optimisation from this project's simpler fixed holdout.
- [Plotly animations](https://plotly.com/python/animations/) documents frames,
  controls and the need for stable traces/scales, used by the Python replay helper.
