"""
Documentation module for Second Brain Database API.

This module provides comprehensive documentation configuration, response models,
authentication examples, security documentation, and base classes for enhanced API documentation.
"""

from .config import DocumentationConfig, get_docs_config
from .models import (
    StandardErrorResponse,
    StandardSuccessResponse,
    ValidationErrorResponse,
    BaseDocumentedModel,
    create_error_responses,
    create_standard_responses
)
from .auth_examples import AuthenticationExamples, get_authentication_documentation
from .security import (
    SecurityLevel,
    SecurityRequirements,
    SecurityDocumentation,
    get_security_requirements_for_endpoint,
    get_comprehensive_security_documentation
)
from .error_responses import (
    ErrorResponseExamples,
    ErrorResponseGuide,
    get_comprehensive_error_documentation
)

__all__ = [
    "DocumentationConfig",
    "get_docs_config",
    "StandardErrorResponse", 
    "StandardSuccessResponse",
    "ValidationErrorResponse",
    "BaseDocumentedModel",
    "create_error_responses",
    "create_standard_responses",
    "AuthenticationExamples",
    "get_authentication_documentation",
    "SecurityLevel",
    "SecurityRequirements", 
    "SecurityDocumentation",
    "get_security_requirements_for_endpoint",
    "get_comprehensive_security_documentation",
    "ErrorResponseExamples",
    "ErrorResponseGuide",
    "get_comprehensive_error_documentation"
]