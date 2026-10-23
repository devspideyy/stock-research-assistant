"""Metadata-driven access to TA-Lib's compiled indicator catalogue.

This is a separate research lab. It does not change the C++ strategy rules or
combine a large indicator collection into an investment recommendation.
"""

from __future__ import annotations

from functools import lru_cache
import math

import numpy as np

from app.engine_bridge import validate_candles

try:
    import talib
    from talib import abstract
except ImportError:
    talib = abstract = None

FIELDS = ("open", "high", "low", "close", "volume")


@lru_cache(maxsize=1)
def catalogue() -> dict[str, dict]:
    if talib is None:
        return {}
    return {
        name: {
            "name": name,
            "display_name": function.info["display_name"],
            "group": function.info["group"],
            "inputs": dict(function.info["input_names"]),
            "parameters": dict(function.parameters),
            "outputs": list(function.output_names),
            "price_scale": "Output scale same as input" in (function.function_flags or []),
        }
        for name in talib.get_functions()
        for function in [abstract.Function(name)]
    }


def calculate(
    candles: list[dict],
    name: str,
    parameters: dict | None = None,
    price_inputs: dict[str, str] | None = None,
    variable_period: int = 20,
) -> dict:
    """Keep warm-up/domain gaps missing and return output aligned to input bars."""
    if talib is None:
        raise RuntimeError("Install the project requirements to enable the TA-Lib indicator lab.")
    if name not in catalogue():
        raise ValueError("Choose a function from the installed TA-Lib catalogue.")
    rows = validate_candles(candles)
    function = abstract.Function(name)  # No mutable singleton shared between sessions.
    defaults = dict(function.parameters)
    parameters = parameters or {}
    if set(parameters) - set(defaults):
        raise ValueError("Unknown indicator parameter.")
    settings = defaults | parameters
    for key, value in settings.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError(f"{key} must be a finite numeric parameter.")
        if isinstance(defaults[key], int) and (not isinstance(value, int) or abs(value) > 10_000):
            raise ValueError(f"{key} must be an integer between -10000 and 10000.")
    arrays = {field: np.array([row[field] for row in rows], dtype=np.float64) for field in FIELDS}
    inputs = dict(function.input_names)
    selections = price_inputs or {}
    if set(selections) - {
        key for key, value in inputs.items() if isinstance(value, str) and value in FIELDS
    }:
        raise ValueError("Unknown single-series input selector.")
    # TA-Lib's abstract defaults for two-series statistics are high/low.
    # Explicit remapping records what was actually compared; it is not market beta.
    mapped_arrays = dict(arrays)
    used_inputs = {}
    for key, default in inputs.items():
        if default == "periods":
            if (
                isinstance(variable_period, bool)
                or not isinstance(variable_period, int)
                or not 2 <= variable_period <= 10_000
            ):
                raise ValueError(
                    "The constant MAVP period schedule must be an integer between 2 and 10000."
                )
            mapped_arrays["periods"] = np.full(len(rows), variable_period, dtype=np.float64)
            used_inputs[key] = {"constant_period_schedule": variable_period}
        elif isinstance(default, str):
            selected = selections.get(key, default)
            if selected not in FIELDS:
                raise ValueError("Indicator inputs must be supplied OHLCV columns.")
            mapped_arrays[default] = arrays[selected]
            used_inputs[key] = selected
        else:
            used_inputs[key] = list(default)
    try:
        function.set_parameters(settings)
        lookback = function.lookback
        raw = function(mapped_arrays)
    except Exception as exc:
        # TA-Lib raises its own generic Exception for invalid C API parameters.
        raise ValueError(f"TA-Lib rejected these {name} settings: {exc}") from exc
    raw_outputs = list(raw) if len(function.output_names) > 1 else [raw]
    columns = {}
    invalid = 0
    for output_name, values in zip(function.output_names, raw_outputs, strict=True):
        cleaned = []
        for index, value in enumerate(values):
            if index < lookback or not np.isfinite(value):
                cleaned.append(None)
                invalid += int(index >= lookback)
            else:
                cleaned.append(int(value) if values.dtype.kind in "iu" else float(value))
        columns[output_name] = cleaned
    return {
        "function": name,
        "display_name": function.info["display_name"],
        "group": function.info["group"],
        "parameters": settings,
        "input_columns": used_inputs,
        "lookback_bars": lookback,
        "timestamps": [row["timestamp"] for row in rows],
        "columns": columns,
        "latest": {key: values[-1] for key, values in columns.items()},
        "domain_gaps": invalid,
        "backend": "TA-Lib compiled library via Python wrapper",
        "wrapper_version": talib.__version__,
        "core_version": talib.__ta_version__.decode(),
    }
