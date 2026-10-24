"""Run actual native research/indicator/risk checks against every cached historical stock."""

from pathlib import Path
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import history, indicators  # noqa: E402
from app.engine_bridge import EngineClient  # noqa: E402
from app.assessment import STRATEGIES  # noqa: E402
from app.validation import run_validation  # noqa: E402
from app.research_protocol import (  # noqa: E402
    latest_complete_window,
    visible_candles,
    execution_options,
    require_quality,
)


def check(symbol):
    dataset = latest_complete_window(history.load_stock(symbol))
    candles = dataset["candles"]
    engine = EngineClient()
    analysis = engine.analyze(candles, price_basis="adjusted")
    settings = {
        "initial_capital": 100000,
        "commission_bps": 10,
        "slippage_bps": 5,
        "evaluation_start": dataset.get("window_start", 0)
        + int(len(visible_candles(dataset)) * 0.7),
        "price_basis": "adjusted",
        **execution_options(dataset),
    }
    require_quality(dataset, settings)
    runs = {
        label: engine.backtest(candles, strategy=key, **settings)
        for label, key in STRATEGIES.items()
    }
    risk = engine.simulate(
        candles, strategy="price_volume", basis="strategy", paths=100, horizon=60, **settings
    )
    stock = engine.simulate(visible_candles(dataset), paths=100, horizon=60, price_basis="adjusted")
    for function in ["RSI", "ATR", "MACD"]:
        indicators.calculate(candles, function)
    if symbol in {"INFY", "TCS", "RELIANCE"}:
        run_validation(dataset, ["Price + volume"], settings)
    assert all(run["evaluation"]["end"] <= history.CUTOFF for run in runs.values())
    assert risk["strategy_calibration"]["metrics"] == runs["Price + volume"]["metrics"]
    assert sum(bin_["count"] for bin_ in stock["terminal_histogram"]) == 100
    return {
        "symbol": symbol,
        "start": candles[0]["timestamp"],
        "end": candles[-1]["timestamp"],
        "bars": len(candles),
        "window_start": visible_candles(dataset)[0]["timestamp"],
        "warmup_bars": dataset.get("window_start", 0),
        "engine_sha256": analysis["_provenance"]["engine_sha256"],
        "strategies": len(runs),
        "strategy_risk_observations": risk["calibration"]["observations"],
    }


def main():
    passed, failed = [], []
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending = {pool.submit(check, symbol): symbol for symbol in history.ready_stocks()}
        for future in as_completed(pending):
            symbol = pending[future]
            try:
                passed.append(future.result())
                print(f"PASS {symbol}", flush=True)
            except Exception as exc:
                failed.append({"symbol": symbol, "error": str(exc)})
                print(f"FAIL {symbol}: {exc}", flush=True)
    report = {
        "cutoff": history.CUTOFF,
        "passed": passed,
        "failed": failed,
        "interpretation": "Software acceptance on real history, not profitability validation.",
    }
    history.write_json(ROOT / "runs/historical_acceptance.json", report)
    print(json.dumps({"passed": len(passed), "failed": len(failed)}), flush=True)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
