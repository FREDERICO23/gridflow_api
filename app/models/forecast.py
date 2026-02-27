import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Forecast(Base):
    """8,760-hour annual load forecast, stored as a TimescaleDB hypertable."""

    __tablename__ = "forecasts"

    hour_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    yhat: Mapped[float] = mapped_column(Float, nullable=False)
    yhat_lower: Mapped[float] = mapped_column(Float, nullable=False)
    yhat_upper: Mapped[float] = mapped_column(Float, nullable=False)
