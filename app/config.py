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

    # ── Redis / Celery ─────────────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"

    # ── Google Cloud Storage ───────────────────────────────────────────────────
    gcs_bucket_raw: str = "gridflow-raw-uploads"
    gcs_bucket_output: str = "gridflow-forecast-outputs"
    gcs_credentials_path: str | None = None  # None → use ADC

    # ── Processing Defaults ────────────────────────────────────────────────────
    # Germany as primary market (Phase 1 confirmed)
    default_timezone: str = "Europe/Berlin"
    default_country_code: str = "DE"

    # 200 MB upload limit
    max_upload_size_bytes: int = 200 * 1024 * 1024

    # Confidence interval — configurable, default 95% (confirmed in spec Q8)
    forecast_confidence_interval: float = 0.95

    # Weather enrichment optional (confirmed in spec Q4)
    weather_enrichment_enabled: bool = True

    # Imputed flag visible in downloads (confirmed in spec Q6)
    include_imputed_flag_in_output: bool = True

    @field_validator("forecast_confidence_interval")
    @classmethod
    def validate_confidence_interval(cls, v: float) -> float:
        if not 0.50 <= v <= 0.99:
            raise ValueError("forecast_confidence_interval must be between 0.50 and 0.99")
        return v

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
