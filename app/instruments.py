"""Public, key-free NSE/BSE cash-equity identifiers; never a live-price feed."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import io
import json
from pathlib import Path
import re
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "runs" / "instrument_catalogue.json"
URLS = {
    exchange: f"https://assets.upstox.com/market-quote/instruments/exchange/{exchange}.json.gz"
    for exchange in ("NSE", "BSE")
}
# NSE's published series legend separates fully paid shares, SME, debt and units.
# BSE encodes the trading group in instrument_type rather than the literal EQ.
EQUITY_TYPES = {
    "NSE": {"EQ", "BE", "BZ", "SM", "ST", "SZ"},
    "BSE": {"A", "B", "T", "Z", "X", "XT", "M", "MT", "MS", "TS", "P", "ZP"},
}


def cash_equities(records: list, exchange: str) -> list[dict]:
    """Exclude indices/derivatives/ETFs; keep separate exchange listings by key."""
    if exchange not in URLS or not isinstance(records, list):
        raise ValueError("Expected an NSE/BSE instrument list.")
    result = {}
    for row in records:
        if not isinstance(row, dict):
            continue
        if (
            row.get("segment") != f"{exchange}_EQ"
            or row.get("instrument_type") not in EQUITY_TYPES[exchange]
        ):
            continue
        fields = ("instrument_key", "trading_symbol", "name", "isin")
        if not all(isinstance(row.get(key), str) and row[key].strip() for key in fields):
            continue
        if not row["instrument_key"].startswith(f"{exchange}_EQ|"):
            continue
        # EQ also contains ETF units, identified by fund ISINs; rights are separate securities.
        if not row["isin"].startswith("INE") or re.search(r"-RE\d*$", row["trading_symbol"]):
            continue
        result[row["instrument_key"]] = {
            **{key: row[key].strip() for key in fields},
            "exchange": exchange,
            "series_or_group": row["instrument_type"],
            "security_type": str(row.get("security_type", "Unspecified")),
        }
    return sorted(result.values(), key=lambda row: row["trading_symbol"])


def refresh_catalogue(path: Path = CACHE) -> dict:
    rows = []
    for exchange, url in URLS.items():
        request = urllib.request.Request(
            url, headers={"User-Agent": "StockResearchStudentProject/0.1"}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            compressed = response.read(25_000_001)
        if len(compressed) > 25_000_000:
            raise ValueError("Instrument download exceeded its size limit.")
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as archive:
            raw = archive.read(150_000_001)
        if len(raw) > 150_000_000:
            raise ValueError("Instrument archive exceeded its decompressed size limit.")
        equities = cash_equities(json.loads(raw), exchange)
        if not equities:
            raise ValueError(f"The {exchange} catalogue returned no validated cash equities.")
        rows.extend(equities)
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "Upstox public beginning-of-day instrument files",
        "source_urls": URLS,
        "is_live_prices": False,
        "scope": "Provider-listed fully paid NSE/BSE company equity shares, including SME and surveillance groups. Excludes funds, debt, rights, partly paid shares and derivatives.",
        "instruments": rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as file:
            temporary = Path(file.name)
            json.dump(payload, file, allow_nan=False)
        temporary.replace(path)  # A failed refresh preserves the previous complete cache.
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return payload


def load_catalogue(path: Path = CACHE) -> dict | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as file:
        result = json.load(file)
    if not isinstance(result, dict) or not isinstance(result.get("instruments"), list):
        raise ValueError("The local catalogue is invalid. Refresh it from the Stock catalogue tab.")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    catalogue = refresh_catalogue() if args.refresh else load_catalogue()
    if catalogue:
        print(
            json.dumps(
                {
                    "fetched_at": catalogue["fetched_at"],
                    "counts": {
                        exchange: sum(
                            row["exchange"] == exchange for row in catalogue["instruments"]
                        )
                        for exchange in URLS
                    },
                    "live_prices": False,
                }
            )
        )
    else:
        print("No catalogue cached. Use --refresh to download public instrument identifiers.")
