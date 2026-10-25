"""Validated JSON boundary between the Python application and the C++ engine."""

from __future__ import annotations

import csv
import io
import hashlib
import json
import math
import os
import subprocess
from statistics import median
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


class EngineError(RuntimeError):
    """A calculation was rejected or the engine returned an invalid response."""


class EngineUnavailable(EngineError):
    """The native executable has not been built or cannot run."""


class CandleValidationError(ValueError):
    """An imported price series is unsafe for calculation."""


def validate_candles(candles: list[dict]) -> list[dict]:
    if not 2 <= len(candles) <= 100_000:
        raise CandleValidationError("Provide between 2 and 100,000 price bars.")
    rows = []
    previous = None
    timestamp_kind = None
    for number, row in enumerate(candles, start=1):
        try:
            stamp = str(row["timestamp"]).strip()
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            kind = "date" if len(stamp) == 10 else ("aware" if parsed.tzinfo else "naive")
            if timestamp_kind is not None and kind != timestamp_kind:
                raise ValueError("use a uniform date/timestamp format and timezone convention")
            timestamp_kind = kind
            if previous is not None and parsed <= previous:
                raise ValueError("timestamps must be strictly increasing with no duplicates")
            values = {key: float(row[key]) for key in ("open", "high", "low", "close", "volume")}
            if not all(math.isfinite(value) for value in values.values()):
                raise ValueError("numbers must be finite")
            if any(values[key] <= 0 for key in ("open", "high", "low", "close")):
                raise ValueError("prices must be positive")
            if values["volume"] < 0:
                raise ValueError("volume cannot be negative")
            if values["low"] > min(values["open"], values["close"]) or values["high"] < max(
                values["open"], values["close"]
            ):
                raise ValueError("high/low must enclose open and close")
            if values["high"] < values["low"]:
                raise ValueError("high cannot be below low")
            normalized = (
                parsed.date().isoformat()
                if kind == "date"
                else parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if kind == "aware"
                else parsed.isoformat(timespec="seconds")
            )
            rows.append({"timestamp": normalized, **values})
            previous = parsed
        except (KeyError, ValueError, TypeError, OverflowError) as exc:
            raise CandleValidationError(f"Bar {number}: {exc}") from exc
    return rows


def load_candles_csv(source: bytes | str | Any) -> list[dict]:
    """Import chronological Date/Open/High/Low/Close/Volume; never silently reorder."""
    if hasattr(source, "getvalue"):
        source = source.getvalue()
    elif hasattr(source, "read"):
        source = source.read()
    if isinstance(source, bytes):
        if len(source) > 30_000_000:
            raise CandleValidationError("CSV exceeds the 30 MB import limit.")
        source = source.decode("utf-8-sig")
    if not isinstance(source, str):
        raise CandleValidationError("CSV must be UTF-8 text.")
    reader = csv.DictReader(io.StringIO(source))
    rows = []
    for raw in reader:
        if len(rows) >= 100_000:
            raise CandleValidationError("CSV exceeds 100,000 bars.")
        normalized = {
            str(key).strip().lower(): value for key, value in raw.items() if key is not None
        }
        normalized["timestamp"] = normalized.get(
            "timestamp", normalized.get("date", normalized.get("datetime", ""))
        )
        rows.append(normalized)
    return validate_candles(rows)


def validate_daily_candles(candles: list[dict], bar_interval: str = "1d") -> list[dict]:
    """Enforce the daily-only experiment contract; not an exchange-calendar check."""
    rows = validate_candles(candles)
    if bar_interval != "1d":
        raise CandleValidationError("Confirm completed daily bars before running experiments.")
    dates = [datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")).date() for row in rows]
    gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
    if min(gaps) < 1 or median(gaps) >= 5:
        raise CandleValidationError(
            "Experiments require daily bars; intraday, weekly or very sparse history was detected."
        )
    return rows


def find_engine() -> Path:
    override = os.getenv("STOCK_RESEARCH_ENGINE")
    if override:
        path = Path(override).expanduser()
        if path.is_file():
            return path.resolve()
        raise EngineUnavailable("STOCK_RESEARCH_ENGINE does not point to an existing executable.")
    name = "engine_cli.exe" if os.name == "nt" else "engine_cli"
    for path in (
        ROOT / "engine/build" / name,
        ROOT / "engine/build/Release" / name,
        ROOT / "engine/build/bin" / name,
    ):
        if path.is_file():
            return path
    raise EngineUnavailable("C++ engine is not built. Run: python scripts/build_engine.py")


class EngineClient:
    """One native batch per operation; no Python replacement for financial calculations."""

    def __init__(self, executable: str | Path | None = None, timeout: int = 90):
        self.executable = Path(executable) if executable is not None else None
        self.timeout = timeout

    def _call(self, command: str, **payload: Any) -> dict:
        executable = self.executable or find_engine()
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            request_json = json.dumps({"command": command, **payload}, allow_nan=False)
            completed = subprocess.run(
                [str(executable)],
                input=request_json,
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=self.timeout,
                shell=False,
                creationflags=creationflags,
            )
        except (FileNotFoundError, OSError) as exc:
            raise EngineUnavailable(f"Cannot start the C++ engine: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise EngineError("Calculation timed out. Reduce the data or simulation size.") from exc
        try:
            response = json.loads(completed.stdout)
        except (ValueError, TypeError) as exc:
            raise EngineError("C++ engine returned an invalid JSON response.") from exc
        if not isinstance(response, dict):
            raise EngineError("C++ engine response must be a JSON object.")
        if completed.returncode != 0 or not response.get("ok"):
            raise EngineError(str(response.get("error", "C++ calculation failed.")))
        if response.get("schema_version") != 1 or not isinstance(response.get("result"), dict):
            raise EngineError("Unsupported native response schema.")
        result = response["result"]
        result["_provenance"] = {
            "engine_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
            "request_sha256": hashlib.sha256(request_json.encode()).hexdigest(),
            "schema_version": 1,
            "command": command,
            "options": payload.get("options", {}),
        }
        return result

    def analyze(self, candles: list[dict], **options: Any) -> dict:
        return self._call("analyze", candles=validate_candles(candles), options=options)

    def portfolio(self, curves: list[dict], **options: Any) -> dict:
        return self._call("portfolio", curves=curves, options=options)

    def diagnostics(self, curves: list[dict], **options: Any) -> dict:
        return self._call("diagnostics", curves=curves, options=options)

    def paper_fill(self, state: dict, **options: Any) -> dict:
        return self._call("paper_fill", state=state, options=options)

    def backtest(self, candles: list[dict], *, bar_interval: str = "1d", **options: Any) -> dict:
        return self._call(
            "backtest", candles=validate_daily_candles(candles, bar_interval), options=options
        )

    def simulate(self, candles: list[dict], *, bar_interval: str = "1d", **options: Any) -> dict:
        return self._call(
            "simulate", candles=validate_daily_candles(candles, bar_interval), options=options
        )

    def depth(self, bids: list[dict], asks: list[dict]) -> dict:
        return self._call("depth", bids=bids, asks=asks)
