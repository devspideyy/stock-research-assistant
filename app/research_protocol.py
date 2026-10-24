"""Shared experiment contracts: windows, quality gates, immutable policies and audit records."""

from __future__ import annotations

from datetime import date, datetime, timezone
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from app import storage

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def reference_sessions() -> list[str]:
    calendar = json.loads((ROOT / "data/research_sessions.json").read_text())
    manifest = json.loads((ROOT / "data/history_manifest.json").read_text())
    if fingerprint(calendar) != manifest["sessions_sha256"]:
        raise ValueError("Observed-session reference differs from its committed checksum.")
    return calendar["dates"]


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def visible_candles(dataset: dict) -> list[dict]:
    return dataset["candles"][dataset.get("window_start", 0) :]


def select_window(dataset: dict, start: str, end: str) -> dict:
    """Keep causal pre-window feature history; never retain observations after end."""
    result = dict(dataset)
    result["candles"] = [c for c in dataset["candles"] if c["timestamp"][:10] <= end]
    result["window_start"] = sum(c["timestamp"][:10] < start for c in result["candles"])
    if len(visible_candles(result)) < 2:
        raise ValueError("Research window requires at least two observations.")
    result["decision_time"] = result["candles"][-1]["timestamp"][:10] + "T15:30:00+05:30"
    return result


def quality_report(dataset: dict, start: int | None = None, end: int | None = None) -> dict:
    rows = dataset["candles"][dataset.get("window_start", 0) if start is None else start : end]
    if len(rows) < 2:
        raise ValueError("Quality checks need at least two evaluated observations.")
    first, last = rows[0]["timestamp"][:10], rows[-1]["timestamp"][:10]
    actual = {c["timestamp"][:10] for c in rows}
    omitted = [
        d
        for d in dataset.get("history_quality", {}).get("omitted_invalid_dates", [])
        if first <= d <= last
    ]
    missing = sorted(d for d in reference_sessions() if first <= d <= last and d not in actual)
    long_gaps = [
        {"after": a["timestamp"][:10], "before": b["timestamp"][:10]}
        for a, b in zip(rows, rows[1:])
        if (date.fromisoformat(b["timestamp"][:10]) - date.fromisoformat(a["timestamp"][:10])).days
        > 10
    ]
    return {
        "start": first,
        "end": last,
        "omitted_invalid": omitted,
        "missing_reference_sessions": missing,
        "long_gaps": long_gaps,
        "calendar": "Observed-market reference, not an exchange-certified holiday calendar",
        "eligible": not (omitted or missing or long_gaps),
    }


def latest_complete_window(dataset: dict, minimum: int = 60) -> dict:
    """Select the tail after disclosed gaps, retaining earlier bars only for feature warm-up."""
    report = quality_report(dataset)
    if report["eligible"]:
        return dataset
    gaps = (
        report["omitted_invalid"]
        + report["missing_reference_sessions"]
        + [g["before"] for g in report["long_gaps"]]
    )
    rows = [c for c in visible_candles(dataset) if c["timestamp"][:10] > max(gaps)]
    if len(rows) < minimum:
        raise ValueError(
            f"Fewer than {minimum} complete trailing observations; review source coverage."
        )
    return select_window(dataset, rows[0]["timestamp"][:10], rows[-1]["timestamp"][:10])


def require_quality(dataset: dict, options: dict, end: int | None = None) -> dict:
    if not dataset.get("is_synthetic"):
        if dataset.get("price_basis") not in {"raw", "adjusted"}:
            raise ValueError("Confirm raw or adjusted price basis before running an experiment.")
        if dataset.get("price_basis") == "raw" and not options.get("raw_reviewed"):
            raise ValueError(
                "Record the raw-price identity and corporate-action coverage review first."
            )
    report = quality_report(
        dataset, options.get("evaluation_start", dataset.get("window_start", 0)), end
    )
    # Explicit fictional fixtures exercise algorithms without claiming exchange sessions.
    if (
        not dataset.get("is_synthetic")
        and not report["eligible"]
        and not options.get("allow_data_gaps", False)
    ):
        raise ValueError(
            "Evaluation crosses missing/invalid reference sessions or a long gap. Choose a complete window or explicitly record an exploratory gap override."
        )
    return report


