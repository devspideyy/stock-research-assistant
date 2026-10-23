"""Read-only audit fixtures; mock providers and isolate persistence in a temporary DB."""

from pathlib import Path
import sys
import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine_bridge import EngineClient
from app.demo import load_demo, SYMBOLS
from app import providers, storage
from app.monitor import run_once
from app.services import build_evidence


def main():
    output = {}
    engine = EngineClient()
    book = engine.depth(
        [{"price": 100, "quantity": 0}, {"price": 99, "quantity": 10}],
        [{"price": 101, "quantity": 10}],
    )
    output["empty_depth_level"] = {
        "actual_spread": book["spread"],
        "spread_using_positive_quantity_levels": 2,
    }
    with (
        patch.dict(os.environ, {"UPSTOX_ACCESS_TOKEN": "audit-placeholder"}),
        patch.object(
            providers,
            "_http_json",
            return_value={"status": "success", "data": {"unverified": {"last_price": 123}}},
        ),
    ):
        output["missing_quote_identity"] = {
            "accepted": providers.fetch_upstox_quote("NSE_EQ|INE123A01010")["quote"]
            == {"last_price": 123}
        }
    data = load_demo(SYMBOLS[0])
    candles = data["candles"]
    evidence = build_evidence(
        candles, engine.analyze(candles), news=[], fundamentals={}, symbol=SYMBOLS[0]
    )
    output["synthetic_label_without_auxiliary_text"] = {
        "actual_flag": evidence["data_quality"]["synthetic"],
        "expected_flag": True,
    }
    cutoff_candles = candles[:-1]
    same_day = {
        "title": "Company announcement before session close",
        "published_at": cutoff_candles[-1]["timestamp"] + "T10:00:00+05:30",
        "source": "Audit fixture",
    }
    cutoff_card = build_evidence(
        cutoff_candles, engine.analyze(cutoff_candles), news=[same_day], symbol="AUDIT"
    )
    output["date_only_news_cutoff"] = {
        "bar_date": cutoff_candles[-1]["timestamp"],
        "publication": same_day["published_at"],
        "included_as_news_fact": any(f["id"].startswith("N") for f in cutoff_card["facts"]),
        "policy_needed": "Explicit exchange session close for a completed daily bar; date alone is not a decision timestamp",
    }
    weekly = [
        dict(row, timestamp=(datetime(2025, 1, 3) + timedelta(weeks=i)).date().isoformat())
        for i, row in enumerate(candles[:30])
    ]
    output["weekly_bars"] = {
        "pass_dashboard_duplicate_date_guard": len({row["timestamp"][:10] for row in weekly})
        == len(weekly),
        "native_daily_annualization": engine.backtest(weekly, strategy="buy_hold")["limitations"][
            "daily_bar_annualization"
        ],
    }
    with (
        tempfile.TemporaryDirectory() as directory,
        patch.dict(
            os.environ,
            {"STOCK_RESEARCH_DB": str(Path(directory) / "audit.sqlite"), "UPSTOX_INSTRUMENTS": ""},
        ),
    ):
        storage.set_setting("checkpoint:live:TEST", {"alert_price": 100, "last_price": 100})
        storage.set_setting("upstox_instruments", {"TEST": "BSE_EQ|INE999A01010"})
        snapshot = {
            "received_at": storage.utc_now(),
            "source": "mock",
            "limitations": "fixture",
            "quote": {
                "last_price": 200,
                "last_trade_time": datetime.now(timezone.utc).timestamp() * 1000,
            },
        }
        with patch.object(providers, "fetch_upstox_quote", return_value=snapshot):
            result = run_once("live", ["TEST"])
        output["remapped_symbol_baseline"] = {
            "change_since_alert": result["observations"][0]["change_since_alert"],
            "event_kind": storage.list_events()[0]["kind"],
            "expected": "new instrument baseline; no cross-instrument return",
        }
    return output


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
