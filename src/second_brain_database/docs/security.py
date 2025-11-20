"""
Security documentation and requirements for API endpoints.

This module provides comprehensive security documentation, including security
requirements for different endpoint types and detailed security scheme information.
"""

from enum import Enum
from typing import Any, Dict, List, Optional


class SecurityLevel(Enum):
    """Security levels for different endpoint types."""

    PUBLIC = "public"
    USER = "user"
    ADMIN = "admin"
    SYSTEM = "system"


class SecurityRequirements:
    """
    Security requirements documentation for different endpoint types.

    This class provides standardized security requirements that can be applied
    to different categories of endpoints.
    """

    @staticmethod
    def get_public_endpoints() -> Dict[str, Any]:
        """
        Get security requirements for public endpoints.

        Returns:
            Dict containing public endpoint security configuration
        """
        return {
            "security": [],  # No authentication required
            "description": "Public endpoints that don't require authentication",
            "examples": ["/docs", "/redoc", "/openapi.json", "/health", "/"],
            "rate_limiting": {
                "enabled": True,
                "requests_per_minute": 100,
                "description": "Rate limiting applied to prevent abuse",
            },
        }

    @staticmethod
    def get_user_endpoints() -> Dict[str, Any]:
        """
        Get security requirements for user-authenticated endpoints.

        Returns:
            Dict containing user endpoint security configuration
        """
        return {
            "security": [{"JWTBearer": []}, {"PermanentToken": []}],
            "description": "Endpoints requiring user authentication via JWT or permanent token",
            "examples": [
                "/auth/me",
                "/auth/refresh",
                "/auth/logout",
                "/auth/change-password",
                "/auth/permanent-tokens",
                "/avatars/*",
                "/banners/*",
                "/themes/*",
                "/shop/*",
            ],
            "authentication_methods": [
                {
                    "method": "JWT Bearer Token",
                    "header": "Authorization: Bearer <jwt_token>",
                    "expiration": "30 minutes",
                    "use_case": "Interactive user sessions",
                },
                {
                    "method": "Permanent API Token",
                    "header": "Authorization: Bearer <permanent_token>",
                    "expiration": "No expiration (until revoked)",
                    "use_case": "Integrations and automation",
                },
            ],
            "rate_limiting": {
                "enabled": True,
                "requests_per_minute": 100,
                "description": "Rate limiting applied per authenticated user",
            },
        }

    @staticmethod
    def get_admin_endpoints() -> Dict[str, Any]:
        """
        Get security requirements for admin-only endpoints.

        Returns:
            Dict containing admin endpoint security configuration
        """
        return {
            "security": [{"JWTBearer": [], "AdminAPIKey": []}, {"PermanentToken": [], "AdminAPIKey": []}],
            "description": "Endpoints requiring admin role and additional API key authentication",
            "examples": ["/admin/*", "/auth/admin/*", "/system/admin/*"],
            "authentication_methods": [
                {
                    "method": "JWT Bearer Token + Admin API Key",
                    "headers": ["Authorization: Bearer <jwt_token>", "X-Admin-API-Key: <admin_api_key>"],
                    "requirements": ["Admin role", "Valid admin API key"],
                    "use_case": "Administrative operations",
                },
                {
                    "method": "Permanent Token + Admin API Key",
                    "headers": ["Authorization: Bearer <permanent_token>", "X-Admin-API-Key: <admin_api_key>"],
                    "requirements": ["Admin role", "Valid admin API key"],
                    "use_case": "Automated admin operations",
                },
            ],
            "additional_security": {
                "role_check": "User must have 'admin' role",
                "api_key_validation": "Valid admin API key required",
                "audit_logging": "All admin operations are logged",
            },
            "rate_limiting": {
                "enabled": True,
                "requests_per_minute": 50,
                "description": "Stricter rate limiting for admin operations",
            },
        }

    @staticmethod
    def get_system_endpoints() -> Dict[str, Any]:
        """
        Get security requirements for system-level endpoints.

        Returns:
            Dict containing system endpoint security configuration
        """
        return {
            "security": [{"AdminAPIKey": []}],
            "description": "System-level endpoints for monitoring and health checks",
            "examples": ["/metrics", "/system/health", "/system/status"],
            "authentication_methods": [
                {
                    "method": "Admin API Key Only",
                    "header": "X-Admin-API-Key: <admin_api_key>",
                    "requirements": ["Valid admin API key"],
                    "use_case": "System monitoring and health checks",
                }
            ],
            "additional_security": {
                "ip_restrictions": "May be restricted to specific IP ranges",
                "monitoring": "Access is monitored and logged",
            },
            "rate_limiting": {
                "enabled": True,
                "requests_per_minute": 200,
                "description": "Higher rate limits for monitoring systems",
            },
        }


