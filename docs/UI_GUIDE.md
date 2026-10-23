# Research workspace

## Find a tool

The sidebar contains three groups:

- **Research:** Overview, Market analysis, Assistant and Saved research.
- **Experiments:** Backtesting and Monte Carlo.
- **Workspace:** Stock universe, Monitoring and Settings.

The active section is highlighted. On a narrow screen, expand the sidebar to
change data and use the main Workspace selector to move between sections.

Overview has chart display ranges, price/volume context, shortcuts and recent
reports. A chart range changes the displayed bars only; experiment calibration
still uses the supplied dataset and the lab's stated assumptions. Demo/import
labels and the last supplied date stay visible. Nothing is labelled live simply
because a chart is interactive.

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

The dark theme is in `.streamlit/config.toml`. Page composition remains in
`app/dashboard.py`; `app/workspace.py` handles navigation, bookmarks and history.
`app/research_labs.py` contains indicator/preset controls and stock search.
`app/ui_helpers.py` holds shared charts and report rendering. The existing SQLite
settings table stores bookmarks and presets; no new framework, service or database
schema is required. Numerical C++ and TA-Lib calculation code is unchanged.

Live feeds, TradingView chart integration, and Level 2/3 are not part of this UI pass.
