#!/usr/bin/env python3
"""Start Flower monitoring dashboard."""
import sys
import os
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

if __name__ == "__main__":
    try:
        subprocess.run([
            "celery", "-A", "second_brain_database.tasks.celery_app",
            "flower", "--port=5555"
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to start Flower: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("Celery not found. Please install celery first.")
        sys.exit(1)