def execution_options(dataset: dict) -> dict:
    if dataset.get("price_basis") == "adjusted":
        return {"position_mode": "fractional_research"}
    return {"position_mode": "whole_shares"}


def identity(dataset: dict) -> str:
    return fingerprint(
        {
            "symbol": dataset["symbol"],
            "candles": dataset["candles"],
            "window_start": dataset.get("window_start", 0),
            "source": dataset.get("history_quality", {}).get("source_sha256"),
        }
    )


def record_run(kind: str, dataset: dict, settings: dict, summary: dict) -> str:
    created = datetime.now(timezone.utc).isoformat()
    identifier = fingerprint([kind, identity(dataset), settings, created])[:20]
    payload = {
        "id": identifier,
        "kind": kind,
        "created_at": created,
        "symbol": dataset["symbol"],
        "dataset_id": identity(dataset),
        "settings": settings,
        "summary": summary,
    }
    with storage.connection() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS research_runs (id TEXT PRIMARY KEY, created_at TEXT, payload TEXT)"
        )
        db.execute(
            "INSERT INTO research_runs VALUES (?,?,?)",
            (identifier, created, json.dumps(payload, allow_nan=False)),
        )
        if kind in {"final_test_attempt", "final_test"}:
            db.execute(
                "INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)",
                ("final_access_" + identity(dataset), json.dumps(created)),
            )
    return identifier


def run_history(limit: int = 100) -> list[dict]:
    with storage.connection() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS research_runs (id TEXT PRIMARY KEY, created_at TEXT, payload TEXT)"
        )
        rows = db.execute(
            "SELECT payload FROM research_runs ORDER BY created_at DESC LIMIT ?", (min(limit, 500),)
        ).fetchall()
    return [json.loads(row[0]) for row in rows]


def frozen_policy(dataset: dict) -> dict | None:
    return storage.get_setting("final_policy_" + identity(dataset))


def rule_settings(options: dict) -> dict:
    return {
        k: v
        for k, v in options.items()
        if k not in {"evaluation_start", "allow_data_gaps", "session_gaps_present"}
    }


def freeze_policy(
    dataset: dict, options: dict, labels: list[str], untouched_attested: bool = False
) -> dict:
    key = "final_policy_" + identity(dataset)
    if storage.get_setting(key):
        raise ValueError("This source/window already has a frozen final-period policy.")
    offset = dataset.get("window_start", 0)
    if len(dataset["candles"]) - offset < 100:
        raise ValueError("A final-period reservation needs at least 100 observations.")
    split = offset + int((len(dataset["candles"]) - offset) * 0.8)
    policy = {
        "settings": rule_settings(options),
        "strategies": labels,
        "start_index": split,
        "start": dataset["candles"][split]["timestamp"],
        "end": dataset["candles"][-1]["timestamp"],
        "untouched_attested": untouched_attested,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with storage.connection() as db:
        # INSERT, never overwrite: a second browser cannot silently change the frozen policy.
        db.execute(
            "INSERT INTO settings(key,value) VALUES (?,?)",
            (key, json.dumps(policy, allow_nan=False)),
        )
    record_run("policy_frozen", dataset, options, policy)
    return policy


def apply_policy(
    dataset: dict, options: dict, labels: list[str], *, final: bool = False
) -> tuple[dict, dict, str]:
    policy = frozen_policy(dataset)
    if not policy:
        if final:
            raise ValueError("Freeze a final-period policy first.")
        return dataset, dict(options), "exploratory"
    result, settings = dict(dataset), dict(options)
    if final:
        if rule_settings(options) != policy["settings"] or labels != policy["strategies"]:
            raise ValueError("Final test must use the exact frozen rules, strategies and costs.")
        settings["evaluation_start"] = policy["start_index"]
        prior = storage.get_setting("final_access_" + identity(dataset)) is not None
        phase = "exposed final-period repeat" if prior else "final-period first access"
        return result, settings, phase
    result["candles"] = dataset["candles"][: policy["start_index"]]
    start = settings.get("evaluation_start", dataset.get("window_start", 0))
    if start >= len(result["candles"]) - 1:
        raise ValueError(
            "Evaluation starts inside the reserved final period. Select a development window."
        )
    return result, settings, "development; final 20% reserved"
