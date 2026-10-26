"""Known accounting, alignment and source-binding cases for the research tools."""

from datetime import datetime, timedelta, timezone
import json
import re

import pytest
from streamlit.testing.v1 import AppTest

from app import history
from app.engine_bridge import EngineClient, EngineError
from app.light_chart import chart_document, chart_payload
from app.paper_journal import configure_account, account_state, record_fill
from app.quant_research import cohort_study, portfolio_study, robustness_study
from app.research_protocol import reference_sessions
from tests.test_dashboard import ROOT, button


def series(symbol, values, weight=0.5):
    return {
        "symbol": symbol,
        "weight": weight,
        "equity": [{"timestamp": f"2020-01-0{i + 1}", "equity": v} for i, v in enumerate(values)],
    }


def source(symbol="ONE"):
    days = [d for d in reference_sessions() if "2020-02-03" <= d <= "2020-12-31"]
    return {
        "symbol": symbol,
        "is_synthetic": False,
        "price_basis": "adjusted",
        "bar_interval": "1d",
        "window_start": 0,
        "corporate_actions": [],
        "candles": [
            {
                "timestamp": d,
                "open": 100 + i * 0.3,
                "high": 100.4 + i * 0.3,
                "low": 99.9 + i * 0.3,
                "close": 100.3 + i * 0.3,
                "volume": 10000,
            }
            for i, d in enumerate(days)
        ],
    }


def test_native_portfolio_conserves_flat_combination_and_tracks_weight_drift():
    result = EngineClient().portfolio(
        [series("A", [100, 120, 80]), series("B", [100, 80, 120])],
        initial_capital=10000,
        weight_cap=0.5,
    )
    assert [r["equity"] for r in result["equity"]] == pytest.approx([10000] * 3)
    assert result["metrics"]["max_drawdown"] == 0
    assert result["metrics"]["sharpe"] is None
    assert result["correlations"][0][1] == pytest.approx(-1)
    assert result["weights"][1]["ending_weight"] == pytest.approx(0.6)
    assert result["_provenance"]["command"] == "portfolio"


def test_native_portfolio_rejects_gaps_leverage_and_entry_cap_violations():
    engine = EngineClient()
    a, b = series("A", [100, 110, 105]), series("B", [100, 95, 105])
    b["equity"][1]["timestamp"] = "2020-01-01"
    with pytest.raises(EngineError, match="increase|matching"):
        engine.portfolio([a, b])
    with pytest.raises(EngineError, match="exceed"):
        engine.portfolio(
            [series("A", [100, 110, 105], 0.7), series("B", [100, 95, 105], 0.7)], weight_cap=0.8
        )
    with pytest.raises(EngineError, match="cap"):
        engine.portfolio([series("A", [100, 110, 105], 0.7)], weight_cap=0.6)


def test_native_diagnostics_have_known_beta_and_do_not_invent_flat_correlations():
    result = EngineClient().diagnostics(
        [series("Strategy", [100, 120, 96, 115.2]), series("Benchmark", [100, 110, 99, 108.9])]
    )
    assert result["beta"] == pytest.approx(2)
    assert result["correlation"] == pytest.approx(1)
    flat = EngineClient().diagnostics(
        [series("Strategy", [100, 100, 100]), series("Benchmark", [100, 100, 100])]
    )
    assert (
        flat["beta"] is None and flat["correlation"] is None and flat["information_ratio"] is None
    )


