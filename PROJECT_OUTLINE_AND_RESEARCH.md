# Stock Research Assistant — revised outline

Updated: 23 October 2026. Implementation has started following the user's instruction. This file records the design; see README.md for the current runnable features and limitations. Live services and external accounts are optional and require configured access.

**College title:** “A Multi-Agent Generative AI Framework for Stock Investment Recommendations Using News Sentiment, Technical Analysis, and Backtesting.”

**Product scope:** a C++ quantitative core with a Python interface, event/news and price-structure research, free-data-dependent liquidity/order-flow analysis, supporting indicators, OpenRouter/local AI, market monitoring, historical backtests, Monte Carlo risk scenarios and an educational research chatbot.

## 1. Confirmed requirements

- Indian cash equities first, initially a small NSE watchlist; US cash equities after India works reliably.
- Derivatives are excluded.
- Lagging indicators provide context and comparison baselines; they are not the main recommendation engine. Use event/news evidence, observed price structure, volume and available liquidity data, without presenting any feature as guaranteed foresight.
- Add L1/L2/deeper-book and executed-order-flow features only where a usable, permitted zero-cost source actually provides the required observations. No paid depth upgrade is mandatory.
- C++ is the preferred language for the numerical and strategy core. Python is used for the interface, integrations and AI.
- No required paid subscription, hosted inference bill, TradingView subscription or paid database.
- OpenRouter models are preferred on the present laptop. Local Ollama models remain an option.
- The RTX 4060 laptop is away for servicing. Development and the initial demo must not depend on that GPU.
- Seven months remain, with a preference for a useful early version.
- Full source files, tests, prompts, setup instructions and documentation will be available locally and later in the intended GitHub account, devspideyy.
- Implementation was authorized on 23 October 2026. Persistent live monitoring and external-data authentication remain explicit setup tasks rather than assumptions.

## 2. Purpose and the user's workflow

The application helps a finance student or individual researcher inspect evidence, understand indicators, compare strategies and explore investment risk.

The user adds a stock to a watchlist, selects indicators and rule parameters, views prices and dated news, requests an AI research report, runs historical strategy comparisons, explores simulated future scenarios and asks a chatbot questions about the results.

Keep three distinct questions visible:

1. What is happening now? — timestamped observations, indicators and monitoring events.
2. What happened historically? — backtests on actual eligible data.
3. What could happen under stated assumptions? — Monte Carlo scenarios.

Generated recommendations must cite supplied evidence and acknowledge disagreement or insufficient information. The project's success is a useful, understandable and reproducible system; beating a benchmark is an experiment, not a promised outcome.

## 3. Why a C++ core and Python application layer

| C++17 quantitative engine | Python application layer |
| --- | --- |
| Candle/quote validation and return calculations | Capability-aware data adapters, CSV import and permitted recording |
| Price structure, relative volume, spreads and supported depth features; contextual indicators | Streamlit charts, visible-depth views and evidence provenance |
| Configurable numerical strategy rules | OpenRouter and Ollama model adapters |
| Exposure checks and execution/accounting rules | FinBERT sentiment inference |
| Historical backtests and performance metrics | Three-agent orchestration and chatbot |
| Monte Carlo simulation and risk summaries | Persistent monitoring worker, storage and report export |

This makes C++ a substantial part of the project. An all-C++ interface/model pipeline would add GUI, HTTP and model-runtime work without helping the first research demonstration.

Initially Python calls a compiled C++ executable using JSON requests and responses. Commands conceptually include indicators, backtest and simulate. Use Python's subprocess.run with argument arrays, shell=False, timeouts and checked return codes. Keep machine-readable JSON on stdout and diagnostics on stderr. Send a whole watchlist/run in a batch rather than spawning one process for every tick. [Python subprocess documentation](https://docs.python.org/3/library/subprocess.html)

