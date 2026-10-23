"""Exercise the actual C++ executable through the same boundary used by the UI."""

import math

import pytest

from app.demo import load_demo
from app.engine_bridge import EngineClient, EngineError, find_engine


@pytest.fixture(scope="module")
def native():
    # Build is a setup requirement, not a silently skipped correctness check.
    return EngineClient(executable=find_engine())


def bar(day, opening, close, volume=100):
    return {
        "timestamp": f"2026-01-{day:02}",
        "open": opening,
        "high": max(opening, close) + 1,
        "low": min(opening, close) - 1,
        "close": close,
        "volume": volume,
    }


def test_buy_hold_fills_next_open_and_accounts_for_fees(native):
    data = [bar(1, 10, 10), bar(2, 20, 21), bar(3, 21, 22)]
    result = native.backtest(
        data, strategy="buy_hold", initial_capital=100, commission_bps=100, slippage_bps=0
    )
    assert result["trades"] == [
        {"timestamp": "2026-01-02", "side": "BUY", "quantity": 4.0, "price": 20.0, "fee": 0.8}
    ]
    assert result["equity"][-1]["equity"] == pytest.approx(107.2)
    assert result["equity"][-1]["cash"] == pytest.approx(19.2)
    assert all(row["cash"] >= 0 for row in result["equity"])


def test_final_close_signal_cannot_fill_without_later_bar(native):
    data = [bar(1, 10, 10), bar(2, 10, 10), bar(3, 10, 14, volume=500)]
    result = native.backtest(
        data, strategy="price_volume", lookback=2, initial_capital=100, volume_threshold=1.2
    )
    assert result["trades"] == []
    assert result["metrics"]["total_return"] == 0


def test_future_bars_never_change_previously_computed_features(native):
    candles = load_demo(count=45)["candles"]
    prefix = native.analyze(candles[:40])["series"]
    extended = native.analyze(candles)["series"]
    assert prefix == extended[:40]


def test_depth_zero_denominator_is_missing_not_neutral(native):
    result = native.depth([{"price": 100, "quantity": 0}], [{"price": 101, "quantity": 0}])
    assert result["depth_imbalance"] is None
    assert result["spread"] == 1
    with pytest.raises(EngineError, match="Crossed|locked"):
        native.depth([{"price": 102, "quantity": 10}], [{"price": 101, "quantity": 20}])


@pytest.mark.parametrize("method", ["bootstrap", "gbm"])
def test_zero_volatility_scenario_preserves_wealth(native, method):
    candles = [bar(day, 100, 100) for day in range(1, 21)]
    result = native.simulate(candles, method=method, paths=100, horizon=20, capital=100000)
    for key in ("p05", "p50", "p95"):
        assert math.isclose(result["summary"][key], 100000, abs_tol=1e-7)
    assert result["summary"]["probability_loss"] == 0


def test_seeded_scenarios_and_stress_are_reproducible(native):
    candles = load_demo(count=70)["candles"]
    settings = {"method": "bootstrap", "paths": 200, "horizon": 30, "seed": 912}
    first = native.simulate(candles, **settings)
    assert first == native.simulate(candles, **settings)
    assert first["summary"]["p05"] <= first["summary"]["p50"] <= first["summary"]["p95"]
    stressed = native.simulate(candles, **settings, initial_shock_pct=-0.25)
    assert stressed["summary"]["p50"] == pytest.approx(first["summary"]["p50"] * 0.75)
