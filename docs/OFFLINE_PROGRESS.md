# Offline development progress — 24 October 2026

The subsequent real-history and heritage-workspace release is documented in
[Historical research](HISTORICAL_RESEARCH.md), which supersedes the earlier demo-first
workflow described below. It adds 46 prepared real stocks and Monte Carlo linked
to net strategy backtests, without broker credentials.

The C++17/Python workstation now supports explainable price/volume research,
bullish/bearish evidence scores, five strategy hypotheses, animated backtest and
Monte Carlo replay, an educational assistant and local research history. The new
offline work adds declared split/bonus/dividend accounting, dividend receivables,
dated editable NSE delivery-cost estimates and chronological multi-period strategy
validation with cost sensitivity and a buy-and-hold benchmark.

The interface groups research, experiments and workspace tools in the sidebar.
Backtesting separates performance, replay and accounting. Validation has a fold
comparison chart, detailed periods, saved studies and reproducibility exports.
A fictional accounting example makes the split/dividend logic demonstrable without
API credentials. All new application code remains C++ or Python; there is no new
framework, service or dependency.

Architecture remains a Python Streamlit interface communicating through validated
JSON with an independent C++ executable. SQLite stores research records and study
snapshots. TA-Lib provides the separate indicator catalogue, with Plotly charts.
Optional OpenRouter/Ollama and read-only broker connections remain separate from
offline calculations. The numerical strategies are fixed rules, not LLM-generated
trades or trained prediction models.

Verification covers economic conservation through corporate actions, dated fee
examples, next-open fills, future-data exclusion, chronological windows, cost stress
and actual Streamlit interactions. All 274 Python tests, nine native C++ groups and
Ruff checks pass. Browser verification includes study save/history, the split/dividend
ledger and itemised fees. Passing software tests establishes implemented
behaviour, not investment effectiveness. See [the accounting/validation contracts](ACCOUNTING_AND_VALIDATION.md)
and the test suite for precise assumptions.

Remaining work depends chiefly on permitted real historical/forward data: reconcile
actions and costs against real examples, freeze a final untouched evaluation period,
compare agent variants with equal evidence/budgets, and validate feed freshness,
reconnect behaviour and uptime when credentials are supplied. Level 2/3, derivatives,
trade execution and US equities remain deferred. A 24/7 service also needs an awake
host or deployment; it cannot be established by a dashboard alone.
