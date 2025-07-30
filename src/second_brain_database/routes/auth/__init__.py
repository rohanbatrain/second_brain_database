"""Authentication package initialization."""

from fastapi import APIRouter

from second_brain_database.routes.auth.routes import router as auth_router
from second_brain_database.routes.auth.browser_auth import router as browser_auth_router

# Create combined router
router = APIRouter()
router.include_router(auth_router)
router.include_router(browser_auth_router)
