# Import all ORM models here so Alembic's env.py picks up their metadata automatically.
from app.models.forecast import Forecast
from app.models.job import Job, JobStatus
from app.models.time_series import TimeSeries
from app.models.weather import PublicHoliday, WeatherObservation

__all__ = ["Job", "JobStatus", "TimeSeries", "Forecast", "WeatherObservation", "PublicHoliday"]
