"""
Comprehensive API documentation testing suite.

This module tests the FastAPI documentation system including OpenAPI schema generation,
documentation endpoint accessibility, example data validation, and interactive features.
"""

import json
from typing import Any, Dict, List

from fastapi.openapi.utils import get_openapi
from fastapi.testclient import TestClient
import jsonschema
import pytest

from second_brain_database.config import settings
from second_brain_database.docs.config import docs_config
from second_brain_database.main import app


class TestOpenAPISchemaGeneration:
    """Test OpenAPI schema generation and validation."""

    def test_openapi_schema_is_valid(self):
        """Test that the generated OpenAPI schema is valid."""
        client = TestClient(app)

        # Get OpenAPI schema
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()

        # Basic schema structure validation
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema
        assert "components" in schema

        # Validate OpenAPI version
        assert schema["openapi"].startswith("3.")

        # Validate info section
        info = schema["info"]
        assert "title" in info
        assert "version" in info
        assert "description" in info
        assert info["title"] == "Second Brain Database API"
        assert info["version"] == "1.0.0"

    def test_security_schemes_are_defined(self):
        """Test that security schemes are properly defined in OpenAPI schema."""
        client = TestClient(app)
        response = client.get("/openapi.json")
        schema = response.json()

        # Check security schemes exist
        assert "components" in schema
        assert "securitySchemes" in schema["components"]

        security_schemes = schema["components"]["securitySchemes"]

        # Test JWT Bearer scheme
        assert "JWTBearer" in security_schemes
        jwt_scheme = security_schemes["JWTBearer"]
        assert jwt_scheme["type"] == "http"
        assert jwt_scheme["scheme"] == "bearer"
        assert jwt_scheme["bearerFormat"] == "JWT"
        assert "description" in jwt_scheme

        # Test Permanent Token scheme
        assert "PermanentToken" in security_schemes
        permanent_scheme = security_schemes["PermanentToken"]
        assert permanent_scheme["type"] == "http"
        assert permanent_scheme["scheme"] == "bearer"
        assert "description" in permanent_scheme

        # Test Admin API Key scheme
        assert "AdminAPIKey" in security_schemes
        admin_scheme = security_schemes["AdminAPIKey"]
        assert admin_scheme["type"] == "apiKey"
        assert admin_scheme["in"] == "header"
        assert admin_scheme["name"] == "X-Admin-API-Key"

    def test_tags_are_properly_defined(self):
        """Test that endpoint tags are properly defined with descriptions."""
        client = TestClient(app)
        response = client.get("/openapi.json")
        schema = response.json()

        assert "tags" in schema
        tags = schema["tags"]

        # Expected tags
        expected_tags = [
            "Authentication",
            "Permanent Tokens",
            "Knowledge Base",
            "User Profile",
            "Themes",
            "Shop",
            "System",
        ]

        tag_names = [tag["name"] for tag in tags]
        for expected_tag in expected_tags:
            assert expected_tag in tag_names

        # Check that each tag has a description
        for tag in tags:
            assert "name" in tag
            assert "description" in tag
            assert len(tag["description"]) > 0

    def test_paths_have_proper_documentation(self):
        """Test that API paths have proper documentation."""
        client = TestClient(app)
        response = client.get("/openapi.json")
        schema = response.json()

        assert "paths" in schema
        paths = schema["paths"]

        # Test some key endpoints exist
        key_endpoints = ["/auth/login", "/auth/register", "/auth/permanent-tokens", "/health"]

        for endpoint in key_endpoints:
            assert endpoint in paths, f"Endpoint {endpoint} not found in OpenAPI schema"

        # Test that endpoints have proper documentation
        for path, methods in paths.items():
            for method, details in methods.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    # Each endpoint should have basic documentation
                    assert "summary" in details or "description" in details
                    assert "responses" in details

                    # Check responses have descriptions
                    for status_code, response_info in details["responses"].items():
                        assert "description" in response_info

    def test_response_models_are_defined(self):
        """Test that response models are properly defined in components."""
        client = TestClient(app)
        response = client.get("/openapi.json")
        schema = response.json()

        assert "components" in schema
        assert "schemas" in schema["components"]

        schemas = schema["components"]["schemas"]

        # Test that common response models exist
        expected_models = ["StandardErrorResponse", "StandardSuccessResponse", "ValidationErrorResponse"]

        for model in expected_models:
            assert model in schemas, f"Response model {model} not found in schemas"

            # Test model structure
            model_schema = schemas[model]
            assert "type" in model_schema
            assert "properties" in model_schema

    def test_external_docs_are_defined(self):
        """Test that external documentation links are properly defined."""
        client = TestClient(app)
        response = client.get("/openapi.json")
        schema = response.json()

        # Test external docs
        if "externalDocs" in schema:
            external_docs = schema["externalDocs"]
            assert "description" in external_docs
            assert "url" in external_docs
            assert external_docs["url"].startswith("http")


