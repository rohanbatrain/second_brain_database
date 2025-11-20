"""
Test MCP Resources

Test resources for MCP development and validation.
Provides test data and mock resources for development and testing purposes.
"""

from datetime import datetime
import json
from typing import Any, Dict, List, Optional

from ....config import settings
from ....managers.logging_manager import get_logger
from ..context import create_mcp_audit_trail
from ..modern_server import mcp
from ..security import get_mcp_user_context

logger = get_logger(prefix="[MCP_TestResources]")


@mcp.resource("test://simple", tags={"development", "resources", "testing"})
async def get_simple_test_resource() -> str:
    """
    Get a simple test resource.

    Returns:
        JSON string containing test data
    """
    try:
        user_context = get_mcp_user_context()

        result = {
            "message": "Hello from MCP test resource!",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_context.user_id,
            "resource_type": "test_simple",
        }

        await create_mcp_audit_trail(
            operation="get_simple_test_resource",
            user_context=user_context,
            resource_type="test",
            resource_id="simple",
            metadata={"test_resource": True},
        )

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error("Failed to get simple test resource: %s", e)
        return json.dumps({"error": f"Failed to retrieve test resource: {str(e)}"}, indent=2)


@mcp.resource("test://data/{data_type}", tags={"development", "resources", "testing"})
async def get_test_data_resource(data_type: str) -> str:
    """
    Get test data resource by type.

    Args:
        data_type: Type of test data to retrieve

    Returns:
        JSON string containing test data
    """
    try:
        user_context = get_mcp_user_context()

        # Generate different test data based on type
        test_data = {}

        if data_type == "users":
            test_data = {
                "users": [
                    {"id": "user_001", "name": "Test User 1", "email": "test1@example.com"},
                    {"id": "user_002", "name": "Test User 2", "email": "test2@example.com"},
                ]
            }
        elif data_type == "families":
            test_data = {
                "families": [
                    {"id": "family_001", "name": "Test Family 1", "member_count": 3},
                    {"id": "family_002", "name": "Test Family 2", "member_count": 5},
                ]
            }
        else:
            test_data = {"message": f"Unknown test data type: {data_type}", "available_types": ["users", "families"]}

        result = {
            "data_type": data_type,
            "data": test_data,
            "resource_type": "test_data",
            "timestamp": datetime.utcnow().isoformat(),
        }

        await create_mcp_audit_trail(
            operation="get_test_data_resource",
            user_context=user_context,
            resource_type="test",
            resource_id=data_type,
            metadata={"data_type": data_type},
        )

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error("Failed to get test data resource for %s: %s", data_type, e)
        return json.dumps({"error": f"Failed to retrieve test data: {str(e)}"}, indent=2)
