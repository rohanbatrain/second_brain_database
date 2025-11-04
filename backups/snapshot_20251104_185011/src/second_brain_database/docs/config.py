"""
Documentation configuration module.

This module provides environment-aware documentation configuration for the FastAPI application,
leveraging the main settings configuration for consistency and avoiding duplication.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from second_brain_database.config import settings


class DocumentationConfig(BaseModel):
    """
    Configuration for API documentation.

    This model provides a structured way to access documentation settings
    from the main application configuration.
    """

    enabled: bool = Field(description="Whether documentation endpoints are enabled")
    docs_url: Optional[str] = Field(description="URL path for Swagger UI documentation")
    redoc_url: Optional[str] = Field(description="URL path for ReDoc documentation")
    openapi_url: Optional[str] = Field(description="URL path for OpenAPI schema")
    access_control_enabled: bool = Field(description="Whether to enable access control for documentation")
    cache_enabled: bool = Field(description="Whether to enable documentation caching")
    cache_ttl: int = Field(description="Documentation cache TTL in seconds")

    contact_info: Dict[str, str] = Field(
        default_factory=lambda: {
            "name": "Second Brain Database Team",
            "url": "https://github.com/rohanbatrain/second_brain_database",
            "email": "contact@rohanbatra.in",
        },
        description="Contact information for API documentation",
    )

    license_info: Dict[str, str] = Field(
        default_factory=lambda: {"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
        description="License information for API documentation",
    )

    servers: list[Dict[str, str]] = Field(
        default_factory=list, description="List of server configurations for documentation"
    )


def get_docs_config() -> DocumentationConfig:
    """
    Get documentation configuration based on main application settings.

    This function creates a DocumentationConfig instance using the main settings,
    ensuring consistency and environment-aware behavior.

    Returns:
        DocumentationConfig: Configured documentation settings
    """
    # Environment-aware URL configuration
    docs_enabled = settings.docs_should_be_enabled

    config = DocumentationConfig(
        enabled=docs_enabled,
        docs_url=settings.DOCS_URL if docs_enabled else None,
        redoc_url=settings.REDOC_URL if docs_enabled else None,
        openapi_url=settings.OPENAPI_URL if docs_enabled else None,
        access_control_enabled=settings.DOCS_ACCESS_CONTROL or settings.is_production,
        cache_enabled=settings.DOCS_CACHE_ENABLED,
        cache_ttl=settings.DOCS_CACHE_TTL,
    )

    # Add server configuration based on base URL and environment
    servers = []
    if settings.BASE_URL:
        server_description = "Production server" if settings.is_production else "Development server"
        servers.append({"url": settings.BASE_URL, "description": server_description})

    # Add additional server configurations for different environments
    if not settings.is_production:
        servers.extend(
            [
                {"url": "http://localhost:8000", "description": "Local development server"},
                {"url": "http://127.0.0.1:8000", "description": "Local development server (127.0.0.1)"},
            ]
        )

    config.servers = servers
    return config


# Global documentation configuration instance
docs_config = get_docs_config()
