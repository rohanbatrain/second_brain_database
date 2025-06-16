from fastapi import APIRouter, HTTPException
from second_brain_database.database import db_manager
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/health")
async def health_check():
    """Basic health check - always returns OK if service is running"""
    return {"status": "ok"}

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