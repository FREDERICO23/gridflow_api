"""Job data endpoints — Phases 4–8.

All endpoints require X-API-Key and a valid job_id (UUID).
Returns 404 if the job does not exist.
Returns 409 if the job has not yet reached the required pipeline stage.
"""

import io
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.dependencies import require_api_key
from app.models.forecast import Forecast
from app.models.job import Job, JobStatus
from app.models.time_series import TimeSeries
from app.models.weather import WeatherObservation
from app.services.quality import generate_quality_report

logger = logging.getLogger(__name__)

router = APIRouter()

# Pipeline stage ordering — used for 409 guards
_STAGE_ORDER = [
    JobStatus.queued,
    JobStatus.parsing,
    JobStatus.normalizing,
    JobStatus.enriching,
    JobStatus.quality_check,
    JobStatus.forecasting,
    JobStatus.complete,
]


def _stage_index(s: JobStatus) -> int:
    try:
        return _STAGE_ORDER.index(s)
    except ValueError:
        return -1


async def _get_job_or_404(db: AsyncSession, job_id: uuid.UUID) -> Job:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


def _require_stage(job: Job, min_stage: JobStatus) -> None:
    """Raise 409 if the job has not yet passed *min_stage*."""
    if job.status == JobStatus.failed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job failed: {job.error_message}",
        )
    if _stage_index(job.status) < _stage_index(min_stage):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Job is at stage '{job.status.value}'; "
                f"data not yet available (requires '{min_stage.value}')"
            ),
        )


# ── Phase 4 — Parsed data ─────────────────────────────────────────────────────

