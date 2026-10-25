"""Regression contracts for reproducible, causal offline research."""

import copy
import hashlib
import io
import json
import math
import zipfile
from datetime import date

import pytest

from app import history, research_protocol as protocol
from app.demo import load_demo
from app.engine_bridge import EngineClient, EngineError
from app.evaluation import evaluate_ratings, sector_reference
from app.sensitivity import risk_sensitivity
from app.light_chart import chart_payload
from app.validation import run_validation


def dataset(count=200):
    return {**load_demo(count=count), "bar_interval": "1d", "price_basis": "adjusted"}


def test_window_retains_only_causal_warmup_and_evaluates_visible_bars():
    source = dataset()
    rows = source["candles"]
    selected = protocol.select_window(source, rows[80]["timestamp"], rows[170]["timestamp"])
    assert selected["window_start"] == 80
    assert selected["candles"] == rows[:171]
    assert protocol.visible_candles(selected) == rows[80:171]
    engine = EngineClient()
    assert engine.analyze(selected["candles"])["summary"] == engine.analyze(rows[:171])["summary"]
    run = engine.backtest(selected["candles"], strategy="buy_hold", evaluation_start=80)
    assert run["evaluation"]["start"] == rows[80]["timestamp"]
    assert run["trades"][0]["timestamp"] == rows[81]["timestamp"]


def test_quality_requires_review_and_records_gap_override():
    source = dataset()
    source["is_synthetic"] = False
    missing = source["candles"].pop(110)["timestamp"]
    source["history_quality"] = {"omitted_invalid_dates": [missing]}
    with pytest.raises(ValueError, match="missing/invalid"):
        protocol.require_quality(source, {})
    report = protocol.require_quality(source, {"allow_data_gaps": True})
    assert report["omitted_invalid"] == [missing] and not report["eligible"]
    selected = protocol.latest_complete_window(source)
    assert protocol.quality_report(selected)["eligible"]
    assert selected["window_start"] == 110
    assert protocol.quality_report(source, 120)["eligible"]
    source["price_basis"] = "raw"
    with pytest.raises(ValueError, match="coverage review"):
        protocol.require_quality(source, {"allow_data_gaps": True})
    assert protocol.require_quality(source, {"raw_reviewed": True, "evaluation_start": 120})[
        "eligible"
    ]


def test_frozen_policy_immutable_and_attempts_permanently_mark_exposure():
    source = dataset()
    options = {"initial_capital": 200000, "lookback": 50, "evaluation_start": 100}
    policy = protocol.freeze_policy(source, options, ["Buy and hold"])
    assert policy["start_index"] == 160 and policy["untouched_attested"] is False
    with pytest.raises(ValueError, match="already"):
        protocol.freeze_policy(source, options, ["Buy and hold"])
    dev, _, phase = protocol.apply_policy(source, options, ["Buy and hold"])
    assert dev["candles"] == source["candles"][:160] and "reserved" in phase
    _, final, phase = protocol.apply_policy(source, options, ["Buy and hold"], final=True)
    assert final["evaluation_start"] == 160 and "first access" in phase
    protocol.record_run("final_test_attempt", source, final, {"failed": True})
    # Exposure survives deletion/retention of journal rows; the durable marker is independent.
    from app import storage

    with storage.connection() as db:
        db.execute("DELETE FROM research_runs")
    assert "repeat" in protocol.apply_policy(source, options, ["Buy and hold"], final=True)[2]
    with pytest.raises(ValueError, match="exact frozen"):
        protocol.apply_policy(source, {**options, "lookback": 51}, ["Buy and hold"], final=True)
    with pytest.raises(ValueError, match="reserved"):
        protocol.apply_policy(source, {**options, "evaluation_start": 165}, ["Buy and hold"])


def test_validation_preserves_custom_parameters_and_avoids_reserved_final():
    source = dataset()
    options = dict(
        initial_capital=200000,
        lookback=50,
        volume_threshold=2.5,
        commission_bps=30,
        slippage_bps=20,
        stop_loss_pct=0.12,
        max_exposure=0.5,
    )
    protocol.freeze_policy(source, options, ["Price + volume", "Buy and hold"])
    study = run_validation(source, ["Price + volume"], options, stress=False)
    for row in study["rows"]:
        inherited = row["provenance"]["options"]
        assert all(inherited[key] == value for key, value in options.items())
        assert row["evaluation"]["end"] < source["candles"][160]["timestamp"]


