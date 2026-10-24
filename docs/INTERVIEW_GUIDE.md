# Placement preparation

## Explain the project in one minute

“I built a C++ quantitative engine with a Python research interface. It computes price/volume features, performs next-bar strategy backtests and explores risk through bootstrap and GBM simulations. Python handles data provenance, role-based AI reports, a chatbot and a separate monitoring worker. The system distinguishes historical evidence, simulated outcomes and generated explanation. I test the accounting and information timing, and compare extra agent complexity against simpler baselines.”

Only claim features that you can run and explain. A demo fixture is not real-market performance.

## Questions to prepare

| Question | What your answer should cover |
| --- | --- |
| Why C++ and Python? | C++ owns reusable numerical logic; Python makes UI/API/model integration approachable. No unsupported claim of speed superiority without measurement. |
| Why a process boundary? | A JSON CLI is independently testable and easy to debug. It adds serialization/startup overhead; batch inputs and profile before using native Python bindings. |
| How do you prevent look-ahead? | Prior levels exclude the current bar; close signals fill next open; only information available by the cutoff is eligible. |
| Why not rely on RSI? | It summarizes past price context. The core research asks whether price/volume, events and accessible liquidity contribute beyond simple indicators. |
| What does a large bid quantity mean? | Displayed resting demand at that instant; it can change/cancel and does not establish executed buying or hidden intent. |
| Why is CVD unavailable? | Snapshot/LTP fields do not establish a complete aggressor-labelled trade tape. Making one up would be a data error. |
| What does Monte Carlo establish? | Conditional scenario distributions under fitted/selected assumptions, not a guaranteed future price or return. |
| Bootstrap versus GBM? | Bootstrap resamples historical return patterns; GBM uses a parametric lognormal price model. Both have model/data risk. |
| Why can a stop lose more than its setting? | This version observes closes and executes at the next open; overnight gaps and costs can exceed the threshold. |
| Why might a profitable backtest fail? | Costs, selection bias, tuning to outcomes, structural changes, data errors and uncertain execution. |
| What do bullish/bearish scores mean? | Transparent, versioned price-evidence weights. They are correlated heuristic points, not calibrated probabilities or a validated valuation rating. Missing factors remain unscored. |
| How does the holdout work? | The final 30% starts in cash; earlier bars warm up causal features only. No fitting occurs. Tuning after looking at the holdout means it is no longer untouched. |
| Does animation rerun the experiment? | No. Plotly frames replay completed native results with bounded displayed points and fixed scales. Metrics and exports use the full data. |
| How do agents differ? | Different evidence roles and a reviewer with explicit inputs/outputs. Test whether they add useful accuracy rather than assuming more agents are better. |
| What fails when the internet goes away? | External refresh/model calls fail visibly; saved data and native calculations remain available. Worker gaps must be recorded. |
| How is 24/7 achieved? | A separate worker on an always-awake host, durable checkpoints, retries and heartbeat monitoring. The browser alone is not infrastructure. |

## Code reading order

Read the native candle validation, feature calculation, backtest loop and simulation methods; then the Python JSON bridge, evidence builder, provider budget/storage boundary and dashboard. Trace one known example from input to output before adding more features.
