"""Routes package initialization."""

from second_brain_database.routes.auth import router as auth_router
from second_brain_database.routes.family import router as family_router
from second_brain_database.routes.main import router as main_router
from second_brain_database.routes.profile.routes import router as profile_router
