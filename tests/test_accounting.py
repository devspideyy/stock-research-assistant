"""Economic invariants and known charge amounts through the actual native boundary."""

from datetime import date, timedelta

import pytest

from app.accounting import nse_delivery_schedule, validate_actions
from app.engine_bridge import EngineClient, EngineError


def history(prices, start="2026-01-01"):
    return [
        {
            "timestamp": (date.fromisoformat(start) + timedelta(days=i)).isoformat(),
            "open": price,
            "high": price + 0.25,
            "low": price - 0.25,
            "close": price,
            "volume": 100,
        }
        for i, price in enumerate(prices)
    ]


def action(kind="split", ex_date="2026-01-24", **values):
    return {
        "type": kind,
        "ex_date": ex_date,
        "announced_date": "2025-12-01",
        "source": "Fictional unit fixture",
        **values,
    }


@pytest.mark.parametrize("kind,ratio", [("split", 2), ("bonus", 1.5), ("split", 0.5)])
def test_share_actions_preserve_wealth_and_do_not_create_false_breakouts(kind, ratio):
    data = history([100] * 23 + [100 / ratio] * 6)
    options = {"corporate_actions": [action(kind, share_multiplier=ratio)], "price_basis": "raw"}
    engine = EngineClient()
    run = engine.backtest(
        data, strategy="buy_hold", initial_capital=1000, commission_bps=0, slippage_bps=0, **options
    )
    assert run["equity"][-1]["position"] == 10 * ratio
    assert all(row["equity"] == pytest.approx(1000) for row in run["equity"])
    context = engine.analyze(data, **options)["summary"]
    assert context["last_close"] == pytest.approx(100 / ratio)
    assert context["return_20d"] == pytest.approx(0)
    assert context["breakout"] == "none"
    scenario = engine.simulate(data, paths=30, horizon=5, capital=1000, **options)
    assert scenario["summary"]["p50"] == pytest.approx(1000)


def test_dividend_entitlement_is_an_asset_until_payment_not_spending_cash():
    data = history([100] * 23 + [95] * 6)
    options = {
        "corporate_actions": [action("cash_dividend", cash_per_share=5, pay_date="2026-01-26")],
        "price_basis": "raw",
    }
    engine = EngineClient()
    run = engine.backtest(
        data, strategy="buy_hold", initial_capital=1000, commission_bps=0, slippage_bps=0, **options
    )
    ex_bar, paid_bar = run["equity"][23], run["equity"][25]
    assert ex_bar["cash"] == 0
    assert ex_bar["dividend_receivable"] == 50
    assert paid_bar["cash"] == 50
    assert paid_bar["dividend_receivable"] == 0
    assert all(row["equity"] == pytest.approx(1000) for row in run["equity"])
    before_payment = engine.backtest(
        data[:25],
        strategy="buy_hold",
        initial_capital=1000,
        commission_bps=0,
        slippage_bps=0,
        **options,
    )
    assert before_payment["metrics"]["dividend_paid"] == 0
    assert before_payment["metrics"]["dividend_receivable"] == 50
    assert engine.analyze(data, **options)["summary"]["return_20d"] == pytest.approx(0)
    # Buying on the ex-date does not earn the prior holder's dividend.
    on_ex = engine.backtest(
        data,
        strategy="buy_hold",
        initial_capital=1000,
        evaluation_start=22,
        commission_bps=0,
        slippage_bps=0,
        **options,
    )
    assert on_ex["metrics"]["dividend_income"] == 0


def test_same_day_split_then_dividend_has_explicit_post_split_units():
    data = history([100] * 23 + [47.5] * 6)
    events = [
        action("cash_dividend", cash_per_share=2.5, pay_date="2026-01-26"),
        action("split", share_multiplier=2),
    ]
    run = EngineClient().backtest(
        data,
        strategy="buy_hold",
        initial_capital=1000,
        commission_bps=0,
        slippage_bps=0,
        price_basis="raw",
        corporate_actions=events,
    )
    assert run["metrics"]["dividend_income"] == 50
    assert run["equity"][-1]["equity"] == pytest.approx(1000)
    assert run["action_ledger"][0]["type"] == "split"


