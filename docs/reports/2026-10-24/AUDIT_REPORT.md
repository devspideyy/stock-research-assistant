# Implementation and research audit

**Date:** 24 October 2026. **Application baseline:** commit `43a9b8c`.
**Scope:** numerical timing/accounting, data boundaries, monitoring, evidence provenance,
indicator integration, provider claims and research validity. This is a correctness and
methodology review, not an exhaustive security audit or proof of financial effectiveness.

## Assessment

The application is a usable research prototype. Its C++/Python separation is reasonable,
the interface is functional, and synthetic data are visibly labelled. It is not yet a
validated live investment-recommendation system. Additional review found failures that
the existing tests did not cover. The number of tests must not be presented as proof
that financial assumptions or provider integrations are correct.

**This audit did not modify application runtime behaviour.** Findings below remain
open. A fixture script and raw results accompany this report.

## Confirmed findings

P1 means resolve before trusting real-data results; P2 means resolve before the affected
feature is evaluated. These are correctness priorities, not security severity scores.

| ID | Priority | Finding | Evidence / effect | Proposed correction |
| --- | --- | --- | --- | --- |
| A01 | P1 | Synthetic provenance is inferred from text rather than passed explicitly | Removing demo news/fundamentals makes `build_evidence` return `synthetic=false` for the same fictional candles. The page banner remains demo, but an exported evidence card can lose that provenance. | Pass an explicit dataset provenance object from every entry point; carry it into facts, IDs, reports and exports. Never infer authenticity from keywords. |
| A02 | P1 | Quote identity is optional | A mocked successful response containing only `last_price=123`, without an instrument token, is accepted for the requested stock. This does not prove a real provider has misidentified anything; it proves the client cannot fail closed on that malformed response. | Require a valid response schema and exact instrument identity, or a documented equivalent identity mapping; reject ambiguous/multiple entries. |
| A03 | P1 | Monitoring baseline is keyed by display symbol | Keeping label TEST while changing its provider instrument key reuses the former stock's price 100. A new stock priced 200 generates a false +100% price-change observation. | Key state by provider, exchange and immutable instrument key; reset baseline on a mapping change and include identity in every event. |
| A04 | P2 | Empty depth levels affect top-of-book calculations | Bid 100 with quantity 0, bid 99 with quantity 10, ask 101 with quantity 10 returns spread 1 instead of spread 2 over executable displayed levels. | Ignore zero-quantity levels before best-price selection, or reject them explicitly; handle empty sides and provider zero-filled padding. |
| A05 | P1 | Daily-frequency guard does not establish daily frequency | Weekly observations have unique dates and pass the dashboard guard; the engine still applies daily 252-session annualization. A single observation per date is necessary but insufficient. | Require explicit bar interval/session metadata, validate plausible spacing and gaps, and suppress annualized outputs when frequency is unverified. Do not reject legitimate holiday gaps merely because they are irregular. |
| A06 | P1 | Date-only bars are used as midnight UTC news cutoffs | A same-day 10:00 IST announcement is excluded from a completed daily bar's evidence, because the date is parsed as 00:00 UTC. This demonstrates ambiguous decision-time semantics; the correct cutoff requires exchange-session information. | Separate bar start, bar close, source publication, first observation and decision timestamps. For daily-close research, use the actual exchange close and documented latency. |
| A07 | P1 | SQLite WAL initialization can fail under concurrent startup | The full suite produced `database is locked` at `PRAGMA journal_mode=WAL` in the existing concurrent-budget test: 235 passed, 1 failed. | Initialize schema/WAL once under controlled startup, use bounded retries for appropriate busy errors, and retain atomic quota reservations. Add repeated cold-start and multi-process tests. |

### Code locations

- A01: `app/services.py`, `build_evidence`, synthetic detection; `app/dashboard.py`, overview caller.
- A02: `app/providers.py`, `fetch_upstox_quote`, optional `instrument_token` validation.
- A03: `app/monitor.py`, `checkpoint:live:{symbol}`.
- A04: `engine/src/engine.cpp`, `depth`, parsing and best-price selection.
- A05: `app/dashboard.py`, duplicate-date guards in the two research labs; native fixed daily conventions.
- A06: `app/services.py`, `_timestamp`, `observed` and eligible-news filtering.
- A07: `app/storage.py`, `connection`; `tests/test_services.py::test_budget_is_atomic_across_threads`.

### Reproduce and interpret

