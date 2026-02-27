"""Open-Meteo weather data fetcher with DB caching.

Weather is fetched once per (year, country_code) and stored in weather_observations.
Subsequent calls for the same year/country are served entirely from the cache.
"""

import logging
from datetime import datetime, timezone

import httpx
import pandas as pd
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.weather import WeatherObservation

logger = logging.getLogger(__name__)

# Representative coordinates per country code (Berlin for DE)
COUNTRY_COORDS: dict[str, tuple[float, float]] = {
    "DE": (52.52, 13.41),
}

_OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


async def fetch_and_cache_weather(
    db: AsyncSession, year: int, country_code: str
) -> None:
    """Ensure hourly weather data for *year*/*country_code* is cached in the DB.

    Skips the API call if ≥ 8_700 rows already exist for the requested period
    (allows for DST — 8760 standard year, 8784 leap year).
    """
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)

    count_result = await db.execute(
        select(func.count()).where(
            WeatherObservation.ts >= start,
            WeatherObservation.ts < end,
            WeatherObservation.country_code == country_code,
        )
    )
    cached_count = count_result.scalar_one()

    if cached_count >= 8_700:
        logger.info(
            "Weather cache hit: %d rows for %d/%s", cached_count, year, country_code
        )
        return

    lat, lon = COUNTRY_COORDS.get(country_code, COUNTRY_COORDS["DE"])
    logger.info("Fetching Open-Meteo weather: year=%d country=%s", year, country_code)

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "hourly": "temperature_2m,shortwave_radiation,wind_speed_10m,precipitation",
        "timezone": "UTC",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(_OPEN_METEO_ARCHIVE_URL, params=params)
        resp.raise_for_status()
        payload = resp.json()

    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        logger.warning("Open-Meteo returned no hourly data for %d/%s", year, country_code)
        return

    rows = [
        {
            "ts": datetime.fromisoformat(t).replace(tzinfo=timezone.utc),
            "country_code": country_code,
            "temperature_2m": hourly.get("temperature_2m", [None] * len(times))[i],
            "solar_radiation": hourly.get("shortwave_radiation", [None] * len(times))[i],
            "wind_speed_10m": hourly.get("wind_speed_10m", [None] * len(times))[i],
            "precipitation": hourly.get("precipitation", [None] * len(times))[i],
        }
        for i, t in enumerate(times)
    ]

    # Upsert in chunks to avoid parameter limit
    chunk_size = 500
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        stmt = pg_insert(WeatherObservation).values(chunk)
        stmt = stmt.on_conflict_do_nothing(index_elements=["ts", "country_code"])
        await db.execute(stmt)

    await db.commit()
    logger.info("Cached %d weather rows for %d/%s", len(rows), year, country_code)


async def load_weather_df(
    db: AsyncSession, year: int, country_code: str
) -> pd.DataFrame | None:
    """Load cached weather data for *year*/*country_code* as a DataFrame.

    For future years where no archive data exists, attempts to use the previous
    year's data as a proxy regressor. Returns None if no data is available.
    """
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)

    result = await db.execute(
        select(WeatherObservation)
        .where(
            WeatherObservation.ts >= start,
            WeatherObservation.ts < end,
            WeatherObservation.country_code == country_code,
        )
        .order_by(WeatherObservation.ts)
    )
    rows = result.scalars().all()

    if not rows:
        # Try previous year as proxy for future forecast years
        prev_start = datetime(year - 1, 1, 1, tzinfo=timezone.utc)
        prev_end = datetime(year, 1, 1, tzinfo=timezone.utc)
        result = await db.execute(
            select(WeatherObservation)
            .where(
                WeatherObservation.ts >= prev_start,
                WeatherObservation.ts < prev_end,
                WeatherObservation.country_code == country_code,
            )
            .order_by(WeatherObservation.ts)
        )
        rows = result.scalars().all()
        if not rows:
            logger.warning(
                "No weather data available for %d or %d/%s", year, year - 1, country_code
            )
            return None
        logger.info("Using prior-year weather as proxy for forecast year %d", year)

    return pd.DataFrame(
        [
            {
                "ts": row.ts,
                "temperature_2m": row.temperature_2m,
                "solar_radiation": row.solar_radiation,
                "wind_speed_10m": row.wind_speed_10m,
                "precipitation": row.precipitation,
            }
            for row in rows
        ]
    )
