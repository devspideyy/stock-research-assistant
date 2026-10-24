"""Deterministic synthetic fixtures. Nothing here is a real security or news report."""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import random
from datetime import date, timedelta
from pathlib import Path

SYMBOLS = ["DEMO_ENERGY", "DEMO_TECH", "DEMO_BANK", "DEMO_CONSUMER", "DEMO_INDUSTRIAL"]


def load_demo(symbol: str = SYMBOLS[0], count: int = 540) -> dict:
    """Return a repeatable fictional price/news/depth bundle for software demonstration."""
    if symbol not in SYMBOLS:
        raise ValueError(f"Unknown demo symbol: {symbol}")
    if not 40 <= count <= 2000:
        raise ValueError("Demo count must be between 40 and 2,000 bars.")
    seed = int.from_bytes(hashlib.sha256(symbol.encode()).digest()[:8], "big")
    rng = random.Random(seed)
    current = date(2024, 1, 2)
    price = 150.0 + SYMBOLS.index(symbol) * 135.0
    candles = []
    while len(candles) < count:
        if current.weekday() < 5:
            index = len(candles)
            regime = 0.0011 if (index // 80) % 3 == 0 else -0.00035
            shock = rng.gauss(regime, 0.014)
            open_price = price * math.exp(rng.gauss(0, 0.003))
            close = open_price * math.exp(shock)
            high = max(open_price, close) * (1 + abs(rng.gauss(0.006, 0.003)))
            low = min(open_price, close) * (1 - abs(rng.gauss(0.006, 0.003)))
            volume = int(900_000 * rng.uniform(0.6, 1.4) * (1 + abs(shock) * 22))
            if index % 53 == 0:
                volume *= 2
            candles.append(
                {
                    "timestamp": current.isoformat(),
                    "open": round(open_price, 4),
                    "high": round(high, 4),
                    "low": round(low, 4),
                    "close": round(close, 4),
                    "volume": volume,
                }
            )
            price = close
        current += timedelta(days=1)
    as_of = candles[-1]["timestamp"]
    news = [
        {
            "id": f"{symbol}-scenario-1",
            "title": "Synthetic scenario: company announces capacity review",
            "summary": "Fictional management update; no verified earnings impact is assumed.",
            "published_at": candles[-3]["timestamp"],
            "source": "Synthetic fixture",
            "url": "",
            "sentiment": "neutral",
            "is_synthetic": True,
        },
        {
            "id": f"{symbol}-scenario-2",
            "title": "Synthetic scenario: demand improves while input costs rise",
            "summary": "Fictional opposing factors demonstrate evidence disagreement.",
            "published_at": candles[-2]["timestamp"],
            "source": "Synthetic fixture",
            "url": "",
            "sentiment": "mixed",
            "is_synthetic": True,
        },
    ]
    depth = {
        "bids": [
            {"price": round(price - 0.05 * (i + 1), 4), "quantity": rng.randint(100, 1500)}
            for i in range(5)
        ],
        "asks": [
            {"price": round(price + 0.05 * (i + 1), 4), "quantity": rng.randint(100, 1500)}
            for i in range(5)
        ],
        "as_of": as_of,
        "source": "Synthetic snapshot",
        "is_synthetic": True,
    }
    fundamentals = {
        "as_of": candles[-25]["timestamp"],
        "source": "Synthetic fixture",
        "revenue_growth_pct": 12.4,
        "debt_to_equity": 0.45,
        "net_margin_pct": 11.2,
        "pe_ratio": 22.0,
        "operating_cash_flow_inr": 125_000_000,
        "note": "Fictional values for interface testing, not investment evidence.",
    }
    return {
        "symbol": symbol,
        "candles": candles,
        "news": news,
        "depth": depth,
        "fundamentals": fundamentals,
        "is_synthetic": True,
        "price_basis": "raw",
        "corporate_actions": [],
        "description": "SYNTHETIC DEMO: fictional prices, events and depth. Weekdays only; not the NSE calendar.",
    }


def load_accounting_demo() -> dict:
    """Known split/dividend fixture, with no random market return to hide ledger errors."""
    bundle = load_demo(count=160)
    current = date(2025, 10, 1)
    dates = []
    while len(dates) < 160:
        if current.weekday() < 5:
            dates.append(current.isoformat())
        current += timedelta(days=1)
    for index, row in enumerate(bundle["candles"]):
        price = 100 if index < 80 else 50 if index < 120 else 48
        row.update(
            timestamp=dates[index],
            open=price,
            high=price,
            low=price,
            close=price,
            volume=1000 if index < 80 else 2000,
        )
    bundle.update(
        symbol="DEMO_ACCOUNTING",
        news=[],
        fundamentals={},
        depth={},
        bar_interval="1d",
        decision_time=dates[-1] + "T15:30:00+05:30",
        description="Fictional accounting fixture: 2-for-1 split, then Rs 2 dividend per new share. No real security.",
        corporate_actions=[
            {
                "type": "split",
                "ex_date": dates[80],
                "announced_date": dates[70],
                "share_multiplier": 2,
                "source": "Fictional accounting fixture",
            },
            {
                "type": "cash_dividend",
                "ex_date": dates[120],
                "announced_date": dates[110],
                "pay_date": dates[125],
                "cash_per_share": 2,
                "source": "Fictional accounting fixture",
            },
        ],
    )
    return bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", choices=SYMBOLS, default=SYMBOLS[0])
    parser.add_argument(
        "--export", type=Path, required=True, help="Output path for synthetic OHLCV CSV"
    )
    args = parser.parse_args()
    args.export.parent.mkdir(parents=True, exist_ok=True)
    with args.export.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(
            output, fieldnames=["timestamp", "open", "high", "low", "close", "volume"]
        )
        writer.writeheader()
        writer.writerows(load_demo(args.symbol)["candles"])
    print(f"Synthetic fixture exported to {args.export}")


if __name__ == "__main__":
    main()
