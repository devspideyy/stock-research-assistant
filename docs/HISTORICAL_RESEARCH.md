# Historical stock workspace — 24 October 2026

The normal application now uses real historical data through **31 December 2020**.
The new ivory/green/brass interface combines a selected stock's chart, indicators,
backtest, validation, simulations and evidence under one workspace. Synthetic
fixtures remain in tests; news/API connections are deferred.

## What was prepared

- 46 stocks, 232,417 retained daily observations in the prepared cohort.
- Earliest retained records reach 1996; availability differs by stock and source.
- A pinned public catalogue exposes 2,577 candidate NSE history files. These are
  discoverable files, not a claim of 2,577 validated pre-2021 histories.
- AXISBANK failed an overlap check. HDFC, INFRATEL and TATAMOTORS were absent under
  those identifiers from the pinned source. No automatic merger/rename mapping was
  invented. These four entries are withheld from the initial cohort.
- The reference cohort comes from a retrospectively selected NIFTY dataset. Missing
  delisted/changed instruments imply survivorship and selection limitations. It is
  not a reconstructed historical index membership or a market-wide performance study.

The machine-readable coverage summary is [HISTORICAL_COVERAGE.csv](HISTORICAL_COVERAGE.csv).
Original price downloads stay under ignored `data/private/history/`, not in Git.

## Sources and reproducibility

1. [Public historical-data repository](https://github.com/aswinv90/indian-market-historical-data):
   per-stock Parquet files containing OHLC, adjusted close, volume and action fields.
   Catalogue/imports are pinned to revision `ea1fded13411`; each local file records
   its complete revision, download URL and SHA-256.
2. [NIFTY stock-history archive](https://www.kaggle.com/datasets/rohanrao/nifty50-stock-market-data):
   raw NSE-origin reference prices, company metadata and cohort identifiers. Used
   for overlap checks and cutoff-date rupee anchoring where available.
3. [Official NSE daily archives](https://www.nseindia.com/all-reports): a direct
   1 January 2020 bhavcopy download was compared against the reference archive.
   All 45 initially comparable stocks matched OHLC within ₹0.02. This is a one-date
   spot check, not certification of every row. Its URL/results are cached locally.

These are free public downloads without broker credentials. They remain third-party
or exchange data under applicable source terms; free access does not establish
redistribution rights or a complete academic-quality dataset. Source URLs are not
executed as instructions, and no downloaded program is run.

To reproduce the prepared cohort:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_history.py --reference-universe
.\.venv\Scripts\python.exe scripts/check_history.py
```

To import another candidate explicitly, use Add another historical stock in the
sidebar or `scripts/prepare_history.py --symbols SYMBOL`. No network request is made
when normal research loads cached stocks. Failed imports preserve previous files.

## Price and quality conventions

The importer removes all observations after the cutoff before computing research
prices. It scales OHLC together using the provider's adjusted-close ratio, rebased
at the cutoff. Where a reference close exists, it anchors the last price to that
date's raw rupee close. Later constant retrospective adjustment factors therefore
cancel. The provider snapshot itself was retrieved later and is **not point-in-time
data**; this cannot establish that the provider's corrections were known in 2020.

These are adjusted research units, not actual historical whole-share execution
prices. The raw-event accounting module remains available for separately verified
raw data; applying its events again to this adjusted library is rejected. Provider
volume units are retained. Missing dividend/action completeness is not independently
certified. No historical announcement or dividend payment dates are fabricated.

Invalid/zero/missing OHLCV records are omitted with their dates retained in source
metadata. More than 2% invalid observations rejects the import. No OHLC repair or
missing-date interpolation occurs. Duplicates are rejected. A long IPO-era reference
beginning after the general archive start restricts earlier provider rows, which
prevented accepting pre-reference TCS history. Optional locally supplied official
listing metadata can constrain dates further. This is not universal listing-date
certification, especially for on-demand stocks lacking a raw reference.

Ordinary overlapping daily returns are spot-checked every 97 observations against
the raw reference. Material disagreement quarantines the stock. Market-calendar
completeness, suspensions, settlement restrictions and all corporate actions still
require review. The [research protocol](RESEARCH_PROTOCOL.md) adds observed-session
gap gates, causal warm-up and separate elapsed-time CAGR. Daily annualised metrics
are withheld for explicitly gap-overridden runs.
Read Historical sources & data quality before interpreting a result.

## Backtest and Monte Carlo connection

The integrated Monte Carlo tab uses the chosen backtest's **net daily equity
returns**, including cash observations and existing execution charges. It uses
circular contiguous blocks to retain some local return dependence. It records
the original backtest hash plus the simulation request hash and source window.
Strategy GBM and a second entry-spread deduction are rejected. Stock-return bootstrap
and GBM remain separate, explicitly labelled stock scenarios.

This is return-distribution sensitivity, not signal recomputation on synthetic OHLC,
a calibrated real-future probability, or proof that an observed winner generalises.
No trades produces a flat-cash warning. Drawdown exceedance, percentiles and tail loss
are conditional on calibration, block length, seed, horizon and selected stresses.
Pre-2024 histories use explicit **hypothetical bps**, because the dated NSE estimate
does not cover those years. These results are not claimed net of all historical
Indian taxes, broker invoices or market impact.

## Verification

All 46 ready stocks passed actual native analysis, five strategy backtests, stock
scenarios, linked strategy simulations and RSI/ATR/MACD calculation. Three
representative stocks also passed the multi-fold validation runner. The acceptance
report in ignored `runs/historical_acceptance.json` records engine hashes and dates.
The updated run retains all earlier feature history and evaluates each stock's
complete observed-session tail (currently 3 February–31 December 2020), with
fractional adjusted research units. It does not certify the entire earlier archive.
Unit/workflow tests additionally cover cutoff isolation, adjustment rebasing,
invalid-source handling, reference-start guards and exact agreement between linked
simulation calibration and backtest metrics. Passing these checks establishes
software behaviour, not profitability or complete data validity.

Verification: **299 Python tests**, **nine native C++ test groups**, Ruff checks,
and the 46-stock acceptance run pass. Browser checks cover the real historical
workspace and the linked backtest/Monte Carlo flow.