def test_actions_reject_double_adjustments_fractional_entitlements_and_late_information():
    engine = EngineClient()
    data = history([100] * 23 + [50] * 3)
    events = [action(share_multiplier=2)]
    with pytest.raises(EngineError, match="double-adjust"):
        engine.backtest(data, price_basis="adjusted", corporate_actions=events)
    events = [action("bonus", share_multiplier=1.5)]
    with pytest.raises(EngineError, match="Fractional"):
        engine.backtest(
            data,
            strategy="buy_hold",
            initial_capital=1100,
            commission_bps=0,
            slippage_bps=0,
            price_basis="raw",
            corporate_actions=events,
        )
    events[0]["announced_date"] = events[0]["ex_date"]
    with pytest.raises(EngineError, match="earlier announced_date"):
        engine.backtest(data, price_basis="raw", corporate_actions=events)
    with pytest.raises(ValueError, match="earlier"):
        validate_actions(events)


def test_future_action_does_not_change_prior_signals_or_fills():
    before = history([100 + i for i in range(23)])
    after = history([100 + i for i in range(23)] + [61, 62, 63])
    engine = EngineClient()
    settings = {"strategy": "indicator", "commission_bps": 0, "slippage_bps": 0}
    prefix = engine.backtest(before, **settings)
    full = engine.backtest(
        after, **settings, price_basis="raw", corporate_actions=[action(share_multiplier=2)]
    )
    assert [
        fill for fill in full["trades"] if fill["timestamp"] <= before[-1]["timestamp"]
    ] == prefix["trades"]
    assert (
        engine.analyze(before)["series"]
        == engine.analyze(after, price_basis="raw", corporate_actions=[action(share_multiplier=2)])[
            "series"
        ][:23]
    )


@pytest.mark.parametrize(
    "start,rate_id,exchange,ipft",
    [
        ("2025-11-01", "NSE-delivery-2024-10", 2.97, 0.10),
        ("2026-03-01", "NSE-delivery-2026-03", 3.0699, 0.0001),
    ],
)
def test_dated_delivery_costs_match_known_round_trip(start, rate_id, exchange, ipft):
    # SMA baseline enters next open after 101, then exits next open after 100.
    data = history([100] * 20 + [101, 100, 100], start=start)
    run = EngineClient().backtest(
        data,
        strategy="indicator",
        initial_capital=100200,
        slippage_bps=0,
        cost_schedule=nse_delivery_schedule(),
    )
    buy, sell = run["trades"]
    assert buy["quantity"] == 1000
    parts = buy["fee_components"]
    assert parts["rate_id"] == rate_id
    assert parts["exchange"] == pytest.approx(exchange)
    assert parts["ipft"] == pytest.approx(ipft)
    assert parts["stt"] == 100
    assert parts["stamp"] == 15
    assert buy["fee"] == pytest.approx(118.7406)
    assert sell["fee"] == pytest.approx(119.0806)
    assert sell["fee_components"]["dp"] == 13
    assert run["metrics"]["realised_pnl"] == pytest.approx(-237.8212)
    assert sum(run["fee_breakdown"].values()) == pytest.approx(run["metrics"]["fees_paid"])


def test_unknown_rate_dates_fail_and_entry_sizing_includes_all_charges():
    engine = EngineClient()
    with pytest.raises(EngineError, match="No verified cost rate"):
        engine.backtest(
            history([100, 100, 100], start="2023-01-01"),
            strategy="buy_hold",
            cost_schedule=nse_delivery_schedule(),
        )
    run = engine.backtest(
        history([100] * 3),
        strategy="buy_hold",
        initial_capital=100.10,
        slippage_bps=0,
        cost_schedule=nse_delivery_schedule(),
    )
    assert run["trades"] == []  # One share plus its buy charges exceeds the account.
