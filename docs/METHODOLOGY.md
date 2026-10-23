# Methodology and evidence boundaries

## Core question

Does dated event, price/volume and accessible liquidity evidence improve useful stock-research alerts and risk understanding over simpler baselines? Multi-agent roles are tested separately from the numerical strategy; they are not assumed to generate profitable trades.

## Three different outputs

1. **Historical observation:** an imported, dated price series or a recorded quote. Store provenance and actual availability. Demo fixtures are synthetic and cannot establish real-market findings.
2. **Backtest:** accounting over eligible historical observations under frozen rules and assumptions. This implementation uses next-observed-open fills, whole shares, explicit hypothetical costs and final mark-to-market. It does not handle corporate actions or a complete India fee schedule automatically.
3. **Scenario:** a C++ bootstrap/GBM simulation conditional on the selected past calibration and stresses. Percentile bands are not bounds on the unknown real future.

## Evidence card

Every research report records the analysis cutoff, horizon, supporting and opposing facts, missing information, invalidation conditions and source references. Separate observed, estimated and generated claims. “Insufficient evidence” is an acceptable result. A language model's asserted confidence is not a calibrated probability.

Indicators describe context. The numerical research baseline uses prior rolling price levels and relative volume rather than making RSI/MACD the recommendation engine. The current bar is excluded from its reference level/volume denominator. A retrospectively confirmed pivot cannot be treated as known earlier.

Displayed book imbalance compares resting bid/ask quantities. It does not identify completed buying, cancellation intent, hidden liquidity or spoofing. Only enable executed-trade features if the provider actually supplies suitable trade events; otherwise label the capability unavailable.

## Experiment protocol

- Freeze the chosen universe and define development/validation/final periods chronologically.
- Set rule thresholds and prompts before inspecting final results.
- Compare price/volume, indicator-only and buy-and-hold baselines on the same dates and consistent accounting. Add news/depth only over their actual shared eligible period.
- Exclude unsupported corporate-action intervals or process the events before interpreting results. Adjusted prices are not raw exchange fills.
- Record failed requests, gaps and model changes. Missing news is not neutral sentiment; unavailable depth is not zero imbalance.
- Use prospective logged model reports and paper observations for cleaner generative-agent evaluation. A modern model may already know historical outcomes.
- Compare single/multiple agents using identical evidence, disclosed model/token budgets, factual-support scores, missing-data handling, latency and cost. Unbounded extra calls are not a fair comparison.
- A selected five-stock case study is not evidence for every security or market regime. Report negative findings and the configurations tried.

## Monte Carlo conventions

Circular-block bootstrap samples contiguous log-return blocks, wrapping at the calibration boundary. GBM fits a daily log mean and sample volatility; stress settings change volatility, drift, initial wealth shock and an entry-spread scenario. Historical drift is noisy. Both models can miss structural breaks.

The engine reports wealth percentiles, probability of a terminal loss, and nonnegative currency VaR/expected shortfall relative to starting wealth. Tail expected loss averages the worst 5% probability mass. Inspect the engine's returned assumptions, calibration window and seed before interpreting any value. Repeatability is tied to the pinned engine/compiler, particularly its normal generator.

## Useful primary references

- [TradingAgents](https://arxiv.org/abs/2412.20138): specialist financial agents are prior work.
- [LLM look-ahead bias](https://arxiv.org/abs/2309.17322): timestamp filtering alone does not remove pretrained outcome knowledge.
- [Queue imbalance](https://arxiv.org/abs/1512.03492): studies a short next-price-movement horizon, not long-term investment performance.
- [NSE feed definitions](https://www.nseindia.com/static/market-data/real-time-data-subscription): L1/L2/L3 names differ from individual-order access.
- [OpenRouter limits](https://openrouter.ai/docs/api_reference/limits): free usage is quota-limited.
- [Upstox Analytics Token](https://upstox.com/developer/api-documentation/analytics-token/): account-dependent read-only data access.

No headline, source or financial result should be invented to fill a missing dataset.
