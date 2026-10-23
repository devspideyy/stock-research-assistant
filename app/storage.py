"""Small SQLite repository. Connections are short lived and safe across workers.

Set STOCK_RESEARCH_DB before importing/using the app to choose another database.
No API credentials or chat prompts are persisted here.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

_INITIALIZE_LOCK = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _initialize(db: sqlite3.Connection) -> None:
    # WAL activation can report BUSY immediately, even with busy_timeout set.
    deadline = time.monotonic() + 10
    while True:
        try:
            if db.execute("PRAGMA journal_mode").fetchone()[0] != "wal":
                db.execute("PRAGMA journal_mode=WAL")
            break
        except sqlite3.OperationalError as exc:
            code = getattr(exc, "sqlite_errorcode", 0) & 255
            if (
                code not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
                or time.monotonic() >= deadline
            ):
                raise
            time.sleep(0.05)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS evidence (
            id TEXT PRIMARY KEY, symbol TEXT NOT NULL, created_at TEXT NOT NULL,
            payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY, evidence_id TEXT, created_at TEXT NOT NULL,
            payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY, event_key TEXT UNIQUE NOT NULL,
            symbol TEXT NOT NULL, kind TEXT NOT NULL, created_at TEXT NOT NULL,
            payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS heartbeats (
            worker TEXT PRIMARY KEY, updated_at TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS usage (
            id INTEGER PRIMARY KEY, provider TEXT NOT NULL, purpose TEXT NOT NULL,
            model TEXT NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL,
            tokens INTEGER DEFAULT 0);
        CREATE INDEX IF NOT EXISTS usage_time ON usage(provider, created_at);
    """)


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    path = Path(os.getenv("STOCK_RESEARCH_DB", "runs/research.sqlite"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA busy_timeout=10000")
        with _INITIALIZE_LOCK:
            _initialize(db)
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def get_setting(key: str, default=None):
    with connection() as db:
        row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else default


def set_setting(key: str, value) -> None:
    with connection() as db:
        db.execute(
            "INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value, allow_nan=False)),
        )


def set_watchlist(symbols: list[str]) -> None:
    set_setting(
        "watchlist", list(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
    )


def get_watchlist() -> list[str]:
    return get_setting(
        "watchlist", ["DEMO_ENERGY", "DEMO_TECH", "DEMO_BANK", "DEMO_CONSUMER", "DEMO_INDUSTRIAL"]
    )


def save_evidence(evidence: dict) -> str:
    with connection() as db:
        db.execute(
            "INSERT OR REPLACE INTO evidence VALUES (?,?,?,?)",
            (evidence["id"], evidence["symbol"], utc_now(), json.dumps(evidence, allow_nan=False)),
        )
    return evidence["id"]


def list_evidence(symbol: str | None = None, limit: int = 50) -> list[dict]:
    with connection() as db:
        query = "SELECT payload FROM evidence"
        params = []
        if symbol:
            query += " WHERE symbol=?"
            params.append(symbol)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 500)))
        rows = db.execute(query, params).fetchall()
    return [json.loads(row[0]) for row in rows]


def save_report(report: dict) -> int:
    with connection() as db:
        cursor = db.execute(
            "INSERT INTO reports(evidence_id,created_at,payload) VALUES (?,?,?)",
            (report.get("evidence", {}).get("id"), utc_now(), json.dumps(report, allow_nan=False)),
        )
        return cursor.lastrowid


def list_reports(limit: int = 20) -> list[dict]:
    with connection() as db:
        rows = db.execute(
            "SELECT payload FROM reports ORDER BY id DESC LIMIT ?", (max(1, min(limit, 500)),)
        ).fetchall()
    return [json.loads(row[0]) for row in rows]


def record_event(event_key: str, symbol: str, kind: str, payload: dict) -> bool:
    """Insert once per deterministic event key; return False for a replay/duplicate."""
    with connection() as db:
        cursor = db.execute(
            "INSERT OR IGNORE INTO events(event_key,symbol,kind,created_at,payload) VALUES (?,?,?,?,?)",
            (event_key, symbol, kind, utc_now(), json.dumps(payload, allow_nan=False)),
        )
        return cursor.rowcount == 1


