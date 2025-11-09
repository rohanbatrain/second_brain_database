"""
Shop MCP Resources

Comprehensive information resources for shop entities and digital assets.
Provides shop information, asset listings, and purchase data through MCP resources.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional

from ....config import settings
from ....managers.logging_manager import get_logger
from ..context import create_mcp_audit_trail
from ..exceptions import MCPAuthorizationError, MCPValidationError
from ..modern_server import mcp
from ..security import get_mcp_user_context

logger = get_logger(prefix="[MCP_ShopResources]")


@mcp.resource("shop://assets/avatars", tags={"production", "resources", "secure", "shop"})
async def get_shop_avatars_resource() -> str:
    """
    Get available shop avatars as a resource.

    Returns:
        JSON string containing available avatars
    """
    try:
        user_context = get_mcp_user_context()

        # Mock avatar data - replace with actual shop integration
        avatars = [
            {
                "id": "avatar_001",
                "name": "Professional Avatar",
                "price": 50,
                "category": "professional",
                "preview_url": "/assets/avatars/professional_preview.png",
            },
            {
                "id": "avatar_002",
                "name": "Casual Avatar",
                "price": 25,
                "category": "casual",
                "preview_url": "/assets/avatars/casual_preview.png",
            },
        ]

        result = {
            "avatars": avatars,
            "total_count": len(avatars),
            "resource_type": "shop_avatars",
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        await create_mcp_audit_trail(
            operation="get_shop_avatars_resource",
            user_context=user_context,
            resource_type="shop",
            resource_id="avatars",
            metadata={"avatar_count": len(avatars)},
        )

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error("Failed to get shop avatars resource: %s", e)
        return json.dumps({"error": f"Failed to retrieve shop avatars: {str(e)}"}, indent=2)


@mcp.resource("shop://assets/themes", tags={"production", "resources", "secure", "shop"})
async def get_shop_themes_resource() -> str:
    """
    Get available shop themes as a resource.

    Returns:
        JSON string containing available themes
    """
    try:
        user_context = get_mcp_user_context()

        # Mock theme data - replace with actual shop integration
        themes = [
            {
                "id": "theme_001",
                "name": "Dark Professional",
                "price": 30,
                "category": "dark",
                "preview_url": "/assets/themes/dark_professional_preview.png",
            },
            {
                "id": "theme_002",
                "name": "Light Minimal",
                "price": 20,
                "category": "light",
                "preview_url": "/assets/themes/light_minimal_preview.png",
            },
        ]

        result = {
            "themes": themes,
            "total_count": len(themes),
            "resource_type": "shop_themes",
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        await create_mcp_audit_trail(
            operation="get_shop_themes_resource",
            user_context=user_context,
            resource_type="shop",
            resource_id="themes",
            metadata={"theme_count": len(themes)},
        )

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error("Failed to get shop themes resource: %s", e)
        return json.dumps({"error": f"Failed to retrieve shop themes: {str(e)}"}, indent=2)