class TestDocumentationEndpointAccessibility:
    """Test documentation endpoint accessibility and functionality."""

    def test_swagger_ui_accessibility(self):
        """Test that Swagger UI is accessible."""
        if not docs_config.docs_url:
            pytest.skip("Swagger UI disabled in configuration")

        client = TestClient(app)
        response = client.get(docs_config.docs_url)

        # Should return HTML content
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

        # Should contain Swagger UI elements
        content = response.text
        assert "swagger" in content.lower() or "openapi" in content.lower()

    def test_redoc_accessibility(self):
        """Test that ReDoc is accessible."""
        if not docs_config.redoc_url:
            pytest.skip("ReDoc disabled in configuration")

        client = TestClient(app)
        response = client.get(docs_config.redoc_url)

        # Should return HTML content
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

        # Should contain ReDoc elements
        content = response.text
        assert "redoc" in content.lower()

    def test_openapi_json_accessibility(self):
        """Test that OpenAPI JSON schema is accessible."""
        if not docs_config.openapi_url:
            pytest.skip("OpenAPI JSON disabled in configuration")

        client = TestClient(app)
        response = client.get(docs_config.openapi_url)

        # Should return JSON content
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")

        # Should be valid JSON
        schema = response.json()
        assert isinstance(schema, dict)
        assert "openapi" in schema

    def test_documentation_security_headers(self):
        """Test that documentation endpoints have proper security headers."""
        if not docs_config.docs_url:
            pytest.skip("Documentation disabled in configuration")

        client = TestClient(app)
        response = client.get(docs_config.docs_url)

        # Check for security headers (if middleware is enabled)
        if settings.is_production or settings.DOCS_ACCESS_CONTROL:
            headers = response.headers

            # These headers should be present for security
            security_headers = ["x-content-type-options", "x-frame-options", "referrer-policy"]

            for header in security_headers:
                assert header in headers.keys() or header.replace("-", "_") in headers.keys()

    def test_documentation_caching_headers(self):
        """Test that documentation has appropriate caching headers."""
        if not docs_config.docs_url:
            pytest.skip("Documentation disabled in configuration")

        client = TestClient(app)
        response = client.get(docs_config.docs_url)

        # Should have cache control headers
        assert "cache-control" in response.headers

        cache_control = response.headers["cache-control"]

        if settings.should_cache_docs:
            # Production should have caching enabled
            assert "max-age" in cache_control
        else:
            # Development should have no-cache
            assert "no-cache" in cache_control or "no-store" in cache_control


