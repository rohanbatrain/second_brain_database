"""
FastMCP 2.x Tool Registration with Native Authentication

This module demonstrates proper tool registration following FastMCP 2.x patterns.
Tools are registered using the @mcp.tool decorator and can access authenticated
user context via FastMCP's native authentication system.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from ...managers.logging_manager import get_logger
from .modern_server import mcp

logger = get_logger(prefix="[MCP_Tools]")

# Import shop tools to register them with the MCP server
# This ensures all shop-related tools are available
try:
    from .tools import shop_tools

    logger.info("Shop tools imported and registered successfully")
except ImportError as e:
    logger.warning("Failed to import shop tools: %s", e)
except Exception as e:
    logger.error("Error importing shop tools: %s", e)

# Import AI tools to register them with the MCP server
# This ensures all AI-related tools are available
# NOTE: AI tools were removed as part of AI orchestration removal
# try:
#     from .tools import ai_tools
#     logger.info("AI tools imported and registered successfully")
# except ImportError as e:
#     logger.warning("Failed to import AI tools: %s", e)
# except Exception as e:
#     logger.error("Error importing AI tools: %s", e)

# Import RAG tools to register them with the MCP server
# This ensures all RAG-related document querying and analysis tools are available
try:
    from .tools import rag_tools

    logger.info("RAG tools imported and registered successfully")
except ImportError as e:
    logger.warning("Failed to import RAG tools: %s", e)
except Exception as e:
    logger.error("Error importing RAG tools: %s", e)


# FastMCP 2.x compliant tool registration
@mcp.tool
async def get_server_info() -> dict:
    """Get basic server information and status."""
    # In FastMCP 2.x, authenticated user context is available via the server
    # when authentication is enabled
    return {
        "server_name": mcp.name,
        "server_version": mcp.version,
        "timestamp": datetime.now().isoformat(),
        "status": "operational",
        "transport": "http" if hasattr(mcp, "_transport") else "stdio",
        "auth_enabled": mcp.auth is not None,
    }


@mcp.tool
async def echo_message(message: str) -> str:
    """Echo a message back to the client.

    Args:
        message: The message to echo back

    Returns:
        The echoed message with a prefix
    """
    return f"Echo: {message}"


@mcp.tool
def add_numbers(a: int, b: int) -> int:
    """Add two integer numbers together.

    Args:
        a: First number to add
        b: Second number to add

    Returns:
        The sum of a and b
    """
    return a + b


@mcp.tool
def health_check_tool() -> dict:
    """Perform a health check and return detailed status.

    Returns:
        Dictionary containing health status information
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "server": mcp.name,
        "version": mcp.version,
        "auth_enabled": mcp.auth is not None,
        "uptime": "N/A",  # Would be calculated in real implementation
    }


# Tool with custom name and description using decorator arguments
@mcp.tool(
    name="process_text",
    description="Process text data with various operations like uppercase, lowercase, or reverse",
    tags={"text", "processing"},
)
def process_data(data: str, operation: str = "uppercase", include_timestamp: bool = False) -> dict:
    """Process data with specified operation."""
    result = {"original": data, "operation": operation}

    if operation == "uppercase":
        result["processed"] = data.upper()
    elif operation == "lowercase":
        result["processed"] = data.lower()
    elif operation == "reverse":
        result["processed"] = data[::-1]
    else:
        result["processed"] = data
        result["warning"] = f"Unknown operation: {operation}"

    if include_timestamp:
        result["timestamp"] = datetime.now().isoformat()

    return result


# Tool with error handling following FastMCP patterns
@mcp.tool(
    name="calculate_division", description="Divide two numbers with proper error handling", tags={"math", "calculation"}
)
def divide_numbers(a: float, b: float) -> dict:
    """Divide two numbers safely."""
    try:
        if b == 0:
            return {"error": "Division by zero is not allowed", "a": a, "b": b}

        result = a / b
        return {"result": result, "a": a, "b": b, "operation": "division"}

    except Exception as e:
        return {"error": f"Calculation error: {str(e)}", "a": a, "b": b}


def register_example_tools():
    """
    Register example tools with the MCP server.

    Note: In FastMCP 2.x, tools are automatically registered when the module
    is imported and the @mcp.tool decorators are executed. This function
    is provided for explicit registration if needed.
    """
    logger.info("Example tools registered with FastMCP 2.x server")
    logger.info("Tools available: get_server_info, echo_message, health_check_tool, process_data, divide_numbers")
    logger.info("Shop tools and AI tools are automatically registered via module imports")


# Auto-register tools when module is imported
register_example_tools()
