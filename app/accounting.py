"""Offline input contracts and a dated, editable NSE delivery-cost estimate."""

from __future__ import annotations

from datetime import date
import json
import math

VERIFIED_THROUGH = "2026-10-24"
SOURCES = {
    "2024": "https://nsearchives.nseindia.com/content/circulars/FA64232.pdf",
    "2026": "https://nsearchives.nseindia.com/content/circulars/FA73061.pdf",
    "taxes": "https://zerodha.com/charges/",
    "dp": "https://support.zerodha.com/category/account-opening/resident-individual/ri-charges/articles/what-do-dp-charges-mean",
}


def nse_delivery_schedule(*, brokerage_bps=0.0, brokerage_cap=0.0, dp_sell=13.0) -> list[dict]:
    """bps are per side; DP is a pre-GST editable assumption, not a broker quote."""
    common = {
        "brokerage_bps": brokerage_bps,
        "brokerage_cap": brokerage_cap,
        "stt_buy_bps": 10.0,
        "stt_sell_bps": 10.0,
        "stamp_buy_bps": 1.5,
        "sebi_bps": 0.01,
        "gst_pct": 18.0,
        "dp_sell": dp_sell,
    }
    # NSE/FA/73061 states prior cash IPFT = Rs 10/crore, not Rs 9.99.
    # Total exchange + IPFT stays Rs 307/crore across the revision.
    return [
        common
        | {
            "id": "NSE-delivery-2024-10",
            "from": "2024-10-01",
            "through": "2026-02-28",
            "exchange_bps": 0.297,
            "ipft_bps": 0.01,
            "source": SOURCES["2024"],
        },
        common
        | {
            "id": "NSE-delivery-2026-03",
            "from": "2026-03-01",
            "through": VERIFIED_THROUGH,
            "exchange_bps": 0.30699,
            "ipft_bps": 0.00001,
            "source": SOURCES["2026"],
        },
    ]


def validate_actions(actions) -> list[dict]:
    if not isinstance(actions, list) or len(actions) > 256:
        raise ValueError("Provide an array of up to 256 corporate actions.")
    seen = set()
    for row in actions:
        if not isinstance(row, dict):
            raise ValueError("Each corporate action must be an object.")
        kind = row.get("type")
        if kind not in {"split", "bonus", "cash_dividend"}:
            raise ValueError(
                "Supported actions: split, bonus, cash_dividend. Rights/mergers are not supported."
            )
        ex_date = date.fromisoformat(row["ex_date"])
        announced = date.fromisoformat(row["announced_date"])
        if (
            announced >= ex_date
            or not isinstance(row.get("source"), str)
            or not row["source"].strip()
        ):
            raise ValueError(
                "Each action needs a source and an announced_date earlier than ex_date."
            )
        identity = (ex_date, "cash" if kind == "cash_dividend" else "shares")
        if identity in seen:
            raise ValueError("At most one share action and one dividend are supported per ex-date.")
        seen.add(identity)
        key = "cash_per_share" if kind == "cash_dividend" else "share_multiplier"
        value = row.get(key)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(f"{key} must be a positive finite number.")
        if kind == "cash_dividend" and date.fromisoformat(row["pay_date"]) < ex_date:
            raise ValueError("pay_date must be on or after ex_date.")
        if kind != "cash_dividend" and (value == 1 or value > 1000):
            raise ValueError("share_multiplier must differ from one and be no more than 1000.")
    json.dumps(actions, allow_nan=False)
    return actions


def load_actions(raw: bytes) -> list[dict]:
    if len(raw) > 1_000_000:
        raise ValueError("Corporate action file exceeds 1 MB.")
    value = json.loads(raw.decode("utf-8-sig"))
    return validate_actions(
        value.get("corporate_actions", []) if isinstance(value, dict) else value
    )


def market_options(dataset: dict) -> dict:
    return {
        "price_basis": dataset.get("price_basis", "unverified"),
        "corporate_actions": dataset.get("corporate_actions", []),
    }
