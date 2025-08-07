# Family management module

from fastapi import APIRouter
from .routes import router as family_router
from .sbd_routes import router as sbd_router

# Combine all family-related routers
router = APIRouter()
router.include_router(family_router)
router.include_router(sbd_router)

__all__ = ["router"]