"""Production Celery application with Redis backend.

Handles async tasks:
- Voice transcription processing
- AI response generation
- Background analytics
- Long-running workflows
"""
from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue

from ..config import settings
from ..managers.logging_manager import get_logger

logger = get_logger(prefix="[CeleryApp]")

# Initialize Celery with Redis broker and backend
celery_app = Celery(
    "second_brain",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "second_brain_database.tasks.ai_tasks",
        "second_brain_database.tasks.voice_tasks",
        "second_brain_database.tasks.workflow_tasks",
        "second_brain_database.tasks.document_tasks",
    ]
)

# Celery Configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=300,  # 5 minutes hard limit
    task_soft_time_limit=240,  # 4 minutes soft limit

    # Result backend
    result_expires=3600,  # 1 hour
    result_backend_transport_options={
        "master_name": "mymaster",
        "retry_policy": {
            "timeout": 5.0
        }
    },

    # Worker settings
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,

    # Task routes
    task_routes={
        "second_brain_database.tasks.ai_tasks.*": {"queue": "ai"},
        "second_brain_database.tasks.voice_tasks.*": {"queue": "voice"},
        "second_brain_database.tasks.workflow_tasks.*": {"queue": "workflows"},
    },

    # Task queues
    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("ai", Exchange("ai"), routing_key="ai"),
        Queue("voice", Exchange("voice"), routing_key="voice"),
        Queue("workflows", Exchange("workflows"), routing_key="workflows"),
    ),

    # Beat schedule for periodic tasks
    beat_schedule={
        "cleanup-expired-sessions": {
            "task": "second_brain_database.tasks.ai_tasks.cleanup_expired_sessions",
            "schedule": crontab(minute="*/30"),  # Every 30 minutes
        },
        "sync-langsmith-traces": {
            "task": "second_brain_database.tasks.ai_tasks.sync_langsmith_traces",
            "schedule": crontab(minute="*/15"),  # Every 15 minutes
        },
    },
)

logger.info("Celery application initialized with Redis broker")
