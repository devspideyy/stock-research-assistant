# Stock Research Assistant

A final-year C++ and Python research workstation for Indian cash equities. The numerical core is C++17; the dashboard, evidence reports, chatbot and monitoring worker are Python. Indicators support price/volume and event research. US equities and derivatives are not implemented.

**Historical research edition.** The main workspace uses a locally cached real-stock library with a hard cutoff of **31 December 2020**. Histories use documented provider-adjusted research units. Synthetic fixtures are reserved for tests. News/live feeds remain optional later integrations; software checks do not establish investment performance.

The [offline research protocol](docs/RESEARCH_PROTOCOL.md) covers shared backtest/validation settings,
gap checks, causal warm-up, fractional adjusted units, frozen final-period controls,
the experiment journal, sector context, rating evaluation and seven linked Monte Carlo sensitivity cases.

## Start on Windows

Use Python 3.12 and a C++17 compiler. VS Code alone does not include a compiler.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/build_engine.py
.\.venv\Scripts\python.exe scripts/prepare_history.py --reference-universe
.\.venv\Scripts\python.exe scripts/run_dashboard.py
```

Open the local URL printed by Streamlit: `http://127.0.0.1:8517`. The project configuration binds it to this computer. The dashboard uses the native engine; it does not silently substitute Python financial calculations when the executable is missing.

For a supplied portable compiler under `.tools/`, the build script discovers GCC/Clang automatically. Otherwise put a compiler on PATH or set `CXX`. CMake is supported when installed; the build script also supports a direct GCC/Clang build. `.tools/`, the virtual environment and build products are deliberately excluded from Git.

On Linux/macOS use `python3 -m venv .venv`, `.venv/bin/python`, and an installed GCC/Clang compiler. CMake/CTest is an alternative build route:

```text
cmake -S engine -B engine/build -DCMAKE_BUILD_TYPE=Release
cmake --build engine/build --config Release
ctest --test-dir engine/build --output-on-failure -C Release
```

## What this version covers

- A real historical library, explicit source/coverage records, stock-wise date windows and validated CSV import through 2020.
- A heritage-style stock workspace with ivory surfaces, forest-green navigation, brass accents and editorial headings.
- C++ prior price levels, relative volume and supporting SMA/EMA/RSI/ATR.
- A parameterized TA-Lib lab exposing all 158 installed functions, with multi-output charts and exports.
- Locally saved indicator presets, evidence/report history and a research watchlist.
- Searchable public NSE/BSE company equity identifiers, including SME and surveillance series/groups; catalogue data is separate from prices.
- Source-linked evidence cards: supporting/opposing observations, missing information, horizon and invalidation conditions.
- Explainable bullish/bearish price-evidence scores, conditional research recommendations and a multi-CSV Stock ideas scanner.
- C++ long-or-cash backtests comparing five hypotheses, with chronological holdout evaluation, next-open fills, trade markers and net closed-trade statistics.
- Declared raw-price split/bonus/dividend accounting, a payment/receivable ledger and a fictional conservation example.
- Editable, dated NSE delivery-cost estimates alongside hypothetical bps, with per-fill charge breakdowns.
- Chronological multi-fold Validation with a buy-and-hold benchmark, doubled-cost/slippage stress, local study history and JSON exports.
- C++ circular-block bootstrap and GBM wealth scenarios, seeded runs, loss/tail summaries and sensitivity settings.
- Monte Carlo linked to a submitted backtest: resamples net daily strategy returns, including cash days and existing fees, with drawdown-threshold risk.
- Play/Pause/checkpoint replay for backtests and simulations, plus a terminal simulation histogram.
- Level 2/3 and order-flow research are deferred; the old depth snapshot lab is no longer shown.
- Deterministic research reports/educational answers plus optional OpenRouter and Ollama providers.
- A separate monitoring worker with persisted events/heartbeats and demo replay; optional authenticated read-only quote access is account-dependent.

The full source tree is editable in Antigravity IDE. The research outline is [PROJECT_OUTLINE_AND_RESEARCH.md](PROJECT_OUTLINE_AND_RESEARCH.md); implementation details and limits here take precedence over planned features in that document.

