"""Tests focus on data gates, quota, provenance and persistent replay safety."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from app import chat, providers, services, storage


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_RESEARCH_DB", str(tmp_path / "test.sqlite"))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


def make_candles(count=30):
    end = datetime.now(timezone.utc) - timedelta(hours=2)
    return [
        {
            "timestamp": (end - timedelta(days=count - i - 1)).isoformat(),
            "open": 100.0 + i,
            "high": 102.0 + i,
            "low": 99.0 + i,
            "close": 101.0 + i,
            "volume": 1000 + i * 10,
        }
        for i in range(count)
    ]


def test_evidence_rejects_bad_and_stale_inputs():
    candles = make_candles()
    fresh = services.build_evidence(candles, {}, symbol="TEST")
    assert fresh["data_quality"]["valid"] is True
    assert fresh["action"] == "RESEARCH_WATCH"
    candles[-1]["close"] = 0
    invalid = services.build_evidence(candles, {}, symbol="TEST")
    assert invalid["data_quality"]["valid"] is False
    assert invalid["action"] == "INSUFFICIENT_EVIDENCE"
    old = make_candles()
    for bar in old:
        bar["timestamp"] = (
            datetime.fromisoformat(bar["timestamp"]) - timedelta(days=10)
        ).isoformat()
    stale = services.build_evidence(old, {}, symbol="TEST")
    assert stale["data_quality"]["historical"] is True
    assert stale["action"] == "INSUFFICIENT_EVIDENCE"


def test_excludes_future_news_and_undated_fundamentals():
    candles = make_candles()
    news = [
        {
            "title": "Outcome published tomorrow",
            "published_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        }
    ]
    card = services.build_evidence(candles, {}, news=news, fundamentals={"revenue_growth": 12})
    assert not any(f["id"].startswith(("N", "F")) for f in card["facts"])
    assert any("look-ahead" in item for item in card["missing"])
    assert any("publication date" in item for item in card["missing"])


def test_synthetic_evidence_never_looks_like_actual_signal():
    card = services.build_evidence(make_candles(), {"source": "SYNTHETIC fixture"})
    assert card["data_quality"]["synthetic"]
    assert card["action"] == "INSUFFICIENT_EVIDENCE"


def test_rule_report_is_cached_and_never_calls_ai(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Rules mode must not access a provider")

    monkeypatch.setattr(providers, "generate", forbidden)
    evidence = services.build_evidence(make_candles(), {})
    report = services.generate_report(evidence)
    assert "no AI" in report["mode"]
    assert set(report["roles"]) == {"news", "market", "reviewer"}
    assert services.generate_report(evidence)["cached"] is True
    assert len(storage.list_reports()) == 1
    answer = chat.answer_question(
        "Why is this alert shown and what is drawdown?", {"evidence": evidence}
    )
    assert "prior portfolio equity peak" in answer["answer"]
    assert evidence["action"] in answer["answer"]
    assert storage.usage_summary()["used"] == 0


def test_event_deduplication_persists():
    assert storage.record_event("same-market-event", "TEST", "alert", {"price": 100})
    assert not storage.record_event("same-market-event", "TEST", "alert", {"price": 100})
    assert len(storage.list_events()) == 1


def test_budget_counts_failures_and_reserves_chat():
    now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    for i in range(40):
        ident = storage.reserve_usage(
            "openrouter", "report", "x:free", now=now + timedelta(minutes=i)
        )
        storage.finish_usage(ident, "failed")
    with pytest.raises(storage.BudgetExceeded, match="daily"):
        storage.reserve_usage("openrouter", "report", "x:free", now=now + timedelta(minutes=41))
    for i in range(10):
        storage.reserve_usage("openrouter", "chat", "x:free", now=now + timedelta(minutes=42 + i))
    with pytest.raises(storage.BudgetExceeded):
        storage.reserve_usage("openrouter", "chat", "x:free", now=now + timedelta(minutes=59))
    # The next UTC day has a separate allowance.
    storage.reserve_usage("openrouter", "chat", "x:free", now=now + timedelta(days=1))


def test_budget_is_atomic_across_threads():
    def reserve(_):
        try:
            storage.reserve_usage("openrouter", "chat", "x:free", daily_limit=5)
            return True
        except storage.BudgetExceeded:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        accepted = list(pool.map(reserve, range(12)))
    assert sum(accepted) == 5


def test_minute_limit_cannot_exceed_safety_cap():
    for _ in range(15):
        storage.reserve_usage("openrouter", "chat", "x:free", minute_limit=100)
    with pytest.raises(storage.BudgetExceeded, match="minute"):
        storage.reserve_usage("openrouter", "chat", "x:free", minute_limit=100)


def test_missing_key_and_paid_model_never_issue_completion(monkeypatch):
    with pytest.raises(providers.ProviderError, match="not configured"):
        providers.generate([{"role": "user", "content": "hi"}], "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret")
    with pytest.raises(providers.ProviderError, match="Only"):
        providers.generate([{"role": "user", "content": "hi"}], "openrouter", "paid/model")
    assert storage.usage_summary()["used"] == 0


def test_free_suffix_still_verifies_catalogue_price(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret")
    monkeypatch.setattr(
        providers,
        "_http_json",
        lambda *a, **kw: {
            "data": [{"id": "model:free", "pricing": {"prompt": "0.01", "completion": "0"}}]
        },
    )
    with pytest.raises(providers.ProviderError, match="nonzero"):
        providers.generate([{"role": "user", "content": "hi"}], "openrouter", "model:free")
    assert storage.usage_summary()["used"] == 0


def test_free_request_has_no_paid_fallback_and_failed_attempt_counts(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret")

    def response(url, **kwargs):
        assert kwargs["payload"]["model"] == "openrouter/free"
        assert kwargs["payload"]["provider"]["allow_fallbacks"] is False
        assert "tools" not in kwargs["payload"]
        raise providers.ProviderError("Provider unavailable")

    monkeypatch.setattr(providers, "_http_json", response)
    with pytest.raises(providers.ProviderError):
        providers.generate([{"role": "user", "content": "hi"}], "openrouter", purpose="chat")
    assert storage.usage_summary()["used"] == 1


def test_grounded_json_rejects_invented_citation_and_link():
    facts = [{"id": "P1", "text": "close 100"}]
    valid = providers.validate_grounded_answer(
        json.dumps({"text": "Supplied close is 100 [P1].", "citations": ["P1"]}), facts
    )
    assert valid["citations"] == ["P1"]
    with pytest.raises(providers.ProviderError, match="unknown"):
        providers.validate_grounded_answer(
            json.dumps({"text": "Claim [P99].", "citations": ["P99"]}), facts
        )
    with pytest.raises(providers.ProviderError, match="URL"):
        providers.validate_grounded_answer(
            json.dumps({"text": "See https://example.com/fake", "citations": []}), facts
        )


def test_live_monitor_missing_token_does_not_fall_back(monkeypatch):
    from app.monitor import run_once

    monkeypatch.delenv("UPSTOX_ACCESS_TOKEN", raising=False)
    storage.set_setting("upstox_instruments", {"TEST": "NSE_EQ|TEST"})
    result = run_once("live", ["TEST"])
    assert result["checked"] == 0
    assert result["errors"]
    assert result["is_synthetic"] is False
    assert storage.get_heartbeat()["payload"]["status"] == "error"
