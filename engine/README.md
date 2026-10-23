# C++ quantitative engine

The engine owns deterministic financial calculations. It does not call AI services,
submit broker orders, or treat a resting order book as executed trade flow.
Application code remains readable C++17 with one vendored dependency:
[nlohmann/json v3.11.3](https://github.com/nlohmann/json/releases/tag/v3.11.3).
Its MIT license is in `third_party/LICENSE.json`.

## Build and test

From the repository root, the project's Python build helper can select an available
compiler. For a standard CMake environment:

```powershell
cmake -S engine -B engine/build -DCMAKE_BUILD_TYPE=Release
cmake --build engine/build --config Release
ctest --test-dir engine/build -C Release --output-on-failure
```

Without CMake, a C++17 compiler can build the CLI directly:

```powershell
clang++ -std=c++17 -O2 -Iengine/include -Iengine/third_party engine/src/engine.cpp engine/src/main.cpp -o engine/build/engine_cli.exe
clang++ -std=c++17 -O2 -Iengine/include -Iengine/third_party engine/src/engine.cpp engine/tests/test_engine.cpp -o engine/build/engine_tests.exe
engine/build/engine_tests.exe
```

On non-Windows systems, omit the `.exe` suffix. A statically linked binary avoids
requiring the compiler runtime DLLs beside the executable when using MinGW.

## JSON protocol

One JSON document on standard input produces one JSON document on standard output.
Successful responses contain `ok: true`, `schema_version: 1`, and `result`.
Invalid requests produce `ok: false`, an `error` string, and a nonzero exit status.
Only stdout is used for protocol output.

All commands except `depth` require `candles`, a chronological list with
`timestamp`, `open`, `high`, `low`, `close`, and `volume`. Prices must be positive,
OHLC bounds valid, and volume nonnegative. Duplicate timestamps are rejected.
Timestamps must use one uniform format: `YYYY-MM-DD`, `YYYY-MM-DDTHH:MM:SS`,
or `YYYY-MM-DDTHH:MM:SSZ`. Normalize timezone-aware inputs to UTC before calling.
At least two candles are required; statistical calibration needs much more history
for meaningful interpretation.

```json
{
  "command": "analyze",
  "candles": [
    {"timestamp":"2025-01-01","open":100,"high":102,"low":99,"close":101,"volume":1000},
    {"timestamp":"2025-01-02","open":101,"high":105,"low":100,"close":104,"volume":1500}
  ],
  "options": {}
}
```

### Analyze

`summary` contains `last_close`, `return_1d`, `relative_volume`, `prior_high`,
`prior_low`, `breakout` (`up`, `down`, `none`), and supporting indicators
`sma20`, `ema20`, `rsi14`, `atr14`. `series` contains every input row with those
features. Unavailable warm-up values are JSON null.

Prior levels use the preceding twenty candles, excluding the current candle.
Before twenty observations, they use available preceding candles. Relative volume
uses current volume divided by preceding average volume; zero historical volume
produces null. RSI and ATR use Wilder smoothing. EMA starts at the first close,
with a twenty-observation display warm-up.

### Backtest

Default options:

| Option | Default | Meaning |
|---|---:|---|
| `strategy` | `price_volume` | `price_volume`, `indicator`, or `buy_hold` |
| `lookback` | 20 | Prior high/low/volume lookback for price-volume rules |
| `volume_threshold` | 1.2 | Minimum relative volume at entry |
| `initial_capital` | 100000 | Starting cash in input price currency |
| `max_exposure` | 1 | Maximum entry allocation, including entry costs |
| `commission_bps` | 10 | Scenario commission per execution; not an official tax schedule |
| `slippage_bps` | 5 | Scenario adverse fill adjustment on both sides |
| `stop_loss_pct` | 0.08 | Close-based stop signal; zero disables |

The price-volume strategy enters after a close above the prior high, with sufficient
relative volume and full lookback history. It exits on a close below the prior low
or configured stop threshold. The indicator comparison uses a fixed twenty-bar SMA.
Buy-and-hold decides after the first close and buys at the second candle's open;
it uses the same executable horizon and cost assumptions as the other strategies.

Every signal executes at the next observed open. A closing stop can therefore
lose more than its configured threshold after an overnight gap. Orders use whole
shares and available cash, with no leverage, shorts, or intrabar fill assumptions.
Final positions remain marked to market; no forced exit is inserted.
`max_exposure` caps entry allocation including costs; holding weights can later drift.

`metrics` contains fractional `total_return`, positive fractional `max_drawdown`,
`annualized_volatility`, nullable `sharpe`, `trade_count` (execution count),
`turnover` (gross executed notional / initial capital), and `exposure` (fraction
of post-start bars with a position). `equity` and `trades` provide the ledger.
Sharpe assumes zero risk-free rate. Annualization assumes daily bars and 252
sessions/year. The engine does not implement corporate-action processing,
survivorship correction, official exchange taxes, or actual execution.
Raw split/dividend events invalidate the accounting. Consistent adjusted OHLC
represents synthetic adjusted units rather than actual historical share lots or
cash dividend distributions. Use that limitation when interpreting comparisons.

### Monte Carlo simulation

Options are `method` (`bootstrap` or `gbm`), `paths` (1000), `horizon` (60),
`seed` (42), `capital` (100000), and `block_size` (5). Paths include step zero.
Limits bound memory use to five million path steps.

Bootstrap samples circular blocks of daily log returns. GBM fits historical
daily log mean and sample log volatility. Its estimated arithmetic drift is
`mean_log_return + sigma^2 / 2`; the daily log increment is drift minus half
variance plus Gaussian volatility. Neither method represents a forecast.

Stress options are `volatility_multiplier` (1), `annual_drift_shift` (0, additive
annual log drift), `initial_shock_pct` (0, fractional initial wealth shock), and
`execution_spread_bps` (0, one-off entry cost). GBM volatility stress preserves
the original fitted arithmetic drift. Bootstrap rescales deviations around the
original mean. The initial shock and spread occur at step one.

`summary.p05/p50/p95` are terminal wealth percentiles, `probability_loss` is
the fraction finishing below starting capital, and `var95` and
`expected_shortfall95` are nonnegative currency losses. ES integrates the worst
5% terminal probability mass, using fractional weights when needed.
`max_drawdown_p50/p95` summarize simulated path drawdowns. `percentiles`
contains each step's bands; `sample_paths` includes up to thirty wealth paths.
`calibration` exposes the fitted parameters and stresses. The same seed reproduces
results within a build; standard-library Gaussian algorithms may vary across
toolchains. Historical drift is especially uncertain with short samples.

### Depth snapshot

Use `command: depth` with `bids` and `asks`, each a list of `price`/`quantity`
objects. The engine sorts prices, rejects duplicate levels and crossed/locked books,
and returns spread, midpoint, spread in basis points, top-level quantity imbalance,
and supplied-depth quantity imbalance. Imbalance is `(bid - ask) / (bid + ask)`;
zero total quantity produces null. Supply contemporaneous sides at equal depths.

Displayed quantity can disappear through executions, cancellations, or sampling.
This command never produces CVD, aggressor classifications, or spoofing claims.

## Tests

The standalone test executable checks excluded-current-bar features, indicator
warm-up, invalid inputs, next-open timing, gap stops, whole-share accounting,
costs and cash constraints, simulation reproducibility, stress effects, tail-risk
ordering, resource limits, and depth calculations.
