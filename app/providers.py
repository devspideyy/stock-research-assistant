"""Explicit LLM connections: local Ollama or verified free-only OpenRouter.

Uses the standard library; no tokens, prompts, or response bodies are logged.
Network errors expose a short category, never an upstream body that may contain
user content. No order API, tools, remote execution, or automatic paid fallback.
"""

from __future__ import annotations

import json
import os
import re
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from app import storage


class ProviderError(RuntimeError):
    pass


def _http_json(
    url: str, *, payload: dict | None = None, headers: dict | None = None, timeout: int = 35
) -> dict:
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        url,
        data=body,
        headers={"Accept": "application/json", **(headers or {})},
        method="POST" if body is not None else "GET",
    )
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read(2_000_000))
    except HTTPError as exc:
        raise ProviderError(
            f"Provider HTTP {exc.code}; check access, quota and configuration. No fallback was used."
        ) from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise ProviderError(
            "Provider unavailable, timed out or returned invalid JSON. No fallback was used."
        ) from None


def availability() -> dict:
    return {
        "rules": True,
        "openrouter_key_present": bool(os.getenv("OPENROUTER_API_KEY")),
        "openrouter_model": os.getenv("OPENROUTER_MODEL", "openrouter/free"),
        "ollama_model": os.getenv("OLLAMA_MODEL", "qwen3:4b"),
        "ollama_url": os.getenv("OLLAMA_URL", "http://localhost:11434"),
        "note": "Ollama availability is only confirmed when a request succeeds.",
    }


def _free_model(model: str) -> None:
    if model == "openrouter/free":
        return
    if not model.endswith(":free") or any(c.isspace() for c in model):
        raise ProviderError(
            "Only openrouter/free or a verified model ID ending in :free is allowed."
        )
    catalog = _http_json("https://openrouter.ai/api/v1/models", timeout=15)
    match = next((item for item in catalog.get("data", []) if item.get("id") == model), None)
    if not match:
        raise ProviderError(
            "The selected free model is absent from the current OpenRouter catalogue."
        )
    prices = match.get("pricing", {})
    if not isinstance(prices, dict):
        raise ProviderError("Model pricing could not be verified; request blocked.")
    try:
        if not {"prompt", "completion"}.issubset(prices) or any(
            Decimal(str(v)) != 0 for v in prices.values()
        ):
            raise ProviderError(
                "The selected route has a nonzero or unverified price; request blocked."
            )
    except InvalidOperation:
        raise ProviderError("Model pricing could not be verified; request blocked.") from None


def generate(
    messages: list[dict], provider: str, model: str | None = None, purpose: str = "report"
) -> dict:
    """One bounded attempt; callers may explicitly retry, consuming another slot."""
    if provider not in {"openrouter", "ollama"}:
        raise ProviderError(
            "Choose openrouter or ollama for AI. Rules mode is generated deterministically by services."
        )
    if purpose not in {"chat", "report"}:
        raise ProviderError("Unknown request purpose.")
    if not messages or len(json.dumps(messages)) > 75_000:
        raise ProviderError("A nonempty prompt shorter than 75,000 characters is required.")
    if provider == "openrouter":
        key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not key:
            raise ProviderError(
                "OPENROUTER_API_KEY is not configured. Choose rules mode or add your key locally."
            )
        selected = model or os.getenv("OPENROUTER_MODEL", "openrouter/free")
        _free_model(selected)
        usage_id = storage.reserve_usage(
            "openrouter",
            purpose,
            selected,
            daily_limit=int(os.getenv("OPENROUTER_DAILY_LIMIT", "50")),
        )
        try:
            result = _http_json(
                "https://openrouter.ai/api/v1/chat/completions",
                payload={
                    "model": selected,
                    "messages": messages,
                    "max_tokens": 1000,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                    "provider": {"allow_fallbacks": False},
                },
                headers={"Authorization": f"Bearer {key}", "X-Title": "Stock Research Lab"},
            )
            if result.get("error"):
                raise ProviderError("OpenRouter rejected this request. No fallback was used.")
            text = result["choices"][0]["message"]["content"]
            actual = result.get("model", selected)
            # The free router can select an underlying model ID without a :free suffix.
            tokens = int(result.get("usage", {}).get("total_tokens", 0))
            storage.finish_usage(usage_id, "completed", tokens)
            if not isinstance(text, str) or not text.strip():
                raise ProviderError("Provider returned an empty answer.")
            return {
                "text": text,
                "model": actual,
                "provider": provider,
                "usage": result.get("usage", {}),
                "mode": "AI / external free route",
            }
        except (ProviderError, KeyError, IndexError, TypeError, ValueError) as exc:
            storage.finish_usage(usage_id, "failed")
            if isinstance(exc, ProviderError):
                raise
            raise ProviderError(
                "Provider response did not match the expected answer format."
            ) from None
    selected = model or os.getenv("OLLAMA_MODEL", "qwen3:4b")
    base = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    parsed = urlparse(base)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.username
        or parsed.password
    ):
        raise ProviderError(
            "OLLAMA_URL must point to your loopback computer (localhost or 127.0.0.1)."
        )
    result = _http_json(
        base + "/api/chat",
        payload={
            "model": selected,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2, "num_predict": 1000},
        },
        timeout=60,
    )
    text = result.get("message", {}).get("content")
    if not isinstance(text, str) or not text.strip():
        raise ProviderError(
            "Ollama returned no text. Ensure the selected local model is installed."
        )
    return {
        "text": text,
        "model": result.get("model", selected),
        "provider": provider,
        "usage": {
            "prompt_tokens": result.get("prompt_eval_count", 0),
            "completion_tokens": result.get("eval_count", 0),
        },
        "mode": "AI / local",
    }


