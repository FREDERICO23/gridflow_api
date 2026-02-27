import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TimeSeries(Base):
    """Hourly energy load time-series data, partitioned as a TimescaleDB hypertable.

    stage='parsed'     — original records written after the parse step
    stage='normalized' — hourly-resampled records written after the normalize step
    """

    __tablename__ = "time_series"

    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    stage: Mapped[str] = mapped_column(
        String(20), primary_key=True, nullable=False, default="normalized"
    )
    value_kw: Mapped[float] = mapped_column(Float, nullable=False)
