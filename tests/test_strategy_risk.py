"""Strategy MC must calibrate from net equity, including entry fees and cash days."""

import math

import pytest

from app.demo import load_demo
from app.engine_bridge import EngineClient, EngineError


def test_strategy_calibration_matches_submitted_backtest_after_costs():
    candles = load_demo(count=120)["candles"]
    engine = EngineClient()
    settings = {
        "strategy": "indicator",
        "evaluation_start": 50,
        "initial_capital": 100000,
        "commission_bps": 25,
        "slippage_bps": 12,
    }
    backtest = engine.backtest(candles, **settings)
    risk = engine.simulate(candles, **settings, basis="strategy", paths=100, horizon=30, seed=9)
    assert risk["strategy_calibration"]["metrics"] == backtest["metrics"]
    assert risk["strategy_calibration"]["evaluation"] == backtest["evaluation"]
    curve = backtest["equity"]
    expected_mean = math.log(curve[-1]["equity"] / curve[0]["equity"]) / (len(curve) - 1)
    assert risk["calibration"]["daily_log_mean"] == pytest.approx(expected_mean)
    assert risk["calibration"]["observations"] == 69
    again = engine.simulate(candles, **settings, basis="strategy", paths=100, horizon=30, seed=9)
    assert risk["sample_paths"] == again["sample_paths"]
    assert 0 <= risk["summary"]["probability_drawdown"] <= 1


def test_flat_cash_risk_is_flat_without_phantom_costs():
    candles = load_demo(count=80)["candles"]
    for candle in candles:
        candle.update(open=100, high=100, low=100, close=100)
    risk = EngineClient().simulate(
        candles,
        basis="strategy",
        strategy="price_volume",
        paths=30,
        horizon=20,
        capital=1000,
        drawdown_threshold=0.2,
    )
    assert risk["strategy_calibration"]["metrics"]["trade_count"] == 0
    assert risk["summary"]["p50"] == pytest.approx(1000)
    assert risk["summary"]["probability_drawdown"] == 0
    assert risk["summary"]["probability_loss"] == 0


@pytest.mark.parametrize(
    "settings,message",
    [
        ({"method": "gbm"}, "block bootstrap"),
        ({"execution_spread_bps": 10}, "twice"),
        ({"evaluation_start": 65}, "20 evaluated daily returns"),
    ],
)
def test_rejects_invalid_strategy_risk_assumptions(settings, message):
    with pytest.raises(EngineError, match=message):
        EngineClient().simulate(load_demo(count=80)["candles"], basis="strategy", **settings)