def fetch_upstox_quote(instrument_key: str) -> dict:
    """Read-only full-quote endpoint. Snapshot depth is not executed order flow."""
    token = os.getenv("UPSTOX_ACCESS_TOKEN", "").strip()
    if not token:
        raise ProviderError(
            "UPSTOX_ACCESS_TOKEN is missing. Live monitoring requires your read-only data access."
        )
    if not isinstance(instrument_key, str) or not re.fullmatch(
        r"(?:NSE_EQ|BSE_EQ)\|[A-Za-z0-9]+", instrument_key
    ):
        raise ProviderError("Use one verified NSE_EQ or BSE_EQ cash-equity instrument key.")
    result = _http_json(
        "https://api.upstox.com/v2/market-quote/quotes?"
        + urlencode({"instrument_key": instrument_key}),
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if result.get("status") != "success" or not result.get("data"):
        raise ProviderError("Upstox did not return a quote for this instrument.")
    data = result["data"]
    if not isinstance(data, dict) or len(data) != 1:
        raise ProviderError("Upstox must return exactly one identified instrument.")
    quote = next(iter(data.values()))
    if not isinstance(quote, dict) or quote.get("instrument_token") != instrument_key:
        raise ProviderError(
            "Upstox returned a missing or different instrument identity; snapshot rejected."
        )
    return {
        "source": "Upstox periodic quote snapshot",
        "received_at": storage.utc_now(),
        "instrument_key": instrument_key,
        "quote": quote,
        "limitations": "Snapshots cannot distinguish executions from cancellations or establish CVD.",
    }


def validate_grounded_answer(text: str, facts: list[dict]) -> dict:
    """Require a compact JSON answer and reject unknown reference IDs/URLs.

    This verifies provenance syntax, not that an LLM interpreted every source
    correctly. Original facts remain visible beside all model interpretations.
    """
    cleaned = text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        value = json.loads(cleaned)
    except (ValueError, TypeError):
        raise ProviderError(
            "Model output was not the required JSON answer; it was not published. Retry explicitly or use rules mode."
        ) from None
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("text"), str)
        or not value["text"].strip()
        or not isinstance(value.get("citations"), list)
    ):
        raise ProviderError("Model answer did not pass the required text/citations structure.")
    if len(value["text"]) > 20_000 or any(not isinstance(item, str) for item in value["citations"]):
        raise ProviderError("Model answer or reference list did not pass validation.")
    allowed = {fact["id"] for fact in facts if "id" in fact}
    inline = set(re.findall(r"\[([A-Z]+\d+)\]", value["text"]))
    cited = set(value["citations"])
    if not cited.issubset(allowed) or not inline.issubset(cited):
        raise ProviderError("Model cited an unknown or undeclared fact; answer was not published.")
    allowed_urls = {fact.get("url", "") for fact in facts}
    urls = re.findall(r"https?://[^\s<>\)\]\"']+", value["text"])
    if any(url.rstrip(".,;") not in allowed_urls for url in urls):
        raise ProviderError("Model supplied an unverified URL; answer was not published.")
    return {"text": value["text"], "citations": list(dict.fromkeys(value["citations"]))}
