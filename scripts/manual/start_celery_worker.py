#!/usr/bin/env python3
"""Start Celery worker for async task processing."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from second_brain_database.tasks.celery_app import celery_app
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[CeleryWorker]")

if __name__ == "__main__":
    logger.info("Starting Celery worker...")
    logger.info("Queues: default, ai, voice, workflows")

    celery_app.worker_main([
        "worker",
        "--loglevel=info",
        "--concurrency=4",
        "--queues=default,ai,voice,workflows",
        "-n", "worker@%h",
    ])
