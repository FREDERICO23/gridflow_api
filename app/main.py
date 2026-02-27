import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.session import engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    yield
    logger.info("Shutting down — disposing DB engine")
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Energy Load Platform API — ingests raw energy consumption data and produces "
        "an 8,760-hour annual load forecast vector with confidence intervals."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Root liveness check (no auth required) ─────────────────────────────────────
@app.get("/health", tags=["System"], summary="Liveness check")
async def health():
    """Returns 200 OK if the service is running."""
    return {"status": "ok"}


# ── Versioned API routes ────────────────────────────────────────────────────────
from app.api.v1.router import api_v1_router  # noqa: E402 — imported after app creation

app.include_router(api_v1_router, prefix="/api/v1")
