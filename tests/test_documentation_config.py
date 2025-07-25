"""
Tests for documentation configuration and response models.

This module tests the documentation configuration system and standardized response models
to ensure they work correctly across different environments.
"""

from datetime import datetime

import pytest

from second_brain_database.config import settings
from second_brain_database.docs import (
    BaseDocumentedModel,
    DocumentationConfig,
    StandardErrorResponse,
    StandardSuccessResponse,
    ValidationErrorResponse,
    create_error_responses,
    create_standard_responses,
    get_docs_config,
)


def test_documentation_config_creation():
    """Test that documentation configuration is created correctly."""
    config = get_docs_config()

    assert isinstance(config, DocumentationConfig)
    assert config.enabled == settings.docs_should_be_enabled
    assert config.cache_enabled == settings.DOCS_CACHE_ENABLED
    assert config.cache_ttl == settings.DOCS_CACHE_TTL

    # Test contact info is properly set
    assert "name" in config.contact_info
    assert "url" in config.contact_info
    assert "email" in config.contact_info

    # Test license info is properly set
    assert "name" in config.license_info
    assert "url" in config.license_info


def test_standard_error_response():
    """Test StandardErrorResponse model creation and validation."""
    error_response = StandardErrorResponse(
        error="test_error", message="Test error message", details={"field": "test_field", "issue": "test_issue"}
    )

    assert error_response.error == "test_error"
    assert error_response.message == "Test error message"
    assert error_response.details["field"] == "test_field"
    assert isinstance(error_response.timestamp, datetime)


def test_standard_success_response():
    """Test StandardSuccessResponse model creation and validation."""
    success_response = StandardSuccessResponse(message="Operation successful", data={"result": "success", "id": "123"})

    assert success_response.success is True
    assert success_response.message == "Operation successful"
    assert success_response.data["result"] == "success"
    assert isinstance(success_response.timestamp, datetime)


def test_validation_error_response():
    """Test ValidationErrorResponse model creation and validation."""
    validation_errors = [
        {"field": "email", "message": "Invalid email format", "type": "value_error.email"},
        {"field": "password", "message": "Password too short", "type": "value_error.any_str.min_length"},
    ]

    validation_response = ValidationErrorResponse(validation_errors=validation_errors)

    assert validation_response.error == "validation_error"
    assert validation_response.message == "Request validation failed"
    assert len(validation_response.validation_errors) == 2
    assert validation_response.validation_errors[0]["field"] == "email"


def test_create_error_responses():
    """Test error responses creation function."""
    error_responses = create_error_responses()

    # Test that common HTTP error codes are included
    expected_codes = [400, 401, 403, 404, 409, 422, 429, 500, 503]
    for code in expected_codes:
        assert code in error_responses
        assert "description" in error_responses[code]
        assert "content" in error_responses[code]

    # Test specific error response structure
    assert "application/json" in error_responses[400]["content"]
    assert "example" in error_responses[400]["content"]["application/json"]


def test_create_standard_responses():
    """Test standard responses creation function."""
    standard_responses = create_standard_responses()

    # Test that success codes are included
    expected_codes = [200, 201, 204]
    for code in expected_codes:
        assert code in standard_responses
        assert "description" in standard_responses[code]

    # Test that 200 and 201 have content, 204 does not
    assert "content" in standard_responses[200]
    assert "content" in standard_responses[201]
    assert "content" not in standard_responses[204]


def test_base_documented_model():
    """Test BaseDocumentedModel functionality."""

    class TestModel(BaseDocumentedModel):
        name: str
        age: int

        model_config = {"json_schema_extra": {"example": {"name": "John Doe", "age": 30}}}

    # Test example retrieval
    example = TestModel.get_example()
    assert example["name"] == "John Doe"
    assert example["age"] == 30

    # Test field info retrieval
    name_info = TestModel.get_field_info("name")
    assert "description" in name_info or name_info == {}  # May be empty if no description

    # Test model creation
    test_instance = TestModel(name="Jane Doe", age=25)
    assert test_instance.name == "Jane Doe"
    assert test_instance.age == 25


