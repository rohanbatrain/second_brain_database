#!/usr/bin/env python3
"""
Production ASGI Application for FastMCP 2.x

This module provides a production-ready ASGI application following
FastMCP 2.x best practices for deployment with uvicorn, gunicorn, or
other ASGI servers.

Usage:
    uvicorn production_app:app --host 0.0.0.0 --port 8001
    gunicorn production_app:app -w 4 -k uvicorn.workers.UvicornWorker

Environment Variables:
    MCP_AUTH_TOKEN: Bearer token for authentication (required for production)
    MCP_SECURITY_ENABLED: Enable security features (default: true)
    MCP_HTTP_CORS_ENABLED: Enable CORS (default: false)
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from second_brain_database.integrations.mcp import mcp
from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

logger = get_logger(prefix="[Production_App]")

def create_middleware():
    """Create middleware for production deployment."""
    middleware = []

    # Add CORS middleware if enabled
    if settings.MCP_HTTP_CORS_ENABLED:
        origins = [origin.strip() for origin in settings.MCP_HTTP_CORS_ORIGINS.split(",")]
        cors_middleware = Middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=[
                "mcp-protocol-version",
                "mcp-session-id",
                "Authorization",
                "Content-Type",
            ],
            expose_headers=["mcp-session-id"],
        )
        middleware.append(cors_middleware)

    return middleware

# Create the production ASGI application
# This follows FastMCP 2.x recommended patterns
middleware = create_middleware()
app = mcp.http_app(middleware=middleware)

logger.info(
    "Production ASGI app created: %s v%s (auth: %s, cors: %s)",
    mcp.name,
    mcp.version,
    "enabled" if mcp.auth else "disabled",
    "enabled" if settings.MCP_HTTP_CORS_ENABLED else "disabled"
)

# Validate production configuration
if settings.is_production and not mcp.auth:
    logger.warning("Production deployment without authentication is not recommended")

# For debugging/info
if __name__ == "__main__":
    print(f"FastMCP 2.x Production App: {mcp.name} v{mcp.version}")
    print(f"Authentication: {'Enabled' if mcp.auth else 'Disabled'}")
    print(f"CORS: {'Enabled' if settings.MCP_HTTP_CORS_ENABLED else 'Disabled'}")
    print(f"Transport: HTTP")
    print(f"ASGI App: Ready for production deployment")
    print()
    print("Deployment commands:")
    print("  # Development")
    print("  uvicorn production_app:app --host 127.0.0.1 --port 8001 --reload")
    print()
    print("  # Production")
    print("  uvicorn production_app:app --host 0.0.0.0 --port 8001")
    print("  gunicorn production_app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8001")
    print()
    print("Environment variables:")
    print("  MCP_AUTH_TOKEN=your-secure-token")
    print("  MCP_SECURITY_ENABLED=true")
    print("  MCP_HTTP_CORS_ENABLED=true (if needed)")
