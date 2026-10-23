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
