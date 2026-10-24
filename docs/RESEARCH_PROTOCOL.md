# Offline research improvements — 25 October 2026

The C++17 engine remains the numerical core. Python handles input checks,
Streamlit presentation, SQLite records and descriptive aggregation. These changes
need no broker, news or language-model API credentials.

## A consistent experiment

Submit a stock/window and backtest settings once. **Challenge these rules in
Validation** imports the exact capital, lookback, volume threshold, entry exposure,
stop, charges and slippage, with parent request hashes. Folds change dates, not
those parameters. An independent validation study remains available explicitly.
Cost stress doubles the submitted base costs and slippage.

The last-submitted experiment is visible across stock-workspace sections. Changing
form controls does not silently replace its results; submit again. Changing the
stock/window clears transient results. Saved studies and the local experiment
journal remain separately labelled snapshots.

## Windows and source quality

Selected windows retain earlier price bars for causal indicator warm-up. Backtest
evaluation begins inside the selected window in cash; stock-scenario calibration
uses only the selected observations. No observation after the selected end is sent
to the engine.

Data health checks known invalid/omitted observations, missing dates against the
committed observed-market session reference, and gaps longer than ten calendar
days. The reference contains 5,226 observed dates from the raw reference cohort,
not an exchange-certified holiday calendar. It cannot distinguish suspension,
non-listing, absent source records or vendor mistakes. Dates before its coverage
have only the omission and long-gap checks; completeness is not certified.

Backtests and each validation fold reject detected evaluation gaps by default.
An explicit exploratory override is recorded. Gap-overridden runs withhold daily
volatility, Sharpe and observation-annualised CAGR; elapsed-calendar CAGR is
reported separately. Daily Monte Carlo is blocked for declared gaps. **Use latest
complete window** selects a trailing segment when enough observations remain.
This is a software eligibility rule, not proof of complete exchange data.

## Research units and execution

Adjusted histories use fractional research units. With proportional charges,
constant price rebasing therefore does not change the economic return through
whole-share rounding. These units do not represent historical broker fills.
Raw-price replay uses whole shares and requires the user to record a review of
instrument identity and corporate-action coverage. That attestation is not an
independent verification of completeness.

An optional raw-price volume cap uses the previous observed day's volume only.
It limits entries and rejects an exit exceeding the cap. It does not simulate
partial fills, circuits, queues or market impact. Provider volume units for the
adjusted library are not certified for execution, so its volume cap is rejected.
Pre-2024 studies use explicitly hypothetical charges, not modern fees presented
as historical tax schedules.

## Frozen final period and journal

After a submitted run, reserve the final 20% of the selected observations. The
source/window policy stores exact rules, strategies and costs and cannot be
overwritten through the UI. Subsequent development backtests and validation
exclude the reserved tail. A final run must match the frozen settings.

Final-test attempts are logged before calculation. A durable access marker
distinguishes first and repeat access even if the displayed journal is bounded.
The journal exports source identities, settings and compact results. This is local
research traceability, not a tamper-proof audit system. Different windows can
create different policies. Charts and earlier experiments may already have shown
the tail; locking cannot retroactively make it untouched. Non-inspection is an
explicit optional user attestation, off by default.

## Risk, comparisons and rating evaluation

Linked strategy Monte Carlo resamples the submitted backtest's net daily equity
returns, including cash days and existing fees. Seven sensitivity cases vary one
factor at a time: blocks of 1/5/20; full/last 252/last 63 returns; and doubled/tripled
costs and slippage. Short history uses the available returns and reports the
actual count. Tail calibration retains original positions and cash observations;
it does not restart the strategy at the tail boundary. Cost cases recompute the
same fixed rule. Seeds, settings and request hashes are exported; no winner is
selected automatically. Strategy signals are not rerun on simulated OHLC paths.

Equally costed buy-and-hold is the primary benchmark. Optional sector context
uses other cached same-sector adjusted histories with complete matching dates.
It excludes the selected stock and incomplete peers, and uses fixed equal initial
weights. This is a gross, current-cohort comparison, not a historical sector index,
survivorship-controlled universe or investable alpha claim.

Rating evaluation tests the existing manually weighted `price-evidence-v1` score
on prefix-only features and later non-overlapping return labels. It excludes the
last 20% or the reserved final period and skips gap-crossing label windows. Group
counts, positive-return fractions, average returns and the unconditional baseline
are descriptive. They do not calibrate bullish/bearish points into probabilities.
Real raw-price labels are withheld to avoid treating split/dividend jumps as returns.

Price charts support synchronized RSI/MACD panels and submitted fill markers.
Earlier warm-up overlays are filtered out of the displayed date window. Clearing
the section selector falls back to Overview.

## Reproduction and remaining limits

`data/history_manifest.json` pins the full Git revision, known-cohort source and
processed-candle hashes, reference CSV member hashes and session-file hash.
Fresh preparation uses that revision; stale local catalogues are rejected.
Reference ZIP repackaging is permitted only when all expected CSV contents match.
Known cached stock candles are checked before loading. New on-demand stocks use
the pinned Git blob and source hash but are not automatically added to the
independently reviewed 46-stock manifest.

Official listing identity, a certified session calendar, complete historical
actions/dividends, point-in-time membership, delisted securities and historical
execution-cost reconciliation still require better permitted source material.
Live prices, news, model-provider access and continuous monitoring remain separate
integrations. Passing software checks does not establish investment effectiveness.
