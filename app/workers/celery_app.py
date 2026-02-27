from celery import Celery

from app.config import settings

celery_app = Celery(
    "gridflow",
    broker=settings.redis_url,
    backend=settings.redis_url,
    # Task modules to auto-discover; tasks.py will be populated in Phase 3
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Reliability
    task_track_started=True,   # Expose STARTED state (maps to "parsing", "normalising", …)
    task_acks_late=True,       # Ack only after task completes (prevents message loss on crash)
    worker_prefetch_multiplier=1,  # One task at a time per worker thread (heavy CPU work)
    # Result expiry — keep results for 24 hours
    result_expires=86400,
)
