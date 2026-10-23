"""Provider files use different exchange series; catalogue refresh is atomic."""

import gzip
import io
import json

import pytest

from app import instruments


def row(exchange, kind, *, symbol="TEST", isin="INE123A01010"):
    return {
        "segment": exchange + "_EQ",
        "instrument_type": kind,
        "instrument_key": exchange + "_EQ|" + isin,
        "isin": isin,
        "trading_symbol": symbol,
        "name": "Example company",
    }


@pytest.mark.parametrize("kind", ["EQ", "BE", "BZ", "SM", "ST", "SZ"])
def test_nse_common_shares_include_trade_to_trade_and_sme(kind):
    assert len(instruments.cash_equities([row("NSE", kind)], "NSE")) == 1


@pytest.mark.parametrize("kind", sorted(instruments.EQUITY_TYPES["BSE"]))
def test_bse_equity_trading_groups(kind):
    assert len(instruments.cash_equities([row("BSE", kind)], "BSE")) == 1


def test_funds_bonds_rights_and_other_exchanges_are_excluded():
    records = [
        row("NSE", "EQ", isin="INF123A01010"),
        row("NSE", "BE", symbol="TEST-RE1"),
        row("NSE", "N1"),
        row("NSE", "GS"),
        row("BSE", "A"),
    ]
    assert instruments.cash_equities(records, "NSE") == []
    assert (
        instruments.cash_equities([row("BSE", kind) for kind in ["F", "G", "E", "IF", "R"]], "BSE")
        == []
    )


def test_listings_are_deduplicated_by_provider_key():
    assert len(instruments.cash_equities([row("BSE", "X")] * 2, "BSE")) == 1


def test_failed_refresh_keeps_previous_complete_cache(tmp_path, monkeypatch):
    path = tmp_path / "catalogue.json"
    previous = {"instruments": [], "fetched_at": "previous"}
    path.write_text(json.dumps(previous), encoding="utf-8")

    def download(request, **_):
        if "BSE.json" in request.full_url:
            raise OSError("Test connection failure")
        return io.BytesIO(gzip.compress(json.dumps([row("NSE", "EQ")]).encode()))

    monkeypatch.setattr(instruments.urllib.request, "urlopen", download)
    with pytest.raises(OSError):
        instruments.refresh_catalogue(path)
    assert instruments.load_catalogue(path) == previous


def test_successful_refresh_has_real_identifier_scope_and_no_price_claim(tmp_path, monkeypatch):
    def download(request, **_):
        exchange = "BSE" if "BSE.json" in request.full_url else "NSE"
        return io.BytesIO(
            gzip.compress(json.dumps([row(exchange, "X" if exchange == "BSE" else "EQ")]).encode())
        )

    monkeypatch.setattr(instruments.urllib.request, "urlopen", download)
    result = instruments.refresh_catalogue(tmp_path / "catalogue.json")
    assert len(result["instruments"]) == 2
    assert result["is_live_prices"] is False
