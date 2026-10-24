"""Key-free historical library. Network work is explicit; normal research reads local files."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile

import pandas as pd
import requests

from app.engine_bridge import validate_daily_candles
from app.research_protocol import fingerprint

ROOT = Path(__file__).resolve().parents[1]
CUTOFF = "2020-12-31"
REPOSITORY = "aswinv90/indian-market-historical-data"
SOURCE = "https://github.com/" + REPOSITORY
KAGGLE = "https://www.kaggle.com/datasets/rohanrao/nifty50-stock-market-data"
ARCHIVE_URL = "https://www.kaggle.com/api/v1/datasets/download/rohanrao/nifty50-stock-market-data"


def library_path() -> Path:
    return Path(os.getenv("STOCK_RESEARCH_HISTORY", ROOT / "data/private/history"))


def download(url: str, maximum: int = 40_000_000) -> bytes:
    with requests.get(
        url,
        timeout=(10, 45),
        stream=True,
        headers={"User-Agent": "StockResearchStudentProject/0.2"},
    ) as response:
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > maximum:
                raise ValueError("Historical download exceeds its size limit.")
            chunks.append(chunk)
    return b"".join(chunks)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as file:
        temporary = Path(file.name)
        json.dump(value, file, allow_nan=False)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def catalogue() -> dict:
    path = library_path() / "catalogue.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"stocks": []}


def source_manifest() -> dict:
    return json.loads((ROOT / "data/history_manifest.json").read_text(encoding="utf-8"))


def verify_reference(raw: bytes) -> None:
    manifest = source_manifest()
    members = manifest.get("reference_members_sha256")
    if members:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            for name, expected in members.items():
                if (
                    archive.getinfo(name).file_size > 80_000_000
                    or hashlib.sha256(archive.read(name)).hexdigest() != expected
                ):
                    raise ValueError("Reference CSV content differs from the committed manifest.")
        return
    if hashlib.sha256(raw).hexdigest() != manifest["reference_sha256"]:
        raise ValueError(
            "Reference archive checksum differs from the committed manifest. Review the data revision; it will not be silently replaced."
        )


def refresh_catalogue() -> dict:
    """Pin a public dataset revision; list files without fetching the entire repository."""
    api = f"https://api.github.com/repos/{REPOSITORY}"
    revision = source_manifest()["revision"]
    folders = json.loads(download(api + f"/contents/data?ref={revision}", 1_000_000))
    tree = next(item["sha"] for item in folders if item["name"] == "NSE")
    files = json.loads(download(api + f"/git/trees/{tree}", 5_000_000))
    if files.get("truncated"):
        raise ValueError("The source catalogue was truncated; previous local catalogue was kept.")
    stocks = []
    for item in files["tree"]:
        name = item["path"]
        if name.endswith("_NS.parquet"):
            symbol = name.removesuffix("_NS.parquet")
            if re.fullmatch(r"[A-Z0-9&._-]{1,35}", symbol):
                stocks.append({"symbol": symbol, "file": name, "git_blob": item["sha"]})
    if not stocks:
        raise ValueError("No price histories found in source catalogue.")
    result = {
        "revision": revision,
        "source": SOURCE,
        "cutoff": CUTOFF,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "stocks": stocks,
    }
    write_json(library_path() / "catalogue.json", result)
    return result


def reference_rows(symbol: str) -> list[dict]:
    """NSE-origin raw prices for independent overlap checks and cutoff-unit anchoring."""
    path = library_path() / "nifty_source.zip"
    if not path.exists():
        return []
    with zipfile.ZipFile(path) as archive:
        name = symbol + ".csv"
        if name not in archive.namelist():
            name = symbol.replace("&", "") + ".csv"
            if name not in archive.namelist():
                return []
        frame = pd.read_csv(io.BytesIO(archive.read(name)))
    return frame.loc[frame.Date <= CUTOFF].to_dict("records")


def prepare_frame(frame: pd.DataFrame, symbol: str, reference: list[dict] | None = None) -> dict:
    """Adjust consistently before import; never add share/dividend events a second time."""
    frame = frame.copy()
    frame.index = pd.to_datetime(frame.index).tz_localize(None)
    frame = frame.loc[frame.index <= pd.Timestamp(CUTOFF)].sort_index()
    reference_start = min((row["Date"] for row in reference or []), default=None)
    # An IPO-era reference starting after the archive's general Jan-2000 start
    # guards against provider histories mapped to an earlier/different instrument.
    guarded_start = (
        reference_start if len(reference or []) >= 60 and reference_start > "2000-02-01" else None
    )
    if guarded_start:
        frame = frame.loc[frame.index >= pd.Timestamp(reference_start)]
    listings = library_path() / "nse_equities.csv"
    listing_date = None
    if listings.exists():
        master = pd.read_csv(listings)
        master.columns = master.columns.str.strip()
        match = master.loc[master.SYMBOL == symbol]
        if not match.empty:
            listing_date = (
                pd.to_datetime(match.iloc[0]["DATE OF LISTING"], format="%d-%b-%Y")
                .date()
                .isoformat()
            )
            frame = frame.loc[frame.index >= pd.Timestamp(listing_date)]
    if len(frame) < 60 or frame.index.has_duplicates:
        raise ValueError("No eligible pre-2021 history, fewer than 60 rows, or duplicate dates.")
    fields = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    if not set(fields).issubset(frame.columns):
        raise ValueError("Historical source lacks OHLCV or adjusted close.")
    valid = (
        frame[fields].notna().all(axis=1)
        & (frame[fields[:5]] > 0).all(axis=1)
        & (frame.Volume >= 0)
    )
    valid &= (frame.High >= frame[["Open", "Close"]].max(axis=1)) & (
        frame.Low <= frame[["Open", "Close"]].min(axis=1)
    )
    rejected = frame.index[~valid].strftime("%Y-%m-%d").tolist()
    frame = frame.loc[valid]
    if len(frame) < 60 or len(rejected) > 0.02 * (len(frame) + len(rejected)):
        raise ValueError("Insufficient usable history or more than 2% invalid observations.")
    # Anchor to the terminal source price. A raw NSE-origin reference can restore
    # cutoff-date rupee units after later provider split adjustments. No later rows enter returns.
    references = {row["Date"]: row for row in reference or []}
    end = frame.index[-1].strftime("%Y-%m-%d")
    anchor_close = float(references.get(end, {}).get("Close", frame.Close.iloc[-1]))
    factor = frame["Adj Close"] / frame.Close * anchor_close / float(frame["Adj Close"].iloc[-1])
    candles = []
    for index, row in frame.iterrows():
        candles.append(
            {
                "timestamp": index.strftime("%Y-%m-%d"),
                **{key.lower(): float(row[key] * factor.loc[index]) for key in fields[:4]},
                "volume": float(row.Volume),
            }
        )
    candles = validate_daily_candles(candles)
    # Public mirror must agree with raw exchange-origin daily returns on ordinary
    # overlapping sessions. Large reference gaps are excluded from this spot check.
    checks, mismatches = 0, []
    dates = frame.index.strftime("%Y-%m-%d").tolist()
    for i in range(1, len(frame), 97):
        before, today = references.get(dates[i - 1]), references.get(dates[i])
        if before and today:
            raw_return = float(today["Close"]) / float(before["Close"]) - 1
            provider_return = float(frame.Close.iloc[i]) / float(frame.Close.iloc[i - 1]) - 1
            if abs(raw_return) < 0.2:
                checks += 1
                if abs(raw_return - provider_return) > 0.004:
                    mismatches.append(dates[i])
    if len(mismatches) > max(2, checks * 0.1):
        raise ValueError("Independent overlap check failed; price history needs manual review.")
    return {
        "symbol": symbol,
        "name": symbol,
        "candles": candles,
        "is_synthetic": False,
        "bar_interval": "1d",
        "price_basis": "adjusted",
        "corporate_actions": [],
        "news": [],
        "fundamentals": {},
        "depth": {},
        "decision_time": end + "T15:30:00+05:30",
        "description": "Real historical daily observations; provider-adjusted research units; hard cutoff 31 Dec 2020.",
        "history_quality": {
            "start": candles[0]["timestamp"],
            "end": end,
            "bars": len(candles),
            "omitted_invalid_dates": rejected,
            "reference_checks": checks,
            "reference_mismatches": mismatches,
            "cutoff_price_anchored": end in references,
            "listing_date_check": listing_date,
            "reference_start_guard": guarded_start,
            "adjustment": "Provider adjusted-close ratio, rebased at cutoff; OHLC scaled together. Volume retains provider split units.",
            "limitations": "Retrospectively adjusted research units, not raw historical lots or a point-in-time constituent universe. Missing/dividend/action completeness is not certified.",
        },
    }


def fetch_stock(symbol: str) -> dict:
    listing = catalogue()
    if listing.get("revision") != source_manifest()["revision"]:
        raise ValueError(
            "Local catalogue revision differs from the committed manifest. Refresh the catalogue first."
        )
    entry = next((item for item in listing["stocks"] if item["symbol"] == symbol), None)
    if entry is None:
        raise ValueError("Stock is absent from the pinned historical catalogue.")
    url = f"https://raw.githubusercontent.com/{REPOSITORY}/{listing['revision']}/data/NSE/{entry['file']}"
    raw = download(url, 5_000_000)
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if entry.get("git_blob") and blob != entry["git_blob"]:
        raise ValueError("Historical file does not match its pinned Git blob.")
    expected = source_manifest()["stocks"].get(symbol)
    if expected and hashlib.sha256(raw).hexdigest() != expected["source_sha256"]:
        raise ValueError("Historical source checksum differs from the committed manifest.")
    reference_path = library_path() / "nifty_source.zip"
    if reference_path.exists():
        verify_reference(reference_path.read_bytes())
    bundle = prepare_frame(pd.read_parquet(io.BytesIO(raw)), symbol, reference_rows(symbol))
    if reference_path.exists():
        with zipfile.ZipFile(reference_path) as archive:
            metadata = pd.read_csv(io.BytesIO(archive.read("stock_metadata.csv")))
        match = metadata.loc[metadata.Symbol == symbol]
        if not match.empty:
            bundle.update(
                name=match.iloc[0]["Company Name"],
                sector=match.iloc[0]["Industry"],
                isin=match.iloc[0]["ISIN Code"],
            )
    bundle["history_quality"].update(
        source=SOURCE,
        source_url=url,
        revision=listing["revision"],
        source_sha256=hashlib.sha256(raw).hexdigest(),
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )
    write_json(library_path() / f"{symbol}.json", bundle)
    return bundle


def ready_stocks() -> list[str]:
    return sorted(
        path.stem
        for path in library_path().glob("*.json")
        if re.fullmatch(r"[A-Z0-9&._-]{1,35}", path.stem)
    )


def load_stock(symbol: str) -> dict:
    if not re.fullmatch(r"[A-Z0-9&._-]{1,35}", symbol):
        raise ValueError("Invalid historical symbol.")
    bundle = json.loads((library_path() / f"{symbol}.json").read_text(encoding="utf-8"))
    if bundle["is_synthetic"] or any(row["timestamp"] > CUTOFF for row in bundle["candles"]):
        raise ValueError("Historical library provenance/cutoff check failed.")
    expected = source_manifest()["stocks"].get(symbol)
    if expected and fingerprint(bundle["candles"]) != expected["candles_sha256"]:
        raise ValueError(
            "Cached history checksum differs from the committed manifest. Re-import the pinned source before research."
        )
    return bundle