class SecurityDocumentation:
    """
    Comprehensive security documentation for the API.

    This class provides detailed security information, best practices,
    and implementation guidelines.
    """

    @staticmethod
    def get_security_overview() -> Dict[str, Any]:
        """
        Get comprehensive security overview documentation.

        Returns:
            Dict containing security overview and best practices
        """
        return {
            "overview": {
                "title": "API Security Overview",
                "description": """
                The Second Brain Database API implements multiple layers of security
                to protect user data and ensure secure access to resources.
                """,
                "security_layers": [
                    {
                        "layer": "Authentication",
                        "description": "Multiple authentication methods including JWT tokens and permanent API tokens",
                        "methods": ["JWT Bearer", "Permanent Tokens", "Admin API Keys"],
                    },
                    {
                        "layer": "Authorization",
                        "description": "Role-based access control with user and admin roles",
                        "features": ["Role validation", "Endpoint-specific permissions", "Resource ownership checks"],
                    },
                    {
                        "layer": "Rate Limiting",
                        "description": "Comprehensive rate limiting to prevent abuse and ensure fair usage",
                        "features": ["Per-IP limits", "Per-user limits", "Endpoint-specific limits"],
                    },
                    {
                        "layer": "Input Validation",
                        "description": "Strict input validation and sanitization",
                        "features": ["Pydantic model validation", "SQL injection prevention", "XSS protection"],
                    },
                    {
                        "layer": "Audit Logging",
                        "description": "Comprehensive logging of security events and user actions",
                        "features": ["Authentication events", "Admin operations", "Failed access attempts"],
                    },
                ],
            },
            "best_practices": {
                "title": "Security Best Practices",
                "for_developers": [
                    "Always use HTTPS in production",
                    "Store tokens securely (never in localStorage for sensitive apps)",
                    "Implement proper token refresh logic",
                    "Handle authentication errors gracefully",
                    "Use permanent tokens for server-to-server communication",
                    "Regularly rotate permanent tokens",
                    "Monitor token usage and revoke unused tokens",
                ],
                "for_integrations": [
                    "Use permanent tokens instead of JWT for long-running processes",
                    "Implement proper error handling for authentication failures",
                    "Respect rate limits and implement backoff strategies",
                    "Use IP restrictions when possible for permanent tokens",
                    "Monitor token usage through the API",
                    "Implement token rotation policies",
                ],
            },
            "common_errors": {
                "title": "Common Security Errors and Solutions",
                "errors": [
                    {
                        "error": "401 Unauthorized",
                        "causes": ["Expired token", "Invalid token", "Missing token"],
                        "solutions": ["Refresh JWT token", "Check token format", "Include Authorization header"],
                    },
                    {
                        "error": "403 Forbidden",
                        "causes": ["Insufficient permissions", "Missing admin role", "Invalid admin API key"],
                        "solutions": ["Check user role", "Verify admin API key", "Contact administrator"],
                    },
                    {
                        "error": "429 Too Many Requests",
                        "causes": ["Rate limit exceeded", "Too many failed attempts"],
                        "solutions": [
                            "Implement backoff strategy",
                            "Reduce request frequency",
                            "Wait for rate limit reset",
                        ],
                    },
                ],
            },
        }

    @staticmethod
    def get_token_management_guide() -> Dict[str, Any]:
        """
        Get comprehensive token management documentation.

        Returns:
            Dict containing token management best practices and guidelines
        """
        return {
            "jwt_tokens": {
                "title": "JWT Token Management",
                "description": "Best practices for managing JWT tokens in client applications",
                "lifecycle": [
                    {
                        "phase": "Acquisition",
                        "description": "Obtain JWT token through login",
                        "best_practices": [
                            "Use secure login endpoints",
                            "Handle 2FA requirements properly",
                            "Store tokens securely",
                        ],
                    },
                    {
                        "phase": "Usage",
                        "description": "Using JWT tokens for API requests",
                        "best_practices": [
                            "Include in Authorization header",
                            "Check expiration before requests",
                            "Handle 401 errors gracefully",
                        ],
                    },
                    {
                        "phase": "Refresh",
                        "description": "Refreshing expired tokens",
                        "best_practices": [
                            "Implement automatic refresh logic",
                            "Handle refresh failures",
                            "Update stored token",
                        ],
                    },
                    {
                        "phase": "Logout",
                        "description": "Properly invalidating tokens",
                        "best_practices": ["Call logout endpoint", "Clear stored tokens", "Handle logout errors"],
                    },
                ],
            },
            "permanent_tokens": {
                "title": "Permanent Token Management",
                "description": "Best practices for managing permanent API tokens",
                "lifecycle": [
                    {
                        "phase": "Creation",
                        "description": "Creating permanent tokens for integrations",
                        "best_practices": [
                            "Use descriptive names",
                            "Set IP restrictions when possible",
                            "Consider expiration dates for temporary integrations",
                            "Store tokens securely",
                        ],
                    },
                    {
                        "phase": "Usage",
                        "description": "Using permanent tokens in applications",
                        "best_practices": [
                            "Use environment variables for storage",
                            "Implement proper error handling",
                            "Monitor usage through API",
                            "Respect rate limits",
                        ],
                    },
                    {
                        "phase": "Monitoring",
                        "description": "Monitoring token usage and security",
                        "best_practices": [
                            "Regularly review token list",
                            "Monitor usage patterns",
                            "Check for suspicious activity",
                            "Review IP restrictions",
                        ],
                    },
                    {
                        "phase": "Rotation",
                        "description": "Rotating tokens for security",
                        "best_practices": [
                            "Implement regular rotation schedule",
                            "Create new token before revoking old",
                            "Update all systems using the token",
                            "Verify new token works before cleanup",
                        ],
                    },
                ],
            },
        }


