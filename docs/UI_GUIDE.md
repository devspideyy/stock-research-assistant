# Research workspace

## Find a tool

The sidebar contains two primary groups and an optional lab collection:

- **Research:** Stock workspace, Stock ideas and Saved research.
- **Workspace:** Stock universe, Monitoring and Settings.
- **Individual research labs:** the standalone pages, retained in an expander.

The active section is highlighted. On a narrow screen, expand the sidebar to
change data and use the main Workspace selector to move between sections.

Stock workspace opens with a real historical stock, source dates, adjusted-unit
metrics and a price/volume chart. The forest-green sidebar, ivory surfaces, brass
accents and serif headings are native Streamlit theme settings. Research sections
keep the same selected stock/window while moving between tools. A chart range changes
displayed bars only; the Research window controls supplied calculation history.
The earliest observations warm up features within that window. All imported/library
research is capped at 31 December 2020; historical data is never labelled live.

## Save research

Build an evidence card and generate a report from Overview. Rules mode requires
no model key. These actions save the records to the existing local SQLite database.
Saved research lets you filter by instrument, inspect the original evidence and
export a card or report. Browsing history does not overwrite the active dataset.
The screen lists up to 100 recent records of each kind.

## Reuse indicator settings

In Market analysis, open Indicator lab. Calculate a function, expand Save these
settings as a preset, enter a name and save. The preset contains the calculated
function, parameter values, chosen input columns and any constant MAVP schedule.
It contains settings, not the price series or a previously calculated signal.

Choose a saved preset and press Load preset to apply its settings. Calculate
again for the active dataset. Up to 30 named presets are stored locally; saving
the same name updates that preset. Indicator calculations retain TA-Lib's warm-up
and missing-domain conventions and do not change the C++ strategy rules.

## Keep a research watchlist

Save the active demo/import from the sidebar or save a real exchange identifier
from Stock universe. The sidebar shows up to four recent bookmarks; Saved research
contains the complete list and removal control. Demo bookmarks reopen their demo
scenario. Imported-file bookmarks retain the label, not the uploaded price file.
Real stock bookmarks retain the exchange identifier; they do not connect prices.

The research watchlist is limited to 50 entries and is separate from Monitoring's
explicit worker configuration. Saving or removing a bookmark never starts polling,
changes the worker's watchlist or submits an order.

## Code map

The heritage theme is in `.streamlit/config.toml`. Page composition remains in
`app/dashboard.py`; `app/workspace.py` handles navigation, bookmarks and history.
`app/research_labs.py` contains indicator/preset controls and stock search.
`app/ui_helpers.py` holds shared charts and report rendering. The existing SQLite
settings table stores bookmarks and presets; no new framework, service or database
schema is required. `app/experiment_ui.py` groups experiment controls and accounting
views; `app/validation.py` runs fixed-rule chronological studies. Native accounting
helpers live in `engine/include/accounting.hpp`.

Live feeds, TradingView chart integration, and Level 2/3 are not part of this UI pass.

## Inspect an offline experiment

Backtesting separates Performance, Equity replay and Trades & accounting. Returns
use every evaluated bar even when replay reduces displayed points. Select a
strategy in Trades & accounting to inspect its fees, dividend receivables, action
ledger and fill markers. The cost model selector switches between hypothetical
bps and the dated NSE delivery estimate. Inputs take effect on explicit submission.

Validation compares fixed rules over disjoint chronological windows, always with
buy-and-hold. It can also double charges and slippage. Save a completed study to
retain it across sessions (most recent 10), or download its JSON. Saved studies
retain their original instrument and synthetic/history label, independently of the
currently selected research data. Original source prices are not stored in studies.

Fictional split/dividend examples remain in automated tests and the examples folder.
The C++ analysis and experiments account for declared actions. The separate TA-Lib
library and chart candles retain the supplied OHLCV; their raw discontinuities
should not be interpreted as genuine price moves.

## Connect Monte Carlo to a backtest

In Stock workspace → Strategies & backtest, submit a strategy comparison. Open
Monte Carlo risk, choose one of those strategies and submit Simulate strategy risk.
The C++ engine reproduces the frozen backtest settings and samples contiguous blocks
of its net daily equity returns, including cash days. The export links the original
backtest request hash, strategy, stock, evaluation dates and costs. A threshold
control estimates conditional drawdown exceedance. Existing costs are not charged
again. Stock scenarios use the stock's returns instead and remain separately labelled.

## Research controls and comparisons

Open **Data health & feature warm-up** to review missing/invalid sessions and,
where available, **Use latest complete window**. Earlier feature history is kept;
it is excluded from the selected evaluation and stock-scenario calibration.
In Chart & indicators, calculate price structure to enable synchronized RSI/MACD
panels. After a backtest, its fill markers are available on the same chart.

**Challenge these rules in Validation** preserves submitted settings. Performance
also contains benchmark/sector context and the experiment journal. The linked risk
tab offers seven calibration/block/cost sensitivity cases after a simulation.
Overview contains descriptive historical rating evaluation. Backtest results offer
a frozen final-period policy for windows of at least 100 observations; read the
[protocol and limitations](RESEARCH_PROTOCOL.md) before interpreting it as untouched.