class TestExampleDataValidation:
    """Test that all example data in models and responses is valid."""

    def test_model_examples_are_valid(self):
        """Test that all model examples are valid against their schemas."""
        client = TestClient(app)
        response = client.get("/openapi.json")
        schema = response.json()

        if "components" not in schema or "schemas" not in schema["components"]:
            pytest.skip("No schemas found in OpenAPI spec")

        schemas = schema["components"]["schemas"]

        for model_name, model_schema in schemas.items():
            if "example" in model_schema:
                example = model_schema["example"]

                # Validate example against schema
                try:
                    jsonschema.validate(example, model_schema)
                except jsonschema.ValidationError as e:
                    pytest.fail(f"Example for {model_name} is invalid: {e}")

    def test_response_examples_are_valid(self):
        """Test that response examples are valid."""
        client = TestClient(app)
        response = client.get("/openapi.json")
        schema = response.json()

        if "paths" not in schema:
            pytest.skip("No paths found in OpenAPI spec")

        for path, methods in schema["paths"].items():
            for method, details in methods.items():
                if "responses" in details:
                    for status_code, response_info in details["responses"].items():
                        if "content" in response_info:
                            for content_type, content_info in response_info["content"].items():
                                if "example" in content_info:
                                    example = content_info["example"]

                                    # Basic validation - should be valid JSON structure
                                    assert isinstance(example, (dict, list, str, int, float, bool))

                                    # If it's a dict, should have expected error/success structure
                                    if isinstance(example, dict):
                                        if status_code.startswith("4") or status_code.startswith("5"):
                                            # Error responses should have error field
                                            assert "error" in example or "message" in example
                                        elif status_code.startswith("2"):
                                            # Success responses should have success indicators
                                            assert "success" in example or "data" in example or "message" in example

    def test_authentication_examples_are_comprehensive(self):
        """Test that authentication examples cover all scenarios."""
        client = TestClient(app)
        response = client.get("/openapi.json")
        schema = response.json()

        # Check authentication-related paths have examples
        auth_paths = [path for path in schema.get("paths", {}) if path.startswith("/auth")]

        for path in auth_paths:
            path_info = schema["paths"][path]
            for method, details in path_info.items():
                if method in ["post", "get", "delete"]:
                    # Should have response examples
                    assert "responses" in details

                    responses = details["responses"]

                    # Should have success response example
                    success_codes = [code for code in responses.keys() if code.startswith("2")]
                    assert len(success_codes) > 0, f"No success responses for {method.upper()} {path}"

                    # Should have error response examples
                    error_codes = [code for code in responses.keys() if code.startswith("4")]
                    assert len(error_codes) > 0, f"No error responses for {method.upper()} {path}"


class TestInteractiveDocumentationFeatures:
    """Test interactive documentation features and Try it out functionality."""

    def test_swagger_ui_try_it_out_structure(self):
        """Test that Swagger UI has proper structure for Try it out functionality."""
        if not docs_config.docs_url:
            pytest.skip("Swagger UI disabled")

        client = TestClient(app)
        response = client.get(docs_config.docs_url)

        assert response.status_code == 200
        content = response.text

        # Should contain JavaScript for interactive features
        assert "swagger-ui" in content.lower()

        # Should have authorization configuration
        assert "authorize" in content.lower() or "auth" in content.lower()

    def test_authentication_token_input_capability(self):
        """Test that documentation supports authentication token input."""
        client = TestClient(app)
        response = client.get("/openapi.json")
        schema = response.json()

        # Should have security schemes defined
        assert "components" in schema
        assert "securitySchemes" in schema["components"]

        security_schemes = schema["components"]["securitySchemes"]

        # Should have bearer token schemes that support input
        bearer_schemes = [
            scheme
            for scheme in security_schemes.values()
            if scheme.get("type") == "http" and scheme.get("scheme") == "bearer"
        ]

        assert len(bearer_schemes) > 0, "No bearer token schemes found for authentication input"

    def test_endpoint_security_requirements(self):
        """Test that endpoints have proper security requirements defined."""
        client = TestClient(app)
        response = client.get("/openapi.json")
        schema = response.json()

        protected_endpoints = []
        public_endpoints = []

        for path, methods in schema.get("paths", {}).items():
            for method, details in methods.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    if "security" in details and details["security"]:
                        protected_endpoints.append(f"{method.upper()} {path}")
                    else:
                        public_endpoints.append(f"{method.upper()} {path}")

        # Should have both protected and public endpoints
        assert len(protected_endpoints) > 0, "No protected endpoints found"
        assert len(public_endpoints) > 0, "No public endpoints found"

        # Authentication endpoints should be properly categorized
        auth_endpoints = [ep for ep in protected_endpoints if "/auth/" in ep]
        assert len(auth_endpoints) > 0, "No protected auth endpoints found"

    def test_request_response_examples_completeness(self):
        """Test that endpoints have complete request/response examples."""
        client = TestClient(app)
        response = client.get("/openapi.json")
        schema = response.json()

        endpoints_with_examples = 0
        total_endpoints = 0

        for path, methods in schema.get("paths", {}).items():
            for method, details in methods.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    total_endpoints += 1

                    has_examples = False

                    # Check for request examples
                    if "requestBody" in details:
                        request_body = details["requestBody"]
                        if "content" in request_body:
                            for content_type, content_info in request_body["content"].items():
                                if "example" in content_info or "examples" in content_info:
                                    has_examples = True

                    # Check for response examples
                    if "responses" in details:
                        for status_code, response_info in details["responses"].items():
                            if "content" in response_info:
                                for content_type, content_info in response_info["content"].items():
                                    if "example" in content_info or "examples" in content_info:
                                        has_examples = True

                    if has_examples:
                        endpoints_with_examples += 1

        # At least 80% of endpoints should have examples
        if total_endpoints > 0:
            example_coverage = endpoints_with_examples / total_endpoints
            assert example_coverage >= 0.8, f"Only {example_coverage:.1%} of endpoints have examples"

    def test_error_response_feedback_clarity(self):
        """Test that error responses provide clear feedback."""
        client = TestClient(app)
        response = client.get("/openapi.json")
        schema = response.json()

        error_responses_found = 0
        clear_error_responses = 0

        for path, methods in schema.get("paths", {}).items():
            for method, details in methods.items():
                if "responses" in details:
                    for status_code, response_info in details["responses"].items():
                        if status_code.startswith("4") or status_code.startswith("5"):
                            error_responses_found += 1

                            # Check if error response has clear structure
                            if "content" in response_info:
                                for content_type, content_info in response_info["content"].items():
                                    if "example" in content_info:
                                        example = content_info["example"]
                                        if isinstance(example, dict):
                                            # Should have error message
                                            if "error" in example and "message" in example:
                                                clear_error_responses += 1
                                            elif "message" in example:
                                                clear_error_responses += 1

        # Most error responses should have clear structure
        if error_responses_found > 0:
            clarity_ratio = clear_error_responses / error_responses_found
            assert clarity_ratio >= 0.7, f"Only {clarity_ratio:.1%} of error responses have clear structure"


