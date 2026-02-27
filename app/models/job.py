import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class JobStatus(str, enum.Enum):
    queued = "queued"
    parsing = "parsing"
    normalizing = "normalizing"
    enriching = "enriching"
    quality_check = "quality_check"
    forecasting = "forecasting"
    complete = "complete"
    failed = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="jobstatus"), nullable=False, default=JobStatus.queued
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gcs_raw_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    gcs_output_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    forecast_year: Mapped[int] = mapped_column(Integer, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
