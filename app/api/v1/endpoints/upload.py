"""Upload endpoint — Phase 3.

POST /upload  — accepts a load-profile file + forecast_year, creates a Job,
               uploads to GCS, and dispatches the Celery processing pipeline.

GET  /upload/{job_id}/status — poll job processing status.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.dependencies import require_api_key
from app.models.job import Job, JobStatus
from app.services.storage import storage_client
from app.workers.tasks import process_job

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a load-profile file",
    description=(
        "Accepts a CSV or Excel load-profile file plus a forecast year. "
        "Creates a processing job, uploads the raw file to GCS, and dispatches "
        "the async Celery pipeline. Poll /upload/{job_id}/status for progress."
    ),
)
async def upload_file(
    file: UploadFile,
    forecast_year: int = Form(..., ge=2000, le=2100, description="Year to forecast"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    # ── Validate file extension ────────────────────────────────────────────────
    filename = file.filename or "upload"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(_ALLOWED_EXTENSIONS)}",
        )

    # ── Read file into memory ─────────────────────────────────────────────────
    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty",
        )

    # ── Create Job record ─────────────────────────────────────────────────────
    job_id = uuid.uuid4()
    gcs_blob = f"jobs/{job_id}/{filename}"
    gcs_raw_path: str | None = None

    try:
        import io
        gcs_raw_path = storage_client.upload_file(
            file_obj=io.BytesIO(data),
            destination_blob=gcs_blob,
            bucket_name=settings.gcs_bucket_raw,
            content_type=file.content_type or "application/octet-stream",
        )
    except RuntimeError:
        # GCS not configured (local dev) — store None, pipeline will use in-memory path
        logger.warning("GCS not configured; job %s will use in-memory file bytes", job_id)

    job = Job(
        id=job_id,
        status=JobStatus.queued,
        file_name=filename,
        file_size_bytes=len(data),
        gcs_raw_path=gcs_raw_path,
        forecast_year=forecast_year,
    )
    db.add(job)
    await db.commit()

    # ── Dispatch Celery task ──────────────────────────────────────────────────
    process_job.delay(str(job_id))
    logger.info("Dispatched process_job for job_id=%s", job_id)

    return {
        "job_id": str(job_id),
        "status": JobStatus.queued,
        "message": "Job created. Poll /api/v1/upload/{job_id}/status for progress.",
    }


@router.get(
    "/upload/{job_id}/status",
    summary="Poll job processing status",
)
async def get_upload_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return {
        "job_id": str(job.id),
        "status": job.status,
        "file_name": job.file_name,
        "forecast_year": job.forecast_year,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_message": job.error_message,
    }