Run from the project folder:

```powershell
.\.venv\Scripts\python.exe scripts/audit_reproductions.py
.\.venv\Scripts\python.exe -m pytest tests/test_services.py::test_budget_is_atomic_across_threads -q
```

The script mocks provider responses, uses fictional inputs and isolates storage in a
temporary database. It makes no authenticated market-data requests and does not edit
the user's watchlist/database. See [raw fixtures](reproductions.json). The SQLite
issue is intermittent: a passing rerun does not invalidate the observed failure.
Cold-start rerun logs are saved alongside this report.
The three additional isolated runs failed, passed, and failed respectively. This
establishes repeatability, not an estimate of production failure frequency.

## Limitations already disclosed, rather than newly discovered bugs

1. **Corporate actions:** split/bonus/dividend accounting is not implemented. Adjusted
   OHLC cannot simply be mixed with historical raw shares or unadjusted volume.
2. **Execution:** next-observed-open execution and close-triggered stops are defined
   research conventions, not guaranteed exchange fills. Auctions, circuits, suspension,
   queue priority, market impact and SME lot requirements are not realistically modelled.
3. **Costs:** configurable bps are hypothetical; dated Indian brokerage/statutory charges
   are not complete. Do not describe the current model as net of all Indian costs.
4. **Universe:** today's provider catalogue omits delisted history and is unsuitable for
   claiming survivorship-free historical selection. Cross-listed exchange instruments
   are not independent companies. Catalogue counts are dated snapshots.
5. **Monte Carlo:** current runs simulate a single invested wealth process, not the
   dynamic strategy or a diversified portfolio. Conditional VaR/ES are model outputs,
   not calibrated future guarantees. Drift, regime and block-length sensitivity remain.
6. **Agents:** three sequential role prompts with a reviewer are implemented. There is
   no measured evidence that these roles outperform one model, a simpler pipeline or
   deterministic rules. Rules mode is correctly distinguished from generative AI.
7. **Grounding:** validating citation IDs and URLs checks structure, not whether the
   referenced fact supports the sentence. Entailment and numerical correctness need evaluation.
8. **Indicators:** 158 is the number of installed TA-Lib functions, including patterns
   and math utilities, not 158 independent predictors. The C++ and TA-Lib EMA/ATR/flat-RSI
   initialization conventions can differ. This needs explicit comparative documentation.
9. **Monitoring:** the worker is periodic snapshot polling, not a full event stream.
   Last-trade age is not feed-transport age. An illiquid stock may have an old trade
   while its quote connection is healthy. Broker access and LLM inference remain untested.

## Corrections to earlier descriptions

- NSE defines Level 1 as best bid/ask, Level 2 as five levels, Level 3 as twenty levels,
  and tick-by-tick as the full order book. Earlier shorthand equating L3 with individual
  order events was imprecise. Feed capabilities must be named explicitly. [NSE definitions](https://www.nseindia.com/static/market-data/real-time-data-subscription)
- All-stock **identifier search** has been implemented; all-stock **live analysis** has
  not. Upstox has connection/category subscription ceilings. [Feed documentation](https://upstox.com/developer/api-documentation/v3/get-market-data-feed/)
- The free one-year Upstox token is a credential lifetime, not a guaranteed perpetual
  free account or a verified entitlement for every dataset. Market-data categories
  currently support it without a static IP. [Token documentation](https://upstox.com/developer/api-documentation/analytics-token/)
- The original 236-test success was accurate for that run. This audit's full-suite run
  failed one concurrent test; reports should preserve both observations.
- The previous 6–8 week estimate was an estimate for continued development, not a
  promise of a statistically validated final system. Prospective observations take
  calendar time and cannot be created by speeding up implementation.

## What appears sound within the inspected scope

The inspected backtest computes signals from a close and executes them at a later
observed open. Prior price levels/relative-volume references exclude the current bar.
Buy/sell costs and whole-share cash constraints are represented. Final holdings are
marked rather than silently force-liquidated. Monte Carlo assumptions and compiler-
dependent seeded-normal reproducibility are disclosed. Native calls use structured
JSON and subprocess argument lists. These are useful foundations, not evidence of alpha.

## Recommended order

Fix A01–A07 with focused regressions before relying on live results. Then establish
frequency/corporate-action/identity contracts, connect a small verified sample, and only
then expand coverage. Keep the production baseline and this audit evidence available
so future fixes can be verified against exactly the same cases.