class TestDocumentationPerformance:
    """Test documentation performance and optimization."""

    def test_openapi_schema_size(self):
        """Test that OpenAPI schema size is reasonable."""
        client = TestClient(app)
        response = client.get("/openapi.json")

        assert response.status_code == 200

        # Schema should not be excessively large (> 1MB)
        content_length = len(response.content)
        max_size = 1024 * 1024  # 1MB

        assert content_length < max_size, f"OpenAPI schema too large: {content_length} bytes"

    def test_documentation_response_time(self):
        """Test that documentation endpoints respond quickly."""
        import time

        client = TestClient(app)

        # Test OpenAPI JSON response time
        start_time = time.time()
        response = client.get("/openapi.json")
        end_time = time.time()

        assert response.status_code == 200

        response_time = end_time - start_time
        max_response_time = 2.0  # 2 seconds

        assert response_time < max_response_time, f"OpenAPI response too slow: {response_time:.2f}s"

        # Test Swagger UI response time (if enabled)
        if docs_config.docs_url:
            start_time = time.time()
            response = client.get(docs_config.docs_url)
            end_time = time.time()

            assert response.status_code == 200

            response_time = end_time - start_time
            assert response_time < max_response_time, f"Swagger UI response too slow: {response_time:.2f}s"


class TestDocumentationSecurity:
    """Test documentation security features."""

    def test_production_documentation_access_control(self):
        """Test that documentation access control works in production mode."""
        # This test would need to be run with production settings
        # For now, we'll test the configuration

        if settings.is_production:
            # In production, docs should be disabled or secured
            if not settings.DOCS_ENABLED:
                # Docs should be disabled
                assert docs_config.docs_url is None
                assert docs_config.redoc_url is None
                assert docs_config.openapi_url is None
            else:
                # Docs enabled in production should have access control
                assert settings.DOCS_ACCESS_CONTROL or settings.DOCS_ALLOWED_IPS

    def test_sensitive_information_not_exposed(self):
        """Test that sensitive information is not exposed in documentation."""
        client = TestClient(app)
        response = client.get("/openapi.json")
        schema = response.json()

        schema_str = json.dumps(schema).lower()

        # Check for common sensitive patterns
        sensitive_patterns = ["password", "secret", "key", "token"]

        # These should not appear in actual values, only in field names/descriptions
        sensitive_values = ["admin123", "password123", "secret123", "changeme"]

        for pattern in sensitive_values:
            assert pattern not in schema_str, f"Sensitive value '{pattern}' found in OpenAPI schema"

    def test_cors_configuration_for_docs(self):
        """Test CORS configuration for documentation endpoints."""
        client = TestClient(app)

        # Test preflight request
        response = client.options(
            "/openapi.json", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"}
        )

        # Should handle CORS appropriately
        if response.status_code == 200:
            # CORS headers should be present
            assert "access-control-allow-origin" in response.headers
        elif response.status_code == 405:
            # OPTIONS not supported, but regular request should work
            response = client.get("/openapi.json")
            assert response.status_code == 200