@router.get(
    "/jobs/{job_id}/parsed",
    summary="Parsed time-series data",
    description="Returns the raw parsed records stored after the parse step.",
)
async def get_parsed(
    job_id: uuid.UUID,
    limit: int = 1000,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    job = await _get_job_or_404(db, job_id)
    _require_stage(job, JobStatus.normalizing)  # parsed rows exist after parsing starts

    result = await db.execute(
        select(TimeSeries)
        .where(TimeSeries.job_id == job_id, TimeSeries.stage == "parsed")
        .order_by(TimeSeries.ts)
        .limit(limit)
        .offset(offset)
    )
    rows = result.scalars().all()

    count_result = await db.execute(
        select(func.count()).where(
            TimeSeries.job_id == job_id, TimeSeries.stage == "parsed"
        )
    )
    total = count_result.scalar_one()

    data = [{"ts": r.ts.isoformat(), "value_kw": r.value_kw} for r in rows]
    date_range = (
        {"start": data[0]["ts"], "end": data[-1]["ts"]} if data else None
    )

    return {
        "job_id": str(job_id),
        "stage": "parsed",
        "total_records": total,
        "returned": len(data),
        "limit": limit,
        "offset": offset,
        "date_range": date_range,
        "data": data,
    }


# ── Phase 5 — Normalized data ─────────────────────────────────────────────────

@router.get(
    "/jobs/{job_id}/normalized",
    summary="Normalized hourly time-series",
    description="Returns the hourly-resampled, timezone-localized records.",
)
async def get_normalized(
    job_id: uuid.UUID,
    limit: int = 1000,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    job = await _get_job_or_404(db, job_id)
    _require_stage(job, JobStatus.enriching)  # normalized rows exist after normalizing

    result = await db.execute(
        select(TimeSeries)
        .where(TimeSeries.job_id == job_id, TimeSeries.stage == "normalized")
        .order_by(TimeSeries.ts)
        .limit(limit)
        .offset(offset)
    )
    rows = result.scalars().all()

    count_result = await db.execute(
        select(func.count()).where(
            TimeSeries.job_id == job_id, TimeSeries.stage == "normalized"
        )
    )
    total = count_result.scalar_one()

    data = [{"ts": r.ts.isoformat(), "value_kw": r.value_kw} for r in rows]
    date_range = (
        {"start": data[0]["ts"], "end": data[-1]["ts"]} if data else None
    )

    return {
        "job_id": str(job_id),
        "stage": "normalized",
        "timezone": settings.default_timezone,
        "total_records": total,
        "returned": len(data),
        "limit": limit,
        "offset": offset,
        "date_range": date_range,
        "data": data,
    }


# ── Phase 6 — Weather enrichment ─────────────────────────────────────────────

@router.get(
    "/jobs/{job_id}/enrichment",
    summary="Weather enrichment data",
    description="Returns cached hourly weather observations for the job's data period.",
)
async def get_enrichment(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    job = await _get_job_or_404(db, job_id)
    _require_stage(job, JobStatus.quality_check)  # enrichment done before quality_check

    # Determine date range from normalized series
    range_result = await db.execute(
        select(func.min(TimeSeries.ts), func.max(TimeSeries.ts)).where(
            TimeSeries.job_id == job_id, TimeSeries.stage == "normalized"
        )
    )
    ts_min, ts_max = range_result.one()
    if ts_min is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No normalized data found for this job",
        )

    result = await db.execute(
        select(WeatherObservation)
        .where(
            WeatherObservation.ts >= ts_min,
            WeatherObservation.ts <= ts_max,
            WeatherObservation.country_code == settings.default_country_code,
        )
        .order_by(WeatherObservation.ts)
    )
    rows = result.scalars().all()

    data = [
        {
            "ts": r.ts.isoformat(),
            "temperature_2m": r.temperature_2m,
            "solar_radiation": r.solar_radiation,
            "wind_speed_10m": r.wind_speed_10m,
            "precipitation": r.precipitation,
        }
        for r in rows
    ]

    return {
        "job_id": str(job_id),
        "country_code": settings.default_country_code,
        "forecast_year": job.forecast_year,
        "record_count": len(data),
        "data": data,
    }


# ── Phase 7 — Quality report ─────────────────────────────────────────────────

@router.get(
    "/jobs/{job_id}/quality-report",
    summary="Data quality report",
    description=(
        "Returns the quality analysis report for the normalized load profile. "
        "Served from cache if already computed during the pipeline."
    ),
)
async def get_quality_report(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    job = await _get_job_or_404(db, job_id)
    _require_stage(job, JobStatus.quality_check)

    # Return cached report if available
    if job.quality_report is not None:
        return job.quality_report

    # Compute on-the-fly if somehow missing (e.g. old jobs)
    result = await db.execute(
        select(TimeSeries)
        .where(TimeSeries.job_id == job_id, TimeSeries.stage == "normalized")
        .order_by(TimeSeries.ts)
    )
    rows = result.scalars().all()
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No normalized data found for quality report",
        )

    import pandas as pd
    df = pd.DataFrame([{"ts": r.ts, "value_kw": r.value_kw} for r in rows])
    report = generate_quality_report(df, str(job_id))

    # Cache for future requests
    job.quality_report = report
    await db.commit()

    return report


# ── Phase 8 — Forecast endpoints ─────────────────────────────────────────────

@router.get(
    "/jobs/{job_id}/forecast",
    summary="8,760-hour annual load forecast (JSON)",
    description="Returns the full forecast vector with 95% confidence intervals.",
)
async def get_forecast(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    job = await _get_job_or_404(db, job_id)
    _require_stage(job, JobStatus.complete)

    result = await db.execute(
        select(Forecast)
        .where(Forecast.job_id == job_id)
        .order_by(Forecast.hour_ts)
    )
    rows = result.scalars().all()

    data = [
        {
            "hour_ts": r.hour_ts.isoformat(),
            "yhat": r.yhat,
            "yhat_lower": r.yhat_lower,
            "yhat_upper": r.yhat_upper,
        }
        for r in rows
    ]

    return {
        "job_id": str(job_id),
        "forecast_year": job.forecast_year,
        "generated_at": job.completed_at.isoformat() if job.completed_at else None,
        "hours": len(data),
        "confidence_interval": settings.forecast_confidence_interval,
        "data": data,
    }


@router.get(
    "/jobs/{job_id}/forecast/download",
    summary="Download forecast as CSV",
    description="Streams the forecast vector as a CSV file attachment.",
    response_class=StreamingResponse,
)
async def download_forecast(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    job = await _get_job_or_404(db, job_id)
    _require_stage(job, JobStatus.complete)

    result = await db.execute(
        select(Forecast)
        .where(Forecast.job_id == job_id)
        .order_by(Forecast.hour_ts)
    )
    rows = result.scalars().all()

    buf = io.StringIO()
    buf.write("hour_ts,yhat,yhat_lower,yhat_upper\n")
    for r in rows:
        buf.write(
            f"{r.hour_ts.isoformat()},{r.yhat:.4f},{r.yhat_lower:.4f},{r.yhat_upper:.4f}\n"
        )

    csv_bytes = buf.getvalue().encode("utf-8")

    return StreamingResponse(
        content=io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="forecast_{job_id}.csv"'
        },
    )
