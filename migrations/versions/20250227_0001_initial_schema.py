"""Initial schema — jobs, time_series, forecasts, weather_observations, public_holidays.

Revision ID: 0001
Revises:
Create Date: 2025-02-27 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. jobs ────────────────────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "parsing",
                "normalizing",
                "enriching",
                "quality_check",
                "forecasting",
                "complete",
                "failed",
                name="jobstatus",
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("gcs_raw_path", sa.String(512), nullable=True),
        sa.Column("gcs_output_path", sa.String(512), nullable=True),
        sa.Column("forecast_year", sa.Integer, nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("quality_report", postgresql.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── 2. time_series (TimescaleDB hypertable on ts) ─────────────────────────
    op.create_table(
        "time_series",
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.String(20), nullable=False, server_default="normalized"),
        sa.Column("value_kw", sa.Float, nullable=False),
        sa.PrimaryKeyConstraint("ts", "job_id", "stage"),
    )
    op.execute(
        "SELECT create_hypertable('time_series', 'ts', if_not_exists => TRUE)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_time_series_job_stage_ts "
        "ON time_series (job_id, stage, ts DESC)"
    )

    # ── 3. forecasts (TimescaleDB hypertable on hour_ts) ──────────────────────
    op.create_table(
        "forecasts",
        sa.Column("hour_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("yhat", sa.Float, nullable=False),
        sa.Column("yhat_lower", sa.Float, nullable=False),
        sa.Column("yhat_upper", sa.Float, nullable=False),
        sa.PrimaryKeyConstraint("hour_ts", "job_id"),
    )
    op.execute(
        "SELECT create_hypertable('forecasts', 'hour_ts', if_not_exists => TRUE)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_forecasts_job_hour_ts "
        "ON forecasts (job_id, hour_ts ASC)"
    )

    # ── 4. weather_observations (TimescaleDB hypertable on ts) ────────────────
    op.create_table(
        "weather_observations",
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("country_code", sa.String(10), nullable=False),
        sa.Column("temperature_2m", sa.Float, nullable=True),
        sa.Column("solar_radiation", sa.Float, nullable=True),
        sa.Column("wind_speed_10m", sa.Float, nullable=True),
        sa.Column("precipitation", sa.Float, nullable=True),
        sa.PrimaryKeyConstraint("ts", "country_code"),
    )
    op.execute(
        "SELECT create_hypertable('weather_observations', 'ts', if_not_exists => TRUE)"
    )

    # ── 5. public_holidays (regular table, cached per year+country) ───────────
    op.create_table(
        "public_holidays",
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("country_code", sa.String(10), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint("date", "country_code"),
    )


def downgrade() -> None:
    op.drop_table("public_holidays")
    op.drop_table("weather_observations")
    op.drop_table("forecasts")
    op.drop_table("time_series")
    op.drop_table("jobs")
    op.execute("DROP TYPE IF EXISTS jobstatus")
