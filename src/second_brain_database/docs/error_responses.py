"""
Comprehensive error response documentation and utilities.

This module provides detailed error response documentation, examples, and utilities
for consistent error handling across the Second Brain Database API.
"""

from typing import Any, Dict, List, Optional

from .models import StandardErrorResponse, ValidationErrorResponse


class ErrorResponseExamples:
    """
    Comprehensive error response examples for different scenarios.

    This class provides realistic error response examples that can be used
    in API documentation and testing.
    """

    @staticmethod
    def get_authentication_errors() -> Dict[str, Any]:
        """
        Get authentication-related error examples.

        Returns:
            Dict containing authentication error scenarios
        """
        return {
            "invalid_token": {
                "status_code": 401,
                "response": {
                    "error": "invalid_token",
                    "message": "The provided authentication token is invalid or malformed",
                    "details": {"token_type": "JWT", "issue": "invalid_signature"},
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
            "expired_token": {
                "status_code": 401,
                "response": {
                    "error": "token_expired",
                    "message": "The authentication token has expired",
                    "details": {"expired_at": "2024-01-01T11:30:00Z", "current_time": "2024-01-01T12:00:00Z"},
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
            "missing_token": {
                "status_code": 401,
                "response": {
                    "error": "authentication_required",
                    "message": "Authentication token is required for this endpoint",
                    "details": {"header": "Authorization", "format": "Bearer <token>"},
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
            "insufficient_permissions": {
                "status_code": 403,
                "response": {
                    "error": "insufficient_permissions",
                    "message": "You don't have sufficient permissions to access this resource",
                    "details": {"required_role": "admin", "current_role": "user"},
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
            "account_disabled": {
                "status_code": 403,
                "response": {
                    "error": "account_disabled",
                    "message": "Your account has been disabled. Please contact support.",
                    "details": {"reason": "policy_violation", "contact": "support@example.com"},
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
        }

    @staticmethod
    def get_validation_errors() -> Dict[str, Any]:
        """
        Get validation error examples with field-specific details.

        Returns:
            Dict containing validation error scenarios
        """
        return {
            "field_validation": {
                "status_code": 422,
                "response": {
                    "error": "validation_error",
                    "message": "Request validation failed",
                    "validation_errors": [
                        {
                            "field": "email",
                            "message": "Invalid email format",
                            "type": "value_error.email",
                            "input": "invalid-email",
                        },
                        {
                            "field": "password",
                            "message": "Password must be at least 8 characters long",
                            "type": "value_error.any_str.min_length",
                            "input": "123",
                        },
                    ],
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
            "missing_required_fields": {
                "status_code": 422,
                "response": {
                    "error": "validation_error",
                    "message": "Required fields are missing",
                    "validation_errors": [
                        {"field": "username", "message": "Field required", "type": "missing", "input": None},
                        {"field": "email", "message": "Field required", "type": "missing", "input": None},
                    ],
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
            "invalid_data_types": {
                "status_code": 422,
                "response": {
                    "error": "validation_error",
                    "message": "Invalid data types provided",
                    "validation_errors": [
                        {
                            "field": "age",
                            "message": "Input should be a valid integer",
                            "type": "int_parsing",
                            "input": "not_a_number",
                        },
                        {
                            "field": "is_active",
                            "message": "Input should be a valid boolean",
                            "type": "bool_parsing",
                            "input": "maybe",
                        },
                    ],
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
        }

    @staticmethod
    def get_rate_limiting_errors() -> Dict[str, Any]:
        """
        Get rate limiting error examples with detailed explanations.

        Returns:
            Dict containing rate limiting error scenarios
        """
        return {
            "general_rate_limit": {
                "status_code": 429,
                "response": {
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests. Please try again later.",
                    "details": {
                        "limit": 100,
                        "window": "60 seconds",
                        "retry_after": 45,
                        "reset_time": "2024-01-01T12:01:00Z",
                    },
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
            "login_rate_limit": {
                "status_code": 429,
                "response": {
                    "error": "login_rate_limit_exceeded",
                    "message": "Too many login attempts. Please wait before trying again.",
                    "details": {
                        "limit": 5,
                        "window": "15 minutes",
                        "retry_after": 900,
                        "lockout_reason": "security_protection",
                    },
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
            "api_quota_exceeded": {
                "status_code": 429,
                "response": {
                    "error": "api_quota_exceeded",
                    "message": "Your API quota has been exceeded for this billing period.",
                    "details": {
                        "quota_limit": 10000,
                        "quota_used": 10000,
                        "quota_reset": "2024-02-01T00:00:00Z",
                        "upgrade_url": "https://example.com/upgrade",
                    },
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
        }

    @staticmethod
    def get_business_logic_errors() -> Dict[str, Any]:
        """
        Get business logic error examples.

        Returns:
            Dict containing business logic error scenarios
        """
        return {
            "insufficient_funds": {
                "status_code": 400,
                "response": {
                    "error": "insufficient_funds",
                    "message": "You don't have enough SBD tokens to complete this purchase",
                    "details": {"required": 250, "available": 100, "shortfall": 150},
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
            "resource_already_owned": {
                "status_code": 409,
                "response": {
                    "error": "resource_conflict",
                    "message": "You already own this item",
                    "details": {
                        "resource_type": "theme",
                        "resource_id": "emotion_tracker-serenityGreen",
                        "owned_since": "2024-01-01T10:00:00Z",
                    },
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
            "resource_not_found": {
                "status_code": 404,
                "response": {
                    "error": "resource_not_found",
                    "message": "The requested resource was not found",
                    "details": {
                        "resource_type": "avatar",
                        "resource_id": "non_existent_avatar",
                        "suggestion": "Check available avatars via GET /avatars/owned",
                    },
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
        }

    @staticmethod
    def get_server_errors() -> Dict[str, Any]:
        """
        Get server error examples.

        Returns:
            Dict containing server error scenarios
        """
        return {
            "internal_server_error": {
                "status_code": 500,
                "response": {
                    "error": "internal_server_error",
                    "message": "An unexpected error occurred. Please try again later.",
                    "details": {"error_id": "err_1234567890", "support_contact": "support@example.com"},
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
            "service_unavailable": {
                "status_code": 503,
                "response": {
                    "error": "service_unavailable",
                    "message": "The service is temporarily unavailable due to maintenance",
                    "details": {
                        "maintenance_window": "2024-01-01T12:00:00Z to 2024-01-01T13:00:00Z",
                        "estimated_completion": "2024-01-01T13:00:00Z",
                        "status_page": "https://status.example.com",
                    },
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
            "database_connection_error": {
                "status_code": 503,
                "response": {
                    "error": "database_unavailable",
                    "message": "Database connection is currently unavailable",
                    "details": {"retry_after": 30, "incident_id": "inc_1234567890"},
                    "timestamp": "2024-01-01T12:00:00Z",
                },
            },
        }


class ErrorResponseGuide:
    """
    Comprehensive error response guide for developers.

    This class provides guidance on error handling, best practices,
    and troubleshooting information.
    """

    @staticmethod
    def get_error_handling_guide() -> Dict[str, Any]:
        """
        Get comprehensive error handling guide.

        Returns:
            Dict containing error handling best practices and guidance
        """
        return {
            "overview": {
                "title": "Error Handling Guide",
                "description": """
                The Second Brain Database API uses standard HTTP status codes and provides
                detailed error information to help developers handle errors gracefully.
                """,
                "error_format": {
                    "description": "All errors follow a consistent format",
                    "structure": {
                        "error": "Error type identifier (string)",
                        "message": "Human-readable error description (string)",
                        "details": "Additional error context (object, optional)",
                        "timestamp": "ISO 8601 timestamp when error occurred (string)",
                    },
                },
            },
            "status_codes": {
                "4xx_client_errors": {
                    "400": "Bad Request - Invalid request data or parameters",
                    "401": "Unauthorized - Authentication required or invalid",
                    "403": "Forbidden - Insufficient permissions",
                    "404": "Not Found - Resource doesn't exist",
                    "409": "Conflict - Resource conflict (e.g., already exists)",
                    "422": "Unprocessable Entity - Validation failed",
                    "429": "Too Many Requests - Rate limit exceeded",
                },
                "5xx_server_errors": {
                    "500": "Internal Server Error - Unexpected server error",
                    "503": "Service Unavailable - Service temporarily down",
                },
            },
            "best_practices": {
                "client_implementation": [
                    "Always check HTTP status codes before processing responses",
                    "Parse error responses to extract detailed error information",
                    "Implement exponential backoff for rate limit errors (429)",
                    "Log error details for debugging and monitoring",
                    "Provide user-friendly error messages based on error types",
                    "Handle network errors and timeouts gracefully",
                ],
                "error_recovery": [
                    "Retry transient errors (5xx) with exponential backoff",
                    "Don't retry client errors (4xx) without fixing the request",
                    "For 401 errors, attempt token refresh before retrying",
                    "For 429 errors, respect the retry_after value",
                    "For validation errors (422), fix the data and retry",
                ],
            },
            "troubleshooting": {
                "common_issues": [
                    {
                        "issue": "401 Unauthorized",
                        "causes": ["Expired token", "Invalid token", "Missing Authorization header"],
                        "solutions": [
                            "Refresh your JWT token",
                            "Check token format",
                            "Include 'Authorization: Bearer <token>' header",
                        ],
                    },
                    {
                        "issue": "422 Validation Error",
                        "causes": ["Invalid field values", "Missing required fields", "Wrong data types"],
                        "solutions": [
                            "Check field requirements",
                            "Validate data before sending",
                            "Review API documentation",
                        ],
                    },
                    {
                        "issue": "429 Rate Limit",
                        "causes": ["Too many requests", "Exceeded quota"],
                        "solutions": [
                            "Implement rate limiting in client",
                            "Use exponential backoff",
                            "Consider upgrading plan",
                        ],
                    },
                ]
            },
        }


def get_comprehensive_error_documentation() -> Dict[str, Any]:
    """
    Get complete error response documentation.

    Returns:
        Dict containing comprehensive error documentation
    """
    examples = ErrorResponseExamples()
    guide = ErrorResponseGuide()

    return {
        "error_examples": {
            "authentication": examples.get_authentication_errors(),
            "validation": examples.get_validation_errors(),
            "rate_limiting": examples.get_rate_limiting_errors(),
            "business_logic": examples.get_business_logic_errors(),
            "server_errors": examples.get_server_errors(),
        },
        "error_handling_guide": guide.get_error_handling_guide(),
    }