def test_cohort_discloses_missing_stock_and_portfolio_keeps_exact_evaluation_dates():
    one, two = source(), source("TWO")
    two["candles"].pop(50)
    study = cohort_study([one, two], "Price + volume", "2020-02-03", "2020-12-31")
    assert [r["symbol"] for r in study["rows"]] == ["ONE"]
    assert study["excluded"][0]["symbol"] == "TWO"
    run = study["rows"][0]["run"]
    benchmark = study["rows"][0]["benchmark"]
    assert run["evaluation"] == benchmark["evaluation"]
    result = portfolio_study(study, {"ONE": 0.5}, 10000, 0.6)
    assert [r["timestamp"] for r in result["portfolios"]["Strategy portfolio"]["equity"]] == [
        r["timestamp"] for r in run["equity"]
    ]
    settings = study["rows"][0]["settings"]
    sensitivity = robustness_study(one, "Price + volume", settings)
    assert len(sensitivity["rows"]) == 11
    assert settings["slippage_bps"] == 5
    assert sensitivity["rows"][-1]["provenance"]["options"]["slippage_bps"] == 15


def quote(now):
    return {
        "source": "Authenticated quote fixture",
        "received_at": now.isoformat(),
        "instrument_key": "NSE_EQ|INE000TEST01",
        "quote": {
            "instrument_token": "NSE_EQ|INE000TEST01",
            "last_price": 100,
            "last_trade_time": int(now.timestamp() * 1000),
        },
    }


def test_paper_ledger_is_idempotent_long_only_and_rejects_stale_quotes():
    now = datetime(2026, 10, 23, 9, tzinfo=timezone.utc)
    configure_account(10000)
    snapshot = quote(now)
    first = record_fill(snapshot, "NSE:TEST", "BUY", 10, "order-one", now=now)
    assert first["held"] == 10
    assert first["cash"] == pytest.approx(10000 - 100 * 1.0005 * 10 * 1.001)
    again = record_fill(snapshot, "NSE:TEST", "BUY", 10, "order-one", now=now)
    assert again == first and len(account_state()["orders"]) == 1
    with pytest.raises(ValueError, match="different"):
        record_fill(snapshot, "NSE:TEST", "BUY", 20, "order-one", now=now)
    with pytest.raises(EngineError, match="sell more"):
        record_fill(snapshot, "NSE:TEST", "SELL", 11, "sell-too-much", now=now)
    with pytest.raises(ValueError, match="fresh quote"):
        record_fill(snapshot, "NSE:TEST", "BUY", 1, "stale", now=now + timedelta(seconds=121))
    assert account_state()["account"]["cash"] == first["cash"]
    assert len(account_state()["orders"]) == 1


def test_local_chart_escapes_imported_labels_and_has_no_vendor_data_script():
    payload = chart_payload(source()["candles"], symbol="</script><script>bad()</script>")
    document = chart_document(payload)
    assert "<script>bad()" not in document
    embedded = re.search(r'id="payload">(.*?)</script>', document, re.S).group(1)
    assert json.loads(embedded)["symbol"] == payload["symbol"]
    assert 'src="https://' not in document
    assert "createSeriesMarkers" in document


def test_offline_quant_ui_and_paper_setup_do_not_need_keys(monkeypatch):
    monkeypatch.delenv("STOCK_RESEARCH_TEST_FIXTURES")
    for symbol in ["ONE", "TWO"]:
        history.write_json(history.library_path() / f"{symbol}.json", source(symbol))
    app = AppTest.from_file(str(ROOT / "app/dashboard.py"), default_timeout=60).run()
    button(app, "Quant research").click().run()
    assert not app.exception
    button(app, "Compare fixed strategy across stocks").click().run()
    assert not app.exception and len(app.session_state["cohort_study"]["rows"]) >= 1
    button(app, "Save comparison study").click().run()
    button(app, "Saved research").click().run()
    assert not app.exception
    assert any(item.label == "Saved quant study" for item in app.selectbox)
    button(app, "Use saved comparison for portfolio research").click().run()
    assert app.session_state["quant_view"] == "Portfolio"
    button(app, "Evaluate portfolio risk").click().run()
    assert not app.exception and app.session_state["portfolio_study"]["portfolios"]
    button(app, "Paper journal").click().run()
    button(app, "Create local paper account").click().run()
    assert not app.exception
    assert account_state()["account"]["cash"] == 100000
