"""Run the actual Streamlit interaction flow with the actual C++ binary."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.demo import SYMBOLS

ROOT = Path(__file__).resolve().parents[1]


def button(app, label):
    return next(item for item in app.button if item.label == label)


def navigate(app, page):
    next(item for item in app.selectbox if item.label == "Workspace").set_value(page).run()
    assert not app.exception


def test_production_workspace_uses_real_history_and_links_strategy_risk(tmp_path, monkeypatch):
    import pandas as pd
    from app import history

    monkeypatch.delenv("STOCK_RESEARCH_TEST_FIXTURES")
    monkeypatch.setenv("STOCK_RESEARCH_DB", str(tmp_path / "production.sqlite"))
    import json

    # Include observed special weekend sessions; business weekdays alone omit Muhurat trading.
    sessions = json.loads((ROOT / "data/research_sessions.json").read_text())["dates"]
    index = pd.DatetimeIndex([day for day in sessions if "2020-01-01" <= day <= "2020-12-31"])
    frame = pd.DataFrame(
        {
            "Open": [100 + i * 0.1 for i in range(len(index))],
            "High": [101 + i * 0.1 for i in range(len(index))],
            "Low": [99 + i * 0.1 for i in range(len(index))],
            "Close": [100 + i * 0.1 for i in range(len(index))],
            "Adj Close": [100 + i * 0.1 for i in range(len(index))],
            "Volume": 1000,
        },
        index=index,
    )
    bundle = history.prepare_frame(frame, "TEST")
    history.write_json(history.library_path() / "TEST.json", bundle)
    app = AppTest.from_file(str(ROOT / "app/dashboard.py"), default_timeout=40).run()
    assert not app.exception
    assert app.session_state["workspace_page"] == "Stock workspace"
    assert next(item for item in app.radio if item.label == "Data source").options == [
        "Historical library",
        "Upload historical CSV",
    ]
    next(item for item in app.get("button_group") if item.label == "Research section").set_value(
        None
    ).run()
    assert not app.exception
    assert any(item.label == "Open research chart" for item in app.button)
    from datetime import date

    period = app.date_input[0].value
    app.date_input[0].set_value((date(2020, 9, 1), date(2020, 9, 1))).run()
    assert not app.exception
    assert any("at least two" in item.value for item in app.info)
    app.date_input[0].set_value(period).run()
    next(item for item in app.get("button_group") if item.label == "Research section").set_value(
        "Strategies & backtest"
    ).run()
    assert not app.exception
    assert next(item for item in app.selectbox if item.label == "Cost model").options == [
        "Hypothetical bps"
    ]
    button(app, "Run strategy comparison").click().run()
    button(app, "Explore Monte Carlo risk").click().run()
    button(app, "Simulate strategy risk").click().run()
    assert not app.exception
    risk = app.session_state["strategy_simulation"]
    assert risk["symbol"] == "TEST" and risk["is_synthetic"] is False
    assert risk["strategy_calibration"]["evaluation"]["end"] == "2020-12-31"
    assert (
        risk["linked_backtest"] == app.session_state["backtests"]["Price + volume"]["_provenance"]
    )


def test_validation_button_inherits_submitted_custom_backtest():
    app = AppTest.from_file(str(ROOT / "app/dashboard.py"), default_timeout=40).run()
    navigate(app, "Backtesting")
    for label, value in {
        "Starting capital": 200000.0,
        "Price structure lookback": 50,
        "Breakout relative-volume threshold": 2.5,
        "Commission / charges per side (bps)": 30.0,
        "Slippage per side (bps)": 20.0,
        "Stop-loss distance (%)": 12.0,
    }.items():
        next(item for item in app.number_input if item.label == label).set_value(value)
    next(
        item for item in app.slider if item.label == "Capital exposure cap at entry (%)"
    ).set_value(50)
    button(app, "Run strategy comparison").click().run()
    submitted = dict(app.session_state["experiment_settings"])
    button(app, "View entries & exits on research chart").click().run()
    button(app, "Calculate price structure").click().run()
    assert not app.exception
    assert app.session_state["chart_analysis"]["result"]["_provenance"]["options"]["lookback"] == 50
    button(app, "Configure a strategy backtest").click().run()
    button(app, "Challenge these rules in Validation").click().run()
    assert not app.exception
    assert app.session_state["validation_import"]["settings"] == submitted
    button(app, "Run validation study").click().run()
    assert not app.exception
    study = app.session_state["validation_study"]
    for row in study["rows"]:
        if row["condition"] == "Base":
            options = row["provenance"]["options"]
            for key in [
                "initial_capital",
                "lookback",
                "volume_threshold",
                "commission_bps",
                "slippage_bps",
                "stop_loss_pct",
                "max_exposure",
            ]:
                assert options[key] == submitted[key]
    assert study["parent_backtests"]


def test_accounting_and_validation_offline_flow(tmp_path, monkeypatch):
    from app import storage

    monkeypatch.setenv("STOCK_RESEARCH_DB", str(tmp_path / "offline.sqlite"))
    app = AppTest.from_file(str(ROOT / "app/dashboard.py"), default_timeout=40).run()
    next(item for item in app.radio if item.label == "Data source").set_value(
        "Accounting example"
    ).run()
    navigate(app, "Backtesting")
    next(item for item in app.selectbox if item.label == "Cost model").set_value(
        "NSE delivery estimate"
    ).run()
    next(item for item in app.selectbox if item.label == "Evaluation window").set_value(
        "Full history (exploratory)"
    )
    button(app, "Run strategy comparison").click().run()
    assert not app.exception
    hold = app.session_state["backtests"]["Buy and hold"]
    assert hold["metrics"]["dividend_income"] > 0
    assert hold["metrics"]["total_return"] < 0  # flat wealth minus actual configured fees/slippage
    assert len(hold["action_ledger"]) == 3
    assert "stt" in hold["fee_breakdown"]
    navigate(app, "Validation")
    button(app, "Run validation study").click().run()
    assert not app.exception
    assert len(app.session_state["validation_study"]["rows"]) == 12
    button(app, "Save validation study").click().run()
    assert not app.exception
    assert len(storage.get_setting("validation_studies")) == 1
    reopened = AppTest.from_file(str(ROOT / "app/dashboard.py"), default_timeout=40).run()
    navigate(reopened, "Validation")
    assert any(item.label == "Saved validation study" for item in reopened.selectbox)
    assert not reopened.exception
    # Loading another source clears the current study, while persisted records remain intact.
    next(item for item in app.radio if item.label == "Data source").set_value(
        "Synthetic demo"
    ).run()
    assert "validation_study" not in app.session_state


def test_research_workflow_and_dataset_invalidation(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_RESEARCH_DB", str(tmp_path / "dashboard.sqlite"))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    app = AppTest.from_file(str(ROOT / "app/dashboard.py"), default_timeout=30).run()
    assert not app.exception
    button(app, "Build evidence card").click().run()
    assert not app.exception
    assert app.session_state["evidence"]["data_quality"]["synthetic"]
    assert app.session_state["evidence"]["assessment"]["bullish"] is not None
    button(app, "Generate analyst report").click().run()
    assert not app.exception
    assert app.session_state["report"]["provider"] == "rules"
    button(app, "Saved research").click().run()
    assert not app.exception
    assert next(item for item in app.selectbox if item.label == "Saved evidence").value[
        "data_quality"
    ]["synthetic"]
    assert any(item.label == "Saved analyst report" for item in app.selectbox)
    navigate(app, "Backtesting")
    button(app, "Run strategy comparison").click().run()
    assert not app.exception
    assert set(app.session_state["backtests"]) == {"Price + volume", "Buy and hold"}
    assert all(
        run["evaluation"]["start_index"] == 378 for run in app.session_state["backtests"].values()
    )
    navigate(app, "Monte Carlo")
    button(app, "Simulate scenarios").click().run()
    assert not app.exception
    assert app.session_state["simulation"]["summary"]["p05"] > 0
    navigate(app, "Market analysis")
    assert not any("depth balance" in item.label for item in app.button)
    navigate(app, "Assistant")
    app.chat_input[0].set_value("What is drawdown, and why is CVD unavailable?").run()
    assert not app.exception
    assert len(app.session_state["chat_history"]) == 2
    navigate(app, "Overview")
    assert app.session_state["backtests"]
    assert app.session_state["simulation"]
    navigate(app, "Monitoring")
    navigate(app, "Settings")
    navigate(app, "Overview")
    selector = next(item for item in app.selectbox if item.label == "Demonstration instrument")
    selector.set_value(SYMBOLS[1]).run()
    assert not app.exception
    assert "backtests" not in app.session_state
    assert "simulation" not in app.session_state
    assert "evidence" not in app.session_state
    next(item for item in app.radio if item.label == "Data source").set_value(
        "Upload historical CSV"
    ).run()
    button(app, "Settings").click().run()
    assert not app.exception
    assert app.session_state["workspace_page"] == "Settings"


def test_indicator_lab_and_stock_search(tmp_path, monkeypatch):
    from app import instruments

    monkeypatch.setenv("STOCK_RESEARCH_DB", str(tmp_path / "dashboard.sqlite"))
    monkeypatch.setattr(
        instruments,
        "load_catalogue",
        lambda: {
            "fetched_at": "2026-10-23T00:00:00+00:00",
            "instruments": [
                {
                    "exchange": "NSE",
                    "trading_symbol": "EXAMPLE",
                    "name": "Example company",
                    "isin": "INE123A01010",
                    "instrument_key": "NSE_EQ|INE123A01010",
                },
            ],
        },
    )
    app = AppTest.from_file(str(ROOT / "app/dashboard.py"), default_timeout=30).run()
    assert not app.exception
    navigate(app, "Market analysis")
    button(app, "Calculate price structure").click().run()
    assert app.session_state["analysis"]["summary"]
    next(item for item in app.radio if item.label == "Chart workspace").set_value(
        "Indicator lab"
    ).run()
    button(app, "Calculate selected indicator").click().run()
    assert not app.exception
    assert app.session_state["indicator_result"]["function"] == "RSI"
    function = next(item for item in app.selectbox if item.label == "Indicator function")
    function.set_value("MACD").run()
    button(app, "Calculate selected indicator").click().run()
    assert not app.exception
    assert set(app.session_state["indicator_result"]["columns"]) == {
        "macd",
        "macdsignal",
        "macdhist",
    }
    navigate(app, "Stock universe")
    search = next(
        item for item in app.text_input if item.label == "Search stock symbol, company or ISIN"
    )
    search.set_value("Example").run()
    assert not app.exception
    selector = next(item for item in app.selectbox if item.label == "Stock identifier")
    assert selector.value["instrument_key"] == "NSE_EQ|INE123A01010"
    selector = next(item for item in app.selectbox if item.label == "Demonstration instrument")
    selector.set_value(SYMBOLS[1]).run()
    assert "indicator_result" not in app.session_state


def test_stock_ideas_preserve_source_and_clear_on_input_change(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_RESEARCH_DB", str(tmp_path / "ideas.sqlite"))
    app = AppTest.from_file(str(ROOT / "app/dashboard.py"), default_timeout=30).run()
    button(app, "Stock ideas").click().run()
    next(item for item in app.radio if item.label == "Idea source").set_value(
        "Five fictional demo scenarios"
    ).run()
    button(app, "Assess available stocks").click().run()
    assert not app.exception
    assert len(app.session_state["idea_cards"]) == 5
    for card in app.session_state["idea_cards"]:
        assert card["assessment"]["bullish"] is not None
        assert card["assessment"]["scope"] == "Illustrative demo"
        assert card["action"] == "INSUFFICIENT_EVIDENCE"
    next(item for item in app.radio if item.label == "Data source").set_value(
        "Upload historical CSV"
    ).run()
    assert (
        len(app.session_state["idea_cards"]) == 5
    )  # Independent demo scan survives an unset main CSV.
    next(item for item in app.selectbox if item.label == "Inspect stock research case").set_value(
        1
    ).run()
    assert not app.exception
    assert len(app.session_state["idea_cards"]) == 5
    next(item for item in app.radio if item.label == "Data source").set_value(
        "Synthetic demo"
    ).run()
    next(item for item in app.radio if item.label == "Idea source").set_value(
        "Current research dataset"
    ).run()
    assert "idea_cards" not in app.session_state
    button(app, "Assess available stocks").click().run()
    assert len(app.session_state["idea_cards"]) == 1


def test_watchlist_and_indicator_presets_survive_new_session(tmp_path, monkeypatch):
    from app import storage

    monkeypatch.setenv("STOCK_RESEARCH_DB", str(tmp_path / "workspace.sqlite"))
    app = AppTest.from_file(str(ROOT / "app/dashboard.py"), default_timeout=30).run()
    button(app, "Save instrument to watchlist").click().run()
    assert not app.exception
    assert storage.get_setting("research_watchlist")[0]["symbol"] == SYMBOLS[0]
    assert storage.get_watchlist() == SYMBOLS  # Research bookmarks do not reconfigure the worker.
    button(app, "Explore market analysis").click().run()
    assert app.session_state["workspace_page"] == "Market analysis"
    next(item for item in app.radio if item.label == "Chart workspace").set_value(
        "Indicator lab"
    ).run()
    next(item for item in app.number_input if item.label == "timeperiod").set_value(21)
    button(app, "Calculate selected indicator").click().run()
    next(item for item in app.text_input if item.label == "Preset name").set_value("RSI 21 swing")
    button(app, "Save indicator preset").click().run()
    assert not app.exception
    assert (
        storage.get_setting("indicator_presets")["RSI 21 swing"]["parameters"]["timeperiod"] == 21
    )

    # A new browser session loads persisted settings, rather than the old widget state.
    reopened = AppTest.from_file(str(ROOT / "app/dashboard.py"), default_timeout=30).run()
    navigate(reopened, "Market analysis")
    next(item for item in reopened.radio if item.label == "Chart workspace").set_value(
        "Indicator lab"
    ).run()
    next(item for item in reopened.selectbox if item.label == "Saved indicator preset").set_value(
        "RSI 21 swing"
    ).run()
    button(reopened, "Load preset").click().run()
    assert not reopened.exception
    assert next(item for item in reopened.number_input if item.label == "timeperiod").value == 21
    button(reopened, "Calculate selected indicator").click().run()
    assert reopened.session_state["indicator_result"]["parameters"]["timeperiod"] == 21
    button(reopened, "Saved research").click().run()
    assert any(item.label == "Saved watchlist item" for item in reopened.selectbox)
    button(reopened, "Remove from research watchlist").click().run()
    assert not reopened.exception
    assert storage.get_setting("research_watchlist") == []
