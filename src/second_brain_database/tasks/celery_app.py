"""Production Celery application with Redis backend.

Handles async tasks:
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
        "second_brain_database.tasks.workflow_tasks",
        "second_brain_database.tasks.document_tasks",
        "second_brain_database.tasks.rag_tasks",  # Add RAG tasks
        "second_brain_database.tasks.blog_tasks",  # Add blog tasks
    ],
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
    result_backend_transport_options={"master_name": "mymaster", "retry_policy": {"timeout": 5.0}},
    # Worker settings
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    # Task routes
    task_routes={
        "second_brain_database.tasks.workflow_tasks.*": {"queue": "workflows"},
        "second_brain_database.tasks.rag_tasks.rag_process_document": {"queue": "rag_processing"},
        "second_brain_database.tasks.rag_tasks.rag_batch_process_documents": {"queue": "rag_batch"},
        "second_brain_database.tasks.rag_tasks.rag_warm_cache": {"queue": "rag_maintenance"},
        "second_brain_database.tasks.rag_tasks.*": {"queue": "rag_default"},
        "second_brain_database.tasks.blog_tasks.*": {"queue": "blog_default"},
        "second_brain_database.tasks.blog_tasks.blog_process_post_content": {"queue": "blog_processing"},
        "second_brain_database.tasks.blog_tasks.blog_aggregate_analytics": {"queue": "blog_analytics"},
        "second_brain_database.tasks.blog_tasks.blog_send_comment_notification": {"queue": "blog_notifications"},
        "second_brain_database.tasks.blog_tasks.blog_warm_cache": {"queue": "blog_maintenance"},
        "second_brain_database.tasks.blog_tasks.blog_cleanup_expired_cache": {"queue": "blog_maintenance"},
    },
    # Task queues
    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("workflows", Exchange("workflows"), routing_key="workflows"),
        Queue("rag_processing", Exchange("rag"), routing_key="rag.processing"),
        Queue("rag_batch", Exchange("rag"), routing_key="rag.batch"),
        Queue("rag_maintenance", Exchange("rag"), routing_key="rag.maintenance"),
        Queue("rag_default", Exchange("rag"), routing_key="rag.default"),
        Queue("blog_processing", Exchange("blog"), routing_key="blog.processing"),
        Queue("blog_analytics", Exchange("blog"), routing_key="blog.analytics"),
        Queue("blog_notifications", Exchange("blog"), routing_key="blog.notifications"),
        Queue("blog_maintenance", Exchange("blog"), routing_key="blog.maintenance"),
        Queue("blog_default", Exchange("blog"), routing_key="blog.default"),
    ),
    # Beat schedule for periodic tasks
    beat_schedule={
        # Add workflow cleanup tasks here if needed
    },
)

logger.info("Celery application initialized with Redis broker")
