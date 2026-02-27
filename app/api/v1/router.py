from fastapi import APIRouter

from app.api.v1.endpoints import system

api_v1_router = APIRouter()

# System / health endpoints (status, docs metadata)
api_v1_router.include_router(system.router, tags=["System"])

# Phase 3+: upload, jobs, forecast endpoints will be registered here
