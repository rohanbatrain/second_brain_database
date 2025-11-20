"""
MCP Configuration Models

Configuration models and validation for MCP server settings.
"""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class RateLimit(BaseModel):
    """Rate limiting configuration for MCP tools."""

    requests_per_minute: int = Field(default=60, ge=1, le=1000, description="Maximum requests per minute per user")
    requests_per_hour: int = Field(default=1000, ge=1, le=10000, description="Maximum requests per hour per user")
    burst_limit: int = Field(default=10, ge=1, le=100, description="Maximum burst requests allowed")

    @field_validator("requests_per_hour")
    @classmethod
    def validate_hourly_limit(cls, v, info):
        """Ensure hourly limit is reasonable compared to per-minute limit."""
        if info.data and "requests_per_minute" in info.data:
            min_hourly = info.data["requests_per_minute"] * 10  # At least 10 minutes worth
            if v < min_hourly:
                raise ValueError(f"Hourly limit must be at least {min_hourly}")
        return v


class SecurityConfig(BaseModel):
    """Security configuration for MCP tools."""

    require_auth: bool = Field(default=True, description="Whether authentication is required for MCP tools")
    allowed_permissions: List[str] = Field(
        default_factory=list, description="List of allowed permissions for MCP access"
    )
    rate_limit: Optional[RateLimit] = Field(default_factory=RateLimit, description="Rate limiting configuration")
    audit_enabled: bool = Field(default=True, description="Whether to enable audit logging for MCP operations")
    ip_whitelist: Optional[List[str]] = Field(default=None, description="Optional IP whitelist for MCP access")
    max_concurrent_tools: int = Field(default=50, ge=1, le=1000, description="Maximum concurrent tool executions")
    request_timeout: int = Field(default=30, ge=1, le=300, description="Request timeout in seconds")


class MCPServerConfig(BaseModel):
    """MCP server configuration."""

    server_name: str = Field(default="SecondBrainMCP", min_length=1, max_length=100, description="MCP server name")
    server_version: str = Field(
        default="1.0.0", pattern=r"^\d+\.\d+\.\d+$", description="MCP server version (semantic versioning)"
    )
    description: str = Field(
        default="Second Brain Database MCP Server", max_length=500, description="MCP server description"
    )
    host: str = Field(default="localhost", description="Host to bind the MCP server to")
    port: int = Field(default=3001, ge=1024, le=65535, description="Port to run the MCP server on")
    enabled: bool = Field(default=True, description="Whether the MCP server is enabled")
    debug_mode: bool = Field(default=False, description="Whether to enable debug mode")
    security: SecurityConfig = Field(default_factory=SecurityConfig, description="Security configuration")

    @field_validator("host")
    @classmethod
    def validate_host(cls, v):
        """Validate host format."""
        if not v or v.strip() == "":
            raise ValueError("Host cannot be empty")
        return v.strip()

    @field_validator("port")
    @classmethod
    def validate_port_range(cls, v):
        """Validate port is in acceptable range."""
        if v < 1024:
            raise ValueError("Port must be >= 1024 for non-root operation")
        return v


class MCPToolConfig(BaseModel):
    """Configuration for individual MCP tools."""

    name: str = Field(..., min_length=1, max_length=100, description="Tool name")
    enabled: bool = Field(default=True, description="Whether the tool is enabled")
    permissions: List[str] = Field(default_factory=list, description="Required permissions for tool access")
    rate_limit_action: Optional[str] = Field(default=None, description="Rate limiting action key")
    audit_enabled: bool = Field(default=True, description="Whether to audit this tool's usage")
    timeout: Optional[int] = Field(default=None, ge=1, le=300, description="Tool-specific timeout in seconds")

    @field_validator("name")
    @classmethod
    def validate_name_format(cls, v):
        """Validate tool name format."""
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Tool name must contain only alphanumeric characters, hyphens, and underscores")
        return v


class MCPResourceConfig(BaseModel):
    """Configuration for MCP resources."""

    name: str = Field(..., min_length=1, max_length=100, description="Resource name")
    uri_template: str = Field(..., min_length=1, description="URI template for the resource")
    enabled: bool = Field(default=True, description="Whether the resource is enabled")
    permissions: List[str] = Field(default_factory=list, description="Required permissions for resource access")
    cache_ttl: Optional[int] = Field(default=None, ge=0, description="Cache TTL in seconds (0 = no cache)")

    @field_validator("uri_template")
    @classmethod
    def validate_uri_template(cls, v):
        """Validate URI template format."""
        if not v.startswith(("http://", "https://", "resource://", "family://", "user://")):
            raise ValueError("URI template must start with a valid scheme")
        return v


class MCPPromptConfig(BaseModel):
    """Configuration for MCP prompts."""

    name: str = Field(..., min_length=1, max_length=100, description="Prompt name")
    enabled: bool = Field(default=True, description="Whether the prompt is enabled")
    permissions: List[str] = Field(default_factory=list, description="Required permissions for prompt access")
    context_aware: bool = Field(default=True, description="Whether the prompt should include user context")

    @field_validator("name")
    @classmethod
    def validate_name_format(cls, v):
        """Validate prompt name format."""
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Prompt name must contain only alphanumeric characters, hyphens, and underscores")
        return v
