"""Main routes module for the Second Brain Database API."""
import logging
from fastapi import APIRouter, HTTPException, status

from second_brain_database.database import db_manager

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/")
async def root():
    """Root endpoint returning basic API information."""
    return {
        "message": "Second Brain Database API",
        "version": "1.0.0",
        "status": "running"
    }

@router.get("/health")
async def health_check():
    """Health check endpoint to verify API and database connectivity."""
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
async def kubernetes_health():
    """Kubernetes health check endpoint"""
    return {"status": "ok"}

@router.get("/ready")
async def readiness_check():
    """Readiness check - verifies database connectivity"""
    try:
        is_connected = await db_manager.health_check()
        if not is_connected:
            raise HTTPException(status_code=503, detail="Database not ready")
        return {"status": "ready"}
    except Exception as e:
        logger.error("Readiness check failed: %s", e)
        raise HTTPException(status_code=503, detail="Service not ready") from e

@router.get("/live")
async def liveness_check():
    """Liveness check - service is alive and responsive"""
    return {"status": "alive"}
