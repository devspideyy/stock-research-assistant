# Free data, keys and coverage

Checked against provider documentation on **23 October 2026**. API availability,
quotas and account pricing can change. These are documented capabilities, not
successful authenticated feed tests on this laptop.

## Credentials to obtain

| Credential | Purpose | Setup |
| --- | --- | --- |
| Upstox Analytics Token | Read-only quotes, history, WebSockets, news, fundamentals and corporate actions | Sign into your own eligible Upstox account, open Developer Apps, select Analytics, Generate Token and copy it locally. Store it as `UPSTOX_ACCESS_TOKEN` in `.env`. |
| OpenRouter API key | Optional generative reports and chatbot | Create a key in your OpenRouter account and store it as `OPENROUTER_API_KEY` in `.env`. Use `OPENROUTER_MODEL=openrouter/free` or a currently available verified free model. |
| No key for the stock catalogue | Public NSE/BSE identifiers | Stock catalogue tab → Refresh. |
| No key for indicators | Local OHLCV calculations | TA-Lib is installed with project requirements. |
| No API key for local Ollama | Optional local LLM | Install Ollama and a suitable model; configure its local URL/name. Local compute and electricity still apply. |

The Upstox Analytics Token is documented as free, read-only and valid for one
year. Its market-data categories do not require a static IP. One token may be
active per account; generating another revokes the old one. The year is a
credential lifetime, not a one-year free API trial. A second account is not
needed to obtain another year of token validity. Do not use another person's
credentials. See [Analytics Token](https://upstox.com/developer/api-documentation/analytics-token/).

Upstox documents its trading/data APIs as free. **Broker account charges are
separate**: check your actual account opening/maintenance terms before opening
an account, especially because you already have Groww. No account opening or
financial transaction is performed by this project. See
[API pricing](https://upstox.com/trading-api/) and
[account charges](https://upstox.com/brokerage-charges/).

Groww's published API offer currently charges ₹499/month plus taxes for market
data. Its described free trial excludes live data and backtesting data, so an
existing Groww account alone does not supply a free live/history feed for this
project. See [Groww API](https://groww.in/trade-api) and
[Groww's explanation of free versus paid access](https://groww.in/blog/api-trading-on-groww).

No TradingView subscription is required for this implementation.

## Local configuration

Copy `.env.example` to `.env` and fill in the two values locally:

```dotenv
UPSTOX_ACCESS_TOKEN=your-own-analytics-token
OPENROUTER_API_KEY=your-own-openrouter-key
OPENROUTER_MODEL=openrouter/free
```

Do not send values in chat or commit `.env`. It is already ignored by Git.
Restart a running app/worker after changing environment settings. Selecting a
real company in the catalogue does not turn synthetic candles into live data.

The existing snapshot adapter reads `UPSTOX_ACCESS_TOKEN` and accepts NSE_EQ and
BSE_EQ keys. It does not yet download research history, stream WebSockets or
automatically ingest news/fundamentals. Those connectors need implementation
and authenticated coverage tests after the token is available. The OpenRouter
adapter already exists but still needs an authenticated inference test.

## Data the project needs

| Data | Required fields | Purpose / caveat |
| --- | --- | --- |
| Instrument master | Exchange, symbol, company, ISIN, provider key, series/group | Search and correct identity; current lists omit delisted history. |
| Daily OHLCV history | Bar timestamp, open/high/low/close, volume, adjustment convention | Investment/swing indicators, backtests and Monte Carlo calibration. |
| Intraday OHLCV history | Bar start, interval, session/timezone, OHLCV, completed-bar status | Intraday studies; current strategy annualization remains daily-only. |
| Live quotes | Provider/exchange timestamp, receipt timestamp, last trade price/time, volume, best bid/ask when supplied | Freshness-aware monitoring; an unchanged last trade is not proof of a feed failure. |
| Corporate actions | ISIN, announcement timestamp, ex/effective date, split/bonus factors, dividends/rights details | Consistent historical adjustments and accounting. Merely fetching events does not implement correct adjustments. |
| Company news | Company mapping, title, publication and first-seen timestamps, source URL, permitted text/summary | Event/sentiment evidence; latest news is not an historical point-in-time archive. |
| Fundamentals | Financial period, original publication timestamp, revision/version, statement type, units | Valuation/quality research without using later information in an earlier backtest. |
| Benchmarks/calendar | Index history, exchange sessions/holidays | Relative performance, market regime and honest closed-market status. |
| Depth snapshots | Timestamped price/quantity levels, side, source and sequence/gap metadata where supplied | Visible spread/imbalance. Not individual-order events or a complete trade tape. |

Upstox's documentation now lists company profile, financial statements, ratios,
shareholding and corporate-action endpoints, plus news queries for up to 30
instrument keys. Their actual symbol coverage, history and publication-date
quality still need validation; do not assume all companies have complete data.
See [Fundamentals](https://upstox.com/developer/api-documentation/fundamentals/)
and [News](https://upstox.com/developer/api-documentation/get-news/).

The history documentation lists daily/weekly/monthly availability from January
2000 and minute/hour data from January 2022, subject to the instrument's actual
listing/available data. Retrieval is chunked: 1–15 minute queries have a one-month
window; daily queries have a ten-year window. This is a provider-level coverage
description, not a promise that every stock has that history. See
[Historical Data V3](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/).

## All stocks and live quotas

The app now reads the public NSE/BSE beginning-of-day files, including ordinary
fully paid equity/SME/surveillance series and groups. It excludes funds, debt,
rights, partly paid shares and derivatives. It keeps both exchange listings of
the same ISIN as separate instruments. The count is a provider catalogue, not a
guarantee of every security ever listed or its ability to trade today.

The NSE filter includes EQ, BE, BZ, SM, ST and SZ, with fund ISINs and rights
symbols excluded. BSE uses A/B/X/etc. trading-group codes rather than literal EQ;
those are mapped separately in `app/instruments.py`. See
[instrument files](https://upstox.com/developer/api-documentation/instruments/)
and [NSE series definitions](https://www.nseindia.com/static/market-data/legend-of-series).

All-stock discovery is feasible without a key. **Simultaneous full-depth
streaming of every stock is a different requirement.** Upstox currently
documents two normal connections and these subscription ceilings:

- LTPC only: up to 5,000 instrument keys.
- Full mode only: up to 2,000 keys.
- Mixed subscription categories have separate, lower combined limits; do not
  assume each connection independently multiplies the account's allowance.
- Full mode supplies five-level displayed depth. Thirty-level mode belongs to
  Upstox Plus and is not assumed free in this project.

The design should cache the full catalogue, update the broad market within
quotas, and allocate richer feeds to the selected watchlist. Historical downloads
also need batching/caching and rate limits. See
[feed limits](https://upstox.com/developer/api-documentation/v3/get-market-data-feed/),
[SDK mode definitions](https://github.com/upstox/upstox-python) and
[REST rate limits](https://upstox.com/developer/api-documentation/rate-limiting/).

Five-level aggregated depth cannot establish hidden liquidity, individual
order cancellations, queue position or genuine aggressor-labelled CVD.
No verified free, complete Indian L3 historical feed has been secured for this
project. A repository of sample data cannot provide missing exchange events.

## Free LLM operation

OpenRouter currently describes 50 free-model requests/day and 20/minute for
an account without the qualifying credit purchase. This project will not require
a purchase or route automatically to a paid model. A three-role report uses
three requests, so continuously asking an LLM about every stock is not feasible
under that free budget. Use cached numerical scans/events first, then ask the
LLM about selected material changes or user questions. Local models can later
serve more requests on available hardware.

The current account limit must be checked from OpenRouter's key endpoint; free
model availability and upstream capacity can be stricter. See
[limits](https://openrouter.ai/docs/api/reference/limits) and
[OpenRouter's free-tier explanation](https://openrouter.ai/blog/tutorials/how-to-get-the-lowest-cost-llm-inference-on-openrouter/).

## Useful repositories

- [upstox/upstox-python](https://github.com/upstox/upstox-python): official Python
  SDK, streaming interface and examples. We use data features only.
- [TA-Lib/ta-lib-python](https://github.com/TA-Lib/ta-lib-python): Python interface
  to the compiled technical-analysis library; Windows wheels are available.
- [TA-Lib/ta-lib](https://github.com/TA-Lib/ta-lib): underlying native library.

Repositories supply code; they do not replace live credentials, data coverage
or permission to redistribute a feed. Price caches and account tokens remain
local and excluded from this Git repository.

## Indicator coverage

The initial prototype exposed SMA/EMA overlays and RSI/ATR context. The new lab
exposes **all 158 functions in the installed TA-Lib 0.6.8 wrapper**, including
multi-output indicators, patterns and math utilities. This is not a claim to
implement every proprietary indicator on every charting platform.

Use **Price & liquidity → Indicator library** to choose a family/function, set
parameters/input columns and calculate. The full catalogue is listed in
[INDICATOR_CATALOGUE.md](INDICATOR_CATALOGUE.md). Warm-up/domain gaps stay missing,
and results export their library versions and settings. The C++ engine still
owns the original evidence features, backtest and simulation; TA-Lib supplies
this expanded indicator lab through its compiled native backend.

Session VWAP needs suitable session/intraday data (bar-based HLC3 weighting is an
approximation to traded-price VWAP); volume profiles and authentic order-flow
tools need more granular inputs. They are not silently fabricated from daily
candles. More indicator selection does not change the original emphasis on
price structure, volume and dated events.
