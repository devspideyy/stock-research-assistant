"""Standalone, read-only monitoring worker with persistent deduplication.

Run once: python -m app.monitor --once --mode demo
Run until stopped: python -m app.monitor --mode demo --interval 60
Live uses explicitly mapped NSE cash-equity keys and UPSTOX_ACCESS_TOKEN. It
polls quote snapshots; it is not an exchange tick/order-event feed. An awake
computer and network are required. No worker is installed or started on import.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone

from app import providers, storage


def _event_key(*parts) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def _quote_time(quote: dict) -> datetime | None:
    value = quote.get("last_trade_time")
    if value:
        try:
            return datetime.fromtimestamp(float(value) / 1000, timezone.utc)
        except (ValueError, TypeError, OverflowError, OSError):
            pass
    try:
        stamp = datetime.fromisoformat(str(quote.get("timestamp", "")).replace("Z", "+00:00"))
        return (
            stamp.replace(tzinfo=timezone.utc)
            if stamp.tzinfo is None
            else stamp.astimezone(timezone.utc)
        )
    except ValueError:
        return None


def _demo_observation(symbol: str) -> tuple[dict, str]:
    from app.demo import load_demo
    from app.engine_bridge import EngineClient
    from app.services import build_evidence

    dataset = load_demo(symbol)
    candles = dataset["candles"]
    analysis = EngineClient().analyze(candles)
    # The source is explicit even when no demo headline is available.
    analysis["source"] = "SYNTHETIC deterministic demo/replay"
    evidence = build_evidence(
        candles,
        analysis,
        dataset.get("news"),
        symbol,
        dataset.get("fundamentals"),
        is_synthetic=True,
        decision_time=candles[-1]["timestamp"] + "T15:30:00+05:30",
    )
    storage.save_evidence(evidence)
    source_time = evidence["as_of"]
    return {
        "symbol": symbol,
        "as_of": source_time,
        "source": "SYNTHETIC deterministic demo/replay",
        "is_synthetic": True,
        "evidence": evidence,
        "message": "Replayed synthetic observation; this is not a live market alert.",
    }, source_time


def run_once(mode: str = "demo", symbols: list[str] | None = None) -> dict:
    """One complete poll; failures are visible, gaps never filled with demo data."""
    if mode not in {"demo", "live"}:
        raise ValueError("Monitoring mode must be demo or live.")
    symbols = list(dict.fromkeys(symbols if symbols is not None else storage.get_watchlist()))
    result = {
        "mode": mode,
        "is_synthetic": mode == "demo",
        "checked": 0,
        "events_added": 0,
        "errors": [],
        "observations": [],
    }
    mapping = storage.get_setting("upstox_instruments", {})
    raw_mapping = os.getenv("UPSTOX_INSTRUMENTS", "")
    if raw_mapping:
        try:
            mapping = json.loads(raw_mapping)
        except json.JSONDecodeError:
            raise ValueError(
                "UPSTOX_INSTRUMENTS must be a JSON object mapping symbols to NSE_EQ/BSE_EQ keys."
            ) from None
    if not isinstance(mapping, dict):
        raise ValueError("The Upstox instrument map must be an object.")
    for symbol in symbols:
        try:
            if mode == "demo":
                observation, source_time = _demo_observation(symbol)
                kind = "demo_replay_observation"
                inserted = storage.record_event(
                    _event_key(mode, symbol, source_time), symbol, kind, observation
                )
            else:
                instrument = mapping.get(symbol)
                if not instrument:
                    raise providers.ProviderError(
                        f"No cash-equity instrument key configured for {symbol}; no live request made."
                    )
                snapshot = providers.fetch_upstox_quote(instrument)
                quote = snapshot["quote"]
                observed = _quote_time(quote)
                age = (datetime.now(timezone.utc) - observed).total_seconds() if observed else None
                fresh = age is not None and 0 <= age <= 120
                source_time = observed.isoformat() if observed else None
                price = quote.get("last_price")
                if price is None or float(price) <= 0:
                    raise providers.ProviderError("Live snapshot has no valid last price.")
                checkpoint_key = f"checkpoint:live:{instrument}"
                previous = storage.get_setting(checkpoint_key, {})
                baseline = previous.get("alert_price")
                change = float(price) / float(baseline) - 1 if baseline else None
                significant = baseline is not None and abs(change) >= 0.005
                observation = {
                    "symbol": symbol,
                    "instrument_key": instrument,
                    "as_of": source_time,
                    "received_at": snapshot["received_at"],
                    "source": snapshot["source"],
                    "is_synthetic": False,
                    "last_price": float(price),
                    "freshness": "recent_trade"
                    if fresh
                    else "stale_or_market_closed_or_timestamp_unavailable",
                    "age_seconds": round(age, 1) if age is not None else None,
                    "change_since_alert": change,
                    "depth": quote.get("depth"),
                    "limitations": snapshot["limitations"],
                }
                kind = "price_change_observation" if significant else "live_snapshot_baseline"
                # A stale quote is recorded as a data gap, never a fresh price alert.
                if not fresh:
                    kind = "stale_snapshot"
                    inserted = storage.record_event(
                        _event_key(mode, instrument, source_time, kind), symbol, kind, observation
                    )
                elif baseline is None or significant:
                    inserted = storage.record_event(
                        _event_key(mode, instrument, source_time, kind, price),
                        symbol,
                        kind,
                        observation,
                    )
                else:
                    inserted = False
                if fresh:
                    storage.set_setting(
                        checkpoint_key,
                        {
                            "as_of": source_time,
                            "alert_price": float(price)
                            if significant or baseline is None
                            else baseline,
                            "last_price": float(price),
                        },
                    )
            storage.set_setting(
                f"checkpoint:{mode}:last:{symbol}",
                {
                    "as_of": source_time,
                    "last_success_at": storage.utc_now(),
                    "is_synthetic": mode == "demo",
                },
            )
            result["checked"] += 1
            result["events_added"] += int(inserted)
            result["observations"].append(observation)
        except (RuntimeError, ValueError, KeyError, TypeError, OSError) as exc:
            error = {"symbol": symbol, "error": str(exc)}
            result["errors"].append(error)
            # One connection-error event per symbol/day/category avoids floods.
            storage.record_event(
                _event_key(mode, symbol, "error", storage.utc_now()[:10], type(exc).__name__),
                symbol,
                "monitor_error",
                error,
            )
    storage.heartbeat(
        "monitor",
        mode=mode,
        is_synthetic=mode == "demo",
        status="error" if result["errors"] else "ok",
        checked=result["checked"],
        events_added=result["events_added"],
        errors=result["errors"],
        note="Dashboard independence does not bypass host sleep, shutdown, network outages or source-access limits.",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once", action="store_true", help="Poll once and exit; useful for validation."
    )
    parser.add_argument("--mode", choices=("demo", "live"), default="demo")
    parser.add_argument(
        "--interval", type=int, default=60, help="Polling interval in seconds (minimum 15)."
    )
    parser.add_argument(
        "--symbols", nargs="+", help="Optional symbols overriding the stored watchlist."
    )
    args = parser.parse_args()
    try:
        while True:
            result = run_once(args.mode, args.symbols)
            print(
                json.dumps({key: value for key, value in result.items() if key != "observations"}),
                flush=True,
            )
            if args.once:
                if result["errors"]:
                    raise SystemExit(1)
                return
            time.sleep(max(15, args.interval))
    except KeyboardInterrupt:
        storage.heartbeat("monitor", mode=args.mode, status="stopped")


if __name__ == "__main__":
    main()
