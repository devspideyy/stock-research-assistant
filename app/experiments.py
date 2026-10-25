"""Complete local experiment snapshots; no credentials or model prompts."""

import json
from uuid import uuid4

from app import storage
from app.research_protocol import fingerprint, identity


def _table(db):
    db.execute(
        "CREATE TABLE IF NOT EXISTS experiment_snapshots "
        "(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, symbol TEXT NOT NULL, "
        "dataset_id TEXT NOT NULL, payload TEXT NOT NULL)"
    )


def save_experiment(dataset: dict, results: dict, settings: dict, **context) -> str:
    snapshot = {
        "version": 1,
        "id": uuid4().hex[:20],
        "created_at": storage.utc_now(),
        "dataset_id": identity(dataset),
        "dataset": dataset,
        "results": results,
        "settings": settings,
        **context,
    }
    snapshot["checksum"] = fingerprint(snapshot)
    with storage.connection() as db:
        _table(db)
        db.execute(
            "INSERT INTO experiment_snapshots VALUES (?,?,?,?,?)",
            (
                snapshot["id"],
                snapshot["created_at"],
                dataset["symbol"],
                snapshot["dataset_id"],
                json.dumps(snapshot, allow_nan=False),
            ),
        )
    return snapshot["id"]


def list_experiments() -> list[dict]:
    with storage.connection() as db:
        _table(db)
        rows = db.execute(
            "SELECT id,created_at,symbol,dataset_id FROM experiment_snapshots "
            "ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
    return [dict(row) for row in rows]


def load_experiment(identifier: str) -> dict:
    with storage.connection() as db:
        _table(db)
        row = db.execute(
            "SELECT payload FROM experiment_snapshots WHERE id=?", (identifier,)
        ).fetchone()
    if row is None:
        raise ValueError("Saved experiment could not be found.")
    snapshot = json.loads(row[0])
    checksum = snapshot.pop("checksum", None)
    if fingerprint(snapshot) != checksum:
        raise ValueError("Saved experiment checksum is invalid.")
    if snapshot["version"] != 1 or identity(snapshot["dataset"]) != snapshot["dataset_id"]:
        raise ValueError("Saved experiment version or source checksum is invalid.")
    effective = snapshot.get("backtest_dataset", snapshot["dataset"])
    for result in snapshot["results"].values():
        evaluation = result["evaluation"]
        if evaluation["end"] != effective["candles"][-1]["timestamp"]:
            raise ValueError("Saved results do not match their price window.")
    return snapshot
