"""Prophet-based energy load forecasting service.

Produces an 8,760-hour (or 8,784 for leap years) annual forecast vector
with 95% confidence intervals.
"""

import logging
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_WEATHER_REGRESSORS = ("temperature_2m", "solar_radiation", "wind_speed_10m")


def _build_holidays_df(holidays: list[date]) -> pd.DataFrame | None:
    """Convert a list of holiday dates into a Prophet-compatible holidays DataFrame."""
    if not holidays:
        return None
    return pd.DataFrame(
        {
            "holiday": "public_holiday",
            "ds": pd.to_datetime([h.isoformat() for h in holidays]),
            "lower_window": 0,
            "upper_window": 1,
        }
    )


def _make_future_df(forecast_year: int) -> pd.DataFrame:
    """Build an hourly date-range covering every hour of *forecast_year* in UTC."""
    start = datetime(forecast_year, 1, 1, tzinfo=timezone.utc)
    end = datetime(forecast_year + 1, 1, 1, tzinfo=timezone.utc)
    hours = pd.date_range(start=start, end=end, freq="1h", inclusive="left", tz="UTC")
    return pd.DataFrame({"ds": hours.tz_localize(None)})


def _align_weather_to_future(
    future_df: pd.DataFrame, weather_df: pd.DataFrame, forecast_year: int
) -> pd.DataFrame:
    """Merge weather regressors into future_df.

    Weather archive data may be from a prior year (proxy); aligns by month-day-hour.
    """
    w = weather_df.copy()
    w["ts"] = pd.to_datetime(w["ts"]).dt.tz_localize(None)

    # Shift weather timestamps to target year by replacing year component
    def _shift_to_year(ts: pd.Series, target_year: int) -> pd.Series:
        try:
            return ts.apply(
                lambda t: t.replace(year=target_year) if t.month != 2 or t.day != 29 else
                t.replace(year=target_year, day=28)
            )
        except Exception:
            return ts

    if w["ts"].dt.year.iloc[0] != forecast_year:
        w["ts"] = _shift_to_year(w["ts"], forecast_year)

    w = w.rename(columns={"ts": "ds"})
    for col in _WEATHER_REGRESSORS:
        if col not in w.columns:
            w[col] = np.nan

    future_df = future_df.merge(
        w[["ds"] + list(_WEATHER_REGRESSORS)], on="ds", how="left"
    )

    # Fill any remaining NaN regressors with column mean
    for col in _WEATHER_REGRESSORS:
        if col in future_df.columns:
            future_df[col] = future_df[col].fillna(future_df[col].mean())

    return future_df


def run_forecast(
    df: pd.DataFrame,
    forecast_year: int,
    weather_df: pd.DataFrame | None,
    holidays: list[date],
) -> pd.DataFrame:
    """Fit Prophet on historical hourly load data and forecast *forecast_year*.

    Args:
        df:            Normalized hourly DataFrame with columns ['ts', 'value_kw'].
        forecast_year: Year to forecast (all 8,760 / 8,784 hours).
        weather_df:    Optional weather DataFrame from cache (may be prior-year proxy).
        holidays:      List of public holiday dates for the forecast country/year.

    Returns:
        DataFrame with columns ['hour_ts', 'yhat', 'yhat_lower', 'yhat_upper'].
        hour_ts is UTC-aware.
    """
    # Lazy import — Prophet is heavy and only needed here
    from prophet import Prophet  # noqa: PLC0415

    # ── Prepare training data ─────────────────────────────────────────────────
    train = df.copy()
    train["ds"] = pd.to_datetime(train["ts"]).dt.tz_localize(None)
    if hasattr(train["ts"].dtype, "tz") or str(train["ts"].dtype).startswith("datetime64[ns,"):
        train["ds"] = pd.to_datetime(train["ts"]).dt.tz_convert("UTC").dt.tz_localize(None)
    train["y"] = train["value_kw"]
    train = train[["ds", "y"]].dropna()

    use_weather = weather_df is not None and not weather_df.empty

    # ── Build holiday DataFrame ───────────────────────────────────────────────
    holidays_df = _build_holidays_df(holidays)

    # ── Instantiate Prophet ───────────────────────────────────────────────────
    m = Prophet(
        interval_width=0.95,
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=True,
        holidays=holidays_df,
    )

    if use_weather:
        for regressor in _WEATHER_REGRESSORS:
            m.add_regressor(regressor, standardize=True)

        # Merge weather into training data
        w = weather_df.copy()
        w["ds"] = pd.to_datetime(w["ts"]).dt.tz_localize(None)
        if hasattr(w["ts"].dtype, "tz"):
            w["ds"] = pd.to_datetime(w["ts"]).dt.tz_convert("UTC").dt.tz_localize(None)

        for col in _WEATHER_REGRESSORS:
            if col not in w.columns:
                w[col] = np.nan

        train = train.merge(w[["ds"] + list(_WEATHER_REGRESSORS)], on="ds", how="left")
        for col in _WEATHER_REGRESSORS:
            train[col] = train[col].fillna(train[col].mean())

    logger.info(
        "Fitting Prophet on %d rows (weather=%s, holidays=%d)",
        len(train),
        use_weather,
        len(holidays),
    )
    m.fit(train)

    # ── Build future DataFrame ────────────────────────────────────────────────
    future_df = _make_future_df(forecast_year)

    if use_weather:
        future_df = _align_weather_to_future(future_df, weather_df, forecast_year)

    # ── Predict ───────────────────────────────────────────────────────────────
    forecast = m.predict(future_df)

    # ── Filter to forecast year only ──────────────────────────────────────────
    forecast["year"] = pd.to_datetime(forecast["ds"]).dt.year
    forecast = forecast[forecast["year"] == forecast_year].copy()

    # Re-attach UTC timezone to output timestamps
    forecast["hour_ts"] = pd.to_datetime(forecast["ds"]).dt.tz_localize("UTC")

    result = forecast[["hour_ts", "yhat", "yhat_lower", "yhat_upper"]].copy()
    result = result.sort_values("hour_ts").reset_index(drop=True)

    logger.info(
        "Forecast complete: %d hours for year %d", len(result), forecast_year
    )
    return result