def get_security_requirements_for_endpoint(endpoint_type: SecurityLevel) -> Dict[str, Any]:
    """
    Get security requirements for a specific endpoint type.

    Args:
        endpoint_type: The security level/type of the endpoint

    Returns:
        Dict containing security requirements for the endpoint type
    """
    requirements = SecurityRequirements()

    if endpoint_type == SecurityLevel.PUBLIC:
        return requirements.get_public_endpoints()
    elif endpoint_type == SecurityLevel.USER:
        return requirements.get_user_endpoints()
    elif endpoint_type == SecurityLevel.ADMIN:
        return requirements.get_admin_endpoints()
    elif endpoint_type == SecurityLevel.SYSTEM:
        return requirements.get_system_endpoints()
    else:
        return requirements.get_user_endpoints()  # Default to user level


def get_comprehensive_security_documentation() -> Dict[str, Any]:
    """
    Get complete security documentation for the API.

    Returns:
        Dict containing comprehensive security documentation
    """
    security_docs = SecurityDocumentation()

    return {
        "security_overview": security_docs.get_security_overview(),
        "token_management": security_docs.get_token_management_guide(),
        "endpoint_requirements": {
            "public": get_security_requirements_for_endpoint(SecurityLevel.PUBLIC),
            "user": get_security_requirements_for_endpoint(SecurityLevel.USER),
            "admin": get_security_requirements_for_endpoint(SecurityLevel.ADMIN),
            "system": get_security_requirements_for_endpoint(SecurityLevel.SYSTEM),
        },
    }