Use CMake for builds and a pinned nlohmann/json dependency. A direct Python binding through pybind11 is a later option only if measurement shows the subprocess boundary is a bottleneck. [CMake tutorial](https://cmake.org/cmake/help/latest/guide/tutorial/index.html), [JSON integration](https://json.nlohmann.me/integration/index.html), [pybind11 build documentation](https://pybind11.readthedocs.io/en/stable/compiling.html)

Application source remains C++ and Python; build files, JSON configuration and Markdown documentation support it.

## 4. Main application modules

| Module | What the user can do |
| --- | --- |
| Watchlist and market overview | Add supported equities, see last price, data timestamps, market status and recent alerts. |
| Price structure and liquidity | Inspect prior-session/rolling levels, price/volume context, relative strength, spread and supported visible-depth features. |
| Indicator workspace | Select indicators, change periods/thresholds and inspect charts and computed values. |
| Strategy builder | Combine a small set of typed conditions and save a versioned strategy. |
| News and evidence | Inspect dated headlines, source links, relevance, sentiment and coverage gaps. |
| AI research report | Read separate news/technical findings and a reviewed recommendation. |
| Backtesting lab | Compare a saved strategy with predefined baselines, costs and trade history. |
| Monte Carlo lab | Choose a horizon, simulation method and assumptions; inspect possible wealth/loss distributions. |
| Research chatbot | Ask finance questions and questions grounded in the selected stock, report, backtest or simulation. |
| Monitoring centre | Configure watchlists, event rules, schedules, AI-call budgets and alert cooldowns; inspect worker health. |
| Settings and exports | Choose a model provider, configure credentials locally and export reports/results. |

For the first interface, use ordinary Streamlit pages/tabs and Python chart APIs. Its chat elements support a chatbot without a separate frontend language. [Streamlit chat documentation](https://docs.streamlit.io/develop/tutorials/chat-and-llm-apps/build-conversational-apps)

## 5. Evidence hierarchy, supporting indicators and strategy controls

**Primary research evidence:** timestamped news/company events; observed price structure, gaps and prior-session/rolling levels; relative trading volume; stock-versus-index/sector strength where comparable data exists; and available liquidity/microstructure evidence. Compute levels from information already available at the decision time. A swing point requiring later confirmation cannot be labelled known at its earlier turning point.

**Liquidity layer:** spread, available bid/ask quantities and visible depth describe current trading conditions. Use them as short-horizon monitoring/execution-quality features and data-quality filters. A brief imbalance is not sufficient evidence for a long-term investment recommendation.

**Supporting indicators:** SMA/EMA, RSI, MACD and Bollinger Bands can describe context or form an indicator-only comparison baseline. ATR/rolling volatility can normalize position/risk assumptions. None supplies guaranteed leading information; price action, volume and order books also reflect observed activity.

Expose controls for historical levels, relative-volume lookbacks, eligible event windows, spread limits, depth persistence, indicator parameters, exposure and decision horizon. Avoid arbitrary fixed weights or a rule that treats one RSI value as the final decision.

A research baseline can test a break of an already-known rolling level with relative-volume confirmation. Then test the addition of news and, separately, available liquidity evidence. Freeze exact definitions on development/validation data and report outcomes, including negative results. An EMA/RSI strategy remains a comparison rather than the central system.

Use the same C++ definitions in monitoring and backtests. A closed-daily-bar signal waits for the close; quote/depth research runs on its own event timestamps. Start with built-in features and validated rules; arbitrary uploaded scripts are unnecessary.

## 6. Generative agents and the deterministic controls

| Role | Responsibility |
| --- | --- |
| News analyst agent | Explains relevant dated events and sentiment, with source IDs and uncertainty. |
| Market-structure and liquidity analyst agent | Interprets C++ price/volume/liquidity observations with indicators as context; reports unsupported/missing features rather than inventing order flow. |
| Reviewer agent | Compares the two reports, identifies disagreement and proposes a position-aware action. |
| Chatbot | Answers educational and result-specific questions using retrieved project information and approved tools. |
| Deterministic monitors | Detect price/volume events, spread or persistent displayed-depth changes, new eligible text, supporting-indicator events and source failures. |
| C++ risk gate | Enforces permitted actions, whole-share sizing, cash and exposure constraints. |

The first three are the multi-agent research workflow. The chatbot is an interactive assistant. Monitoring and risk checks are software workers/rules rather than extra permanently running LLMs.

Agents receive separate role instructions, restricted evidence/tool interfaces and validated output schemas. Store short reports, supporting references, model/provider identity, prompt version and observable inputs/outputs.

Output actions should distinguish enter, keep holding, stay in cash, exit an existing holding and insufficient evidence. No leverage or short positions are needed for the initial cash-equity simulation.

## 7. OpenRouter now and local models later

Implement one model-provider interface with two adapters:

- OpenRouter: preferred on the present laptop; model inference happens remotely.
- Ollama: optional on the serviced RTX 4060 laptop when available, or a smaller CPU model after testing the current machine.

Provide a rules-only mode when no model is available and a clearly labelled recorded-demo replay. Neither should pretend to be fresh AI analysis.

For zero-spend OpenRouter use, allow only currently verified free models/free routes, keep credentials out of Git/logs, disable paid fallback/plugins and bound retries. The free-model catalogue and availability can change. The free router can choose a supported free model, but scientific comparisons should select a validated model and log the actual returned model/provider. [Free router](https://openrouter.ai/openrouter/free), [model fallbacks](https://openrouter.ai/docs/guides/routing/model-fallbacks)

As checked on 22 October 2026, OpenRouter's free tier is limited to 20 requests/minute and 50/day. The larger daily allowance requires a credit purchase and is outside the current zero-spend plan. Recheck limits during setup and display actual remaining quota when available. [OpenRouter pricing](https://openrouter.ai/pricing), [limits](https://openrouter.ai/docs/api_reference/limits)

Five stocks times three separate agent calls consume 15 requests for a full round before chatbot questions or retries. Continuous cloud-model deliberation is therefore not feasible on this free allowance. An illustrative budget is a few batched watchlist briefs, a reserved chatbot allowance and a small event/retry allowance. This is an application policy, not extra provider capacity.

When local hardware returns, test a quantized 4B model first, such as Qwen3 4B Q4_K_M, with a modest context and sequential agent calls sharing one loaded model. Its roughly 2.6 GB download does not represent total runtime VRAM. Model choice remains a measured decision. [Model details](https://ollama.com/library/qwen3:4b-q4_K_M), [Ollama hardware support](https://docs.ollama.com/gpu)

Local Ollama supports schema-constrained output; Python must still validate references, allowed actions and numbers. A valid JSON response can contain incorrect claims. [Structured outputs](https://docs.ollama.com/capabilities/structured-outputs)

## 8. Live market monitoring and the 24/7 requirement

A separate Python worker runs independently of the Streamlit dashboard:

1. Receive permitted quote updates or poll at a provider-compliant interval.
2. Validate identity, timestamps, freshness and connection status.
3. Invoke C++ bar rules on completed bars and separate quote/depth rules on valid, timestamped observations.
4. Store events and checkpoints.
5. Call the research agents only for meaningful events or scheduled briefs within the AI budget.
6. Publish alerts and let the dashboard display stored state.

Examples of events: a break of a previously known level with unusual volume, a new relevant company event, widening spreads, persistent displayed-depth imbalance or stale/disconnected data. Indicator threshold events remain optional supporting alerts. De-duplicate events, require persistence where appropriate and avoid repeatedly explaining unchanged conditions.

During exchange sessions monitor price events; outside sessions continue permitted text updates, health checks and scheduled tasks. Use the exchange calendar and Asia/Kolkata timezone rather than assuming weekdays always trade.

Persist last processed candles, source availability times, alert IDs, pending jobs and worker heartbeat. Resume after restart, back off on failures and show gaps/reauthentication needs. A single-worker lock prevents duplicate service instances.

Use SQLite behind a Python storage layer for watchlists, durable events and run metadata; CSV/JSON remain useful for import/export. A Python model layer such as SQLModel avoids requiring separately authored SQL scripts. The UI and worker use short transactions and tested concurrent access.

**Operating reality:** a 24/7-capable worker needs an awake, powered, connected computer or an available always-on host. Closing the browser should not stop it; sleeping/shutting down the laptop does. Free hosted UI availability is not a dependable always-on-worker guarantee. Start with an existing machine and show uptime/last-seen status honestly. Do not promise uninterrupted free hosting.

Later setup can register the worker for startup/restart using the operating system. No service, scheduled job or Codex automation is being created during this outline step.

## 9. India data sources and what “live” means

**Live-data candidate:** Upstox's current Analytics Token is documented as free, read-only and valid for one year. It supports market quotes, history, news and WebSockets without a static IP for those categories. Account access, eligibility, entitlements and permitted storage/use must be verified before relying on it. No account has been connected here. [Analytics Token documentation](https://upstox.com/developer/api-documentation/analytics-token/)

Its Market Feed V3 provides real-time updates using WebSockets/Protobuf. Use a small cash-equity watchlist and a Python SDK/decoder; do not write the wire protocol by hand or subscribe to derivatives. [Market Feed V3](https://upstox.com/developer/api-documentation/v3/get-market-data-feed/)

For the initial microstructure candidate, the normal full mode supplies five price levels; it is not an order-by-order feed. Deeper-book availability depends on the account's current entitlement. Keep zero-cost verification in the source feasibility check, and do not enable a paid upgrade to obtain it.

If no suitable authenticated feed is available, provide permitted periodic/delayed data and replay modes, clearly labelled. Always show the source timestamp and last refresh. Do not label a periodically fetched or stale quote as guaranteed real-time.

**Recent news candidate:** Upstox's News API currently returns only the past seven days. It includes headlines, summaries, links and publication times, but does not provide a multi-year news archive. Collect eligible observations prospectively, subject to data-use terms. [News API](https://upstox.com/developer/api-documentation/get-news/)

**Historical data/import:** retain a provider-independent CSV/JSON import path. NSE lists OHLC/volume, announcements and corporate actions in its academic research-data basket. Its research access is conditional; public website downloads are not an unrestricted simulation licence, and general terms restrict scraping/simulation. Resolve the applicable academic conditions before using that route for scored backtests. [NSE research list](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/Data%20list%20under%20NSE%20Data%20Sharing%20Policy%20for%20Research%20and%20Analysis_20250728.pdf), [research conditions](https://www.nseindia.com/static/nse-disclaimer), [general terms](https://www.nse.in/static/nse-terms-of-use)

An optional yfinance connector can be evaluated for permitted personal research, with adjustment/coverage checks. Its authors identify it as unofficial and distinguish its software licence from Yahoo data-use rights. Keep the import fallback. [Authors' repository](https://github.com/ranaroussi/yfinance)

Journalistic news and exchange/company disclosures remain separately labelled. RSS availability alone does not establish permission for automated AI processing. No free, complete historical Indian journalism archive has been established in this research.

Retain source IDs, publication/update/dissemination times, first-seen times, versions and URLs. For backtests, require an eligible as-of version or conservative availability time. Missing text is missing evidence, not automatically neutral sentiment. Keep third-party raw data out of the public GitHub repository unless redistribution rights are established.

## 9A. Level 1/2/3 and honest rder-oflow capabilities

**Naming matters:** NSE describes L1 as best bid/ask, L2 as five price levels, L3 as twenty price levels and tick-by-tick as its full-book product. NSE L3 therefore must not be equated automatically with sequenced individual-order events. Direct exchange feeds are subscription products; broker access may provide a subset under different terms. [NSE feed definitions](https://www.nseindia.com/static/market-data/real-time-data-subscription)

| Available observations | Supported research features |
| --- | --- |
| OHLCV bars | Prior/rolling levels, gaps, breakouts, relative volume, relative strength and risk context; no reconstructed order book. |
| Best bid/ask plus quantities | Spread, midpoint, top-of-book displayed imbalance and freshness. Last price alone is not complete L1. |
| Aggregated price-level depth | Visible depth ladder/heatmap, top-N displayed imbalance, persistence and sampled depth changes; indicative sweep cost only for the shown size/levels. |
| Suitable complete trade prints | Trade rate and traded-volume-at-price; signed volume/delta/CVD only with a documented aggressor flag or an explicitly labelled estimation method. |
| Adequately sequenced order events | Potential book reconstruction, order additions/cancellations and event-based flow, after validating feed semantics and gap recovery. |

Depth imbalance uses quantities currently displayed at the selected levels, not executed buy/sell volume. For example, (visible bid quantity - visible ask quantity) / (their sum) is undefined if the sum is zero and must not be converted into a success probability. Record the number of levels and source with the value.

A decrease in displayed bid quantity may represent executions, cancellations or intervening changes; snapshots alone do not identify which. LTP/last-quantity updates need not include every exchange print. Do not manufacture true CVD, footprint charts, exact cancellation counts or queue position from candle colours or sparse broker snapshots. If trade signing is estimated, label it and retain unclassified trades.

Likewise, candle-derived VWAP/volume profiles are approximations unless the supplied data supports the exact calculation. Visible depth does not expose all hidden liquidity or prove institutional intent, spoofing or iceberg orders.

Start with five-level broker depth if genuinely free/permitted for the user. Optional deeper levels can be added only after confirming a zero-cost entitlement; a promotional entitlement is not a permanent availability promise. Full sequenced order data is an optional capability, not an assumed free requirement.

Each provider reports capabilities, available fields, depth count, event/update timestamps, sampling and gaps. Disable unsupported controls rather than replacing missing measurements with invented values. Store permitted source observations from implementation onwards for replay, with retention and licensing rules. No generally available free multi-year Indian order-book archive has been verified here.

Keep investment-horizon analysis and intraday liquidity research separate. Test whether accessible liquidity evidence improves alerts and execution-quality estimates; do not infer long-term returns from a momentary queue imbalance.

## 10. Backtesting lab

Start with daily bars, one stock plus cash per run, whole shares, INR accounting and a fixed small universe.

Compare:
- Buy-and-hold.
- Technical-only rules.
- Price-structure/relative-volume rules as a non-indicator-only baseline.
- Sentiment-only rules over available eligible text history.
- A predefined combined numerical strategy over that same overlapping interval.

Handle warm-up bars, missing sessions, split/bonus/dividend policy, exposure limits and explicit trading charges/slippage. Use raw execution prices with explicit corporate-action accounting or another fully consistent documented method. Do not mix adjusted closes with raw opens.

A signal using day t's close executes no earlier than the next permitted session, initially at its open with cost/slippage assumptions. Benchmark accounting must use compatible assumptions. Verify dated Indian delivery-equity charges during implementation rather than inventing current rates.

Display equity curve, drawdown curve, trade ledger, net return, volatility, Sharpe with a stated risk-free assumption, turnover, exposure and trade count. Do not aggregate independent stock backtests into a portfolio without a separate funded allocation model.

Use chronological development/validation/test windows; select thresholds on the past only. Report the selected-stock/universe limitation. Historical sentiment comparisons cover actual overlapping text/price dates rather than filling years of missing news.

Modern LLMs may know historical outcomes from pretraining. Historical generative-agent returns are exploratory unless model timing and data availability can be justified. Keep the primary numerical backtest separate from prospective agent-signal evaluation. [Glasserman and Lin](https://arxiv.org/abs/2309.17322)

**Separate microstructure evaluation:** daily OHLCV backtests cannot validate a depth/order-flow strategy. Use permitted recorded quote/depth events and a forward paper/replay experiment over the actual common period. Compare price/volume rules, then added news, then added available depth, on identical assets/dates. Record when information was received, assume explicit decision latency, and use the next eligible observation with spread/fees/slippage. Sparse snapshots do not justify guaranteed limit-order fills or queue simulation. Treat outages and stale depth as invalid evidence, not zero imbalance.

## 11. Monte Carlo simulation lab

This is a C++ risk-scenario engine, useful without a GPU or LLM. It complements backtesting rather than replacing historical evidence.

**Method A — circular-block return bootstrap:** resample blocks of historical returns to retain some short-run dependence. Expose the calibration window and block length. This remains conditional on the observed sample and cannot invent every future crisis. [Time-series bootstrap reference](https://arch.readthedocs.io/en/latest/bootstrap/timeseries-bootstraps.html)

**Method B — geometric Brownian motion:** provide a simpler comparison with explicitly stated drift, volatility and distribution assumptions. Start from a chosen current/as-of price and estimate inputs from eligible earlier data. It is a simplified scenario model; market jumps and changing volatility are limitations.

Suggested controls:
- Investment amount and initial share/cash allocation.
- Horizon in trading days, initially 20, 60 or 252.
- Simulation count, initially 1,000–5,000, adjustable after CPU measurement.
- Random seed, calibration period, bootstrap block length and stress assumptions.

Show a small sample of paths, a percentile fan chart, terminal wealth/loss distribution, 5th/50th/95th percentiles, simulated loss probability, 95% loss VaR, tail expected loss and drawdown summaries.

Define loss consistently relative to starting wealth and label all values with the horizon. Estimated probabilities are conditional on the simulation assumptions; percentile bands are not guaranteed forecast bounds. Hold calibration parameters fixed for comparisons and distinguish Monte Carlo sampling error from model risk.

Initially simulate a fixed long position plus cash. If later simulating a dynamic strategy, execute the actual C++ policy and accounting on each path. Do not label price-path results as strategy returns. A later multi-stock version must retain cross-stock dependence by sampling joint returns/blocks or using a calibrated joint model.

## 12. Chatbot for doubts

Support questions such as:
- What does RSI measure, and why can it stay high during a strong trend?
- Which evidence caused this stock's alert?
- Why did the reviewer disagree with the technical analyst?
- How were these backtest costs and drawdown calculated?
- What assumptions produced this Monte Carlo loss estimate?

Provide two modes: a finance/project tutor using curated notes, and a stock/run assistant using the selected dated evidence and saved engine outputs.

Use small deterministic retrieval over guides, ticker evidence and run IDs initially. A vector database is unnecessary for the first version. The chatbot invokes approved read-only queries/calculations and cites their results. It must distinguish observed facts, scenario assumptions and generated explanation.

News/document content is evidence, not instructions. Chatbot messages do not grant shell, arbitrary-code, credential or order-placement access. Provider failure/quota exhaustion should be visible; cached material must be labelled. OpenRouter chat shares the same request allowance as the research agents.

## 13. Proposed codebase

This is a future structure; the source files below have not been created.

```text
final_yr_finance_project/
  engine/
    CMakeLists.txt
    include/stock_research/    # Candle, signal, trade, config and result types
    src/
      indicators/
      market_structure/
      microstructure/        # Capability-gated quote/depth/trade features
      strategies/
      risk/
      backtest/
      simulation/
      metrics/
      cli/
    tests/
  app/
    dashboard.py
    pages/
    engine_bridge.py          # Batch JSON calls to the C++ executable
    data/                    # Includes permitted quote/depth recorder and capabilities
    llm/                      # OpenRouter and Ollama adapters
    agents/
    chatbot/
    monitoring/               # Separate worker and event scheduling
    storage/
    reporting/
  prompts/
  configs/                    # Markets, strategy and quota settings
  docs/                       # Methodology, finance notes and interview guide
  tests/                      # Python integration/provider/chatbot tests
  data/                       # Local third-party data, generally Git-ignored
  runs/                       # Local experiment results/checkpoints
  .env.example                # Placeholder names only
  .gitignore
  requirements.txt
  README.md
```

Use plain C++ types and small modules, a reusable engine library plus CLI, typed Python models and a versioned JSON contract. Avoid unnecessary template complexity, frontend frameworks, microservices and early parallelisation.

Tools: C++17/compiler/CMake/nlohmann-json; Python/Streamlit/Plotly; requests or provider SDKs; optional Transformers/PyTorch for FinBERT; Pydantic/SQLModel; CTest and pytest. Pin versions when implementation starts.

FinBERT is a financial sentiment classifier, not a generative agent. Its current weights have noncommercial/share-alike terms, so retain attribution and separate model/data licences from the application-code licence. [Model card](https://huggingface.co/ProsusAI/finbert)

## 14. Validation and research contribution

Verify known indicator examples, next-session execution, transaction-cost accounting, cash/holding conservation, corporate actions, absence of future evidence, malformed JSON and stale-feed failures.

Also verify spread/depth-imbalance examples, zero denominators, future-dependent swing confirmation, out-of-order updates, disconnect gaps and correct disabling of unsupported trade/order-flow features. Assess whether news/price/volume/depth add useful information beyond the indicator-only baseline; do not assume that deeper data improves performance.

For Monte Carlo, verify seeded repeatability within a pinned build/runtime, zero-volatility/constant-return cases, percentile ordering and consistent loss definitions. Use numerical tolerances across different compilers/platforms.

For monitoring, test restart recovery, duplicate-event suppression, disconnect/reconnect handling and quota exhaustion without losing numerical alerts.

Compare single-agent and multi-agent reports using the same evidence and disclosed model/call budgets. Score source support, numerical consistency, recognition of missing data and usefulness. Compare runtime and response quality across OpenRouter/local models when both become available; log model changes rather than silently mixing experiments.

The contribution is a compact, inspectable C++/Python research workflow combining historical evaluation, uncertainty scenarios, monitoring and evidence-grounded AI. Prior multi-agent trading work must be cited; extra agents are not automatically better. [TradingAgents paper](https://arxiv.org/abs/2412.20138)

## 15. Delivery milestones

The expanded requirements exceed the earlier four-to-six-week small-core scope. Plan milestones rather than promising a fixed date without knowing available working hours.

| Stage | Deliverable |
| --- | --- |
| 1 | Verify free data access and exact quote/depth capabilities, define contracts and establish the C++ build. |
| 2 | One complete flow: import prices → C++ price/volume features and supporting indicators/backtest → Python charts. |
| 3 | Monte Carlo lab with documented assumptions and verified accounting. |
| 4 | OpenRouter/local provider selection, three-agent report and result-grounded chatbot. |
| 5 | Persistent watchlist worker, capability-dependent depth views/recording, alerts, restart recovery and quota/freshness display. |
| 6 | Usability, source/setup documentation, frozen comparisons and presentation demo. |

An initial vertical slice can target roughly 2–3 focused weeks. The expanded integrated system is a provisional 6–10-focused-week effort, conditional on data access, hardware setup and working time. These are planning estimates, not measured completion dates.

Use the remaining months for prospective observations, robustness checks, the US cash-equity adapter and final report/presentation. US support needs its own source/calendar/currency/cost configuration; changing ticker suffixes alone is insufficient.

Start forward observation only after implementation is requested and the data-use conditions are established. A short first paper run demonstrates functioning software, not durable profitability.

## 16. Viewing the outline and future code in VS Code

Workspace:
C:\Users\Somaditya\Documents\ChatGPT\final_yr_finance_project

Open VS Code → File → Open Folder → choose that folder. Select PROJECT_OUTLINE_AND_RESEARCH.md in Explorer, then press Ctrl+Shift+V for the formatted Markdown preview.

Alternatively, in PowerShell:

```powershell
code "C:\Users\Somaditya\Documents\ChatGPT\final_yr_finance_project"
```

The VS Code launcher is available on this machine. The future C++ engine and Python app will appear as ordinary editable folders in the same workspace.

For implementation, plan the Microsoft C/C++, CMake Tools and Python extensions plus a separate compiler/CMake installation as needed. VS Code's C++ extension does not itself include a compiler. No compiler/CMake was detected on PATH in this review; that does not prove none is installed elsewhere. [VS Code C++ setup](https://code.visualstudio.com/docs/languages/cpp), [CLI usage](https://code.visualstudio.com/docs/configure/command-line)

The intended remote owner remains devspideyy. Earlier GitHub authentication was unavailable, and no remote repository has been created during planning. All source code can later be versioned/pushed when the correct account is authenticated.

This outline contains future research milestones as well as the initial design. Use README.md and the tested source tree to distinguish implemented functionality from planned extensions.
