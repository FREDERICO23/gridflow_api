from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Application ────────────────────────────────────────────────────────────
    app_name: str = "GridFlow API"
    app_version: str = "0.1.0"
    debug: bool = False

    # ── Authentication ─────────────────────────────────────────────────────────
    api_key: str = "dev-api-key"

    # ── Database ───────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://gridflow:gridflow@db:5432/gridflow"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalise_database_url(cls, v: str) -> str:
        """Accept postgres:// or postgresql:// and rewrite to postgresql+asyncpg://."""
        for prefix in ("postgresql://", "postgres://"):
            if v.startswith(prefix):
                return "postgresql+asyncpg://" + v[len(prefix):]
        return v

    # ── Redis / Celery ─────────────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"

    # ── Google Cloud Storage ───────────────────────────────────────────────────
    gcs_bucket_raw: str = "gridflow-raw-uploads"
    gcs_bucket_output: str = "gridflow-forecast-outputs"
    gcs_credentials_path: str | None = None   # path to service-account JSON file
    gcs_credentials_json: str | None = None   # raw JSON content (alternative to file)

    # ── Processing Defaults ────────────────────────────────────────────────────
    # Germany as primary market (Phase 1 confirmed)
    default_timezone: str = "Europe/Berlin"
    default_country_code: str = "DE"

    # Confidence interval — fixed at 95% (Q8: standard, not user-configurable)
    forecast_confidence_interval: float = 0.95

    # Weather enrichment optional (confirmed in spec Q4)
    weather_enrichment_enabled: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
