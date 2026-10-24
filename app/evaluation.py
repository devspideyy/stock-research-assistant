"""Descriptive benchmark and rating checks. Numerical price features remain native C++."""

from statistics import mean

from app import history
from app.accounting import market_options
from app.assessment import assess_market
from app.engine_bridge import EngineClient
from app.research_protocol import visible_candles, frozen_policy, quality_report, record_run


def sector_reference(dataset: dict, run: dict) -> dict:
    sector = dataset.get("sector")
    dates = [row["timestamp"] for row in run["equity"]]
    peers, skipped, paths = [], [], []
    if not sector:
        return {"available": False, "reason": "No sourced sector metadata attached."}
    for symbol in history.ready_stocks():
        if symbol == dataset["symbol"]:
            continue
        peer = history.load_stock(symbol)
        if peer.get("sector") != sector or peer.get("price_basis") != "adjusted":
            continue
        prices = {c["timestamp"]: c["close"] for c in peer["candles"]}
        if any(stamp not in prices for stamp in dates):
            skipped.append(symbol)
            continue
        peers.append({"symbol": symbol, "sha256": peer["history_quality"]["source_sha256"]})
        paths.append([prices[stamp] / prices[dates[0]] for stamp in dates])
    if not paths:
        return {
            "available": False,
            "reason": "No same-sector peer has complete observations on the evaluation dates.",
            "skipped": skipped,
        }
    curve = [mean(path[i] for path in paths) for i in range(len(dates))]
    return {
        "available": True,
        "sector": sector,
        "peers": peers,
        "skipped": skipped,
        "dates": dates,
        "growth": curve,
        "total_return": curve[-1] - 1,
        "strategy_difference": run["metrics"]["total_return"] - (curve[-1] - 1),
        "method": "Fixed equal initial weights; adjusted-unit peer buy-and-hold; gross before costs. Current cached cohort, not historical index membership or investable alpha.",
    }


def evaluate_ratings(dataset: dict, horizon: int = 21) -> dict:
    if not dataset.get("is_synthetic") and dataset.get("price_basis") != "adjusted":
        raise ValueError(
            "Historical rating labels require adjusted research prices to avoid raw split/dividend jumps."
        )
    if not 5 <= horizon <= 63:
        raise ValueError("Rating horizon must be 5–63 daily observations.")
    offset = dataset.get("window_start", 0)
    policy = frozen_policy(dataset)
    end = policy["start_index"] if policy else offset + int(len(visible_candles(dataset)) * 0.8)
    candles = dataset["candles"]
    engine = EngineClient()
    observations, skipped = [], 0
    for i in range(max(40, offset), end - horizon, horizon):
        if not quality_report(dataset, i, i + horizon + 1)["eligible"]:
            skipped += 1
            continue
        # Prefix-only feature requests. Future observations are used only as evaluation labels.
        summary = engine.analyze(candles[: i + 1], **market_options(dataset))["summary"]
        rating = assess_market(
            summary,
            {"valid": True, "historical": True, "synthetic": dataset["is_synthetic"]},
            i + 1,
        )
        forward = candles[i + horizon]["close"] / candles[i]["close"] - 1
        observations.append(
            {
                "as_of": candles[i]["timestamp"],
                "label_date": candles[i + horizon]["timestamp"],
                "stance": rating["stance"],
                "bullish": rating["bullish"],
                "bearish": rating["bearish"],
                "forward_return": forward,
            }
        )
    groups = []
    for stance in sorted({row["stance"] for row in observations}):
        rows = [r for r in observations if r["stance"] == stance]
        groups.append(
            {
                "stance": stance,
                "observations": len(rows),
                "positive_fraction": sum(r["forward_return"] > 0 for r in rows) / len(rows),
                "mean_forward_return": mean(r["forward_return"] for r in rows),
            }
        )
    result = {
        "symbol": dataset["symbol"],
        "rating_version": "price-evidence-v1",
        "horizon": horizon,
        "development_end": candles[end - 1]["timestamp"],
        "rows": observations,
        "groups": groups,
        "skipped_gap_windows": skipped,
        "baseline_positive_fraction": sum(r["forward_return"] > 0 for r in observations)
        / len(observations)
        if observations
        else None,
        "limitations": "Descriptive associations, not calibrated probabilities or strategy profitability. Fixed weights; non-overlapping labels; correlated/regime-dependent observations; final 20% excluded.",
    }
    record_run(
        "rating_evaluation",
        dataset,
        {"horizon": horizon},
        {k: v for k, v in result.items() if k != "rows"},
    )
    return result
