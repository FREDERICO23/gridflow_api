from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import settings

# Declares the X-API-Key header in OpenAPI schema
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str = Security(api_key_scheme)) -> str:
    """FastAPI dependency — validates the X-API-Key header on every protected endpoint."""
    if not api_key or api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return api_key
