"""Small research experiments. Python coordinates; the C++ engine computes results."""

from itertools import product

from app.accounting import market_options
from app.assessment import STRATEGIES
from app.computation import calculate
from app.research_protocol import (
    execution_options,
    fingerprint,
    frozen_policy,
    reference_sessions,
    require_quality,
    select_window,
    visible_candles,
)


def cohort_study(
    sources: list[dict],
    label: str,
    start: str,
    end: str,
    *,
    capital=100000.0,
    commission=10.0,
    slippage=5.0,
    progress=None,
) -> dict:
    if not 1 <= len(sources) <= 8 or label not in STRATEGIES:
        raise ValueError("Choose 1–8 stocks and a supported fixed strategy.")
    if len({source["symbol"] for source in sources}) != len(sources):
        raise ValueError(
            "Choose distinct stocks; duplicate source symbols are not comparable sleeves."
        )
    expected = [d for d in reference_sessions() if start <= d <= end]
    if len(expected) < 100:
        raise ValueError(
            "Choose at least 100 observed daily sessions for a useful holdout comparison."
        )
    rows, excluded = [], []
    for index, source in enumerate(sources):
        if progress:
            progress(index / len(sources), source["symbol"])
        try:
            dataset = select_window(source, start, end)
            if dataset.get("is_synthetic") or dataset.get("price_basis") != "adjusted":
                raise ValueError(
                    "Cohort research requires real adjusted histories with proportional research costs."
                )
            if [c["timestamp"] for c in visible_candles(dataset)] != expected:
                raise ValueError(
                    "Coverage differs from the requested observed-session calendar; no gap filling."
                )
            policy = frozen_policy(dataset)
            if policy and end >= policy["start"]:
                raise ValueError(
                    "Window overlaps a frozen final period; choose an earlier development end date."
                )
            options = dict(
                initial_capital=capital,
                commission_bps=commission,
                slippage_bps=slippage,
                lookback=20,
                volume_threshold=1.2,
                stop_loss_pct=0.08,
                max_exposure=1.0,
                evaluation_start=dataset["window_start"] + int(len(expected) * 0.7),
                **market_options(dataset),
                **execution_options(dataset),
            )
            require_quality(dataset, options)
            run = calculate("backtest", dataset["candles"], strategy=STRATEGIES[label], **options)
            benchmark = calculate("backtest", dataset["candles"], strategy="buy_hold", **options)
            rows.append(
                {
                    "symbol": source["symbol"],
                    "name": source.get("name", source["symbol"]),
                    "run": run,
                    "benchmark": benchmark,
                    "settings": options,
                    "source_hash": fingerprint(dataset["candles"]),
                    "source": dataset.get("history_quality", {}),
                }
            )
        except (ValueError, RuntimeError, OSError) as exc:
            excluded.append({"symbol": source["symbol"], "reason": str(exc)})
    if progress:
        progress(1.0, "Complete")
    return {
        "strategy": label,
        "start": start,
        "end": end,
        "rows": rows,
        "excluded": excluded,
        "requested": [s["symbol"] for s in sources],
        "method": "Fixed rules with a last-30% chronological evaluation, causal earlier warm-up, identical dates and explicit proportional costs. Exclusions are disclosed. Current prepared cohort; survivorship control and untouched status are not established.",
    }


