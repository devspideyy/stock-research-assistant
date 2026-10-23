"""Local settings loader. Values are data; no interpolation or code is executed."""

from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIXES = ("OPENROUTER_", "OLLAMA_", "UPSTOX_", "STOCK_RESEARCH_")


def load_local_settings(path: Path | None = None) -> None:
    """Load app-specific .env values without overwriting the terminal environment."""
    source = path or ROOT / ".env"
    if source.is_file():
        for raw in source.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = (part.strip() for part in line.split("=", 1))
            if not key.startswith(PREFIXES) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
                continue
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if value:
                os.environ.setdefault(key, value)
    os.environ.setdefault("STOCK_RESEARCH_DB", str(ROOT / "runs/research.sqlite"))
