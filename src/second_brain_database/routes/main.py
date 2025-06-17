"""Main routes module for the Second Brain Database API."""
import logging
from fastapi import APIRouter, HTTPException, status, Request

from second_brain_database.database import db_manager
from second_brain_database.security_manager import security_manager

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/")
async def root(request: Request):
    await security_manager.check_rate_limit(request, "root", rate_limit_requests=10, rate_limit_period=60)
    return {
        "message": "Second Brain Database API",
        "version": "1.0.0",
        "status": "running"
    }

@router.get("/health")
async def health_check(request: Request):
    await security_manager.check_rate_limit(request, "health", rate_limit_requests=5, rate_limit_period=30)
    try:
        # Check database connection
        db_healthy = await db_manager.health_check()

        if not db_healthy:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection failed"
            )

        return {
            "status": "healthy",
            "database": "connected",
            "api": "running"
        }
    except Exception as e:
        logger.error("Health check failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unavailable"
        ) from e

@router.get("/healthz")
async def kubernetes_health(request: Request):
    await security_manager.check_rate_limit(request, "healthz", rate_limit_requests=20, rate_limit_period=60)
    return {"status": "ok"}

@router.get("/ready")
async def readiness_check(request: Request):
    await security_manager.check_rate_limit(request, "ready", rate_limit_requests=3, rate_limit_period=30)
    try:
        is_connected = await db_manager.health_check()
        if not is_connected:
            raise HTTPException(status_code=503, detail="Database not ready")
        return {"status": "ready"}
    except Exception as e:
        logger.error("Readiness check failed: %s", e)
        raise HTTPException(status_code=503, detail="Service not ready") from e

@router.get("/live")
async def liveness_check(request: Request):
    await security_manager.check_rate_limit(request, "live", rate_limit_requests=15, rate_limit_period=60)
    return {"status": "alive"}
