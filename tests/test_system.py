"""Tests for system / health endpoints (Phase 1)."""

import pytest
from httpx import AsyncClient

from app.config import settings


# ── GET /health ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_requires_no_auth(client: AsyncClient):
    """Health check must be accessible without an API key."""
    response = await client.get("/health")
    assert response.status_code == 200


# ── GET /api/v1/status (auth required) ────────────────────────────────────────

@pytest.mark.asyncio
async def test_status_rejects_missing_key(client: AsyncClient):
    response = await client.get("/api/v1/status")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_status_rejects_wrong_key(client: AsyncClient):
    response = await client.get(
        "/api/v1/status",
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_status_with_valid_key(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/status", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["service"] == settings.app_name
    assert data["version"] == settings.app_version

    # DB and storage may be unavailable in CI — accept any valid status string
    assert data["db"] in ("ok", "error")
    assert data["storage"] in ("ok", "error", "not_configured")

    # Config block should reflect Germany defaults
    cfg = data["config"]
    assert cfg["default_timezone"] == "Europe/Berlin"
    assert cfg["default_country_code"] == "DE"
    assert cfg["forecast_confidence_interval"] == settings.forecast_confidence_interval
    assert cfg["max_upload_size_mb"] == 200


# ── GET /docs and /redoc (OpenAPI UI) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_openapi_docs_accessible(client: AsyncClient):
    response = await client.get("/docs")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_redoc_accessible(client: AsyncClient):
    response = await client.get("/redoc")
    assert response.status_code == 200


# ── Config validation ──────────────────────────────────────────────────────────

def test_confidence_interval_default():
    assert settings.forecast_confidence_interval == 0.95


def test_default_market_is_germany():
    assert settings.default_timezone == "Europe/Berlin"
    assert settings.default_country_code == "DE"


def test_max_upload_size_is_200mb():
    assert settings.max_upload_size_bytes == 200 * 1024 * 1024


def test_imputed_flag_visible_in_output():
    assert settings.include_imputed_flag_in_output is True
