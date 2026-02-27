"""Data quality analysis for normalized hourly load profiles."""

import logging
from datetime import datetime

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_OUTLIER_IQR_FACTOR = 3.0
_FLAT_PERIOD_MIN_HOURS = 3


def generate_quality_report(df: pd.DataFrame, job_id: str) -> dict:
    """Compute a quality report for a normalized hourly time-series.

    Args:
        df: DataFrame with columns ['ts', 'value_kw']. Expected to be hourly.
        job_id: UUID string, stored in the report for traceability.

    Returns:
        A serialisable dict suitable for storing in Job.quality_report (JSON column).
    """
    if df.empty:
        return {
            "job_id": job_id,
            "total_records": 0,
            "passed": False,
            "error": "No data",
        }

    ts = pd.to_datetime(df["ts"])
    values = df["value_kw"].astype(float)

    # ── Date range ────────────────────────────────────────────────────────────
    ts_min: datetime = ts.min().to_pydatetime()
    ts_max: datetime = ts.max().to_pydatetime()

    # ── Coverage ──────────────────────────────────────────────────────────────
    # Expected hours = full span from first to last timestamp + 1
    span_hours = max(int((ts_max - ts_min).total_seconds() / 3600) + 1, 1)
    non_null = int(values.notna().sum())
    missing_hours = span_hours - non_null
    coverage_percent = round(non_null / span_hours * 100, 2)

    # ── Descriptive statistics ────────────────────────────────────────────────
    clean = values.dropna()
    stats = {
        "mean_kw": round(float(clean.mean()), 3) if not clean.empty else None,
        "min_kw": round(float(clean.min()), 3) if not clean.empty else None,
        "max_kw": round(float(clean.max()), 3) if not clean.empty else None,
        "std_kw": round(float(clean.std()), 3) if not clean.empty else None,
        "p5_kw": round(float(np.percentile(clean, 5)), 3) if not clean.empty else None,
        "p95_kw": round(float(np.percentile(clean, 95)), 3) if not clean.empty else None,
    }

    # ── Outlier detection (IQR method) ────────────────────────────────────────
    q1 = float(clean.quantile(0.25)) if not clean.empty else 0.0
    q3 = float(clean.quantile(0.75)) if not clean.empty else 0.0
    iqr = q3 - q1
    lower_fence = q1 - _OUTLIER_IQR_FACTOR * iqr
    upper_fence = q3 + _OUTLIER_IQR_FACTOR * iqr
    outlier_count = int(((clean < lower_fence) | (clean > upper_fence)).sum())

    # ── Flat periods (≥ N consecutive hours with identical value) ─────────────
    flat_count = 0
    flat_total_hours = 0
    if not clean.empty:
        run_lengths = _run_length_encoding(values.fillna(-9999))
        for val, length in run_lengths:
            if length >= _FLAT_PERIOD_MIN_HOURS and val != -9999:
                flat_count += 1
                flat_total_hours += length

    passed = coverage_percent >= 95.0

    return {
        "job_id": job_id,
        "total_records": len(df),
        "date_range": {
            "start": ts_min.isoformat(),
            "end": ts_max.isoformat(),
        },
        "coverage_percent": coverage_percent,
        "missing_hours": missing_hours,
        "statistics": stats,
        "outliers": {
            "count": outlier_count,
            "method": "IQR",
            "threshold_factor": _OUTLIER_IQR_FACTOR,
        },
        "flat_periods": {
            "count": flat_count,
            "total_hours": flat_total_hours,
            "min_consecutive_hours": _FLAT_PERIOD_MIN_HOURS,
        },
        "passed": passed,
    }


def _run_length_encoding(series: pd.Series) -> list[tuple]:
    """Return list of (value, run_length) tuples for the series."""
    if series.empty:
        return []
    runs = []
    current = series.iloc[0]
    count = 1
    for val in series.iloc[1:]:
        if val == current:
            count += 1
        else:
            runs.append((current, count))
            current = val
            count = 1
    runs.append((current, count))
    return runs
