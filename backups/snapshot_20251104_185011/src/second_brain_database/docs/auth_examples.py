"""
Authentication examples and documentation for API documentation.

This module provides comprehensive examples and documentation for all authentication
methods supported by the Second Brain Database API.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List


class AuthenticationExamples:
    """
    Comprehensive authentication examples for API documentation.

    This class provides realistic examples for all authentication flows,
    including JWT tokens, permanent tokens, and admin API keys.
    """

    @staticmethod
    def get_jwt_examples() -> Dict[str, Any]:
        """
        Get JWT authentication examples and documentation.

        Returns:
            Dict containing JWT authentication examples and flows
        """
        return {
            "registration_flow": {
                "description": "Complete user registration and authentication flow",
                "steps": [
                    {
                        "step": 1,
                        "action": "Register new user",
                        "endpoint": "POST /auth/register",
                        "request": {
                            "username": "john_doe",
                            "email": "john.doe@example.com",
                            "password": "SecurePassword123!",
                            "client_side_encryption": False,
                        },
                        "response": {
                            "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJqb2huX2RvZSIsImV4cCI6MTY0MDk5NTIwMH0.example_signature",
                            "token_type": "bearer",
                            "client_side_encryption": False,
                            "issued_at": 1640993400,
                            "expires_at": 1640995200,
                            "is_verified": False,
                            "two_fa_enabled": False,
                        },
                    },
                    {
                        "step": 2,
                        "action": "Verify email address",
                        "endpoint": "GET /auth/verify-email?token=verification_token_here",
                        "response": {"message": "Email verified successfully"},
                    },
                    {
                        "step": 3,
                        "action": "Login with verified account",
                        "endpoint": "POST /auth/login",
                        "request": {
                            "username": "john_doe",
                            "password": "SecurePassword123!",
                            "client_side_encryption": False,
                        },
                        "response": {
                            "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJqb2huX2RvZSIsImV4cCI6MTY0MDk5NTIwMH0.example_signature",
                            "token_type": "bearer",
                            "client_side_encryption": False,
                            "issued_at": 1640993400,
                            "expires_at": 1640995200,
                            "is_verified": True,
                            "role": "user",
                            "username": "john_doe",
                            "email": "john.doe@example.com",
                        },
                    },
                ],
            },
            "login_with_2fa": {
                "description": "Login flow with 2FA authentication",
                "steps": [
                    {
                        "step": 1,
                        "action": "Initial login attempt",
                        "endpoint": "POST /auth/login",
                        "request": {"username": "john_doe", "password": "SecurePassword123!"},
                        "response": {
                            "status_code": 422,
                            "detail": "2FA authentication required",
                            "two_fa_required": True,
                            "available_methods": ["totp", "backup"],
                            "username": "john_doe",
                            "email": "john.doe@example.com",
                        },
                    },
                    {
                        "step": 2,
                        "action": "Login with 2FA code",
                        "endpoint": "POST /auth/login",
                        "request": {
                            "username": "john_doe",
                            "password": "SecurePassword123!",
                            "two_fa_code": "123456",
                            "two_fa_method": "totp",
                        },
                        "response": {
                            "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJqb2huX2RvZSIsImV4cCI6MTY0MDk5NTIwMH0.example_signature",
                            "token_type": "bearer",
                            "client_side_encryption": False,
                            "issued_at": 1640993400,
                            "expires_at": 1640995200,
                            "is_verified": True,
                            "role": "user",
                            "username": "john_doe",
                            "email": "john.doe@example.com",
                        },
                    },
                ],
            },
            "token_refresh": {
                "description": "Token refresh flow",
                "endpoint": "POST /auth/refresh",
                "headers": {"Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."},
                "response": {
                    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.new_token_payload.new_signature",
                    "token_type": "bearer",
                },
            },
            "logout": {
                "description": "User logout (token invalidation)",
                "endpoint": "POST /auth/logout",
                "headers": {"Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."},
                "response": {"message": "Successfully logged out"},
            },
        }

    @staticmethod
    def get_permanent_token_examples() -> Dict[str, Any]:
        """
        Get permanent token authentication examples and documentation.

        Returns:
            Dict containing permanent token examples and management flows
        """
        return {
            "create_token": {
                "description": "Create a new permanent API token",
                "endpoint": "POST /auth/permanent-tokens",
                "headers": {"Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."},
                "request": {
                    "description": "CI/CD Pipeline Token",
                    "ip_restrictions": ["192.168.1.0/24", "10.0.0.0/8"],
                    "expires_at": None,
                },
                "response": {
                    "token_id": "pt_1234567890abcdef",
                    "token": "sbd_permanent_1234567890abcdef1234567890abcdef1234567890abcdef",
                    "description": "CI/CD Pipeline Token",
                    "created_at": "2024-01-01T12:00:00Z",
                    "expires_at": None,
                    "ip_restrictions": ["192.168.1.0/24", "10.0.0.0/8"],
                    "last_used_at": None,
                    "usage_count": 0,
                    "is_revoked": False,
                },
            },
            "list_tokens": {
                "description": "List all permanent tokens for the authenticated user",
                "endpoint": "GET /auth/permanent-tokens",
                "headers": {"Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."},
                "response": {
                    "tokens": [
                        {
                            "token_id": "pt_1234567890abcdef",
                            "description": "CI/CD Pipeline Token",
                            "created_at": "2024-01-01T12:00:00Z",
                            "expires_at": None,
                            "last_used_at": "2024-01-01T15:30:00Z",
                            "usage_count": 42,
                            "is_revoked": False,
                            "ip_restrictions": ["192.168.1.0/24"],
                        },
                        {
                            "token_id": "pt_abcdef1234567890",
                            "description": "Mobile App Integration",
                            "created_at": "2024-01-02T09:00:00Z",
                            "expires_at": "2024-12-31T23:59:59Z",
                            "last_used_at": "2024-01-02T10:15:00Z",
                            "usage_count": 15,
                            "is_revoked": False,
                            "ip_restrictions": [],
                        },
                    ],
                    "total_count": 2,
                    "active_count": 2,
                    "revoked_count": 0,
                },
            },
            "revoke_token": {
                "description": "Revoke a permanent token",
                "endpoint": "DELETE /auth/permanent-tokens/pt_1234567890abcdef",
                "headers": {"Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."},
                "response": {
                    "message": "Token revoked successfully",
                    "token_id": "pt_1234567890abcdef",
                    "revoked_at": "2024-01-01T16:00:00Z",
                },
            },
            "usage_with_permanent_token": {
                "description": "Using a permanent token to access protected endpoints",
                "examples": [
                    {
                        "endpoint": "GET /auth/me",
                        "headers": {
                            "Authorization": "Bearer sbd_permanent_1234567890abcdef1234567890abcdef1234567890abcdef"
                        },
                        "response": {
                            "username": "john_doe",
                            "email": "john.doe@example.com",
                            "is_verified": True,
                            "role": "user",
                            "two_fa_enabled": True,
                            "created_at": "2024-01-01T10:00:00Z",
                        },
                    },
                    {
                        "endpoint": "POST /knowledge/documents",
                        "headers": {
                            "Authorization": "Bearer sbd_permanent_1234567890abcdef1234567890abcdef1234567890abcdef",
                            "Content-Type": "application/json",
                        },
                        "request": {
                            "title": "API Integration Notes",
                            "content": "Notes about integrating with the Second Brain Database API",
                            "tags": ["api", "integration", "documentation"],
                        },
                        "response": {
                            "document_id": "doc_987654321",
                            "title": "API Integration Notes",
                            "created_at": "2024-01-01T16:30:00Z",
                            "updated_at": "2024-01-01T16:30:00Z",
                        },
                    },
                ],
            },
        }

    @staticmethod
    def get_admin_examples() -> Dict[str, Any]:
        """
        Get admin API key authentication examples.

        Returns:
            Dict containing admin authentication examples
        """
        return {
            "admin_operations": {
                "description": "Administrative operations using admin API key",
                "examples": [
                    {
                        "endpoint": "GET /admin/users",
                        "headers": {
                            "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                            "X-Admin-API-Key": "admin_key_1234567890abcdef",
                        },
                        "response": {
                            "users": [
                                {
                                    "user_id": "user_123",
                                    "username": "john_doe",
                                    "email": "john.doe@example.com",
                                    "role": "user",
                                    "is_verified": True,
                                    "created_at": "2024-01-01T10:00:00Z",
                                }
                            ],
                            "total_count": 1,
                            "page": 1,
                            "per_page": 50,
                        },
                    },
                    {
                        "endpoint": "GET /admin/system/health",
                        "headers": {"X-Admin-API-Key": "admin_key_1234567890abcdef"},
                        "response": {
                            "status": "healthy",
                            "database": "connected",
                            "redis": "connected",
                            "uptime": 86400,
                            "version": "1.0.0",
                        },
                    },
                ],
            }
        }

    @staticmethod
    def get_error_examples() -> Dict[str, Any]:
        """
        Get authentication error examples.

        Returns:
            Dict containing common authentication error scenarios
        """
        return {
            "invalid_credentials": {
                "endpoint": "POST /auth/login",
                "request": {"username": "john_doe", "password": "wrong_password"},
                "response": {
                    "status_code": 401,
                    "error": "authentication_failed",
                    "message": "Invalid username or password",
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
            "expired_token": {
                "endpoint": "GET /auth/me",
                "headers": {"Authorization": "Bearer expired_jwt_token"},
                "response": {
                    "status_code": 401,
                    "error": "token_expired",
                    "message": "JWT token has expired",
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
            "invalid_token": {
                "endpoint": "GET /auth/me",
                "headers": {"Authorization": "Bearer invalid_token"},
                "response": {
                    "status_code": 401,
                    "error": "invalid_token",
                    "message": "Invalid or malformed token",
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
            "missing_token": {
                "endpoint": "GET /auth/me",
                "headers": {},
                "response": {
                    "status_code": 401,
                    "error": "authentication_required",
                    "message": "Authentication token required",
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
            "insufficient_permissions": {
                "endpoint": "GET /admin/users",
                "headers": {"Authorization": "Bearer valid_user_token"},
                "response": {
                    "status_code": 403,
                    "error": "insufficient_permissions",
                    "message": "Admin privileges required",
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
            "rate_limit_exceeded": {
                "endpoint": "POST /auth/login",
                "response": {
                    "status_code": 429,
                    "error": "rate_limit_exceeded",
                    "message": "Too many login attempts. Please try again later",
                    "details": {"retry_after": 60},
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
        }


def get_authentication_documentation() -> Dict[str, Any]:
    """
    Get comprehensive authentication documentation for OpenAPI schema.

    Returns:
        Dict containing complete authentication documentation
    """
    examples = AuthenticationExamples()

    return {
        "jwt_authentication": {
            "summary": "JWT Bearer Token Authentication",
            "description": """
            JWT (JSON Web Token) Bearer authentication is the primary authentication method
            for interactive user sessions and short-term API access.
            """,
            "examples": examples.get_jwt_examples(),
        },
        "permanent_token_authentication": {
            "summary": "Permanent API Token Authentication",
            "description": """
            Permanent tokens provide long-lived authentication for integrations,
            automation, and server-to-server communication.
            """,
            "examples": examples.get_permanent_token_examples(),
        },
        "admin_authentication": {
            "summary": "Admin API Key Authentication",
            "description": """
            Admin API keys provide additional security for administrative operations
            and system management endpoints.
            """,
            "examples": examples.get_admin_examples(),
        },
        "error_scenarios": {
            "summary": "Authentication Error Scenarios",
            "description": """
            Common authentication error scenarios and their responses.
            """,
            "examples": examples.get_error_examples(),
        },
    }
