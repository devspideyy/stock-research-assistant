# Stock Research Assistant

A final-year C++ and Python research workstation for Indian cash equities. The numerical core is C++17; the dashboard, evidence reports, chatbot and monitoring worker are Python. Indicators support price/volume and event research. US equities and derivatives are not implemented.

**Development version.** Built-in prices, company information, headlines and depth are fictional synthetic fixtures. Results from them demonstrate software behavior, not investment performance. Real-data use requires your own permitted dataset or configured provider.

## Start on Windows

Use Python 3.12 and a C++17 compiler. VS Code alone does not include a compiler.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/build_engine.py
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

- Five fictional watchlist scenarios and validated chronological OHLCV CSV import.
- C++ prior price levels, relative volume and supporting SMA/EMA/RSI/ATR.
- A parameterized TA-Lib lab exposing all 158 installed functions, with multi-output charts and exports.
- Searchable public NSE/BSE company equity identifiers, including SME and surveillance series/groups; catalogue data is separate from prices.
- Source-linked evidence cards: supporting/opposing observations, missing information, horizon and invalidation conditions.
- C++ long-or-cash, whole-share backtests with next-observed-open execution, configurable hypothetical fees/slippage and three baselines.
- C++ circular-block bootstrap and GBM wealth scenarios, seeded runs, loss/tail summaries and sensitivity settings.
- Displayed depth spread/imbalance analysis for supplied snapshots. No inferred true CVD, footprint, cancellations or hidden liquidity.
- Deterministic research reports/educational answers plus optional OpenRouter and Ollama providers.
- A separate monitoring worker with persisted events/heartbeats and demo replay; optional authenticated read-only quote access is account-dependent.

The full source tree is editable in Antigravity IDE. The research outline is [PROJECT_OUTLINE_AND_RESEARCH.md](PROJECT_OUTLINE_AND_RESEARCH.md); implementation details and limits here take precedence over planned features in that document.

Start with [docs/FREE_DATA_SETUP.md](docs/FREE_DATA_SETUP.md) for the two optional provider credentials, free-data coverage and quotas. The complete installed function list is in [docs/INDICATOR_CATALOGUE.md](docs/INDICATOR_CATALOGUE.md). No API key is needed for indicator calculations or the stock identifier catalogue.

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

Optionally attach a JSON file containing separately sourced `news`, `fundamentals` and/or `depth`. See [examples/evidence_template.json](examples/evidence_template.json) for the exact shape. Replace the fictional example with permitted evidence and its actual publication/source timestamps. The attachment is validated, never fetched from its URLs. Future-dated news/fundamentals are excluded from a historical evidence card; a depth snapshot remains separate from daily investment research. Any synthetic evidence must remain labelled synthetic.

**Corporate actions are not automatically processed.** Select a consistent data convention and account for splits, bonuses and dividends before interpreting a historical result. Raw discontinuous prices invalidate returns. Adjusted OHLC is a research convention, not a reproduction of actual historical whole-share accounting. Recorded output discloses the assumptions.

Export a clearly synthetic example if you want to test the importer:

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
- Fees and slippage are hypothetical scenarios. The prototype does not implement the complete dated Indian tax/brokerage schedule.
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
scripts/           Build and launch helpers in Python
tests/             Boundary and integration checks
docs/              Methodology and placement preparation
```

## Next research milestones

Verify a permitted live-data account and data coverage; add genuine timestamped news and archived depth only where available; implement corporate actions and dated fees; evaluate held-out/forward periods; compare single versus multiple agents under matched evidence and budgets. A compact fundamentals panel should use dated, sourced figures before supporting investment-horizon conclusions.

Repository: [devspideyy/stock-research-assistant](https://github.com/devspideyy/stock-research-assistant). It is private, so sign in to the owner account to view it. The local application works independently of GitHub.

## Interface design

The workspace uses native Python/Streamlit components: a section navigation rail, an overview price chart, compact metric cards, a neutral light theme and restrained teal chart accents. Data and assistant controls are grouped in sidebar panels. Demo/import status remains visible on each page. No JavaScript, HTML or CSS application files are required. Research results persist while navigating sections.
