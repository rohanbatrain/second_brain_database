#!/usr/bin/env python3
"""Start Flower monitoring dashboard."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

if __name__ == "__main__":
    os.system("celery -A second_brain_database.tasks.celery_app flower --port=5555")
