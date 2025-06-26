"""
Main application module for Second Brain Database API.

This module sets up the FastAPI application with proper lifespan management,
database connections, and routing configuration.
"""
from contextlib import asynccontextmanager
import asyncio

import uvicorn
from fastapi import FastAPI, HTTPException

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.routes import auth_router, main_router
from second_brain_database.routes.auth.periodics.cleanup import periodic_2fa_cleanup
from second_brain_database.routes.auth.periodics.redis_flag_sync import periodic_blocklist_whitelist_reconcile
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting up FastAPI application...")
    try:
        await db_manager.connect()
        logger.info("Database connection established")
    except Exception as e:
        logger.error("Failed to connect to database: %s", e)
        raise HTTPException(
            status_code=503,
            detail='Service not ready: Database connection failed'
        ) from e

    # Start periodic 2FA cleanup task
    cleanup_task = asyncio.create_task(periodic_2fa_cleanup())
    # Start periodic blocklist/whitelist reconciliation task
    reconcile_task = asyncio.create_task(periodic_blocklist_whitelist_reconcile())

    yield

    # Shutdown
    logger.info("Shutting down FastAPI application...")
    cleanup_task.cancel()
    reconcile_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    try:
        await reconcile_task
    except asyncio.CancelledError:
        pass
    await db_manager.disconnect()
    logger.info("Database connection closed")

# Create FastAPI app with lifespan
app = FastAPI(
    title="Second Brain Database API",
    description="A FastAPI application for second brain database management",
    version="1.0.0",
    lifespan=lifespan
)
app.include_router(auth_router)
app.include_router(main_router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
