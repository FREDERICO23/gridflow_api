"""Celery task definitions.

The processing pipeline runs as a single task (process_job) that progresses
through each stage, updating job.status at every step.

Pipeline:  queued → parsing → normalizing → enriching → quality_check → forecasting → complete
                                                                                    ↘ failed
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.models.forecast import Forecast
from app.models.job import Job, JobStatus
from app.models.time_series import TimeSeries
from app.services.forecaster import run_forecast
from app.services.holidays import fetch_and_cache_holidays, load_holidays
from app.services.normalizer import normalize_to_hourly
from app.services.parser import parse_load_profile
from app.services.quality import generate_quality_report
from app.services.storage import storage_client
from app.services.weather import fetch_and_cache_weather, load_weather_df
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


# ── Entry point ────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="gridflow.process_job", max_retries=0)
def process_job(self, job_id: str) -> None:
    """Celery entry point — runs the full async pipeline in a new event loop."""
    asyncio.run(_run_pipeline(job_id))


# ── Async pipeline ─────────────────────────────────────────────────────────────

async def _run_pipeline(job_id: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Job).where(Job.id == uuid.UUID(job_id)))
        job = result.scalar_one_or_none()
        if job is None:
            logger.error("process_job: job %s not found", job_id)
            return

        try:
            df_parsed = await _stage_parsing(db, job)
            df_norm = await _stage_normalizing(db, job, df_parsed)

            if settings.weather_enrichment_enabled:
                await _stage_enriching(db, job)

            await _stage_quality_check(db, job, df_norm)
            await _stage_forecasting(db, job, df_norm)

            job.status = JobStatus.complete
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info("Job %s completed successfully", job_id)

        except Exception as exc:
            logger.exception("Job %s failed: %s", job_id, exc)
            job.status = JobStatus.failed
            job.error_message = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
            raise


# ── Stage helpers ──────────────────────────────────────────────────────────────

async def _set_status(db, job: Job, status: JobStatus) -> None:
    job.status = status
    await db.commit()
    logger.info("Job %s → %s", job.id, status.value)


async def _stage_parsing(db, job: Job) -> pd.DataFrame:
    await _set_status(db, job, JobStatus.parsing)
    raw_bytes = _download_raw(job)
    df_parsed = parse_load_profile(raw_bytes, job.file_name)
    await _bulk_insert_series(db, job.id, df_parsed, stage="parsed")
    await db.commit()
    return df_parsed


async def _stage_normalizing(db, job: Job, df_parsed: pd.DataFrame) -> pd.DataFrame:
    await _set_status(db, job, JobStatus.normalizing)
    df_norm = normalize_to_hourly(df_parsed, settings.default_timezone)
    await _bulk_insert_series(db, job.id, df_norm, stage="normalized")
    await db.commit()
    return df_norm


async def _stage_enriching(db, job: Job) -> None:
    await _set_status(db, job, JobStatus.enriching)
    # Cache weather for forecast year and prior year (proxy regressor for future years)
    for year in sorted({job.forecast_year, job.forecast_year - 1}):
        try:
            await fetch_and_cache_weather(db, year, settings.default_country_code)
        except Exception as exc:
            logger.warning("Weather fetch failed for %d: %s — continuing", year, exc)
    try:
        await fetch_and_cache_holidays(db, job.forecast_year, settings.default_country_code)
    except Exception as exc:
        logger.warning("Holiday fetch failed: %s — continuing without holidays", exc)


async def _stage_quality_check(db, job: Job, df_norm: pd.DataFrame) -> None:
    await _set_status(db, job, JobStatus.quality_check)
    report = generate_quality_report(df_norm, str(job.id))
    job.quality_report = report
    await db.commit()


async def _stage_forecasting(db, job: Job, df_norm: pd.DataFrame) -> None:
    await _set_status(db, job, JobStatus.forecasting)

    weather_df = None
    holidays = []
    if settings.weather_enrichment_enabled:
        weather_df = await load_weather_df(db, job.forecast_year, settings.default_country_code)
        holidays = await load_holidays(db, job.forecast_year, settings.default_country_code)

    df_forecast = run_forecast(df_norm, job.forecast_year, weather_df, holidays)
    await _bulk_insert_forecasts(db, job.id, df_forecast)

    # Upload forecast CSV to GCS (best-effort — skipped if GCS not configured)
    try:
        gcs_path = _upload_forecast_csv(df_forecast, str(job.id))
        job.gcs_output_path = gcs_path
    except RuntimeError:
        logger.warning("GCS upload skipped (not configured) for job %s", job.id)

    await db.commit()


# ── DB bulk helpers ────────────────────────────────────────────────────────────

async def _bulk_insert_series(
    db, job_id: uuid.UUID, df: pd.DataFrame, stage: str
) -> None:
    if df.empty:
        return
    rows = [
        {"ts": row.ts, "job_id": job_id, "stage": stage, "value_kw": row.value_kw}
        for row in df.itertuples(index=False)
    ]
    chunk_size = 1000
    for i in range(0, len(rows), chunk_size):
        stmt = pg_insert(TimeSeries).values(rows[i : i + chunk_size])
        stmt = stmt.on_conflict_do_nothing(index_elements=["ts", "job_id", "stage"])
        await db.execute(stmt)


async def _bulk_insert_forecasts(
    db, job_id: uuid.UUID, df: pd.DataFrame
) -> None:
    if df.empty:
        return
    rows = [
        {
            "hour_ts": row.hour_ts,
            "job_id": job_id,
            "yhat": float(row.yhat),
            "yhat_lower": float(row.yhat_lower),
            "yhat_upper": float(row.yhat_upper),
        }
        for row in df.itertuples(index=False)
    ]
    chunk_size = 1000
    for i in range(0, len(rows), chunk_size):
        stmt = pg_insert(Forecast).values(rows[i : i + chunk_size])
        stmt = stmt.on_conflict_do_nothing(index_elements=["hour_ts", "job_id"])
        await db.execute(stmt)


# ── GCS helpers ────────────────────────────────────────────────────────────────

def _download_raw(job: Job) -> bytes:
    """Download raw uploaded file from GCS."""
    if job.gcs_raw_path is None:
        raise RuntimeError(
            f"Job {job.id} has no gcs_raw_path — file was not uploaded to GCS"
        )
    path = job.gcs_raw_path
    if path.startswith("gs://"):
        path = path[5:]
    bucket, blob = path.split("/", 1)
    return storage_client.download_bytes(source_blob=blob, bucket_name=bucket)


def _upload_forecast_csv(df: pd.DataFrame, job_id: str) -> str:
    """Serialise forecast to CSV and upload to GCS output bucket."""
    import io

    buf = io.StringIO()
    df.to_csv(
        buf,
        index=False,
        columns=["hour_ts", "yhat", "yhat_lower", "yhat_upper"],
        date_format="%Y-%m-%dT%H:%M:%S%z",
    )
    csv_bytes = buf.getvalue().encode("utf-8")
    blob_name = f"jobs/{job_id}/forecast.csv"
    return storage_client.upload_file(
        file_obj=io.BytesIO(csv_bytes),
        destination_blob=blob_name,
        bucket_name=settings.gcs_bucket_output,
        content_type="text/csv",
    )