Start with [docs/FREE_DATA_SETUP.md](docs/FREE_DATA_SETUP.md) for the two optional provider credentials, free-data coverage and quotas. The complete installed function list is in [docs/INDICATOR_CATALOGUE.md](docs/INDICATOR_CATALOGUE.md). No API key is needed for indicator calculations or the stock identifier catalogue.

## Dashboard workflow

Start in **Stock workspace**. Choose a cached real stock and research window in
**Research data**, then move between chart/indicators, strategies/backtest,
validation, stock scenarios and evidence. The backtest includes a **Monte Carlo risk**
tab. A separate stock scenario remains available for comparison.
Individual research labs are grouped in a sidebar expander. Saved research retains
evidence/report exports and watchlist management. After preparation, research runs
offline without credentials. See [the UI guide](docs/UI_GUIDE.md)
for presets and the difference between research bookmarks and the worker watchlist.

The initial local cohort contains **46 prepared stocks**, with source records reaching
back to 1996 where available, and a catalogue of 2,577 candidate history files for
explicit on-demand import. Four cohort entries were withheld; this is not a complete
point-in-time NSE universe. See [sources, coverage and validation](docs/HISTORICAL_RESEARCH.md).

Use **Assess selected stock** for the current instrument or **Stock ideas** to compare
available histories. See [recommendation rules and the next research steps](docs/RESEARCH_RECOMMENDATIONS.md)
for score weights, strategy definitions, replay limits and the remaining validation work.
Scores are heuristic evidence points, not probabilities; demo/history cards are not current recommendations.

## Backtest and risk workflow

Choose the stock and research dates in the sidebar. Open **Backtest**, choose a
rule and submit **Run strategy comparison**. Buy-and-hold is included automatically.
The first result shows ending investment, net profit/loss, worst historical fall
and the net-return difference from buy-and-hold. Equity playback, trades and
advanced statistics are separate views; only the selected view builds its charts.
Cost and execution assumptions remain editable in the advanced settings.

Open **Monte Carlo** from the section bar or **Risk / Monte Carlo** in the sidebar.
**Backtested strategy** uses the selected rule's submitted net returns, including
cash days and costs. **Stock price scenarios** works directly from stock returns.
These are different conditional experiments. Animation is optional in both flows.
Calibration dates and observation counts stay visible alongside strategy risk.

**Save complete experiment** stores the source price snapshot, settings, complete
backtest results and any linked strategy simulation in the local SQLite database.
Use **Saved research → Reopen complete experiment** to restore them after a restart.
The saved source is clearly labelled; select Historical library to start a new run.
Changing the data source, stock or date window clears active results with an
explanation, while saved experiments remain available.

The UI caches deterministic native requests by prices, all submitted options and
the engine executable hash. Local history cache entries also track file versions
and the pinned manifest. These bounded in-memory caches clear on restart; saved
experiments persist independently. No broker or model key is needed for this flow.

## Use Antigravity IDE

Open this folder in **Antigravity IDE** through **File > Open Folder**. Start with `engine/src/engine.cpp` for the C++ calculations and `app/dashboard.py` for the interface.

After the environment/compiler setup above, choose **Terminal > Run Task** to build the C++ engine, run the dashboard or run tests. **Ctrl+Shift+B** builds the engine. The dashboard task now opens the app in your default browser and reuses a healthy server already running on port 8517.

You can also start it from the project terminal:

```powershell
.\.venv\Scripts\python.exe start_app.py
```

This launcher checks readiness before opening the browser. A new server runs separately from the launcher; startup errors are saved to `runs/dashboard.log`. For a different port use `start_app.py --port 8518`. The local address works on the computer running the server; it is not a publicly hosted website. The original `scripts/run_dashboard.py` command remains available to run a foreground server with terminal logs and **Ctrl+C** to stop it.

On the original development laptop the dependencies and native executable are already prepared; run the dashboard task without repeating setup. Optional Python and Microsoft C/C++ editor extensions provide navigation and debugging, but the app does not require them to launch.

