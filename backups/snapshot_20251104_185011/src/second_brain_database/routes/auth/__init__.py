"""Authentication package initialization."""

from second_brain_database.routes.auth.routes import router, require_admin
from second_brain_database.routes.auth.dependencies import (
    enforce_ip_lockdown,
    enforce_user_agent_lockdown,
    enforce_all_lockdowns,
    get_current_user_dep,
)