def list_events(limit: int = 100) -> list[dict]:
    with connection() as db:
        rows = db.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ?", (max(1, min(limit, 1000)),)
        ).fetchall()
    return [dict(row) | {"payload": json.loads(row["payload"])} for row in rows]


def heartbeat(worker: str = "monitor", **payload) -> dict:
    updated = utc_now()
    with connection() as db:
        db.execute(
            "INSERT INTO heartbeats VALUES (?,?,?) ON CONFLICT(worker) DO UPDATE SET updated_at=excluded.updated_at,payload=excluded.payload",
            (worker, updated, json.dumps(payload, allow_nan=False)),
        )
    return {"worker": worker, "updated_at": updated, **payload}


def get_heartbeat(worker: str = "monitor") -> dict | None:
    with connection() as db:
        row = db.execute("SELECT * FROM heartbeats WHERE worker=?", (worker,)).fetchone()
    return dict(row) | {"payload": json.loads(row["payload"])} if row else None


class BudgetExceeded(RuntimeError):
    """Local request allowance exhausted; never falls back to paid routes."""


def reserve_usage(
    provider: str,
    purpose: str,
    model: str,
    *,
    daily_limit: int = 50,
    minute_limit: int = 15,
    chat_reserve: int = 10,
    now: datetime | None = None,
) -> int:
    """Atomically count an attempt before HTTP. Failures still consume local quota.

    This allowance only covers this database, not other applications or keys.
    Report calls stop early to leave chat capacity within the same UTC day.
    """
    now = now or datetime.now(timezone.utc)
    stamp = now.astimezone(timezone.utc)
    day = stamp.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    minute = (stamp - timedelta(seconds=60)).isoformat()
    daily_limit = max(0, min(int(daily_limit), 50))
    minute_limit = max(0, min(int(minute_limit), 15))
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        daily = db.execute(
            "SELECT COUNT(*) FROM usage WHERE provider=? AND created_at>=?", (provider, day)
        ).fetchone()[0]
        recent = db.execute(
            "SELECT COUNT(*) FROM usage WHERE provider=? AND created_at>?", (provider, minute)
        ).fetchone()[0]
        ceiling = daily_limit if purpose == "chat" else max(0, daily_limit - max(0, chat_reserve))
        if daily >= ceiling:
            raise BudgetExceeded(
                "Local daily allowance reached (report requests reserve capacity for chat). It resets at 00:00 UTC."
            )
        if recent >= minute_limit:
            raise BudgetExceeded(
                "Local per-minute allowance reached. Wait one minute before retrying."
            )
        result = db.execute(
            "INSERT INTO usage(provider,purpose,model,created_at,status) VALUES (?,?,?,?,?)",
            (provider, purpose, model, stamp.isoformat(), "reserved"),
        )
        return result.lastrowid


def finish_usage(usage_id: int, status: str, tokens: int = 0) -> None:
    with connection() as db:
        db.execute(
            "UPDATE usage SET status=?,tokens=? WHERE id=?", (status, max(0, int(tokens)), usage_id)
        )


def usage_summary(provider: str = "openrouter") -> dict:
    now = datetime.now(timezone.utc)
    day = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    with connection() as db:
        rows = db.execute(
            "SELECT purpose,status,COUNT(*) AS count,SUM(tokens) AS tokens FROM usage WHERE provider=? AND created_at>=? GROUP BY purpose,status",
            (provider, day),
        ).fetchall()
    records = [dict(row) for row in rows]
    used = sum(row["count"] for row in records)
    limit = max(0, min(int(os.getenv("OPENROUTER_DAILY_LIMIT", "50")), 50))
    return {
        "provider": provider,
        "utc_date": day[:10],
        "used": used,
        "remaining": max(0, limit - used),
        "daily_limit": limit,
        "chat_reserve": 10,
        "records": records,
        "scope": "This database only; other applications share the upstream account limits.",
    }