## Import a price series

Upload UTF-8 CSV in the dashboard with these columns (case-insensitive; `Date` is accepted instead of `timestamp`):

```text
timestamp,open,high,low,close,volume
2026-01-02,100,103,99,102,50000
2026-01-05,102,104,101,103,62000
```

Use daily bars, oldest first, with no duplicate timestamps. Prices must be positive, volumes nonnegative and high/low must enclose open/close. The importer rejects invalid data rather than silently reordering or repairing it. Uploaded candles alone do not contain order-book or news data.

Confirm **completed daily bars** before running experiments and flag fictional/test
files explicitly. Intraday, weekly and very sparse spacing are rejected by the daily
experiment boundary; this does not verify exchange-calendar completeness. For date-only
bars, confirm the **decision time (India time)** against the source. The default 15:30
is a declared research convention, not verification of a special session's close.
News published after this cutoff is excluded. The programmatic evidence builder requires
explicit provenance and a timezone-aware cutoff for date-only inputs; missing declarations
produce insufficient evidence.

Optionally attach a JSON file containing separately sourced `news`, `fundamentals` and/or `depth`. See [examples/evidence_template.json](examples/evidence_template.json) for the exact shape. Replace the fictional example with permitted evidence and its actual publication/source timestamps. The attachment is validated, never fetched from its URLs. Future-dated news/fundamentals are excluded from a historical evidence card; a depth snapshot remains separate from daily investment research. Any synthetic evidence must remain labelled synthetic.

Declare the **Price basis**. Raw prices can receive sourced split/bonus/cash-dividend events using the optional action JSON upload. Already-adjusted history must not also receive those events. Events are supplied by you; missing actions are not discovered automatically. Fractional entitlements, rights and mergers are unsupported. Adjusted OHLC remains a research convention rather than actual historical exchange fills. See [accounting and validation](docs/ACCOUNTING_AND_VALIDATION.md) for the format, fee coverage and assumptions.

Corporate-action conservation examples remain in the automated tests and examples
folder. Normal startup offers Historical library and CSV import. In **Validation**,
run a study to compare separate periods and cost sensitivity. No key is needed.

Synthetic exports are available for development boundary checks; their dates are
outside the normal pre-2021 workspace and they are not the user research dataset:

```powershell
.\.venv\Scripts\python.exe -m app.demo --export data/private/synthetic_example.csv
```

## Optional AI providers

The default **rules** mode makes no model request and is visibly labelled as deterministic. It is useful while no API key/local model is available; it is not an LLM agent result.

For OpenRouter, configure `OPENROUTER_API_KEY` locally and choose a currently available `:free` model or `openrouter/free`. The app enforces free-only routing and a local shared usage budget for reports and chat. It never automatically falls back to a paid model. Provider quotas and availability can be more restrictive. A three-role report uses multiple requests. Returned model identity is recorded; the random free router is unsuitable for a controlled model comparison.

For local inference, install Ollama separately, download a model permitted for your use, and set `OLLAMA_MODEL` / `OLLAMA_URL`. The current laptop does not need the serviced RTX 4060 to run the numerical engine or use OpenRouter. Local LLM speed/memory depends on the actual machine.

Copy `.env.example` to `.env` and fill in optional settings locally, or export values in your terminal. The loader reads app-specific values only and does not override existing environment variables. Real `.env` files, keys and local databases are ignored. The application does not publish credentials or datasets. Never put keys in source files or send them in chat.

## Monitoring and real-data limits

The worker is separate from the dashboard. Review available options with:

```powershell
.\.venv\Scripts\python.exe -m app.monitor --help
```

Use `--once` to test a single cycle before running a continuous worker. Demo mode replays synthetic observations; it is never labelled a live NSE feed. Real quote access requires an eligible, permitted account/token and source identifiers. No order-placement functionality is provided.

An always-running worker needs an awake, connected computer. Closing the browser is independent of the worker; sleeping the host stops monitoring. Heartbeat and event timestamps show what was actually observed. This project does not guarantee 24/7 cloud uptime or unlimited free LLM calls.

