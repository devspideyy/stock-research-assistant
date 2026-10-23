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


def test_research_workflow_and_dataset_invalidation(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_RESEARCH_DB", str(tmp_path / "dashboard.sqlite"))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    app = AppTest.from_file(str(ROOT / "app/dashboard.py"), default_timeout=30).run()
    assert not app.exception
    button(app, "Build evidence card").click().run()
    assert not app.exception
    assert app.session_state["evidence"]["data_quality"]["synthetic"]
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
    button(app, "Run the three-strategy comparison").click().run()
    assert not app.exception
    assert len(app.session_state["backtests"]) == 3
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
    button(reopened, "Market analysis").click().run()
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
