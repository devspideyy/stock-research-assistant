"""Known directional cases, causal fills, holdout accounting and faithful playback."""

from datetime import date, timedelta

import pytest

from app.engine_bridge import EngineClient
from app.services import build_evidence
from app.ui_helpers import equity_charts, simulation_chart


def candles(prices, volume=100):
    return [
        {
            "timestamp": (date(2026, 1, 1) + timedelta(days=i)).isoformat(),
            "open": price,
            "high": price + 0.5,
            "low": price - 0.5,
            "close": price,
            "volume": volume,
        }
        for i, price in enumerate(prices)
    ]


@pytest.mark.parametrize("direction", [1, -1])
def test_rating_has_known_direction_and_preserves_demo_gate(direction):
    data = candles([150 + direction * i for i in range(45)])
    data[-1]["volume"] = 200
    card = build_evidence(
        data,
        EngineClient().analyze(data),
        is_synthetic=True,
        decision_time=data[-1]["timestamp"] + "T15:30:00+05:30",
    )
    case = card["assessment"]
    assert case["bullish" if direction == 1 else "bearish"] == 100
    assert case["bearish" if direction == 1 else "bullish"] == 0
    assert case["scope"] == "Illustrative demo"
    assert card["action"] == "INSUFFICIENT_EVIDENCE"
    assert case["coverage"] == 100
    assert any(fact["id"] == "R1" for fact in card["facts"])


def test_missing_volume_is_unscored_and_invalid_prices_have_no_rating():
    data = candles([100 + i for i in range(30)], volume=0)
    native = EngineClient().analyze(data)
    options = {"is_synthetic": False, "decision_time": data[-1]["timestamp"] + "T15:30:00+05:30"}
    card = build_evidence(data, native, **options)
    assert card["assessment"]["coverage"] == 85
    volume = next(f for f in card["assessment"]["factors"] if f["reference"] == "V1")
    assert not volume["available"]
    assert volume["bullish"] == volume["bearish"] == 0
    data[-1]["close"] = -1
    assert build_evidence(data, native, **options)["assessment"]["bullish"] is None


def test_recommendation_requires_daily_interval_and_keeps_native_provenance():
    data = candles([100 + i for i in range(30)])
    native = EngineClient().analyze(data)
    cutoff = data[-1]["timestamp"] + "T15:30:00+05:30"
    card = build_evidence(
        data, native, is_synthetic=False, decision_time=cutoff, bar_interval="unconfirmed"
    )
    assert card["assessment"]["bullish"] is None
    assert card["action"] == "INSUFFICIENT_EVIDENCE"
    assert card["numerical_provenance"]["engine_sha256"] == native["_provenance"]["engine_sha256"]
    for i, row in enumerate(data):
        row["timestamp"] = (date(2026, 1, 1) + timedelta(weeks=i)).isoformat()
    weekly = build_evidence(
        data,
        EngineClient().analyze(data),
        is_synthetic=False,
        decision_time=data[-1]["timestamp"] + "T15:30:00+05:30",
    )
    assert weekly["assessment"]["bullish"] is None
    assert not weekly["data_quality"]["valid"]


def test_holdout_starts_in_cash_and_next_open_uses_evaluation_period():
    data = candles([100 + i for i in range(40)])
    result = EngineClient().backtest(
        data,
        strategy="buy_hold",
        evaluation_start=28,
        initial_capital=1000,
        commission_bps=0,
        slippage_bps=0,
    )
    assert result["evaluation"]["bars"] == 12
    assert result["equity"][0]["timestamp"] == data[28]["timestamp"]
    assert result["equity"][0]["equity"] == result["equity"][0]["cash"] == 1000
    assert result["equity"][0]["position"] == 0
    assert result["trades"][0]["timestamp"] == data[29]["timestamp"]
    assert result["trades"][0]["price"] == 129
    assert result["metrics"]["closed_trades"] == 0
    assert result["metrics"]["win_rate"] is None


def test_pullback_signal_fills_next_open_and_is_causal():
    data = candles([100 + 2 * i for i in range(20)] + [138.25, 140, 142, 143, 144])
    settings = {"strategy": "trend_pullback", "commission_bps": 0, "slippage_bps": 0}
    prefix = EngineClient().backtest(data[:23], **settings)
    assert prefix["trades"][0]["timestamp"] == data[21]["timestamp"]
    assert prefix["trades"][0]["price"] == 140
    data[-1].update(open=30, high=31, low=29, close=30)
    extended = EngineClient().backtest(data, **settings)
    previous = [fill for fill in extended["trades"] if fill["timestamp"] <= data[22]["timestamp"]]
    assert previous == prefix["trades"]


def test_range_strategy_exits_at_next_open_after_midpoint_recovery():
    data = candles([100] * 19 + [99.1, 99.3, 100.2, 100.5])
    for row in data:
        row.update(high=101, low=99)
    result = EngineClient().backtest(
        data, strategy="range_reversion", commission_bps=0, slippage_bps=0
    )
    assert [fill["side"] for fill in result["trades"]] == ["BUY", "SELL"]
    assert result["trades"][0]["timestamp"] == data[21]["timestamp"]
    assert result["trades"][1]["timestamp"] == data[22]["timestamp"]
    assert result["trades"][1]["net_pnl"] > 0
    assert result["metrics"]["closed_trades"] == 1
    assert result["metrics"]["win_rate"] == 1
    assert result["metrics"]["profit_factor"] is None  # No losing trades is not a finite ratio.


def test_realised_pnl_counts_both_entry_and_exit_fees():
    data = candles([100, 100, 110, 124, 100, 92])
    data[2].update(open=100, low=99, high=111, volume=200)
    data[3].update(open=120, low=119, high=125)
    data[4].update(open=124, low=99, high=125)
    data[5].update(open=90, low=89, high=95)
    result = EngineClient().backtest(
        data, lookback=2, initial_capital=1000, commission_bps=100, slippage_bps=0
    )
    assert result["metrics"]["fees_paid"] == pytest.approx(16.8)
    assert result["metrics"]["realised_pnl"] == pytest.approx(-256.8)
    assert result["metrics"]["closed_trades"] == 1
    assert result["metrics"]["win_rate"] == 0
    assert result["trades"][-1]["net_pnl"] == pytest.approx(-256.8)


@pytest.mark.parametrize("flat", [False, True])
def test_mc_histogram_covers_all_paths_and_playback_is_faithful(flat):
    data = candles([100 if flat else 100 + (i % 5) for i in range(30)])
    result = EngineClient().simulate(data, paths=100, horizon=40, seed=17)
    assert sum(row["count"] for row in result["terminal_histogram"]) == 100
    figure = simulation_chart(result, replay=True)
    assert len(figure.frames) <= 36
    assert all(len(trace.y) == 1 for trace in figure.frames[0].data)
    assert figure.frames[-1].data[-1].y[-1] == result["summary"]["p50"]
    assert figure.layout.yaxis.autorange is False
    assert figure.layout.xaxis.range == (0, 40)


def test_long_backtest_replay_is_bounded_and_preserves_terminal_values():
    data = candles([100 + i * 0.1 for i in range(540)])
    result = EngineClient().backtest(data, strategy="buy_hold")
    figure, _ = equity_charts({"Benchmark": result}, replay=True)
    assert len(figure.frames) <= 36
    assert len(figure.data[0].x) <= 300
    assert figure.frames[-1].data[0].y[-1] == result["equity"][-1]["equity"]
    assert all(frame.data[0].x[-1] in figure.layout.xaxis.categoryarray for frame in figure.frames)
    assert len(figure.to_json()) < 4_000_000
