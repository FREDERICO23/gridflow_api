"""Public holiday fetcher with DB caching via Nager.Date API.

Holidays are fetched once per (year, country_code) and stored in public_holidays.
"""

import logging
from datetime import date, datetime

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.weather import PublicHoliday

logger = logging.getLogger(__name__)

_NAGER_DATE_URL = "https://date.nager.at/api/v3/PublicHolidays/{year}/{country_code}"


async def fetch_and_cache_holidays(
    db: AsyncSession, year: int, country_code: str
) -> None:
    """Ensure public holidays for *year*/*country_code* are cached in the DB."""
    start = date(year, 1, 1)
    end = date(year, 12, 31)

    count_result = await db.execute(
        select(func.count()).where(
            PublicHoliday.date >= start,
            PublicHoliday.date <= end,
            PublicHoliday.country_code == country_code,
        )
    )
    if count_result.scalar_one() > 0:
        logger.info("Holiday cache hit for %d/%s", year, country_code)
        return

    url = _NAGER_DATE_URL.format(year=year, country_code=country_code)
    logger.info("Fetching holidays from Nager.Date: %s", url)

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        holidays_data = resp.json()

    if not holidays_data:
        logger.warning("No holidays returned for %d/%s", year, country_code)
        return

    rows = [
        {
            "date": date.fromisoformat(h["date"]),
            "country_code": country_code,
            "name": h.get("localName") or h.get("name", ""),
        }
        for h in holidays_data
    ]

    stmt = pg_insert(PublicHoliday).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=["date", "country_code"])
    await db.execute(stmt)
    await db.commit()
    logger.info("Cached %d holidays for %d/%s", len(rows), year, country_code)


async def load_holidays(
    db: AsyncSession, year: int, country_code: str
) -> list[date]:
    """Load cached public holidays as a list of date objects."""
    result = await db.execute(
        select(PublicHoliday.date).where(
            PublicHoliday.date >= date(year, 1, 1),
            PublicHoliday.date <= date(year, 12, 31),
            PublicHoliday.country_code == country_code,
        )
    )
    return [row for (row,) in result.all()]
