"""Google Cloud Storage client with lazy initialisation.

The client defers GCS library imports and credential loading until the first
actual call, so the API starts cleanly even when GCS is not yet configured
(local development, CI without credentials, etc.).
"""

import logging
from typing import BinaryIO

from app.config import settings

logger = logging.getLogger(__name__)


class GCSClient:
    """Thin wrapper around google-cloud-storage with lazy initialisation."""

    def __init__(self) -> None:
        self._client = None

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _get_client(self):
        """Return the Storage client, initialising it on first call."""
        if self._client is not None:
            return self._client

        try:
            from google.cloud import storage  # noqa: PLC0415

            if settings.gcs_credentials_path:
                self._client = storage.Client.from_service_account_json(
                    settings.gcs_credentials_path
                )
                logger.info("GCS client initialised from service account file")
            else:
                # Falls back to Application Default Credentials (ADC):
                # gcloud auth application-default login  OR  GOOGLE_APPLICATION_CREDENTIALS env var
                self._client = storage.Client()
                logger.info("GCS client initialised via Application Default Credentials")

        except Exception as exc:
            logger.warning("GCS client could not be initialised: %s", exc)

        return self._client

    # ── Public API ─────────────────────────────────────────────────────────────

    async def check_connection(self) -> str:
        """Return 'ok', 'error', or 'not_configured' for the /status endpoint."""
        client = self._get_client()
        if client is None:
            return "not_configured"
        try:
            client.get_bucket(settings.gcs_bucket_raw)
            return "ok"
        except Exception as exc:
            logger.warning("GCS connection check failed: %s", exc)
            return "error"

    def upload_file(
        self,
        file_obj: BinaryIO,
        destination_blob: str,
        bucket_name: str | None = None,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a file-like object to GCS.

        Returns the full GCS path: ``gs://<bucket>/<blob>``.
        Raises RuntimeError if GCS is not configured.
        """
        client = self._get_client()
        if client is None:
            raise RuntimeError("GCS client is not configured — check credentials")

        target_bucket = bucket_name or settings.gcs_bucket_raw
        blob = client.bucket(target_bucket).blob(destination_blob)
        blob.upload_from_file(file_obj, content_type=content_type)
        gcs_path = f"gs://{target_bucket}/{destination_blob}"
        logger.info("Uploaded to %s", gcs_path)
        return gcs_path

    def download_bytes(
        self,
        source_blob: str,
        bucket_name: str | None = None,
    ) -> bytes:
        """Download a blob and return its raw bytes."""
        client = self._get_client()
        if client is None:
            raise RuntimeError("GCS client is not configured — check credentials")

        target_bucket = bucket_name or settings.gcs_bucket_output
        blob = client.bucket(target_bucket).blob(source_blob)
        return blob.download_as_bytes()

    def get_signed_url(
        self,
        blob_name: str,
        bucket_name: str | None = None,
        expiration_minutes: int = 60,
    ) -> str:
        """Generate a signed URL for temporary read access to a blob."""
        import datetime

        client = self._get_client()
        if client is None:
            raise RuntimeError("GCS client is not configured — check credentials")

        target_bucket = bucket_name or settings.gcs_bucket_output
        blob = client.bucket(target_bucket).blob(blob_name)
        return blob.generate_signed_url(
            expiration=datetime.timedelta(minutes=expiration_minutes),
            method="GET",
        )


# Module-level singleton used throughout the application
storage_client = GCSClient()
