#!/usr/bin/env python3
"""Production LiveKit Voice Worker startup script.

NOTE: Voice worker functionality is currently disabled.
LangChain/LangGraph integration has been removed.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[VoiceWorkerStartup]")

if __name__ == "__main__":
    logger.warning("Voice Worker is DISABLED - LangChain/LangGraph integration removed")
    logger.warning("This script is kept for reference but does not start any services")
    logger.info("To re-enable voice functionality, implement alternative AI integration")
    sys.exit(0)
