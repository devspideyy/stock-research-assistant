# Future research and implementation programme

**Date:** 24 October 2026. This is a proposed study and engineering plan, not completed
experiments. Provider documents establish advertised capabilities; authenticated
coverage and account entitlements remain unverified. Start with the companion audit.

## 1. Research contribution and questions

Frame the project as an **evidence-grounded research and monitoring system for Indian
cash equities**. The contribution should be reproducibility, information timing,
transparent disagreement and measurable agent usefulness under a constrained budget.
Adding more indicators or agent names alone is not a convincing academic contribution.

Pre-register four questions before examining test results:

1. Do dated company events add information beyond price/volume baselines?
2. Does a reviewer improve factual support, uncertainty reporting and useful abstention?
3. Does a three-role process improve outcomes over a single model under matched budgets?
4. Can the system monitor selected Indian equities reliably with the actual free quota?

TradingAgents is relevant prior work for specialized roles and collaboration. Its authors'
reported performance does not establish performance for our data, market, costs or
implementation. Compare its architecture and experimental design; do not copy its
results into the project. [Paper](https://arxiv.org/abs/2412.20138),
[author repository](https://github.com/TauricResearch/TradingAgents).

## 2. Data contract before data volume

Create explicit records for instrument identity, bar interval, session/timezone,
adjustment basis, source timestamps, receipt timestamps and dataset version. Persist
immutable raw responses separately from validated research tables. Checksums make
experiments repeatable; they do not prove that an upstream dataset is financially correct.

Use provider instrument keys and exchange/ISIN mappings. Preserve symbol changes,
listing periods and effective dates. Store daily catalogue snapshots going forward.
Today's master is not a point-in-time historical universe and omits delisted history.
Until historical membership is obtained, call the sample a disclosed fixed/current-
survivor sample and avoid market-wide generalizations. [Provider instrument definitions](https://upstox.com/developer/api-documentation/instruments/).

Distinguish stock availability, quote entitlement, historical coverage and order-book
coverage. A successful quote for one stock does not prove complete coverage of its
sector or all exchanges. Validate a small sample containing liquid main-board stocks,
an illiquid case, cross-listings, a recent IPO, corporate actions and an SME instrument.

## 3. Price history, actions and execution

Upstox provides configurable historical intervals and retrieval windows, but its generic
history documentation is not proof of complete adjustment/publication semantics.
Check listing-specific coverage, missing sessions, timestamp meaning, split/bonus factors,
volume units and revisions. Do not infer that all stocks have data from the documented
earliest date. [Historical API](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/).

Separate two experiments: consistently adjusted total-return research, and raw-price
execution accounting with corporate-action events. Compare known split/bonus/dividend
examples against source records. Preserve announcement and ex/effective dates; each
has a different role. Never fill a missing historical day with a present quote.

Extend execution incrementally: dated fees, lot sizes, price bands, suspension, auction
semantics and volume-participation constraints. Keep close-triggered next-open stops
clearly named. Compare spread/impact stress across liquidity groups. NSE explains
that impact cost depends on order size; a bid/ask spread alone does not capture it.
[NSE impact cost](https://www.nseindia.com/static/products-services/indices-impact-cost).

Acceptance: action-adjustment reconciliation fixtures, accounting identities, no
negative cash, correct lot constraints and rejection/explicit qualification of unsuitable
datasets. A convenient price series is not automatically a valid execution dataset.

## 4. A defensible backtest study

Use chronological development, validation and a final untouched test period. Record
every parameter/model trial. If labels or holding windows overlap, ensure train/test
boundaries do not share those outcomes. Random row splitting is inappropriate here.

Baseline arms should include cash, consistently costed buy-and-hold, the current
price/volume rule, the simple indicator rule, and an event-enhanced rule. Align tradable
start dates and capital/exposure assumptions. Compare matched-period and full-history
results separately rather than letting different warm-up periods obscure comparisons.

Report return, drawdown, volatility, exposure, turnover, fills/round trips, costs and
benchmark-relative performance. Explain the risk-free-rate convention. Estimate
uncertainty with methods that respect temporal dependence; avoid interpreting a few
trades as statistically decisive. Add market/sector regime and liquidity breakdowns.

Repeated tuning can produce attractive performance by chance. Bailey et al. motivate
measuring backtest-overfitting risk; use a trial registry and a locked evaluation
protocol now, and consider PBO/deflated-Sharpe procedures when the experiment count
and sample support them. Such statistics do not cure bad timestamps or missing actions.
[Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf).

## 5. News and sentiment

Archive publication time, first-seen time, source URL, company mapping, deduplication
ID and permitted text. Decide how corrected stories, syndicated duplicates, multiple
companies and after-hours publications are handled. Validate whether the provider
supplies an historical archive or only recent stories before designing a news backtest.

Compare a simple lexical baseline, a finance-specific classifier such as FinBERT, and
the selected LLM. FinBERT is relevant domain-adaptation research; its original results
do not transfer automatically to Indian corporate language, mixed languages or current
headlines. Check the chosen model/dataset licences before distributing them.
[FinBERT paper](https://arxiv.org/abs/1908.10063).

Create a modest manually reviewed Indian-company test set, ideally with independent
annotations and a clear neutral/uncertain policy. Measure per-class precision/recall,
macro F1, entity-linking errors and abstentions. Sentiment accuracy and subsequent
return prediction are separate targets. A positive announcement may already be priced in.

Modern models may know historical outcomes from pretraining. Date filtering the prompt
alone does not remove that contamination. Treat company masking as a diagnostic,
not proof of purity, and prioritize genuinely prospective logged evaluations.
[Glasserman and Lin](https://arxiv.org/abs/2309.17322).

## 6. Agent evaluation and grounding

Use exactly the same evidence snapshot across deterministic, single-model and multi-role
arms. Pin the model identifier where possible and record the actually served identity,
prompt version, generation settings, timestamp, latency, token usage and failures.
The random free router is convenient for demonstrations but weak for controlled comparisons.

Match total call/token budgets or report the difference explicitly. A single model with
an equivalent revision budget is a useful comparison against three specialist prompts.
Role labels do not establish independent opinions. Add ablations for reviewer/no-reviewer,
news/no-news and price-volume/indicator context.

Score claim support, factual/numerical errors, unsupported causal claims, citation
correctness, contradictory conclusions, useful abstention and latency/cost. Verify
citations semantically: an existing fact ID can still support the wrong sentence.
Treat external news as untrusted content; retain bounded outputs and no execution tools.
Partial failures need durable state so a rejected third role does not waste two calls.

Under the app's current 50-call local daily cap with ten calls reserved for chat, only
40 report calls remain: thirteen complete three-call reports, with one spare call.
That is a code-budget calculation, not a promise of upstream capacity. Query current
account limits and obey provider backoff. Do not multiply accounts to evade quotas.
[OpenRouter limits](https://openrouter.ai/docs/api/reference/limits).

## 7. Indicators and the non-lagging requirement

Maintain a broad selectable catalogue for exploration, but preselect small, distinct
feature families for experiments: structure, volume, volatility, trend and dated events.
Do not feed dozens of correlated oscillators into a voting system and call the votes
independent confirmation. All price-derived indicators summarize observed information;
calling one 'leading' does not prove forecasting ability.

Standardize warm-up, initialization and missing-value policies. Add explicit parity
tests where definitions match and document intentional differences where they do not.
MAVP's current constant schedule is not an adaptive indicator. BETA/CORREL on selected
OHLCV columns are not benchmark beta/correlation. Session VWAP needs appropriate
session/traded-value inputs; bar HLC3-volume weighting is an approximation.

## 8. Monte Carlo and uncertainty

Keep GBM and circular-block bootstrap as transparent baselines. Investigate block-size
sensitivity and data-driven selection, and compare recent versus long calibration windows.
The arch documentation is a useful reference for stationary/circular bootstraps and
block-length methods, not a requirement to replace the native engine.
[Time-series bootstrap methods](https://bashtage.github.io/arch/bootstrap/timeseries-bootstraps.html).

Separate invested-asset wealth simulation from strategy-return simulation. For the latter,
account for cash periods, turnover, costs and dependence. A portfolio extension needs
jointly sampled returns/correlations rather than independent single-stock paths.
Consider volatility clustering only after the simpler models have been assessed.

Report Monte Carlo sampling error and sensitivity to the historical drift estimate.
More simulated paths reduce numerical noise, not model uncertainty. Test distributions
against held-out/prospective observations; fan charts remain conditional distributions,
not guaranteed price intervals or validated loss limits.

## 9. Microstructure: correct names and realistic scope

NSE's definitions distinguish best bid/ask, five levels, twenty levels and a full-order-
book tick product. Neither twenty displayed levels nor Upstox's thirty-level mode should
be casually called a complete individual-order history. Five-level snapshots can support
spread/visible-imbalance studies; cancellations, aggressor flow and true CVD require
appropriate event/trade information. [NSE feed definitions](https://www.nseindia.com/static/market-data/real-time-data-subscription).

First study spread, depth stability and short-horizon quote changes with sampling/gap
metadata. Do not mix an intraday liquidity observation into a long-horizon investment
score without separately testing its incremental usefulness. No verified free complete
order-event archive is available to this project; make advanced order-flow work conditional.

## 10. Monitoring and free operation

Separate source publication/trade times, feed-transport health and receipt times. Track
closed markets, illiquid stocks, quote age, last heartbeat and reconnect gaps separately.
Batch/persist calls within documented REST limits, cache history and use streaming only
where supported. Today's worker has neither a fleet scheduler nor full-universe quota control.

Archive daily universe snapshots broadly; allocate richer data to selected instruments.
Upstox currently distinguishes normal LTPC/full/mixed subscription limits and Plus depth.
Do not assume two connections independently multiply all account allowances.
[Market Data Feed V3](https://upstox.com/developer/api-documentation/v3/get-market-data-feed/).

Validate duplicate events, disconnects, authentication expiry, restart recovery, missing
timestamps and host sleep. Use bounded exponential backoff with jitter and provider
retry guidance. An awake local machine is adequate for a student demonstration; it is
not a guarantee of free hosted 24/7 uptime.

## 11. Architecture and placement value

Keep the understandable C++ numerical engine, Python orchestration and Streamlit UI.
SQLite is suitable for this prototype after startup/concurrency problems are fixed.
Use an immutable raw-data cache and clear service boundaries before considering heavier
infrastructure. Do not add Kafka, Kubernetes, vector databases or agent frameworks
without a measured requirement. Profile batch sizes before changing the JSON process
boundary to native bindings; do not claim C++ speedups without measurements.

For interviews, demonstrate one trace from source timestamp through validation, feature,
decision, execution assumption and reproducible result. Explain failure cases, why an
agent abstained, and what extra complexity gained over a baseline. Keep external SDK
licences/versions and data-provider redistribution conditions visible in documentation.

## 12. Milestones and completion gates

| Milestone | Engineering estimate | Evidence required before moving on |
| --- | --- | --- |
| Correctness repairs | 2–4 focused days | A01–A07 regressions; repeated concurrent startup checks; explicit time/provenance contract |
| Small real-data integration | About 1 week after credentials | Identity/freshness/coverage checks; stable history cache; no synthetic fallback |
| Actions, costs and backtest protocol | 1–2 weeks | Reconciled action fixtures; frozen splits; cost/lot constraints; trial log |
| News/fundamentals and AI | 1–2 weeks | Timestamped evidence; reviewed labels/claims; matched-budget agent runs |
| Monitoring reliability | About 1 week, overlapping | Recorded restart/gap/backoff tests; quota measurements; bounded watchlist |
| Evaluation and write-up | 2–3 weeks plus observation time | Baseline/ablation results, error analysis, reproducible artifacts and honest limitations |

These are planning estimates, not additive guarantees: credentials, data quality,
available weekly hours and parallelizable work affect duration. Allow roughly **8–12
weeks of part-time work** for a substantially evaluated version. Start a forward log
early; a 4–8 week observation period provides an initial operational study, not strong
statistical proof from a small daily sample. Remaining academic time should be used
to improve evidence quality, not expand the feature count indefinitely.

## Immediate next work without credentials

Repair the audit cases, add data/session schemas, design the locked experiment protocol,
prepare corporate-action fixtures, annotate sample news with clear licensing, and build
disconnect/recovery simulations. None requires account tokens. Once those are ready,
connect the smallest representative real-data sample before broadening coverage.
