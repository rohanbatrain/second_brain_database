# Family management module

from fastapi import APIRouter

from .admin_health import router as admin_health_router
from .health import router as health_router
from .routes import router as family_router
from .extended_routes import router as extended_router # Import extended_routes

# Combine all family-related routers
router = APIRouter()
router.include_router(family_router)
router.include_router(health_router)
router.include_router(admin_health_router)  # Admin-only sensitive endpoints
router.include_router(extended_router) # Include extended_routes

__all__ = ["router"]
