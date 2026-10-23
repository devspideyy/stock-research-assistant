"""Validate optional user-supplied, dated research evidence; never fetch URLs."""

import json
import math
from datetime import datetime
from urllib.parse import urlparse


def load_evidence_json(raw: bytes | str) -> dict:
    """Accept news/fundamentals/depth with provenance, keeping missing data missing."""
    if len(raw) > 1_000_000:
        raise ValueError("Evidence attachment exceeds 1 MB.")
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Evidence must be a JSON object.")
    result = {"news": [], "fundamentals": {}, "depth": {}}
    news = data.get("news", [])
    if not isinstance(news, list) or len(news) > 50:
        raise ValueError("Provide at most 50 news items.")
    for item in news:
        if not isinstance(item, dict):
            raise ValueError("Each news item must be an object.")
        for field in ("title", "published_at", "source"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(f"Each news item needs {field}.")
        datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))
        url = str(item.get("url", ""))
        if url and (urlparse(url).scheme not in {"https", "http"} or not urlparse(url).hostname):
            raise ValueError("Source links must be HTTP/HTTPS URLs.")
        result["news"].append(
            {
                "title": item["title"][:1000],
                "summary": str(item.get("summary", ""))[:4000],
                "published_at": item["published_at"],
                "source": item["source"][:250],
                "url": url,
                "is_synthetic": bool(item.get("is_synthetic", False)),
            }
        )
    fundamentals = data.get("fundamentals", {})
    if fundamentals:
        if (
            not isinstance(fundamentals, dict)
            or not fundamentals.get("published_at")
            or not fundamentals.get("source")
        ):
            raise ValueError("Fundamentals need published_at and source.")
        datetime.fromisoformat(str(fundamentals["published_at"]).replace("Z", "+00:00"))
        result["fundamentals"] = fundamentals
    depth = data.get("depth", {})
    if depth:
        if not isinstance(depth, dict) or not depth.get("as_of") or not depth.get("source"):
            raise ValueError(
                "Depth needs as_of and source; it remains separate from daily evidence."
            )
        datetime.fromisoformat(str(depth["as_of"]).replace("Z", "+00:00"))
        for side in ("bids", "asks"):
            levels = depth.get(side)
            if not isinstance(levels, list) or not 1 <= len(levels) <= 100:
                raise ValueError("Depth needs 1–100 aggregated price levels on each side.")
            for level in levels:
                price, quantity = float(level["price"]), float(level["quantity"])
                if (
                    not math.isfinite(price)
                    or not math.isfinite(quantity)
                    or price <= 0
                    or quantity < 0
                ):
                    raise ValueError("Invalid depth price or quantity.")
        result["depth"] = depth
    # Reject nonstandard JSON NaN/Infinity even in otherwise uninspected fields.
    json.dumps(result, allow_nan=False)
    return result
