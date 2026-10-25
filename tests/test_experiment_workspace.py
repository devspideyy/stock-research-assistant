"""Saved experiments preserve data/result binding and reopen without recalculation."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app import experiments, storage
from app.demo import load_demo
from app.engine_bridge import EngineClient

ROOT = Path(__file__).resolve().parents[1]


def click(app, label):
    next(item for item in app.button if item.label == label).click().run()
    assert not app.exception


def test_saved_snapshot_rejects_changed_results_and_survives_a_new_connection():
    dataset = {**load_demo(count=80), "bar_interval": "1d"}
    settings = {"initial_capital": 100000}
    result = EngineClient().backtest(dataset["candles"], strategy="buy_hold", **settings)
    identifier = experiments.save_experiment(dataset, {"Buy and hold": result}, settings)
    reopened = experiments.load_experiment(identifier)
    assert reopened["dataset"] == dataset
    assert reopened["results"]["Buy and hold"] == result
    assert experiments.list_experiments()[0]["id"] == identifier
    with storage.connection() as db:
        payload = json.loads(
            db.execute(
                "SELECT payload FROM experiment_snapshots WHERE id=?", (identifier,)
            ).fetchone()[0]
        )
        payload["results"]["Buy and hold"]["metrics"]["total_return"] = 999
        db.execute(
            "UPDATE experiment_snapshots SET payload=? WHERE id=?",
            (json.dumps(payload), identifier),
        )
    with pytest.raises(ValueError, match="checksum"):
        experiments.load_experiment(identifier)


def test_native_cache_invalidates_options_prices_and_engine_and_returns_copies(
    tmp_path, monkeypatch
):
    from app import computation

    executable = tmp_path / "engine"
    executable.write_bytes(b"first engine")
    calls = []

    class Engine:
        def __init__(self, path):
            pass

        def backtest(self, candles, **options):
            calls.append((candles, options))
            return {"close": candles[0]["close"], "capital": options["initial_capital"]}

    monkeypatch.setattr(computation, "find_engine", lambda: executable)
    monkeypatch.setattr(computation, "EngineClient", Engine)
    candles = load_demo(count=40)["candles"]
    result = computation.calculate("backtest", candles, initial_capital=1000)
    result["close"] = -1
    assert computation.calculate("backtest", candles, initial_capital=1000)["close"] > 0
    assert len(calls) == 1
    computation.calculate("backtest", candles, initial_capital=2000)
    candles[0]["close"] += 0.01
    computation.calculate("backtest", candles, initial_capital=2000)
    executable.write_bytes(b"different engine version")
    computation.calculate("backtest", candles, initial_capital=2000)
    assert len(calls) == 4


def test_risk_is_visible_before_backtest_and_complete_experiment_reopens(monkeypatch):
    from app import computation, ui_helpers

    def no_animation(*args, **kwargs):
        raise AssertionError("Animation must not be prepared until requested")

    monkeypatch.setattr(ui_helpers, "add_replay", no_animation)
    app = AppTest.from_file(str(ROOT / "app/dashboard.py"), default_timeout=40).run()
    click(app, "Risk / Monte Carlo")
    assert any("First run a backtest" in item.value for item in app.info)
    click(app, "Set up a backtest")
    next(item for item in app.number_input if item.label == "Starting capital").set_value(200000.0)
    next(
        item for item in app.number_input if item.label == "Commission / charges per side (bps)"
    ).set_value(27.0)
    click(app, "Run strategy comparison")
    submitted = app.session_state["backtests"]
    assert set(submitted) == {"Price + volume", "Buy and hold"}
    assert not any(item.label == "Animated backtest replay" for item in app.toggle)
    click(app, "Explore Monte Carlo risk")
    next(
        item for item in app.number_input if item.label == "Risk horizon (daily observations)"
    ).set_value(42)
    next(item for item in app.number_input if item.label == "Risk seed").set_value(7)
    click(app, "Simulate strategy risk")
    risk = app.session_state["strategy_simulation"]
    click(app, "Save complete experiment")
    identifier = experiments.list_experiments()[0]["id"]
    snapshot = experiments.load_experiment(identifier)
    assert snapshot["strategy_simulation"] == risk

    def no_recalculation(*args, **kwargs):
        raise AssertionError("Reopening should use saved results")

    monkeypatch.setattr(computation, "calculate", no_recalculation)
    reopened = AppTest.from_file(str(ROOT / "app/dashboard.py"), default_timeout=40).run()
    click(reopened, "Saved research")
    click(reopened, "Reopen complete experiment")
    assert reopened.session_state["backtests"] == submitted
    assert reopened.session_state["strategy_simulation"] == risk
    assert reopened.session_state["active_snapshot"]["dataset"] == snapshot["dataset"]
    assert (
        next(item for item in reopened.number_input if item.label == "Starting capital").value
        == 200000.0
    )
    assert (
        next(
            item
            for item in reopened.number_input
            if item.label == "Commission / charges per side (bps)"
        ).value
        == 27.0
    )
    click(reopened, "Explore Monte Carlo risk")
    assert any(item.label == "Median ending investment" for item in reopened.metric)
    assert (
        next(
            item
            for item in reopened.number_input
            if item.label == "Risk horizon (daily observations)"
        ).value
        == 42
    )
    assert next(item for item in reopened.number_input if item.label == "Risk seed").value == 7
    next(item for item in reopened.radio if item.label == "Data source").set_value(
        "Synthetic demo"
    ).run()
    assert not reopened.exception
    assert "backtests" not in reopened.session_state
    assert any("source details changed" in item.value for item in reopened.info)
