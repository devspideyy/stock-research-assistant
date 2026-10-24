"""One-factor-at-a-time sensitivity of the same net-return backtest, not an optimiser."""

from app.engine_bridge import EngineClient
from app.research_protocol import record_run


def risk_sensitivity(
    dataset: dict, settings: dict, strategy: str, *, paths=500, horizon=126, seed=42
) -> dict:
    engine = EngineClient()
    scenarios = [("Full calibration", 0, block, 1) for block in [1, 5, 20]]
    scenarios += [("Last 252 net returns", 252, 5, 1), ("Last 63 net returns", 63, 5, 1)]
    scenarios += [("2× costs and slippage", 0, 5, 2), ("3× costs and slippage", 0, 5, 3)]
    rows = []
    for label, tail, block, multiplier in scenarios:
        options = dict(settings)
        options["slippage_bps"] = settings.get("slippage_bps", 5) * multiplier
        options["cost_multiplier"] = settings.get("cost_multiplier", 1) * multiplier
        result = engine.simulate(
            dataset["candles"],
            **options,
            strategy=strategy,
            basis="strategy",
            method="bootstrap",
            calibration_observations=tail,
            block_size=block,
            paths=paths,
            horizon=horizon,
            seed=seed,
            capital=settings.get("initial_capital", 100000),
        )
        rows.append(
            {
                "scenario": label,
                "block": block,
                "cost_multiplier": multiplier,
                "observations": result["calibration"]["observations"],
                **result["summary"],
                "provenance": result["_provenance"],
            }
        )
    report = {
        "symbol": dataset["symbol"],
        "strategy": strategy,
        "paths": paths,
        "horizon": horizon,
        "seed": seed,
        "rows": rows,
        "method": "One factor at a time; fixed seed/horizon. Tail windows retain the original backtest's positions and cash days; costs recompute that same fixed rule. No winner selection or parameter fitting.",
    }
    record_run("risk_sensitivity", dataset, settings, report)
    return report
