"""Explicitly download a historical catalogue and selected real stock histories."""

from pathlib import Path
import sys
import argparse
import json
import csv
import io
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import history  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="+")
    parser.add_argument("--refresh-catalogue", action="store_true")
    parser.add_argument(
        "--reference-universe",
        action="store_true",
        help="Prepare the archive's 50-stock cohort; not a point-in-time full NSE universe.",
    )
    args = parser.parse_args()
    listing = (
        history.refresh_catalogue()
        if args.refresh_catalogue or not history.catalogue()["stocks"]
        else history.catalogue()
    )
    reference_path = history.library_path() / "nifty_source.zip"
    if not reference_path.exists():
        reference_path.parent.mkdir(parents=True, exist_ok=True)
        raw = history.download(history.ARCHIVE_URL)
        history.verify_reference(raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if "stock_metadata.csv" not in archive.namelist():
                raise ValueError("Reference archive does not match the expected schema.")
        reference_path.write_bytes(raw)
    history.verify_reference(reference_path.read_bytes())
    with zipfile.ZipFile(reference_path) as archive:
        cohort = list(
            csv.DictReader(io.StringIO(archive.read("stock_metadata.csv").decode("utf-8-sig")))
        )
    symbols = args.symbols or (
        [row["Symbol"] for row in cohort]
        if args.reference_universe
        else [
            "INFY",
            "TCS",
            "HDFCBANK",
            "ICICIBANK",
            "RELIANCE",
            "ITC",
            "LT",
            "SBIN",
            "HINDUNILVR",
            "MARUTI",
        ]
    )
    print(
        f"Catalogue: {len(listing['stocks'])} files at {listing['revision'][:12]}; research cutoff {history.CUTOFF}",
        flush=True,
    )
    report_path = history.library_path() / "download_report.json"
    previous = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    failures = {row["symbol"]: row for row in previous.get("failures", [])}
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending = {pool.submit(history.fetch_stock, symbol): symbol for symbol in symbols}
        for future in as_completed(pending):
            symbol = pending[future]
            try:
                result = future.result()
                q = result["history_quality"]
                failures.pop(symbol, None)
                print(
                    f"READY {symbol}: {q['start']} .. {q['end']}, {q['bars']} bars, {q['reference_checks']} overlap checks",
                    flush=True,
                )
            except Exception as exc:
                failures[symbol] = {"symbol": symbol, "error": str(exc)}
                print(f"WITHHELD {symbol}: {exc}", flush=True)
    history.write_json(
        report_path,
        {
            "failures": list(failures.values()),
            "attempted": symbols,
            "ready_symbols": history.ready_stocks(),
            "cutoff": history.CUTOFF,
            "catalogue_files": len(listing["stocks"]),
        },
    )
    print(json.dumps({"ready": len(history.ready_stocks()), "withheld": len(failures)}), flush=True)


if __name__ == "__main__":
    main()
