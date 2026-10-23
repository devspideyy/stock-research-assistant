"""Offline regressions for the correctness audit; no broker or model calls."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
import subprocess
import sys

import pytest

from app import providers, services, storage
from app.demo import SYMBOLS, load_demo
from app.engine_bridge import CandleValidationError, EngineClient
from app.monitor import run_once


def test_provenance_does_not_depend_on_auxiliary_text():
    candles = load_demo(SYMBOLS[0])["candles"]
    card = services.build_evidence(candles, {}, is_synthetic=True)
    assert card["data_quality"]["synthetic"] is True
    assert card["action"] == "INSUFFICIENT_EVIDENCE"
    unknown = services.build_evidence(candles, {})
    assert unknown["data_quality"]["synthetic"] is None
    assert not unknown["data_quality"]["valid"]
    mixed = services.build_evidence(candles, {}, is_synthetic=False, news=[{"is_synthetic": True}])
    assert mixed["data_quality"]["synthetic"] is True
    assert mixed["action"] == "INSUFFICIENT_EVIDENCE"


def test_daily_news_requires_explicit_cutoff_and_excludes_after_close():
    candles = load_demo(SYMBOLS[0])["candles"]
    date = candles[-1]["timestamp"]
    news = [
        {"title": "Morning announcement", "published_at": date + "T10:00:00+05:30"},
        {"title": "After close", "published_at": date + "T16:00:00+05:30"},
    ]
    card = services.build_evidence(
        candles,
        {},
        news=news,
        is_synthetic=True,
        decision_time=date + "T15:30:00+05:30",
    )
    assert [fact["text"] for fact in card["facts"] if fact["id"].startswith("N")] == [
        "Morning announcement"
    ]
    unknown = services.build_evidence(candles, {}, news=news, is_synthetic=False)
    assert not any(fact["id"].startswith("N") for fact in unknown["facts"])
    assert not unknown["data_quality"]["valid"]


@pytest.mark.parametrize(
    "data",
    [
        {"x": {"last_price": 100}},
        {"x": {"instrument_token": "BSE_EQ|OTHER", "last_price": 100}},
        {"x": {"instrument_token": "NSE_EQ|TEST"}, "y": {}},
        {"x": None},
    ],
)
def test_quote_rejects_unidentified_or_ambiguous_results(monkeypatch, data):
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "fixture-only")
    monkeypatch.setattr(
        providers, "_http_json", lambda *a, **kw: {"status": "success", "data": data}
    )
    with pytest.raises(providers.ProviderError):
        providers.fetch_upstox_quote("NSE_EQ|TEST")


def test_remapping_label_starts_new_instrument_baseline(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_RESEARCH_DB", str(tmp_path / "monitor.sqlite"))
    monkeypatch.delenv("UPSTOX_INSTRUMENTS", raising=False)
    price = [100]
    monkeypatch.setattr(
        providers,
        "fetch_upstox_quote",
        lambda key: {
            "received_at": storage.utc_now(),
            "source": "fixture",
            "limitations": "fixture",
            "quote": {
                "last_price": price[0],
                "last_trade_time": datetime.now(timezone.utc).timestamp() * 1000,
            },
        },
    )
    storage.set_setting("upstox_instruments", {"TEST": "NSE_EQ|ONE"})
    assert run_once("live", ["TEST"])["events_added"] == 1
    price[0] = 200
    storage.set_setting("upstox_instruments", {"TEST": "BSE_EQ|TWO"})
    result = run_once("live", ["TEST"])
    assert not result["errors"]
    assert result["observations"][0]["change_since_alert"] is None
    assert storage.list_events()[0]["kind"] == "live_snapshot_baseline"
    assert storage.list_events()[0]["payload"]["instrument_key"] == "BSE_EQ|TWO"


@pytest.mark.parametrize("operation", ["backtest", "simulate"])
def test_daily_experiments_reject_weekly_or_unconfirmed_inputs(operation):
    candles = load_demo(SYMBOLS[0])["candles"][:30]
    weekly = [
        dict(row, timestamp=(datetime(2025, 1, 3) + timedelta(weeks=i)).date().isoformat())
        for i, row in enumerate(candles)
    ]
    with pytest.raises(CandleValidationError, match="weekly"):
        getattr(EngineClient(), operation)(weekly)
    with pytest.raises(CandleValidationError, match="Confirm"):
        getattr(EngineClient(), operation)(candles, bar_interval="unconfirmed")


def test_quota_is_atomic_on_multiprocess_cold_start(tmp_path):
    environment = os.environ | {"STOCK_RESEARCH_DB": str(tmp_path / "cold.sqlite")}
    code = """
from app import storage
try:
    storage.reserve_usage('openrouter', 'chat', 'fixture:free', daily_limit=3)
    print('accepted')
except storage.BudgetExceeded:
    print('limited')
"""

    def reserve(_):
        return subprocess.run(
            [sys.executable, "-c", code],
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        ).stdout.strip()

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(reserve, range(6)))
    assert results.count("accepted") == 3
    assert results.count("limited") == 3
