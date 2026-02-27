import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.dependencies import require_api_key
from app.services.storage import storage_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/status",
    summary="Service status",
    description=(
        "Returns service version, database connection status, and storage connectivity. "
        "Requires a valid X-API-Key header."
    ),
)
async def get_status(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    # ── DB liveness ────────────────────────────────────────────────────────────
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("DB health check failed: %s", exc)
        db_status = "error"

    # ── GCS liveness ───────────────────────────────────────────────────────────
    storage_status = await storage_client.check_connection()

    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "db": db_status,
        "storage": storage_status,
        "config": {
            "default_timezone": settings.default_timezone,
            "default_country_code": settings.default_country_code,
            "forecast_confidence_interval": settings.forecast_confidence_interval,
            "weather_enrichment_enabled": settings.weather_enrichment_enabled,
            "max_upload_size_mb": settings.max_upload_size_bytes // (1024 * 1024),
        },
    }
