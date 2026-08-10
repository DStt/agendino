"""
Celery configuration and initialization
"""
import os
from celery import Celery

# Create Celery app
celery_app = Celery("agendino")

# Configure Celery with Redis as broker and backend
redis_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
celery_app.conf.update(
    broker_url=redis_url,
    result_backend=redis_url,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes hard limit
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit (triggers SoftTimeLimitExceeded)
    result_expires=3600,  # Results expire after 1 hour
)

# Auto-discover tasks from the celery_tasks module
celery_app.autodiscover_tasks(["celery_tasks"])