def test_environment_aware_configuration():
    """Test that documentation configuration respects environment settings."""
    config = get_docs_config()

    # In development (DEBUG=True), docs should be enabled
    if settings.DEBUG:
        assert config.enabled is True
        assert config.docs_url is not None
        assert config.redoc_url is not None
        assert config.openapi_url is not None

    # Test server configuration
    if settings.BASE_URL:
        assert len(config.servers) > 0
        assert config.servers[0]["url"] == settings.BASE_URL


def test_authentication_examples():
    """Test authentication examples generation."""
    from second_brain_database.docs import AuthenticationExamples, get_authentication_documentation

    # Test JWT examples
    jwt_examples = AuthenticationExamples.get_jwt_examples()
    assert "registration_flow" in jwt_examples
    assert "login_with_2fa" in jwt_examples
    assert "token_refresh" in jwt_examples
    assert "logout" in jwt_examples

    # Test permanent token examples
    permanent_examples = AuthenticationExamples.get_permanent_token_examples()
    assert "create_token" in permanent_examples
    assert "list_tokens" in permanent_examples
    assert "revoke_token" in permanent_examples
    assert "usage_with_permanent_token" in permanent_examples

    # Test admin examples
    admin_examples = AuthenticationExamples.get_admin_examples()
    assert "admin_operations" in admin_examples

    # Test error examples
    error_examples = AuthenticationExamples.get_error_examples()
    assert "invalid_credentials" in error_examples
    assert "expired_token" in error_examples
    assert "missing_token" in error_examples

    # Test comprehensive documentation
    auth_docs = get_authentication_documentation()
    assert "jwt_authentication" in auth_docs
    assert "permanent_token_authentication" in auth_docs
    assert "admin_authentication" in auth_docs
    assert "error_scenarios" in auth_docs


def test_security_documentation():
    """Test security documentation generation."""
    from second_brain_database.docs import (
        SecurityDocumentation,
        SecurityLevel,
        SecurityRequirements,
        get_comprehensive_security_documentation,
        get_security_requirements_for_endpoint,
    )

    # Test security requirements for different endpoint types
    public_reqs = get_security_requirements_for_endpoint(SecurityLevel.PUBLIC)
    assert public_reqs["security"] == []  # No auth required
    assert "rate_limiting" in public_reqs

    user_reqs = get_security_requirements_for_endpoint(SecurityLevel.USER)
    assert len(user_reqs["security"]) > 0  # Auth required
    assert "authentication_methods" in user_reqs

    admin_reqs = get_security_requirements_for_endpoint(SecurityLevel.ADMIN)
    assert len(admin_reqs["security"]) > 0  # Auth required
    assert "additional_security" in admin_reqs

    # Test comprehensive security documentation
    security_docs = get_comprehensive_security_documentation()
    assert "security_overview" in security_docs
    assert "token_management" in security_docs
    assert "endpoint_requirements" in security_docs

    # Test security overview structure
    overview = security_docs["security_overview"]["overview"]
    assert "security_layers" in overview
    assert len(overview["security_layers"]) > 0

    # Test token management guide
    token_mgmt = security_docs["token_management"]
    assert "jwt_tokens" in token_mgmt
    assert "permanent_tokens" in token_mgmt


def test_security_requirements_class():
    """Test SecurityRequirements class methods."""
    from second_brain_database.docs import SecurityRequirements

    # Test all endpoint type methods
    public = SecurityRequirements.get_public_endpoints()
    assert "security" in public
    assert "examples" in public

    user = SecurityRequirements.get_user_endpoints()
    assert "security" in user
    assert "authentication_methods" in user

    admin = SecurityRequirements.get_admin_endpoints()
    assert "security" in admin
    assert "additional_security" in admin

    system = SecurityRequirements.get_system_endpoints()
    assert "security" in system
    assert "authentication_methods" in system
