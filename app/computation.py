"""Bounded UI caches for immutable history and deterministic native calculations."""

from hashlib import sha256
import json
from pathlib import Path

import streamlit as st

from app import history
from app.engine_bridge import EngineClient, find_engine


def file_version(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return str(path.resolve()), stat.st_mtime_ns, stat.st_size


@st.cache_data(max_entries=8, show_spinner=False)
def _history(version: tuple, manifest_hash: str) -> dict:
    # The file version invalidates local edits; the manifest pins source integrity.
    return history.load_stock(Path(version[0]).stem)


def load_history(symbol: str) -> dict:
    manifest_hash = sha256((history.ROOT / "data/history_manifest.json").read_bytes()).hexdigest()
    return _history(file_version(history.library_path() / f"{symbol}.json"), manifest_hash)


@st.cache_data(max_entries=4, show_spinner=False)
def _engine_hash(version: tuple) -> str:
    return sha256(Path(version[0]).read_bytes()).hexdigest()


@st.cache_data(max_entries=16, show_spinner=False)
def _calculate(executable: str, revision: str, operation: str, request_json: str):
    # All candles, options (including seed), and the executable hash enter the cache key.
    request = json.loads(request_json)
    return getattr(EngineClient(executable), operation)(request["candles"], **request["options"])


def calculate(operation: str, candles: list, **options) -> dict:
    executable = find_engine()
    revision = _engine_hash(file_version(executable))
    # Hash one canonical string, rather than making Streamlit recursively hash
    # thousands of candle dictionaries on every interaction.
    request_json = json.dumps(
        {"candles": candles, "options": options}, sort_keys=True, allow_nan=False
    )
    return _calculate(str(executable), revision, operation, request_json)
