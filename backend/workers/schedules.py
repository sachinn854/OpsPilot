"""
Celery Beat periodic schedule.

Import this module to register the beat schedule on the celery_app.
The schedule runs automatically when you start Celery Beat:

    celery -A backend.workers.celery_app beat --loglevel=info

Schedule:
  morning_github_report — every weekday at 08:00 UTC
  run_health_check      — every 30 minutes
"""
from celery.schedules import crontab

from backend.workers.celery_app import celery_app

celery_app.conf.beat_schedule = {
    "morning-github-report": {
        "task": "workers.morning_github_report",
        "schedule": crontab(hour=8, minute=0, day_of_week="1-5"),  # Mon–Fri 08:00 UTC
        "args": [],
        "kwargs": {"org_id": "default"},
    },
    "service-health-check": {
        "task": "workers.run_health_check",
        "schedule": crontab(minute="*/30"),  # every 30 min
        "args": [],
        "kwargs": {"services": ["api", "worker", "database"]},
    },
}