def test_fractional_units_invariant_to_adjusted_price_rebasing():
    engine = EngineClient()
    candles = dataset(80)["candles"]
    rebased = [
        {**row, **{key: row[key] * 100 for key in ["open", "high", "low", "close"]}}
        for row in candles
    ]
    options = dict(
        strategy="buy_hold",
        initial_capital=1000,
        commission_bps=17,
        slippage_bps=12,
        position_mode="fractional_research",
    )
    first = engine.backtest(candles, **options)
    second = engine.backtest(rebased, **options)
    assert first["metrics"]["total_return"] == pytest.approx(second["metrics"]["total_return"])
    assert first["trades"][0]["quantity"] == pytest.approx(second["trades"][0]["quantity"] * 100)
    assert all(r["cash"] >= 0 for r in second["equity"])


def test_volume_cap_uses_previous_volume_and_rejects_unfillable_exit():
    engine = EngineClient()
    rows = copy.deepcopy(dataset(60)["candles"])
    for row in rows:
        row.update(open=100, close=100, low=99, high=101, volume=100)
    options = dict(
        strategy="buy_hold",
        initial_capital=100000,
        price_basis="raw",
        commission_bps=0,
        slippage_bps=0,
        max_volume_participation=0.1,
    )
    before = engine.backtest(rows, **options)
    rows[1]["volume"] = 1e9
    after = engine.backtest(rows, **options)
    assert before["trades"][0] == after["trades"][0]
    assert after["trades"][0]["quantity"] == 10
    with pytest.raises(EngineError, match="raw price"):
        engine.backtest(rows, **{**options, "price_basis": "adjusted"})
    # SMA20 signal on bar 20 fills on bar 21; low volume then blocks the next exit.
    rows[19].update(open=100, close=102, low=99, high=103)
    rows[20].update(open=100, close=103, low=99, high=104)
    rows[21].update(open=100, close=90, low=89, high=101, volume=1)
    with pytest.raises(EngineError, match="Exit exceeds"):
        engine.backtest(rows, **{**options, "strategy": "indicator", "lookback": 2})


def test_calendar_growth_and_gap_metrics():
    source = dataset(80)
    run = EngineClient().backtest(source["candles"], strategy="buy_hold", session_gaps_present=True)
    metrics = run["metrics"]
    days = (
        date.fromisoformat(source["candles"][-1]["timestamp"])
        - date.fromisoformat(source["candles"][0]["timestamp"])
    ).days
    assert metrics["calendar_cagr"] == pytest.approx(
        (1 + metrics["total_return"]) ** (365.2425 / days) - 1
    )
    assert metrics["sharpe"] is None and metrics["annualized_volatility"] is None
    assert metrics["cagr"] is None
    with pytest.raises(EngineError, match="complete observed-session"):
        EngineClient().simulate(source["candles"], session_gaps_present=True)


def test_mc_tail_keeps_original_positions_and_costs():
    source = dataset()
    engine = EngineClient()
    options = dict(
        strategy="buy_hold",
        initial_capital=100000,
        commission_bps=25,
        slippage_bps=10,
        position_mode="fractional_research",
        evaluation_start=40,
    )
    backtest = engine.backtest(source["candles"], **options)
    risk = engine.simulate(
        source["candles"],
        **options,
        basis="strategy",
        paths=100,
        horizon=10,
        calibration_observations=63,
    )
    curve = backtest["equity"]
    expected = math.log(curve[-1]["equity"] / curve[-64]["equity"]) / 63
    assert risk["calibration"]["daily_log_mean"] == pytest.approx(expected)
    assert risk["calibration"]["observations"] == 63
    assert risk["strategy_calibration"]["metrics"] == backtest["metrics"]
    report = risk_sensitivity(
        source,
        {k: v for k, v in options.items() if k != "strategy"},
        "buy_hold",
        paths=100,
        horizon=10,
    )
    assert len(report["rows"]) == 7
    assert len({r["provenance"]["request_sha256"] for r in report["rows"]}) == 7


