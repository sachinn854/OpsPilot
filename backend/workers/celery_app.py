"""
Celery application instance.

Broker + result backend both use the same Redis instance as the API.
Import `celery_app` anywhere to register tasks or schedule them.

Start the worker:
    celery -A backend.workers.celery_app worker --loglevel=info

Start the scheduler (Celery Beat):
    celery -A backend.workers.celery_app beat --loglevel=info
"""
from celery import Celery

from backend.config import settings

celery_app = Celery(
    "copilot",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "backend.workers.tasks",
        "backend.workers.webhook_handler",
        "backend.workers.schedules",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Prevent tasks from running more than 10 minutes.
    task_time_limit=600,
    task_soft_time_limit=540,
)