def robustness_study(dataset: dict, label: str, settings: dict, *, progress=None) -> dict:
    if label not in STRATEGIES:
        raise ValueError("Unsupported strategy.")
    policy = frozen_policy(dataset)
    if policy and dataset["candles"][-1]["timestamp"] >= policy["start"]:
        raise ValueError("Run robustness on a development window before the frozen final period.")
    require_quality(dataset, settings)
    base = int(settings.get("lookback", 20))
    lookbacks = sorted({max(2, base // 2), base, min(200, round(base * 1.5))})
    threshold = settings.get("volume_threshold", 1.2)
    volumes = (
        [round(threshold * f, 3) for f in [0.8, 1, 1.2]]
        if label == "Price + volume"
        else [threshold]
    )
    if label in {"Indicator baseline", "Buy and hold"}:
        lookbacks = [base]  # These native rules do not use the structure lookback.
    cases = [
        ("Parameter grid", lookback, volume, 1) for lookback, volume in product(lookbacks, volumes)
    ]
    cases += [("2× costs", base, threshold, 2), ("3× costs", base, threshold, 3)]
    rows = []
    for index, (name, lookback, volume, multiplier) in enumerate(cases):
        if progress:
            progress(index / len(cases), f"{index + 1}/{len(cases)} · {name}")
        options = {
            **settings,
            "lookback": lookback,
            "volume_threshold": volume,
            "cost_multiplier": settings.get("cost_multiplier", 1) * multiplier,
            "slippage_bps": settings.get("slippage_bps", 5) * multiplier,
        }
        run = calculate("backtest", dataset["candles"], strategy=STRATEGIES[label], **options)
        rows.append(
            {
                "case": name,
                "lookback": lookback,
                "volume_threshold": volume,
                "cost_multiplier": multiplier,
                "metrics": run["metrics"],
                "provenance": run["_provenance"],
            }
        )
    if progress:
        progress(1.0, "Complete")
    return {
        "symbol": dataset["symbol"],
        "strategy": label,
        "rows": rows,
        "evaluation_start": settings["evaluation_start"],
        "method": "Fixed nearby settings and cost stresses on the same dates. Exploratory sensitivity, not an optimiser or independent validation. Inspecting this window for tuning makes it development data.",
    }


def curve(symbol: str, run: dict, weight: float = 0) -> dict:
    return {"symbol": symbol, "equity": run["equity"], "weight": weight}


def benchmark_diagnostics(run: dict, benchmark: dict) -> dict:
    return calculate("diagnostics", [curve("Strategy", run), curve("Buy and hold", benchmark)])


def portfolio_study(study: dict, weights: dict[str, float], capital: float, cap: float) -> dict:
    if not weights:
        raise ValueError("Choose portfolio stocks and initial weights.")
    available = {row["symbol"]: row for row in study["rows"]}
    if set(weights) - available.keys():
        raise ValueError("Portfolio prices must come from the displayed cohort study.")
    results = {}
    for name, key in [("Strategy portfolio", "run"), ("Buy-and-hold portfolio", "benchmark")]:
        curves = [
            curve(symbol, available[symbol][key], weight) for symbol, weight in weights.items()
        ]
        results[name] = calculate("portfolio", curves, initial_capital=capital, weight_cap=cap)
    diagnostics = benchmark_diagnostics(
        results["Strategy portfolio"], results["Buy-and-hold portfolio"]
    )
    return {
        "portfolios": results,
        "diagnostics": diagnostics,
        "weights": weights,
        "strategy": study["strategy"],
        "source_requests": {
            symbol: available[symbol]["run"]["_provenance"]["request_sha256"] for symbol in weights
        },
    }


def research_report(study: dict) -> str:
    lines = [
        "# Cross-stock research report",
        f"\nStrategy: {study['strategy']}\n",
        f"Source window: {study['start']} to {study['end']}\n",
        study["method"],
        "\n| Stock | Evaluation | Net return | Buy & hold | Worst fall | Fills |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in study["rows"]:
        run, hold = row["run"], row["benchmark"]
        m = run["metrics"]
        lines.append(
            f"| {row['symbol']} | {run['evaluation']['start']} to {run['evaluation']['end']} | {m['total_return']:.2%} | {hold['metrics']['total_return']:.2%} | {m['max_drawdown']:.2%} | {m['trade_count']} |"
        )
    lines.append("\nExcluded inputs:")
    lines.extend(f"- {row['symbol']}: {row['reason']}" for row in study["excluded"])
    lines.append("\nSource records:")
    lines.extend(
        f"- {row['symbol']}: {row.get('source', {}).get('source_url', 'local supplied prices')} · SHA256 {row['source_hash']}"
        for row in study["rows"]
    )
    lines.append(
        "\nThis is exploratory historical evidence, not a present-day stock recommendation. No news or fundamentals are inferred."
    )
    return "\n".join(lines)
