# Family management module

from fastapi import APIRouter
from .routes import router as family_router
from .health import router as health_router
from .admin_health import router as admin_health_router

# Combine all family-related routers
router = APIRouter()
router.include_router(family_router)
router.include_router(health_router)
router.include_router(admin_health_router)  # Admin-only sensitive endpoints

__all__ = ["router"]
