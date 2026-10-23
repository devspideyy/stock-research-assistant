"""Run the actual Streamlit interaction flow with the actual C++ binary."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.demo import SYMBOLS

ROOT = Path(__file__).resolve().parents[1]


def button(app, label):
    return next(item for item in app.button if item.label == label)


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
    button(app, "Run the three-strategy comparison").click().run()
    assert not app.exception
    assert len(app.session_state["backtests"]) == 3
    button(app, "Simulate scenarios").click().run()
    assert not app.exception
    assert app.session_state["simulation"]["summary"]["p05"] > 0
    button(app, "Inspect displayed-depth balance").click().run()
    assert not app.exception
    assert app.session_state["depth_result"]["spread"] > 0
    app.chat_input[0].set_value("What is drawdown, and why is CVD unavailable?").run()
    assert not app.exception
    assert len(app.session_state["chat_history"]) == 2
    selector = next(
        item for item in app.sidebar.selectbox if item.label == "Demonstration instrument"
    )
    selector.set_value(SYMBOLS[1]).run()
    assert not app.exception
    assert "backtests" not in app.session_state
    assert "simulation" not in app.session_state
    assert "evidence" not in app.session_state
