"""Causal fold boundaries, stress accounting and persisted offline study contracts."""

import pytest

from app import storage, validation
from app.demo import load_accounting_demo, load_demo
from app.engine_bridge import EngineClient


def test_fold_history_never_contains_future_bars_or_actions(monkeypatch):
    dataset = load_accounting_demo()
    requests = []
    original = EngineClient.backtest

    def recorded(self, candles, **options):
        requests.append((candles, options))
        return original(self, candles, **options)

    monkeypatch.setattr(EngineClient, "backtest", recorded)
    study = validation.run_validation(
        dataset, ["Buy and hold"], {"commission_bps": 0, "slippage_bps": 0}, stress=False
    )
    windows = validation.chronological_folds(len(dataset["candles"]))
    assert len(requests) == 3
    assert windows[0][0] == 64
    assert all(left[1] == right[0] for left, right in zip(windows, windows[1:]))
    assert windows[-1][1] == len(dataset["candles"])
    for (candles, options), (start, end), row in zip(requests, windows, study["rows"], strict=True):
        assert candles == dataset["candles"][:end]
        assert options["evaluation_start"] == start
        assert all(a["ex_date"] <= candles[-1]["timestamp"] for a in options["corporate_actions"])
        assert row["evaluation"]["start"] == candles[start]["timestamp"]
        assert row["metrics"]["total_return"] == pytest.approx(0)
        assert row["provenance"]["engine_sha256"]
    assert len(requests[0][1]["corporate_actions"]) == 1
    assert len(requests[-1][1]["corporate_actions"]) == 2


def test_stress_doubles_base_costs_and_preserves_comparable_benchmark():
    dataset = {**load_demo(count=120), "bar_interval": "1d"}
    study = validation.run_validation(
        dataset,
        ["Indicator baseline"],
        {"commission_bps": 10, "slippage_bps": 5},
        folds=2,
    )
    assert len(study["rows"]) == 8  # strategy + always included hold, two folds, two conditions
    rows = study["rows"]
    for stressed in [r for r in rows if r["condition"] != "Base"]:
        base = next(
            r
            for r in rows
            if r["fold"] == stressed["fold"]
            and r["strategy"] == stressed["strategy"]
            and r["condition"] == "Base"
        )
        assert base["provenance"]["options"]["cost_multiplier"] == 1
        assert stressed["provenance"]["options"]["cost_multiplier"] == 2
        assert stressed["provenance"]["options"]["slippage_bps"] == 10
        assert stressed["evaluation"] == base["evaluation"]
        assert stressed["provenance"]["request_sha256"] != base["provenance"]["request_sha256"]
        if stressed["strategy"] == "Buy and hold":
            assert stressed["excess_return"] == 0
            assert stressed["metrics"]["total_return"] < base["metrics"]["total_return"]
    assert len(validation.summary_rows(study)) == 4


def test_validation_rejects_invalid_windows_and_unconfirmed_history():
    with pytest.raises(ValueError, match="at least 60"):
        validation.chronological_folds(50)
    dataset = load_demo(count=80)
    with pytest.raises(ValueError, match="Confirm completed daily"):
        validation.run_validation(dataset, ["Buy and hold"], {})
    dataset["bar_interval"] = "1d"
    with pytest.raises(ValueError, match="supported strategy"):
        validation.run_validation(dataset, ["unknown"], {})


def test_saved_studies_deduplicate_and_bound_retention(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_RESEARCH_DB", str(tmp_path / "studies.sqlite"))
    for i in range(12):
        validation.save_study({"id": str(i)})
    validation.save_study({"id": "11", "note": "updated"})
    studies = storage.get_setting("validation_studies")
    assert len(studies) == 10
    assert [s["id"] for s in studies] == list(map(str, range(11, 1, -1)))
    assert studies[0]["note"] == "updated"
