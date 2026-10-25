"""Local simulated fills on fresh read-only broker snapshots; no order API."""

from datetime import datetime, timezone
import json
import math
from uuid import uuid4

import pandas as pd
import streamlit as st

from app import providers, storage
from app.computation import calculate
from app.monitor import _quote_time
from app.ui_helpers import number


def tables(db):
    db.execute(
        "CREATE TABLE IF NOT EXISTS paper_account (id INTEGER PRIMARY KEY CHECK(id=1), initial_cash REAL, cash REAL, positions TEXT)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS paper_orders (id TEXT PRIMARY KEY, created_at TEXT, payload TEXT)"
    )


def configure_account(capital: float) -> None:
    if not math.isfinite(capital) or not 1000 <= capital <= 1e9:
        raise ValueError("Paper capital must be ₹1,000–₹1,000,000,000.")
    with storage.connection() as db:
        tables(db)
        db.execute("INSERT OR IGNORE INTO paper_account VALUES (1,?,?,?)", (capital, capital, "{}"))


def account_state() -> dict:
    with storage.connection() as db:
        tables(db)
        row = db.execute("SELECT * FROM paper_account WHERE id=1").fetchone()
        orders = db.execute(
            "SELECT payload FROM paper_orders ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
    return {
        "account": dict(row) | {"positions": json.loads(row["positions"])} if row else None,
        "orders": [json.loads(r[0]) for r in orders],
    }


def record_fill(
    snapshot: dict,
    symbol: str,
    side: str,
    quantity: int,
    request_id: str,
    *,
    commission=10.0,
    slippage=5.0,
    now: datetime | None = None,
) -> dict:
    with storage.connection() as db:
        tables(db)
        db.execute("BEGIN IMMEDIATE")
        previous = db.execute(
            "SELECT payload FROM paper_orders WHERE id=?", (request_id,)
        ).fetchone()
        if previous:
            record = json.loads(previous[0])
            if (record["symbol"], record["side"], record["quantity"]) != (symbol, side, quantity):
                raise ValueError("This paper order ID already belongs to a different request.")
            return record
        quote = snapshot["quote"]
        instrument = snapshot["instrument_key"]
        observed = _quote_time(quote)
        current = now or datetime.now(timezone.utc)
        if observed is None or not 0 <= (current - observed).total_seconds() <= 120:
            raise ValueError(
                "A fresh quote no older than 120 seconds is required; stale, future or closed-market snapshots cannot create paper fills."
            )
        if quote.get("instrument_token") != instrument or snapshot.get("is_synthetic"):
            raise ValueError("Verified broker instrument identity is required.")
        row = db.execute("SELECT * FROM paper_account WHERE id=1").fetchone()
        if not row:
            raise ValueError("Create a paper account first.")
        positions = json.loads(row["positions"])
        result = calculate(
            "paper_fill",
            {
                "cash": row["cash"],
                "held": positions.get(instrument, 0),
                "side": side,
                "quantity": quantity,
                "last_price": quote["last_price"],
                "commission_bps": commission,
                "slippage_bps": slippage,
            },
        )
        positions[instrument] = result["held"]
        record = {
            "id": request_id,
            "symbol": symbol,
            "instrument_key": instrument,
            "recorded_at": current.isoformat(),
            "quote_time": observed.isoformat(),
            "source": snapshot["source"],
            "received_at": snapshot["received_at"],
            "commission_bps": commission,
            "slippage_bps": slippage,
            "simulated": True,
            **result,
        }
        db.execute(
            "UPDATE paper_account SET cash=?,positions=? WHERE id=1",
            (result["cash"], json.dumps(positions)),
        )
        db.execute(
            "INSERT INTO paper_orders VALUES (?,?,?)",
            (request_id, current.isoformat(), json.dumps(record, allow_nan=False)),
        )
    return record


def paper_journal() -> None:
    st.write(
        "Record forward simulated fills against fresh read-only quotes. This page never places broker orders."
    )
    state = account_state()
    account = state["account"]
    if not account:
        capital = st.number_input("Initial simulated cash", 1000.0, 1e9, 100000.0)
        if st.button("Create local paper account", type="primary"):
            configure_account(capital)
            st.rerun()
        st.caption(
            "You can prepare the account without API keys. Simulated fills require a fresh authenticated quote."
        )
        return
    a, b = st.columns(2)
    a.metric("Simulated cash available", number(account["cash"], prefix="₹ "), border=True)
    b.metric("Recorded simulated fills", len(state["orders"]), border=True)
    st.caption(
        "Latest 100 fills shown. Holdings and cash persist locally; no account reset is performed by changing initial-capital fields."
    )
    if account["positions"]:
        st.dataframe(
            pd.DataFrame(
                [
                    {"Instrument": key, "Shares": value}
                    for key, value in account["positions"].items()
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    mapping = storage.get_setting("upstox_instruments", {})
    if not mapping:
        st.info(
            "Set verified Upstox instrument mappings in Monitoring, then configure your token locally. No live data or paper fills are fabricated while the feed is unavailable."
        )
    else:
        import os

        symbol = st.selectbox("Paper instrument", list(mapping))
        if st.button(
            "Fetch fresh read-only quote", disabled=not bool(os.getenv("UPSTOX_ACCESS_TOKEN"))
        ):
            try:
                st.session_state.paper_quote = {
                    "symbol": symbol,
                    "snapshot": providers.fetch_upstox_quote(mapping[symbol]),
                }
            except (RuntimeError, ValueError, OSError) as exc:
                st.error(str(exc))
        quote = st.session_state.get("paper_quote")
        if quote and quote["symbol"] == symbol:
            st.caption(
                f"Observed quote: {quote['snapshot']['quote']['last_price']} · {_quote_time(quote['snapshot']['quote'])}"
            )
            with st.form("paper_fill_form"):
                side = st.selectbox("Simulated side", ["BUY", "SELL"])
                quantity = st.number_input("Whole shares", 1, 1000000, 1)
                a, b = st.columns(2)
                commission = a.number_input("Paper charges (bps)", 0.0, 500.0, 10.0)
                slippage = b.number_input("Paper slippage (bps)", 0.0, 500.0, 5.0)
                if st.form_submit_button("Record simulated fill", type="primary"):
                    try:
                        record_fill(
                            quote["snapshot"],
                            symbol,
                            side,
                            quantity,
                            uuid4().hex,
                            commission=commission,
                            slippage=slippage,
                        )
                        st.session_state.pop("paper_quote", None)
                        st.rerun()
                    except (ValueError, RuntimeError, OSError) as exc:
                        st.error(str(exc))
    if state["orders"]:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        key: row[key]
                        for key in [
                            "recorded_at",
                            "symbol",
                            "side",
                            "quantity",
                            "fill_price",
                            "fee",
                            "quote_time",
                        ]
                    }
                    for row in state["orders"]
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        st.download_button("Export paper ledger", json.dumps(state, indent=2), "paper_ledger.json")
    st.caption(
        "Snapshot fills use editable slippage and proportional charges. They do not model an exchange queue, market impact or actual broker invoices. Strategy signals need completed, current OHLCV; 2020 research ratings are never reused as live signals."
    )
