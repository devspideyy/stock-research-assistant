# Offline accounting and validation

Implemented 24 October 2026. No broker, model, TradingView subscription or API key is
needed for these calculations. These are auditable research conventions, not a
broker statement simulator or evidence of market profitability.

## Price and event contract

For imported data choose raw, already adjusted, or unverified prices. Declared events
are accepted only with raw prices; adjusted data plus events is rejected to prevent
double adjustment. Event sources are recorded, not fetched or independently verified.
An event needs a valid announcement date earlier than its ex-date. The ex-date must
match exactly one supplied daily bar with a prior observation. At most one share
event and one cash dividend per ex-date are supported.

The [fictional action example](../examples/corporate_actions.json) and its
[matching raw prices](../examples/accounting_fixture.csv) are for native/automated
accounting checks. The historical research UI now caps normal data at 2020 and
reserves synthetic fixture controls for tests. Never attach fictional events to
a real security. See [the current historical workflow](HISTORICAL_RESEARCH.md).

| Field | Meaning |
| --- | --- |
| `type` | `split`, `bonus`, or `cash_dividend` |
| `ex_date`, `announced_date`, `source` | Required for every event |
| `share_multiplier` | New shares per old share; 2 means a 2-for-1 split or 1:1 bonus |
| `cash_per_share`, `pay_date` | Gross dividend per share and known payment date |

Share events change holdings, entry cost basis and stop reference on ex-date. Whole
shares are required; fractional entitlements/cash in lieu are rejected. Bonus credit
latency is not represented. A same-day share event is applied before a dividend;
the supplied dividend must therefore use post-share-event units. Rights, mergers,
demergers, delistings and liquidation distributions require a different model.

Gross dividends accrue to shares held before the ex-date's opening fill. Buying on
ex-date earns no entitlement; selling on ex-date retains the entitlement. The
receivable is an asset in equity, not spending cash. Payment is credited on the
first observed date on/after `pay_date`; a payment beyond the dataset stays unpaid.
Gross dividends belong to the closed trade's P&L even if payment is later. Withholding,
income tax, settlement failures and payment-time intraday ordering are not modelled.

Native signals use causal forward-normalised OHLC and split-normalised volume.
Factors apply from the event date onward, so later actions cannot rewrite prior
signals. ATR/price levels are returned in the raw units at each observation.
Dividends use the previous split-adjusted close for the total-return-style factor;
this is a convention, not a claim about the actual ex-date market move. Executions
always use supplied raw opens, with configured slippage. MC uses the same normalised
past returns but has no future dividend/share-payment ledger. Chart candles and
the separate TA-Lib indicator library retain source OHLCV and disclose that limit.

Missing actions are not detectable from a file alone. Already-adjusted OHLC avoids
some discontinuities but gives hypothetical historical fills and share sizes.

## Dated cost estimate

The default hypothetical bps mode remains available. The optional **NSE delivery
estimate** covers trade dates 2024-10-01 through 2026-10-24. Unknown execution dates
are rejected; it is not silently carried backward or forward. A programmatic custom
schedule must have nonoverlapping dated rows with IDs and sources.

| Component | Assumption |
| --- | --- |
| Brokerage | Editable bps per side, optional cap per fill; default zero |
| Delivery STT | 0.1% buy and sell |
| Exchange / IPFT before 2026-03-01 | ₹297 / ₹10 per crore per side |
| Exchange / IPFT from 2026-03-01 | ₹306.99 / ₹0.01 per crore per side |
| SEBI fee | ₹10 per crore per side |
| Stamp duty | 0.015% buy only |
| DP | Editable pre-GST sell charge; ₹13 is one broker example |
| GST | 18% of brokerage, exchange, IPFT, SEBI and DP in this estimate |

NSE's split between exchange and IPFT changes, while their combined ₹307/crore
remains constant. This follows the cash-segment table and effective date in
[NSE/FA/73061](https://nsearchives.nseindia.com/content/circulars/FA73061.pdf), together
with [NSE/FA/64232](https://nsearchives.nseindia.com/content/circulars/FA64232.pdf).
Tax/broker assumptions were reviewed against [Zerodha's charge table](https://zerodha.com/charges/)
and [DP explanation](https://support.zerodha.com/category/account-opening/resident-individual/ri-charges/articles/what-do-dp-charges-mean).
Their current pages are not certification of every historical account/tax treatment.
The schedule deliberately has a review cutoff and editable broker inputs.

This covers single-stock long/cash daily delivery simulations, not BSE, intraday,
derivatives, NRI/account-specific taxation or exact contract-note rounding. DP uses
one sell charge per fill; the daily single-position engine has at most one sell per
stock/day. Account maintenance, personal capital-gains/dividend taxes, minimum
brokerage rules, auction/settlement penalties, price limits, partial fills and market
impact are excluded. Whole-share sizing includes entry charges. Final mark-to-market
does not invent an exit or its costs. Exports retain the exact submitted schedule.

## Chronological Validation

At least 60 completed daily bars are required. The first 40% (at least 30 bars) is
initial feature history. Remaining bars are split into 2–5 disjoint test windows,
each at least five bars. Every fold starts in cash and uses its preceding history
for causal features only. The last close generates no imaginary next-open fill.
Future bars/actions are absent from an earlier fold's engine request.

These are fixed rules, not a trained model or parameter search. Each selected
strategy is compared with buy-and-hold on identical dates, capital and costs.
Optional stress doubles every charge component and slippage, including fixed
charges; this is sensitivity analysis, not a future-fee forecast. Position sizes
and signals may differ under stress. No universal claim of monotone strategy
returns under higher costs is made.

The UI reports positive folds, folds exceeding hold, median fold return and worst
fold drawdown, plus all per-fold details. It never stitches independent portfolios
or calls the best displayed rule a validated winner. Repeated tuning after viewing
these windows makes them exploratory. Reserve a genuinely untouched final dataset
and prospective observations for the dissertation's final conclusions.

Each study includes the source-candle hash, exact settings, engine/request hashes,
dates and synthetic flag. Up to ten studies persist in existing SQLite settings.
Keep original CSV/actions and the matching engine build too; hashes alone cannot
reconstruct inputs. No live financial or AI request is part of this workflow.
