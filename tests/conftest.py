"""Shared pytest fixtures for the GridFlow API test suite."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client() -> AsyncClient:
    """Async test client that talks directly to the ASGI app (no network required)."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


@pytest.fixture
def api_key() -> str:
    """The API key configured in settings (defaults to 'dev-api-key' in tests)."""
    return settings.api_key


@pytest.fixture
def auth_headers(api_key: str) -> dict[str, str]:
    """Ready-made headers dict with X-API-Key set."""
    return {"X-API-Key": api_key}
