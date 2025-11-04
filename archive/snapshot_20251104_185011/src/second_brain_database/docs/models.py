"""
Documentation response models and base classes.

This module provides standardized response models for consistent API documentation,
including error responses, success responses, and base classes for enhanced model documentation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel, ConfigDict, Field


class StandardErrorResponse(BaseModel):
    """
    Standard error response model for consistent error documentation.

    This model provides a standardized structure for all API error responses,
    ensuring consistent error handling and documentation across the application.
    """

    error: str = Field(..., description="Error type or category identifier", example="validation_error")

    message: str = Field(
        ...,
        description="Human-readable error message describing what went wrong",
        example="The provided data is invalid",
    )

    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error details and context",
        example={"field": "username", "issue": "already_exists"},
    )

    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when the error occurred")

    request_id: Optional[str] = Field(None, description="Unique request identifier for tracking")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "validation_error",
                "message": "The provided data is invalid",
                "details": {"field": "email", "issue": "invalid_format"},
                "timestamp": "2024-01-01T12:00:00Z",
                "request_id": "req_123456789",
            }
        }
    )


class ValidationErrorResponse(BaseModel):
    """
    Validation error response model for detailed field-level error documentation.

    This model provides detailed validation error information with field-specific
    error messages for comprehensive error handling documentation.
    """

    error: str = Field(default="validation_error", description="Error type identifier")

    message: str = Field(default="Request validation failed", description="General validation error message")

    validation_errors: List[Dict[str, Any]] = Field(..., description="List of field-specific validation errors")

    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp when the validation error occurred"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "validation_error",
                "message": "Request validation failed",
                "validation_errors": [
                    {"field": "email", "message": "Invalid email format", "type": "value_error.email"},
                    {
                        "field": "password",
                        "message": "Password must be at least 8 characters",
                        "type": "value_error.any_str.min_length",
                    },
                ],
                "timestamp": "2024-01-01T12:00:00Z",
            }
        }
    )


class StandardSuccessResponse(BaseModel):
    """
    Standard success response model for consistent success documentation.

    This model provides a standardized structure for API success responses,
    ensuring consistent response format across the application.
    """

    success: bool = Field(default=True, description="Indicates successful operation completion")

    message: str = Field(..., description="Human-readable success message", example="Operation completed successfully")

    data: Optional[Dict[str, Any]] = Field(None, description="Response data payload")

    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when the operation completed")

    request_id: Optional[str] = Field(None, description="Unique request identifier for tracking")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "User created successfully",
                "data": {"user_id": "user_123456789", "username": "john_doe"},
                "timestamp": "2024-01-01T12:00:00Z",
                "request_id": "req_123456789",
            }
        }
    )


class BaseDocumentedModel(BaseModel):
    """
    Base class for enhanced model documentation.

    This base class provides common configuration and utilities for all
    documented models, ensuring consistent documentation standards.
    """

    model_config = ConfigDict(
        # Enable JSON schema generation with examples
        json_schema_mode="validation",
        # Use enum values in schema
        use_enum_values=True,
        # Validate assignment
        validate_assignment=True,
        # Allow population by field name
        populate_by_name=True,
        # Generate schema with examples
        json_schema_extra={},
    )

    @classmethod
    def get_example(cls) -> Dict[str, Any]:
        """
        Get example data for the model.

        Returns:
            Dict[str, Any]: Example data for documentation
        """
        if hasattr(cls.model_config, "json_schema_extra") and cls.model_config.json_schema_extra:
            return cls.model_config.json_schema_extra.get("example", {})
        return {}

    @classmethod
    def get_field_info(cls, field_name: str) -> Dict[str, Any]:
        """
        Get detailed field information for documentation.

        Args:
            field_name: Name of the field to get info for

        Returns:
            Dict[str, Any]: Field information including description, type, constraints
        """
        if field_name not in cls.model_fields:
            return {}

        field_info = cls.model_fields[field_name]
        return {
            "description": field_info.description,
            "type": str(field_info.annotation),
            "required": field_info.is_required(),
            "default": field_info.default if field_info.default is not None else None,
        }


def create_error_responses() -> Dict[int, Dict[str, Any]]:
    """
    Create standardized error response documentation for common HTTP status codes.

    Returns:
        Dict[int, Dict[str, Any]]: Dictionary of HTTP status codes and their response documentation
    """
    return {
        400: {
            "description": "Bad Request - Invalid request data",
            "model": StandardErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": "bad_request",
                        "message": "Invalid request data provided",
                        "details": {"field": "parameter", "issue": "invalid_value"},
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                }
            },
        },
        401: {
            "description": "Unauthorized - Authentication required",
            "model": StandardErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": "authentication_required",
                        "message": "Valid authentication token required",
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                }
            },
        },
        403: {
            "description": "Forbidden - Insufficient permissions",
            "model": StandardErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": "insufficient_permissions",
                        "message": "You don't have permission to access this resource",
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                }
            },
        },
        404: {
            "description": "Not Found - Resource not found",
            "model": StandardErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": "not_found",
                        "message": "The requested resource was not found",
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                }
            },
        },
        409: {
            "description": "Conflict - Resource conflict",
            "model": StandardErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": "resource_conflict",
                        "message": "Resource already exists or conflicts with existing data",
                        "details": {"field": "username", "issue": "already_exists"},
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                }
            },
        },
        422: {
            "description": "Unprocessable Entity - Validation failed",
            "model": ValidationErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": "validation_error",
                        "message": "Request validation failed",
                        "validation_errors": [
                            {"field": "email", "message": "Invalid email format", "type": "value_error.email"}
                        ],
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                }
            },
        },
        429: {
            "description": "Too Many Requests - Rate limit exceeded",
            "model": StandardErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": "rate_limit_exceeded",
                        "message": "Too many requests. Please try again later",
                        "details": {"retry_after": 60},
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                }
            },
        },
        500: {
            "description": "Internal Server Error - Server error occurred",
            "model": StandardErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": "internal_server_error",
                        "message": "An internal server error occurred",
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                }
            },
        },
        503: {
            "description": "Service Unavailable - Service temporarily unavailable",
            "model": StandardErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": "service_unavailable",
                        "message": "Service is temporarily unavailable",
                        "details": {"retry_after": 300},
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                }
            },
        },
    }


def create_standard_responses(success_model: Optional[Type[BaseModel]] = None) -> Dict[int, Dict[str, Any]]:
    """
    Create standardized success response documentation.

    Args:
        success_model: Optional custom success response model

    Returns:
        Dict[int, Dict[str, Any]]: Dictionary of success response documentation
    """
    model = success_model or StandardSuccessResponse

    return {
        200: {
            "description": "Success - Operation completed successfully",
            "model": model,
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Operation completed successfully",
                        "data": {},
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                }
            },
        },
        201: {
            "description": "Created - Resource created successfully",
            "model": model,
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Resource created successfully",
                        "data": {"id": "resource_123456789"},
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                }
            },
        },
        204: {"description": "No Content - Operation completed successfully with no response body"},
    }
