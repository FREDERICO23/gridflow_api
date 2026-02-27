from fastapi import APIRouter

from app.api.v1.endpoints import jobs, system, upload

api_v1_router = APIRouter()

# System / health endpoints (status, docs metadata)
api_v1_router.include_router(system.router, tags=["System"])

# File upload + job status polling
api_v1_router.include_router(upload.router, tags=["Upload"])

# Job data: parsed, normalized, enrichment, quality-report, forecast
api_v1_router.include_router(jobs.router, tags=["Jobs"])
