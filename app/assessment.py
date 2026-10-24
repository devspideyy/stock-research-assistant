"""Versioned, explainable research rules. Scores are evidence points, not probabilities."""

from __future__ import annotations

import math

STRATEGIES = {
    "Price + volume": "price_volume",
    "Trend pullback": "trend_pullback",
    "Range reversion": "range_reversion",
    "Indicator baseline": "indicator",
    "Buy and hold": "buy_hold",
}

STRATEGY_GUIDE = {
    "price_volume": (
        "Breakout",
        "Close above the prior range with relative volume above your threshold.",
        "Exit below the prior range low or on the close-based stop; false breakouts are a key risk.",
    ),
    "trend_pullback": (
        "Uptrend",
        "Higher prior highs/lows, positive 20-bar return, an up-close within 1.5 ATR below the prior high and relative volume ≥ 0.8.",
        "Exit below the prior range low or on the close-based stop; a weakening trend can keep falling.",
    ),
    "range_reversion": (
        "Range",
        "Mixed prior structure, |20-bar return| ≤ 2 ATR/close, and an up-close in the bottom 20% of the prior range.",
        "Exit at the range midpoint, a break below support or the close-based stop; range breaks are a key risk.",
    ),
    "indicator": (
        "Comparison baseline",
        "Close above the 20-bar SMA.",
        "Exit below the SMA or on the close-based stop; lag and whipsaw are key risks.",
    ),
    "buy_hold": (
        "Passive benchmark",
        "Buy at the next observed open after the evaluation starts.",
        "Hold to the final mark; no strategy stop. Full downside exposure remains.",
    ),
}


def finite(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def assess_market(summary: dict, quality: dict, count: int) -> dict:
    """Fixed hypotheses for a single daily-price series; no optimiser or LLM score."""
    output = {
        "version": "price-evidence-v1",
        "bullish": None,
        "bearish": None,
        "coverage": 0,
        "stance": "Unavailable",
        "regime": "Unconfirmed",
        "recommendation": "Insufficient validated price history",
        "factors": [],
        "strategies": [],
        "invalidation": [],
        "scope": "Unverified data",
        "risk": "Unassessed",
        "limitations": [
            "Heuristic evidence points, not calibrated probabilities, returns or investment suitability.",
            "Price/volume assessment only. News meaning, valuation, sector and benchmark strength are not scored.",
            "Strategy suggestions match predefined rules to observed structure; they are not validated winners.",
            "Price factors overlap; weights and thresholds are manually chosen, versioned research hypotheses.",
        ],
    }
    close, atr_pct, momentum, structure = [
        finite(summary.get(key))
        for key in ("last_close", "atr_pct", "return_20d", "structure_direction")
    ]
    if (
        not quality.get("valid")
        or count < 21
        or any(value is None for value in (close, atr_pct, momentum, structure))
    ):
        return output
    output["scope"] = (
        "Illustrative demo"
        if quality.get("synthetic")
        else "Historical as-of assessment"
        if quality.get("historical")
        else "Dated research observation"
    )
    breakout = summary.get("breakout", "none")
    direction = 1 if breakout == "up" else -1 if breakout == "down" else 0
    volume = finite(summary.get("relative_volume"))
    day_return = finite(summary.get("return_1d"))
    sma = finite(summary.get("sma20"))
    factors = [
        (
            "Prior-range break",
            30,
            direction,
            True,
            "P2",
            f"Prior range: {breakout}; latest candle excluded from reference levels.",
        ),
        (
            "Higher/lower prior structure",
            30,
            structure,
            True,
            "P3",
            "Two consecutive prior ten-bar ranges: higher highs/lows = bullish; lower highs/lows = bearish.",
        ),
        (
            "20-bar price displacement",
            15,
            1 if momentum > atr_pct else -1 if momentum < -atr_pct else 0,
            True,
            "P3",
            f"20-bar return {momentum:.2%}; noise threshold is one current ATR/close ({atr_pct:.2%}).",
        ),
        (
            "Volume participation proxy",
            15,
            (1 if day_return and day_return > 0 else -1 if day_return and day_return < 0 else 0)
            if volume is not None and volume >= 1.2
            else 0,
            volume is not None and day_return is not None,
            "V1",
            "Relative volume ≥ 1.2 plus the close-to-close direction. This is a candle proxy, not executed order flow.",
        ),
        (
            "Moving-average context",
            10,
            1 if sma is not None and close > sma else -1 if sma is not None and close < sma else 0,
            sma is not None,
            "I1",
            "Close relative to SMA20; only 10 of 100 possible points.",
        ),
    ]
    output["factors"] = [
        {
            "factor": name,
            "weight": weight,
            "bullish": weight if available and sign > 0 else 0,
            "bearish": weight if available and sign < 0 else 0,
            "available": available,
            "reference": reference,
            "rule": rule,
        }
        for name, weight, sign, available, reference, rule in factors
    ]
    output["bullish"] = sum(f["bullish"] for f in output["factors"])
    output["bearish"] = sum(f["bearish"] for f in output["factors"])
    output["coverage"] = sum(f["weight"] for f in output["factors"] if f["available"])
    gap = output["bullish"] - output["bearish"]
    output["stance"] = "Bullish" if gap >= 25 else "Bearish" if gap <= -25 else "Mixed / neutral"
    output["regime"] = (
        "Upside breakout"
        if direction > 0
        else "Downside breakdown"
        if direction < 0
        else "Uptrend"
        if structure > 0 and momentum > 0
        else "Downtrend"
        if structure < 0 and momentum < 0
        else "Range / mixed"
    )
    output["risk"] = (
        "Elevated price volatility" if atr_pct >= 0.03 else "Lower observed price volatility"
    )
    output["recommendation"] = (
        "Bullish watch: require a confirmed setup before considering entry"
        if gap >= 25
        else "Avoid fresh long entries until price structure recovers"
        if gap <= -25
        else "Wait: opposing evidence does not establish a directional setup"
    )
    output["strategies"] = (
        ["price_volume", "trend_pullback"]
        if gap >= 25
        else []
        if gap <= -25
        else ["range_reversion"]
        if output["regime"] == "Range / mixed"
        else []
    )
    support, resistance = finite(summary.get("prior_low")), finite(summary.get("prior_high"))
    if support is not None and resistance is not None:
        output["invalidation"] = [
            f"Reassess the bullish case below prior support {support:.2f}.",
            f"Reassess the bearish case after recovery above prior resistance {resistance:.2f}.",
        ]
    if output["risk"] == "Elevated price volatility":
        output["limitations"].append(
            "ATR/close ≥ 3%: a fixed risk allocation can produce large price swings and gap losses."
        )
    return output