def test_rating_labels_exclude_final_and_use_prefix_features(monkeypatch):
    source = dataset()
    requests = []
    original = EngineClient.analyze

    def recorded(self, candles, **options):
        requests.append(candles[-1]["timestamp"])
        return original(self, candles, **options)

    monkeypatch.setattr(EngineClient, "analyze", recorded)
    result = evaluate_ratings(source, 10)
    assert result["rows"] and len(requests) == len(result["rows"])
    for stamp, row in zip(requests, result["rows"], strict=True):
        assert stamp == row["as_of"] < row["label_date"] <= result["development_end"]
    assert result["rating_version"] == "price-evidence-v1"


def test_sector_reference_excludes_self_and_incomplete_peers(monkeypatch):
    source = {**dataset(60), "symbol": "SELF", "sector": "Technology"}
    peer = {**copy.deepcopy(source), "symbol": "PEER", "history_quality": {"source_sha256": "hash"}}
    absent = {**copy.deepcopy(peer), "symbol": "GAP"}
    absent["candles"].pop(-5)
    monkeypatch.setattr(history, "ready_stocks", lambda: ["SELF", "PEER", "GAP"])
    monkeypatch.setattr(history, "load_stock", lambda symbol: {"PEER": peer, "GAP": absent}[symbol])
    run = EngineClient().backtest(source["candles"], strategy="buy_hold")
    result = sector_reference(source, run)
    assert [p["symbol"] for p in result["peers"]] == ["PEER"]
    assert result["skipped"] == ["GAP"] and result["growth"][0] == 1
    assert "gross before costs" in result["method"]


def test_reference_content_hash_survives_zip_repackaging(monkeypatch):
    raw = b"Date,Close\n2020-12-31,100\n"
    monkeypatch.setattr(
        history,
        "source_manifest",
        lambda: {"reference_members_sha256": {"TEST.csv": hashlib.sha256(raw).hexdigest()}},
    )

    def archive(content, compression):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=compression) as output:
            output.writestr("TEST.csv", content)
        return buffer.getvalue()

    history.verify_reference(archive(raw, zipfile.ZIP_STORED))
    history.verify_reference(archive(raw, zipfile.ZIP_DEFLATED))
    with pytest.raises(ValueError, match="manifest"):
        history.verify_reference(archive(raw + b"corruption", zipfile.ZIP_STORED))


def test_catalogue_uses_committed_revision_and_corrupt_cache_fails(monkeypatch):
    calls = []

    def download(url, limit):
        calls.append(url)
        return json.dumps(
            [{"name": "NSE", "sha": "tree"}]
            if "/contents/" in url
            else {"tree": [{"path": "TEST_NS.parquet", "sha": "blob"}]}
        ).encode()

    monkeypatch.setattr(history, "download", download)
    monkeypatch.setattr(
        history,
        "source_manifest",
        lambda: {"revision": "pinned", "stocks": {"TEST": {"candles_sha256": "wrong"}}},
    )
    assert history.refresh_catalogue()["revision"] == "pinned"
    assert "ref=pinned" in calls[0] and all("main" not in url for url in calls)
    stale = history.catalogue()
    stale["revision"] = "main"
    history.write_json(history.library_path() / "catalogue.json", stale)
    with pytest.raises(ValueError, match="Refresh the catalogue"):
        history.fetch_stock("TEST")
    assert len(calls) == 2  # no stale-revision download was attempted
    bundle = {**dataset(60), "symbol": "TEST", "is_synthetic": False}
    for row in bundle["candles"]:
        row["timestamp"] = row["timestamp"].replace("2024", "2020")
    history.write_json(history.library_path() / "TEST.json", bundle)
    with pytest.raises(ValueError, match="checksum"):
        history.load_stock("TEST")


def test_indicator_panels_and_trade_markers_share_visible_window():
    rows = dataset(60)["candles"]
    stamps = [r["timestamp"] for r in rows]
    panel = {"RSI 14": {"timestamps": stamps, "columns": {"RSI": [50] * 60}}}
    trades = [
        {"timestamp": stamps[5], "side": "BUY", "price": 100},
        {"timestamp": stamps[45], "side": "SELL", "price": 110},
    ]
    result = chart_payload(rows[40:], panels=panel, trades=trades)
    assert [r["time"] for r in result["lines"][0]["data"]] == stamps[40:]
    assert [r["side"] for r in result["fills"]] == ["SELL"]
    assert [r["time"] for r in result["fills"]] == [stamps[45]]
    assert result["lines"][0]["pane"] == 2
