from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WeatherObservation(Base):
    """Hourly weather data cached from Open-Meteo, stored as a TimescaleDB hypertable.

    Keyed by (ts, country_code) so a single row exists per hour per country.
    Re-used across all jobs for the same country/year — never fetched twice.
    """

    __tablename__ = "weather_observations"

    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    country_code: Mapped[str] = mapped_column(
        String(10), primary_key=True, nullable=False
    )
    temperature_2m: Mapped[float | None] = mapped_column(Float, nullable=True)
    solar_radiation: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed_10m: Mapped[float | None] = mapped_column(Float, nullable=True)
    precipitation: Mapped[float | None] = mapped_column(Float, nullable=True)


class PublicHoliday(Base):
    """Public holidays cached from Nager.Date, keyed by (date, country_code)."""

    __tablename__ = "public_holidays"

    date: Mapped[date] = mapped_column(Date, primary_key=True, nullable=False)
    country_code: Mapped[str] = mapped_column(
        String(10), primary_key=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