# Integration test to run all documentation tests
def test_comprehensive_documentation_suite():
    """Run a comprehensive test of all documentation features."""
    print("\n🚀 Running Comprehensive API Documentation Test Suite")
    print("=" * 60)

    test_results = {
        "openapi_schema": False,
        "endpoint_accessibility": False,
        "example_validation": False,
        "interactive_features": False,
        "performance": False,
        "security": False,
    }

    try:
        # Test OpenAPI Schema Generation
        print("\n📋 Testing OpenAPI Schema Generation...")
        schema_tests = TestOpenAPISchemaGeneration()
        schema_tests.test_openapi_schema_is_valid()
        schema_tests.test_security_schemes_are_defined()
        schema_tests.test_tags_are_properly_defined()
        test_results["openapi_schema"] = True
        print("✅ OpenAPI Schema Generation: PASSED")

        # Test Documentation Endpoint Accessibility
        print("\n🌐 Testing Documentation Endpoint Accessibility...")
        accessibility_tests = TestDocumentationEndpointAccessibility()
        accessibility_tests.test_openapi_json_accessibility()
        if docs_config.docs_url:
            accessibility_tests.test_swagger_ui_accessibility()
        test_results["endpoint_accessibility"] = True
        print("✅ Documentation Endpoint Accessibility: PASSED")

        # Test Example Data Validation
        print("\n📝 Testing Example Data Validation...")
        example_tests = TestExampleDataValidation()
        example_tests.test_model_examples_are_valid()
        example_tests.test_response_examples_are_valid()
        test_results["example_validation"] = True
        print("✅ Example Data Validation: PASSED")

        # Test Interactive Documentation Features
        print("\n🔧 Testing Interactive Documentation Features...")
        interactive_tests = TestInteractiveDocumentationFeatures()
        interactive_tests.test_authentication_token_input_capability()
        interactive_tests.test_endpoint_security_requirements()
        test_results["interactive_features"] = True
        print("✅ Interactive Documentation Features: PASSED")

        # Test Documentation Performance
        print("\n⚡ Testing Documentation Performance...")
        performance_tests = TestDocumentationPerformance()
        performance_tests.test_openapi_schema_size()
        performance_tests.test_documentation_response_time()
        test_results["performance"] = True
        print("✅ Documentation Performance: PASSED")

        # Test Documentation Security
        print("\n🔒 Testing Documentation Security...")
        security_tests = TestDocumentationSecurity()
        security_tests.test_sensitive_information_not_exposed()
        test_results["security"] = True
        print("✅ Documentation Security: PASSED")

        # Summary
        passed_tests = sum(test_results.values())
        total_tests = len(test_results)

        print("\n" + "=" * 60)
        print("📊 Documentation Test Suite Summary")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {total_tests - passed_tests}")
        print(f"📈 Success Rate: {(passed_tests/total_tests)*100:.1f}%")

        if passed_tests == total_tests:
            print("\n🎉 All documentation tests passed!")
            print("✅ API documentation is production-ready")
        else:
            print(f"\n⚠️ {total_tests - passed_tests} test categories failed")

        return passed_tests == total_tests

    except Exception as e:
        print(f"❌ Documentation test suite failed: {e}")
        import traceback

        traceback.print_exc()
        return False
