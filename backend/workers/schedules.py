"""
Celery Beat periodic schedule.

Import this module to register the beat schedule on the celery_app.
The schedule runs automatically when you start Celery Beat:

    celery -A backend.workers.celery_app beat --loglevel=info

Schedule:
  morning_github_report     — every weekday at 08:00 UTC
  run_health_check          — every 30 minutes
  slack_digest_morning      — every day at 09:00 UTC
  slack_digest_evening      — every day at 18:00 UTC
"""
from celery.schedules import crontab

from backend.workers.celery_app import celery_app

celery_app.conf.beat_schedule = {
    "morning-github-report": {
        "task": "workers.morning_github_report",
        "schedule": crontab(hour=8, minute=0, day_of_week="1-5"),
        "args": [],
        "kwargs": {"org_id": "default"},
    },
    "service-health-check": {
        "task": "workers.run_health_check",
        "schedule": crontab(minute="*/30"),
        "args": [],
        "kwargs": {"services": ["api", "worker", "database"]},
    },
    # Keyword alerts — scan every 15 minutes
    "slack-keyword-scan": {
        "task": "workers.scan_keyword_alerts",
        "schedule": crontab(minute="*/15"),
        "args": [],
        "kwargs": {},
    },
    # Slack digest — summarise all channel activity twice a day
    "slack-digest-morning": {
        "task": "workers.slack_channel_digest",
        "schedule": crontab(hour=9, minute=0),   # 09:00 UTC daily
        "args": [],
        "kwargs": {"org_id": "default", "hours": 12},
    },
    "slack-digest-evening": {
        "task": "workers.slack_channel_digest",
        "schedule": crontab(hour=18, minute=0),  # 18:00 UTC daily
        "args": [],
        "kwargs": {"org_id": "default", "hours": 9},
    },
}
