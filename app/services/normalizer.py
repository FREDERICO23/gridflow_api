"""Time-series normalization: resample to 1-hour mean, localize to configured timezone."""

import logging

import pandas as pd
import pytz

logger = logging.getLogger(__name__)


def normalize_to_hourly(
    df: pd.DataFrame,
    timezone: str = "Europe/Berlin",
) -> pd.DataFrame:
    """Resample a parsed load-profile DataFrame to hourly mean values.

    Args:
        df: DataFrame with columns ['ts', 'value_kw']. ts may be tz-naive or tz-aware.
        timezone: Target IANA timezone string (default: Europe/Berlin).

    Returns:
        DataFrame with columns ['ts', 'value_kw'] at exactly 1-hour frequency,
        timezone-aware in *timezone*. Gaps up to 2 consecutive hours are forward-filled.
    """
    tz = pytz.timezone(timezone)

    ts = df["ts"].copy()

    # ── Localize / convert timezone ────────────────────────────────────────────
    if ts.dt.tz is None:
        # Naive → localize, fold ambiguous DST times to the first occurrence
        ts = ts.dt.tz_localize(tz, ambiguous="infer", nonexistent="shift_forward")
    else:
        ts = ts.dt.tz_convert(tz)

    series = pd.Series(df["value_kw"].values, index=ts, name="value_kw")
    series.index.name = "ts"

    # ── Resample to 1-hour mean ────────────────────────────────────────────────
    hourly = series.resample("1h").mean()

    # ── Forward-fill short gaps (≤ 2 hours) ───────────────────────────────────
    hourly = hourly.ffill(limit=2)

    result = hourly.reset_index()
    result.columns = pd.Index(["ts", "value_kw"])

    logger.info(
        "Normalized to %d hourly records (tz=%s)", len(result), timezone
    )
    return result
