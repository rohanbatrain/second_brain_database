#!/usr/bin/env python3
"""Start Celery Beat for periodic tasks."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from second_brain_database.tasks.celery_app import celery_app
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[CeleryBeat]")

if __name__ == "__main__":
    logger.info("Starting Celery Beat scheduler...")

    celery_app.start([
        "beat",
        "--loglevel=info",
    ])
