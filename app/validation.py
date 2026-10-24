"""Fixed-rule chronological validation. No fitting, optimiser or external data calls."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from statistics import median

from app import storage
from app.accounting import market_options
from app.assessment import STRATEGIES
from app.engine_bridge import EngineClient, validate_daily_candles


def chronological_folds(count: int, folds: int = 3) -> list[tuple[int, int]]:
    """First 40% warms up; remaining bars form disjoint [start, end) tests."""
    if not 2 <= folds <= 5 or count < 60:
        raise ValueError("Validation requires at least 60 daily bars and 2–5 folds.")
    first = max(30, int(count * 0.4))
    edges = [first + (count - first) * i // folds for i in range(folds + 1)]
    if min(b - a for a, b in zip(edges, edges[1:])) < 5:
        raise ValueError(
            "Each fold needs at least five daily bars. Use fewer folds or more history."
        )
    return list(zip(edges, edges[1:]))


def run_validation(
    dataset: dict, labels: list[str], options: dict, *, folds: int = 3, stress: bool = True
) -> dict:
    candles = validate_daily_candles(dataset["candles"], dataset.get("bar_interval", "unconfirmed"))
    windows = chronological_folds(len(candles), folds)
    if not labels or any(label not in STRATEGIES for label in labels):
        raise ValueError("Choose at least one supported strategy.")
    labels = list(dict.fromkeys([*labels, "Buy and hold"]))
    settings = {**options, **market_options(dataset)}
    settings.pop("strategy", None)
    settings.pop("evaluation_start", None)
    # A stress run always doubles the explicitly submitted base, never a previous stress.
    settings["cost_multiplier"] = 1
    rows = []
    engine = EngineClient()
    for condition in ["Base", "2× costs + slippage"] if stress else ["Base"]:
        for index, (start, end) in enumerate(windows, 1):
            fold_options = {**settings, "evaluation_start": start}
            fold_options["corporate_actions"] = [
                action
                for action in settings["corporate_actions"]
                if action["ex_date"] <= candles[end - 1]["timestamp"][:10]
            ]
            if condition != "Base":
                fold_options["cost_multiplier"] = 2
                fold_options["slippage_bps"] = settings.get("slippage_bps", 5) * 2
            for label in labels:
                run = engine.backtest(candles[:end], strategy=STRATEGIES[label], **fold_options)
                rows.append(
                    {
                        "condition": condition,
                        "fold": index,
                        "strategy": label,
                        "metrics": run["metrics"],
                        "evaluation": run["evaluation"],
                        "provenance": run["_provenance"],
                    }
                )
    for row in rows:
        benchmark = next(
            item
            for item in rows
            if item["condition"] == row["condition"]
            and item["fold"] == row["fold"]
            and item["strategy"] == "Buy and hold"
        )
        row["excess_return"] = row["metrics"]["total_return"] - benchmark["metrics"]["total_return"]
    source_hash = hashlib.sha256(
        json.dumps(candles, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()
    created = datetime.now(timezone.utc).isoformat()
    return {
        "version": 1,
        "id": hashlib.sha256((source_hash + created).encode()).hexdigest()[:16],
        "created_at": created,
        "symbol": dataset["symbol"],
        "is_synthetic": dataset["is_synthetic"],
        "candles_sha256": source_hash,
        "settings": settings,
        "rows": rows,
        "method": "Fixed rules; expanding feature history; disjoint chronological tests; each fold starts in cash. No fitting or parameter selection.",
        "limitations": [
            "Fold returns are separate experiments, not a stitched portfolio return.",
            "Reusing these periods to tune rules makes them exploratory, not untouched tests.",
            "Single-stock history cannot establish survivorship control or investment effectiveness.",
            "Export retains hashes/options/results, not source prices. Keep the original CSV and action file.",
        ],
    }


def summary_rows(study: dict) -> list[dict]:
    rows = study["rows"]
    result = []
    for condition, label in dict.fromkeys((r["condition"], r["strategy"]) for r in rows):
        group = [r for r in rows if r["condition"] == condition and r["strategy"] == label]
        result.append(
            {
                "condition": condition,
                "strategy": label,
                "folds": len(group),
                "positive_folds": sum(r["metrics"]["total_return"] > 0 for r in group),
                "beats_hold_folds": sum(r["excess_return"] > 1e-12 for r in group),
                "median_return": median(r["metrics"]["total_return"] for r in group),
                "worst_drawdown": max(r["metrics"]["max_drawdown"] for r in group),
            }
        )
    return result


def save_study(study: dict) -> bool:
    # One bounded setting keeps retention atomic; avoids adding a second persistence system.
    previous = storage.get_setting("validation_studies", [])
    previous = [item for item in previous if item["id"] != study["id"]]
    storage.set_setting("validation_studies", [study, *previous][:10])
    return True
