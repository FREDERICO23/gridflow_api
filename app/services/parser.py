"""Load profile file parser.

Supports CSV (comma or semicolon delimited, German locale) and Excel (.xlsx/.xls).
Auto-detects timestamp and power columns; converts kWh to kW where needed.
"""

import io
import logging
from typing import cast

import pandas as pd

logger = logging.getLogger(__name__)

# Column-name fragments used for auto-detection (lowercase)
_TIMESTAMP_HINTS = ("time", "date", "ts", "datetime", "zeitstempel", "datum")
_VALUE_HINTS = ("kw", "mw", "power", "load", "value", "leistung", "verbrauch", "energie")
# kWh/MWh columns need unit conversion
_ENERGY_HINTS = ("kwh", "mwh")


def _detect_column(columns: list[str], hints: tuple[str, ...]) -> str | None:
    """Return the first column whose lowercased name contains any of the hints."""
    for col in columns:
        col_lower = col.lower()
        for hint in hints:
            if hint in col_lower:
                return col
    return None


def _parse_csv(data: bytes) -> pd.DataFrame:
    """Try semicolon separator first (German locale), then comma."""
    import pandas.errors as pd_errors

    if not data or not data.strip():
        raise ValueError("File is empty")

    for sep in (";", ","):
        try:
            df = pd.read_csv(
                io.BytesIO(data),
                sep=sep,
                decimal=",",   # German decimal comma; pandas ignores if not needed
                encoding="utf-8-sig",  # handle BOM
                engine="python",
            )
            if len(df.columns) >= 2:
                return df
        except pd_errors.EmptyDataError:
            raise ValueError("File is empty")
        except Exception:
            continue

    # Last resort: let pandas sniff
    try:
        return pd.read_csv(io.BytesIO(data), encoding="utf-8-sig")
    except pd_errors.EmptyDataError:
        raise ValueError("File is empty")


def _parse_excel(data: bytes) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(data), engine="openpyxl")


def _detect_interval_minutes(ts_series: pd.Series) -> float:
    """Return the most common gap between timestamps in minutes."""
    deltas = ts_series.sort_values().diff().dropna()
    if deltas.empty:
        return 60.0
    median_delta = deltas.median()
    return max(median_delta.total_seconds() / 60, 1.0)


def parse_load_profile(data: bytes, filename: str) -> pd.DataFrame:
    """Parse raw file bytes into a clean DataFrame with columns [ts, value_kw].

    Args:
        data: Raw file bytes.
        filename: Original filename (used to detect format via extension).

    Returns:
        DataFrame sorted by ts with columns ['ts' (tz-naive), 'value_kw' (float)].

    Raises:
        ValueError: If timestamp or value column cannot be found, or data is empty.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "csv"

    if ext in ("xlsx", "xls"):
        df = _parse_excel(data)
    else:
        df = _parse_csv(data)

    if df.empty:
        raise ValueError(f"Parsed file '{filename}' is empty")

    cols = list(df.columns)

    # ── Detect timestamp column ────────────────────────────────────────────────
    ts_col = _detect_column(cols, _TIMESTAMP_HINTS)
    if ts_col is None:
        # Fallback: try the first column
        ts_col = cols[0]
        logger.warning("No timestamp column detected; using first column '%s'", ts_col)

    # ── Detect value column ────────────────────────────────────────────────────
    remaining = [c for c in cols if c != ts_col]
    value_col = _detect_column(remaining, _VALUE_HINTS)
    if value_col is None:
        if len(remaining) == 1:
            value_col = remaining[0]
            logger.warning("No value column detected; using '%s'", value_col)
        else:
            raise ValueError(
                f"Cannot detect value column in {cols!r}. "
                "Expected a column containing: kw, mw, power, load, value, kwh, or mwh."
            )

    # ── Parse timestamps ───────────────────────────────────────────────────────
    ts = pd.to_datetime(df[ts_col], dayfirst=True, utc=False, errors="coerce")
    if ts.isna().all():
        raise ValueError(f"Could not parse any timestamps from column '{ts_col}'")

    # ── Parse values ───────────────────────────────────────────────────────────
    values = pd.to_numeric(df[value_col], errors="coerce")

    result = pd.DataFrame({"ts": ts, "value_kw": values}).dropna(subset=["ts"])
    result = result.sort_values("ts").reset_index(drop=True)

    if result.empty:
        raise ValueError("No valid rows remain after parsing")

    # ── Convert kWh / MWh → kW if column name indicates energy ───────────────
    col_lower = value_col.lower()
    is_energy = any(hint in col_lower for hint in _ENERGY_HINTS)
    if is_energy:
        interval_min = _detect_interval_minutes(result["ts"])
        hours_per_interval = interval_min / 60.0
        if "mwh" in col_lower:
            result["value_kw"] = result["value_kw"] * 1000.0 / hours_per_interval
        else:
            result["value_kw"] = result["value_kw"] / hours_per_interval
        logger.info(
            "Converted energy column '%s' to average kW (interval=%.0f min)",
            value_col,
            interval_min,
        )

    logger.info(
        "Parsed '%s': %d records, value column='%s'",
        filename,
        len(result),
        value_col,
    )
    return cast(pd.DataFrame, result)