The current version does not automatically stream/record a full exchange order book, reconstruct individual orders, supply a historical news archive or download model weights. Genuine microstructure experiments require eligible historical/recorded data with event-time, sampling and gap handling. Candle-only backtests do not validate order-flow strategies.

## Financial conventions

- Signals formed at a close fill at the next observed open; final signals without a next bar do not fill.
- Configured stops are close-based signals, not guaranteed intraday stop fills.
- Entry sizing uses whole shares and includes fees; an exposure limit at entry can drift as prices move.
- Final holdings are marked to the last close; there is no artificial final liquidation.
- Choose hypothetical bps or an editable NSE delivery estimate with reviewed coverage from 2024-10-01 through 2026-10-24. It is not a complete India tax/invoice engine, and is not a BSE schedule. Slippage remains a scenario.
- Annualized metrics assume daily observations and 252 sessions/year, with a zero risk-free rate for Sharpe.
- Monte Carlo output is conditional on historical calibration and explicit stress assumptions. It is not a forecast or guaranteed loss bound.
- Historical modern-LLM decisions may contain pretrained future knowledge. Keep forward model evaluation separate from numerical strategy tests.

See [docs/METHODOLOGY.md](docs/METHODOLOGY.md) and [docs/INTERVIEW_GUIDE.md](docs/INTERVIEW_GUIDE.md).

## Test and inspect

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app scripts tests
.\.venv\Scripts\python.exe scripts/build_engine.py --test
```

Native tests live under `engine/tests/`. The Python integration suite exercises the compiled executable when available. No test needs a paid service, broker token or model download.

The checked-in `requirements.lock.txt` records the tested dependency versions for Python 3.12. Use `pip install -r requirements.lock.txt` for that environment. The broader `requirements.txt` permits compatible updates; re-run tests after changing dependencies.

## Source layout

```text
engine/            C++ calculations, CLI protocol, CMake and native tests
app/dashboard.py   Streamlit interface
app/engine_bridge.py  Validated native-process boundary
app/demo.py        Deterministic, explicitly synthetic fixtures
app/services.py    Evidence and role-based research reports
app/providers.py   Free-only OpenRouter / local Ollama adapters
app/chat.py        Educational and result-grounded answers
app/monitor.py     Separate worker
app/storage.py     SQLite run, event and usage records
app/indicators.py  Compiled TA-Lib catalogue and validated calculations
app/instruments.py  Public NSE/BSE identifier refresh and local cache
app/research_labs.py  Indicator controls and stock catalogue interface
app/workspace.py   Sidebar navigation, research bookmarks and saved records
app/ui_helpers.py  Shared chart styling and evidence/report presentation
app/assessment.py  Versioned, explainable price-evidence rules and strategy definitions
app/recommendations.py  Stock-idea scanning and strategy guide
app/animations.py  Bounded Plotly replay of completed experiments
scripts/           Build and launch helpers in Python
tests/             Boundary and integration checks
docs/              Methodology and placement preparation
```

## Next research milestones

Verify a permitted live-data account and data coverage; add genuine timestamped news and archived depth only where available; implement corporate actions and dated fees; evaluate held-out/forward periods; compare single versus multiple agents under matched evidence and budgets. A compact fundamentals panel should use dated, sourced figures before supporting investment-horizon conclusions.

Repository: [devspideyy/stock-research-assistant](https://github.com/devspideyy/stock-research-assistant). It is private, so sign in to the owner account to view it. The local application works independently of GitHub.

## Interface design

See the [24 October correctness audit and future research reports](docs/reports/2026-10-24/README.md) for open findings and updated validation status. An intermittent SQLite concurrency failure was observed despite the earlier successful test run.

The workspace uses native Python/Streamlit components: a full sidebar, chart-led
overview, metric cards, a dark navy theme and teal/gold accents. Data, watchlist
and connection controls are grouped in the sidebar. Demo/import status remains
visible on research pages. No JavaScript, HTML or CSS application files or new
dependencies were added for the redesign. TradingView integration remains a later
step; current charts use Plotly. Research results persist while navigating sections.
