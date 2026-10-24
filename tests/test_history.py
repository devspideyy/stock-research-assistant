"""Historical cutoff, adjustment, provenance and malformed-source boundaries."""

import copy
import json

import pandas as pd
import pytest

from app import history


def source_frame():
    index = pd.bdate_range("2020-07-01", "2021-01-15")
    return pd.DataFrame(
        {
            "Open": 100.0,
            "High": 102.0,
            "Low": 98.0,
            "Close": 100.0,
            "Adj Close": 80.0,
            "Volume": 1000.0,
        },
        index=index,
    )


def test_cutoff_and_future_adjustment_factors_do_not_leak_into_research():
    frame = source_frame()
    reference = [{"Date": "2020-12-31", "Close": 200.0}]
    bundle = history.prepare_frame(frame, "TEST", reference)
    changed = frame.copy()
    changed.loc[changed.index > "2020-12-31", ["Open", "High", "Low", "Close"]] *= 200
    changed["Adj Close"] *= 0.25  # a later retrospective constant rebasing cancels at cutoff
    assert history.prepare_frame(changed, "TEST", reference)["candles"] == bundle["candles"]
    assert bundle["candles"][-1]["timestamp"] == "2020-12-31"
    assert bundle["candles"][-1]["close"] == 200
    assert bundle["candles"][0]["open"] == 200
    assert bundle["price_basis"] == "adjusted" and bundle["corporate_actions"] == []
    assert bundle["is_synthetic"] is False


def test_invalid_observations_are_disclosed_and_excessive_loss_is_rejected():
    frame = source_frame()
    frame.iloc[4, frame.columns.get_loc("High")] = 90  # impossible enclosure, never 'repaired'
    bundle = history.prepare_frame(frame, "TEST")
    assert bundle["history_quality"]["omitted_invalid_dates"] == [frame.index[4].date().isoformat()]
    assert frame.index[4].date().isoformat() not in [c["timestamp"] for c in bundle["candles"]]
    frame.iloc[:10, frame.columns.get_loc("Close")] = float("nan")
    with pytest.raises(ValueError, match="2% invalid"):
        history.prepare_frame(frame, "TEST")


def test_duplicate_post_cutoff_and_missing_columns_fail_closed():
    frame = source_frame()
    with pytest.raises(ValueError, match="duplicate dates"):
        history.prepare_frame(pd.concat([frame.iloc[:1], frame]), "TEST")
    with pytest.raises(ValueError, match="lacks OHLCV"):
        history.prepare_frame(frame.drop(columns="Adj Close"), "TEST")
    with pytest.raises(ValueError, match="No eligible pre-2021"):
        history.prepare_frame(frame.loc[frame.index > "2020-12-31"], "TEST")


def test_reference_start_guard_excludes_earlier_provider_instrument_history():
    frame = source_frame()
    dates = frame.index[10:]
    reference = [
        {"Date": day.date().isoformat(), "Close": 100.0} for day in dates if day.year <= 2020
    ]
    bundle = history.prepare_frame(frame, "TEST", reference)
    assert bundle["candles"][0]["timestamp"] == dates[0].date().isoformat()
    assert bundle["history_quality"]["reference_start_guard"] == dates[0].date().isoformat()


def test_failed_download_preserves_previous_history_and_cached_reads_do_not_fetch(monkeypatch):
    bundle = history.prepare_frame(source_frame(), "TEST")
    history.write_json(history.library_path() / "TEST.json", bundle)
    history.write_json(
        history.library_path() / "catalogue.json",
        {"stocks": [{"symbol": "TEST", "file": "TEST_NS.parquet"}], "revision": "abc"},
    )
    history.write_json(history.library_path() / "download_report.json", {"failures": []})

    def blocked(*args, **kwargs):
        raise OSError("network unavailable")

    monkeypatch.setattr(history, "download", blocked)
    with pytest.raises(OSError, match="network unavailable"):
        history.fetch_stock("TEST")
    assert history.load_stock("TEST") == bundle
    assert history.ready_stocks() == ["TEST"]
    changed = copy.deepcopy(bundle)
    changed["candles"][-1]["timestamp"] = "2021-01-01"
    history.write_json(history.library_path() / "TEST.json", changed)
    with pytest.raises(ValueError, match="cutoff"):
        history.load_stock("TEST")
    assert json.loads((history.library_path() / "catalogue.json").read_text())["revision"] == "abc"
