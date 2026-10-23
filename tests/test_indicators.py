"""Exercise the installed catalogue, known values and information timing."""

import json

import pytest

from app.demo import SYMBOLS, load_demo
from app.indicators import calculate, catalogue


@pytest.fixture(scope="module")
def candles():
    return load_demo(SYMBOLS[0])["candles"]


def test_catalogue_includes_major_families():
    functions = catalogue()
    assert len(functions) >= 150
    assert {"RSI", "MACD", "BBANDS", "OBV", "ADX", "STOCH", "CDLENGULFING"} <= functions.keys()


@pytest.mark.parametrize("name", sorted(catalogue()))
def test_complete_catalogue_defaults_are_aligned_and_serializable(candles, name):
    result = calculate(candles, name)
    assert all(len(values) == len(candles) for values in result["columns"].values())
    assert result["timestamps"] == [row["timestamp"] for row in candles]
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize(
    "name",
    ["SMA", "EMA", "RSI", "MACD", "BBANDS", "ADX", "OBV", "MAVP", "HT_DCPERIOD", "CDLENGULFING"],
)
def test_appending_future_bars_does_not_change_past_outputs(candles, name):
    prefix = calculate(candles[:300], name)
    full = calculate(candles, name)
    for output, values in prefix["columns"].items():
        assert values == full["columns"][output][:300]


def test_known_sma_values_and_missing_warmup():
    rows = [
        {
            "timestamp": f"2026-01-0{day}",
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": 100,
        }
        for day, price in enumerate([1.0, 2.0, 3.0, 4.0], 1)
    ]
    assert calculate(rows, "SMA", {"timeperiod": 3})["columns"]["real"] == [None, None, 2.0, 3.0]
    assert calculate(rows, "RSI")["latest"]["real"] is None


def test_single_series_mapping_is_actually_used(candles):
    result = calculate(candles, "SMA", {"timeperiod": 3}, {"price": "open"})
    assert result["latest"]["real"] == pytest.approx(sum(row["open"] for row in candles[-3:]) / 3)
    assert result["input_columns"] == {"price": "open"}


def test_numeric_domain_errors_remain_missing(candles):
    result = calculate(candles, "ACOS")
    assert result["domain_gaps"] > 0
    assert result["latest"]["real"] is None


@pytest.mark.parametrize(
    "name,settings", [("NOT_REAL", {}), ("SMA", {"period_typo": 3}), ("SMA", {"timeperiod": -1})]
)
def test_invalid_settings_are_rejected(candles, name, settings):
    with pytest.raises(ValueError):
        calculate(candles, name, settings)
