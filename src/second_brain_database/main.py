"""
Main application module for Second Brain Database API.

This module sets up the FastAPI application with proper lifespan management,
database connections, and routing configuration.
"""
from contextlib import asynccontextmanager
import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes import auth_router, main_router
from second_brain_database.routes.auth.periodics.cleanup import (
    periodic_2fa_cleanup,
    periodic_avatar_rental_cleanup,
    periodic_banner_rental_cleanup,
    periodic_email_verification_token_cleanup,
    periodic_session_cleanup,
    periodic_trusted_ip_lockdown_code_cleanup,
    periodic_admin_session_token_cleanup,
)
from second_brain_database.routes.auth.periodics.redis_flag_sync import periodic_blocklist_whitelist_reconcile
from second_brain_database.routes.sbd_tokens.routes import router as sbd_tokens_router
from second_brain_database.routes.themes.routes import router as themes_router
from second_brain_database.routes.shop.routes import router as shop_router
from second_brain_database.routes.avatars.routes import router as avatars_router
from second_brain_database.routes.banners.routes import router as banners_router

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

    # Start periodic cleanup tasks
    cleanup_task = asyncio.create_task(periodic_2fa_cleanup())
    reconcile_task = asyncio.create_task(periodic_blocklist_whitelist_reconcile())
    avatar_cleanup_task = asyncio.create_task(periodic_avatar_rental_cleanup())
    banner_cleanup_task = asyncio.create_task(periodic_banner_rental_cleanup())
    email_verif_cleanup_task = asyncio.create_task(periodic_email_verification_token_cleanup())
    session_cleanup_task = asyncio.create_task(periodic_session_cleanup())
    trusted_ip_cleanup_task = asyncio.create_task(periodic_trusted_ip_lockdown_code_cleanup())
    admin_session_cleanup_task = asyncio.create_task(periodic_admin_session_token_cleanup())

    yield

    # Shutdown
    logger.info("Shutting down FastAPI application...")
    cleanup_task.cancel()
    reconcile_task.cancel()
    avatar_cleanup_task.cancel()
    banner_cleanup_task.cancel()
    email_verif_cleanup_task.cancel()
    session_cleanup_task.cancel()
    trusted_ip_cleanup_task.cancel()
    admin_session_cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    try:
        await reconcile_task
    except asyncio.CancelledError:
        pass
    try:
        await avatar_cleanup_task
    except asyncio.CancelledError:
        pass
    try:
        await banner_cleanup_task
    except asyncio.CancelledError:
        pass
    try:
        await email_verif_cleanup_task
    except asyncio.CancelledError:
        pass
    try:
        await session_cleanup_task
    except asyncio.CancelledError:
        pass
    try:
        await trusted_ip_cleanup_task
    except asyncio.CancelledError:
        pass
    try:
        await admin_session_cleanup_task
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
app.include_router(sbd_tokens_router)
app.include_router(themes_router)
app.include_router(shop_router)
app.include_router(avatars_router)
app.include_router(banners_router)

# Instrumentator for Prometheus metrics
Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_respect_env_var=False,
    should_instrument_requests_inprogress=True,
).add().instrument(app).expose(app, include_in_schema=False, endpoint="/metrics")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
