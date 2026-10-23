"""Data-boundary checks prevent silent time-series and native-process errors."""

import json

import pytest

from app.demo import SYMBOLS, load_demo
from app.engine_bridge import (
    CandleValidationError,
    EngineClient,
    EngineError,
    load_candles_csv,
    validate_candles,
)


def test_demo_is_repeatable_and_never_real_market_evidence():
    first = load_demo(SYMBOLS[0])
    assert first == load_demo(SYMBOLS[0])
    assert first["is_synthetic"]
    assert all(news["is_synthetic"] for news in first["news"])
    assert len(validate_candles(first["candles"])) == 540


def test_csv_import_does_not_silently_reorder_time():
    text = (
        "Date,Open,High,Low,Close,Volume\n2026-01-02,10,12,9,11,100\n2026-01-01,11,12,10,11,200\n"
    )
    with pytest.raises(CandleValidationError, match="strictly increasing"):
        load_candles_csv(text)


@pytest.mark.parametrize("field,value", [("close", "nan"), ("volume", -1), ("high", 1)])
def test_reject_invalid_financial_rows(field, value):
    rows = load_demo(count=40)["candles"]
    rows[1][field] = value
    with pytest.raises(CandleValidationError):
        validate_candles(rows)


def test_native_errors_are_not_treated_as_results(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.engine_bridge.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1, stdout=json.dumps({"ok": False, "error": "bad horizon"})
        ),
    )
    with pytest.raises(EngineError, match="bad horizon"):
        EngineClient(executable="fake-native").simulate(load_demo(count=40)["candles"])


def test_native_contract_version_is_checked(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.engine_bridge.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=json.dumps({"ok": True, "schema_version": 99, "result": {}})
        ),
    )
    with pytest.raises(EngineError, match="schema"):
        EngineClient(executable="fake-native").analyze(load_demo(count=40)["candles"])
