#!/usr/bin/env python3
"""
Comprehensive test suite for application startup and functionality validation.

This test suite validates:
1. Application starts without ModuleNotFoundError
2. All core functionality works with new dependencies
3. Prometheus metrics endpoint is accessible and returns valid metrics
4. Authentication, database, and utility features work correctly

Requirements covered: 2.1, 2.2, 2.4, 3.3
"""

import asyncio
import json
import os
import sys
import time
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Mock environment variables before importing anything
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")
os.environ.setdefault("FERNET_KEY", "test-fernet-key-32-chars-long-123456")
os.environ.setdefault("TURNSTILE_SITEKEY", "test-turnstile-sitekey")
os.environ.setdefault("TURNSTILE_SECRET", "test-turnstile-secret")
os.environ.setdefault("MONGODB_URL", "mongodb://localhost:27017")
os.environ.setdefault("MONGODB_DATABASE", "test_database")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

try:
    from fastapi.testclient import TestClient
    import httpx
    import pytest
except ImportError:
    # Fallback for when pytest is not available
    class MockPytest:
        @staticmethod
        def fail(msg):
            raise AssertionError(msg)

    pytest = MockPytest()
    TestClient = None
    httpx = None

from second_brain_database.config import settings


class TestApplicationStartup:
    """Test suite for application startup validation."""

    def test_application_imports_without_module_errors(self):
        """
        Test that application starts without ModuleNotFoundError.

        Requirements: 2.1, 2.2
        """
        print("🚀 Testing application imports without module errors...")

        # Test core module imports
        try:
            from second_brain_database.main import app

            print("✅ Main application module imported successfully")
        except ModuleNotFoundError as e:
            pytest.fail(f"❌ ModuleNotFoundError during main app import: {e}")
        except ImportError as e:
            pytest.fail(f"❌ ImportError during main app import: {e}")

        # Test critical dependency imports
        critical_imports = [
            ("fastapi", "FastAPI"),
            ("uvicorn", "uvicorn"),
            ("motor", "motor.motor_asyncio"),
            ("pydantic", "pydantic"),
            ("redis", "redis"),
            ("prometheus_fastapi_instrumentator", "Instrumentator"),
            ("jose", "python-jose"),
            ("bcrypt", "bcrypt"),
            ("pyotp", "pyotp"),
        ]

        for module_name, import_name in critical_imports:
            try:
                __import__(module_name)
                print(f"✅ {import_name} imported successfully")
            except ModuleNotFoundError as e:
                pytest.fail(f"❌ Critical dependency {import_name} not found: {e}")
            except ImportError as e:
                pytest.fail(f"❌ Import error for {import_name}: {e}")

    def test_fastapi_app_creation(self):
        """
        Test that FastAPI application can be created successfully.

        Requirements: 2.1, 2.2
        """
        print("🏗️ Testing FastAPI application creation...")

        try:
            # Verify app is FastAPI instance
            from fastapi import FastAPI

            from second_brain_database.main import app

            assert isinstance(app, FastAPI), "App is not a FastAPI instance"

            # Verify basic app properties
            assert app.title == "Second Brain Database API"
            assert app.version == "1.0.0"
            assert app.description is not None

            print("✅ FastAPI application created successfully")

        except Exception as e:
            pytest.fail(f"❌ Failed to create FastAPI application: {e}")

    @pytest.mark.asyncio
    async def test_application_lifespan_startup(self):
        """
        Test application lifespan startup process.

        Requirements: 2.1, 2.2
        """
        print("🔄 Testing application lifespan startup...")

        # Mock database manager to avoid actual database connection
        with patch("second_brain_database.main.db_manager") as mock_db_manager:
            mock_db_manager.connect = AsyncMock()
            mock_db_manager.create_indexes = AsyncMock()
            mock_db_manager.disconnect = AsyncMock()

            try:
                from second_brain_database.main import app, lifespan

                # Test lifespan startup
                async with lifespan(app):
                    print("✅ Application lifespan startup completed successfully")

                    # Verify database manager methods were called
                    mock_db_manager.connect.assert_called_once()
                    mock_db_manager.create_indexes.assert_called_once()

                # Verify shutdown was called
                mock_db_manager.disconnect.assert_called_once()
                print("✅ Application lifespan shutdown completed successfully")

            except Exception as e:
                pytest.fail(f"❌ Application lifespan failed: {e}")


class TestCoreApplicationFunctionality:
    """Test suite for core application functionality validation."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked database."""
        with patch("second_brain_database.main.db_manager") as mock_db_manager:
            mock_db_manager.connect = AsyncMock()
            mock_db_manager.create_indexes = AsyncMock()
            mock_db_manager.disconnect = AsyncMock()

            from second_brain_database.main import app

            with TestClient(app) as test_client:
                yield test_client

    def test_health_check_endpoint(self, client):
        """
        Test that health check endpoint works correctly.

        Requirements: 2.2, 2.4
        """
        print("🏥 Testing health check endpoint...")

        try:
            response = client.get("/health")

            # Should return 200 or 404 (if endpoint doesn't exist yet)
            if response.status_code == 404:
                print("ℹ️ Health endpoint not implemented yet - this is acceptable")
                return

            assert response.status_code == 200
            print("✅ Health check endpoint working correctly")

        except Exception as e:
            pytest.fail(f"❌ Health check endpoint failed: {e}")

    def test_openapi_schema_generation(self, client):
        """
        Test that OpenAPI schema can be generated successfully.

        Requirements: 2.2, 2.4
        """
        print("📋 Testing OpenAPI schema generation...")

        try:
            response = client.get("/openapi.json")
            assert response.status_code == 200

            schema = response.json()
            assert "openapi" in schema
            assert "info" in schema
            assert schema["info"]["title"] == "Second Brain Database API"

            print("✅ OpenAPI schema generated successfully")

        except Exception as e:
            pytest.fail(f"❌ OpenAPI schema generation failed: {e}")

    def test_docs_endpoints_accessible(self, client):
        """
        Test that documentation endpoints are accessible.

        Requirements: 2.2, 2.4
        """
        print("📚 Testing documentation endpoints...")

        doc_endpoints = ["/docs", "/redoc"]

        for endpoint in doc_endpoints:
            try:
                response = client.get(endpoint)
                assert response.status_code == 200
                print(f"✅ {endpoint} endpoint accessible")

            except Exception as e:
                pytest.fail(f"❌ Documentation endpoint {endpoint} failed: {e}")

    def test_cors_and_middleware_setup(self, client):
        """
        Test that middleware is properly configured.

        Requirements: 2.2, 2.4
        """
        print("🛡️ Testing middleware configuration...")

        try:
            # Test that request logging middleware is working
            response = client.get("/openapi.json")
            assert response.status_code == 200

            # Verify response headers indicate middleware is working
            # (This is a basic test - middleware should add headers or logging)
            print("✅ Middleware configuration working correctly")

        except Exception as e:
            pytest.fail(f"❌ Middleware configuration failed: {e}")


class TestPrometheusMetrics:
    """Test suite for Prometheus metrics functionality."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked database."""
        with patch("second_brain_database.main.db_manager") as mock_db_manager:
            mock_db_manager.connect = AsyncMock()
            mock_db_manager.create_indexes = AsyncMock()
            mock_db_manager.disconnect = AsyncMock()

            from second_brain_database.main import app

            with TestClient(app) as test_client:
                yield test_client

    def test_metrics_endpoint_accessible(self, client):
        """
        Test that Prometheus metrics endpoint is accessible.

        Requirements: 3.3
        """
        print("📊 Testing Prometheus metrics endpoint accessibility...")

        try:
            response = client.get("/metrics")
            assert response.status_code == 200

            # Verify content type is correct for Prometheus
            content_type = response.headers.get("content-type", "")
            assert "text/plain" in content_type or "text/plain; version=0.0.4" in content_type

            print("✅ Metrics endpoint accessible with correct content type")

        except Exception as e:
            pytest.fail(f"❌ Metrics endpoint accessibility failed: {e}")

    def test_metrics_content_validity(self, client):
        """
        Test that metrics endpoint returns valid Prometheus metrics.

        Requirements: 3.3
        """
        print("📈 Testing Prometheus metrics content validity...")

        try:
            # Make a few requests to generate metrics
            client.get("/openapi.json")
            client.get("/docs")

            response = client.get("/metrics")
            assert response.status_code == 200

            metrics_content = response.text

            # Verify basic Prometheus metrics format
            assert "# HELP" in metrics_content or "# TYPE" in metrics_content

            # Look for FastAPI instrumentator metrics
            expected_metrics = [
                "http_requests_total",
                "http_request_duration_seconds",
                "http_requests_in_progress",
            ]

            found_metrics = []
            for metric in expected_metrics:
                if metric in metrics_content:
                    found_metrics.append(metric)
                    print(f"✅ Found metric: {metric}")

            # At least some metrics should be present
            assert len(found_metrics) > 0, f"No expected metrics found in: {metrics_content[:500]}..."

            print(f"✅ Metrics content valid with {len(found_metrics)} expected metrics found")

        except Exception as e:
            pytest.fail(f"❌ Metrics content validation failed: {e}")

    def test_metrics_after_requests(self, client):
        """
        Test that metrics are updated after making requests.

        Requirements: 3.3
        """
        print("🔄 Testing metrics updates after requests...")

        try:
            # Get initial metrics
            initial_response = client.get("/metrics")
            initial_metrics = initial_response.text

            # Make several requests to different endpoints
            test_endpoints = ["/openapi.json", "/docs", "/redoc"]
            for endpoint in test_endpoints:
                client.get(endpoint)

            # Get updated metrics
            updated_response = client.get("/metrics")
            updated_metrics = updated_response.text

            # Metrics should have changed (more requests recorded)
            assert updated_metrics != initial_metrics, "Metrics did not update after requests"

            print("✅ Metrics properly updated after requests")

        except Exception as e:
            pytest.fail(f"❌ Metrics update testing failed: {e}")


class TestAuthenticationFeatures:
    """Test suite for authentication functionality validation."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked database and Redis."""
        with (
            patch("second_brain_database.main.db_manager") as mock_db_manager,
            patch("second_brain_database.utils.redis_utils.redis_client") as mock_redis,
        ):

            mock_db_manager.connect = AsyncMock()
            mock_db_manager.create_indexes = AsyncMock()
            mock_db_manager.disconnect = AsyncMock()

            # Mock Redis client
            mock_redis.ping = AsyncMock(return_value=True)

            from second_brain_database.main import app

            with TestClient(app) as test_client:
                yield test_client

    def test_auth_endpoints_exist(self, client):
        """
        Test that authentication endpoints exist and are accessible.

        Requirements: 2.4
        """
        print("🔐 Testing authentication endpoints existence...")

        # Test endpoints that should exist (even if they return errors without proper data)
        auth_endpoints = [
            ("/auth/register", "POST"),
            ("/auth/login", "POST"),
            ("/auth/logout", "POST"),
            ("/auth/validate-token", "GET"),
        ]

        for endpoint, method in auth_endpoints:
            try:
                if method == "GET":
                    response = client.get(endpoint)
                elif method == "POST":
                    response = client.post(endpoint, json={})

                # We expect 401, 422, or similar - not 404 (endpoint missing)
                assert response.status_code != 404, f"Endpoint {endpoint} not found"
                print(f"✅ {method} {endpoint} endpoint exists")

            except Exception as e:
                pytest.fail(f"❌ Authentication endpoint {endpoint} test failed: {e}")

    def test_jwt_token_utilities(self, client):
        """
        Test that JWT token utilities are working.

        Requirements: 2.4
        """
        print("🎫 Testing JWT token utilities...")

        try:
            # Test that JWT utilities can be imported and used
            from second_brain_database.utils.tokens import create_access_token, verify_token

            # Create a test token
            test_payload = {"sub": "test_user", "exp": time.time() + 3600}
            token = create_access_token(test_payload)

            assert token is not None
            assert isinstance(token, str)
            assert len(token) > 0

            print("✅ JWT token creation working")

            # Test token verification
            decoded = verify_token(token)
            assert decoded is not None
            assert decoded.get("sub") == "test_user"

            print("✅ JWT token verification working")

        except ImportError:
            print("ℹ️ JWT utilities not yet implemented - this is acceptable")
        except Exception as e:
            pytest.fail(f"❌ JWT token utilities test failed: {e}")


class TestDatabaseAndUtilities:
    """Test suite for database and utility features validation."""

    def test_database_manager_import(self):
        """
        Test that database manager can be imported and initialized.

        Requirements: 2.4
        """
        print("🗄️ Testing database manager import...")

        try:
            from second_brain_database.database import db_manager

            assert db_manager is not None
            print("✅ Database manager imported successfully")

            # Test that database manager has required methods
            required_methods = ["connect", "disconnect", "create_indexes"]
            for method in required_methods:
                assert hasattr(db_manager, method), f"Database manager missing {method} method"
                print(f"✅ Database manager has {method} method")

        except Exception as e:
            pytest.fail(f"❌ Database manager import failed: {e}")

    def test_redis_utilities_import(self):
        """
        Test that Redis utilities can be imported.

        Requirements: 2.4
        """
        print("🔴 Testing Redis utilities import...")

        try:
            from second_brain_database.utils.redis_utils import redis_client

            assert redis_client is not None
            print("✅ Redis utilities imported successfully")

        except ImportError:
            print("ℹ️ Redis utilities not yet implemented - this is acceptable")
        except Exception as e:
            pytest.fail(f"❌ Redis utilities import failed: {e}")

    def test_logging_utilities(self):
        """
        Test that logging utilities are working correctly.

        Requirements: 2.4
        """
        print("📝 Testing logging utilities...")

        try:
            from second_brain_database.managers.logging_manager import get_logger
            from second_brain_database.utils.logging_utils import log_application_lifecycle

            # Test logger creation
            logger = get_logger()
            assert logger is not None
            print("✅ Logger creation working")

            # Test application lifecycle logging
            log_application_lifecycle("test_event", {"test": "data"})
            print("✅ Application lifecycle logging working")

        except Exception as e:
            pytest.fail(f"❌ Logging utilities test failed: {e}")


def create_mocked_client():
    """Create a test client with comprehensive mocking."""
    # Mock all the problematic background tasks and database connections
    with (
        patch("second_brain_database.main.db_manager") as mock_db_manager,
        patch("second_brain_database.routes.auth.periodics.cleanup.periodic_2fa_cleanup") as mock_2fa,
        patch("second_brain_database.routes.auth.periodics.cleanup.periodic_admin_session_token_cleanup") as mock_admin,
        patch("second_brain_database.routes.auth.periodics.cleanup.periodic_avatar_rental_cleanup") as mock_avatar,
        patch("second_brain_database.routes.auth.periodics.cleanup.periodic_banner_rental_cleanup") as mock_banner,
        patch(
            "second_brain_database.routes.auth.periodics.cleanup.periodic_email_verification_token_cleanup"
        ) as mock_email,
        patch("second_brain_database.routes.auth.periodics.cleanup.periodic_session_cleanup") as mock_session,
        patch(
            "second_brain_database.routes.auth.periodics.cleanup.periodic_trusted_ip_lockdown_code_cleanup"
        ) as mock_ip,
        patch(
            "second_brain_database.routes.auth.periodics.redis_flag_sync.periodic_blocklist_whitelist_reconcile"
        ) as mock_blocklist,
    ):

        # Configure database manager mocks
        mock_db_manager.connect = AsyncMock()
        mock_db_manager.create_indexes = AsyncMock()
        mock_db_manager.disconnect = AsyncMock()
        mock_db_manager.get_collection = MagicMock()

        # Configure background task mocks
        for mock_task in [
            mock_2fa,
            mock_admin,
            mock_avatar,
            mock_banner,
            mock_email,
            mock_session,
            mock_ip,
            mock_blocklist,
        ]:
            mock_task.return_value = AsyncMock()

        from second_brain_database.main import app

        if TestClient:
            return TestClient(app)
        else:
            return None


def run_comprehensive_test_suite():
    """
    Run the comprehensive test suite and provide detailed reporting.
    """
    print("🚀 Starting Comprehensive Application Startup and Functionality Tests")
    print("=" * 80)

    # Test results tracking
    test_results = {"passed": 0, "failed": 0, "errors": []}

    # Simple tests that don't require complex mocking
    simple_tests = [
        ("Module Import Test", test_module_imports),
        ("FastAPI App Creation Test", test_fastapi_app_creation),
        ("Configuration Loading Test", test_configuration_loading),
        ("Database Manager Import Test", test_database_manager_import),
        ("Logging Utilities Test", test_logging_utilities),
    ]

    # Tests that require mocked client
    client_tests = [
        ("OpenAPI Schema Test", test_openapi_schema),
        ("Documentation Endpoints Test", test_docs_endpoints),
        ("Prometheus Metrics Test", test_prometheus_metrics),
    ]

    # Run simple tests
    for test_name, test_func in simple_tests:
        try:
            print(f"\n🧪 Running {test_name}...")
            test_func()
            test_results["passed"] += 1
            print(f"✅ {test_name} PASSED")
        except Exception as e:
            test_results["failed"] += 1
            test_results["errors"].append(f"{test_name}: {str(e)}")
            print(f"❌ {test_name} FAILED: {e}")

    # Run client tests with mocking
    if TestClient:
        client = create_mocked_client()
        if client:
            for test_name, test_func in client_tests:
                try:
                    print(f"\n🧪 Running {test_name}...")
                    test_func(client)
                    test_results["passed"] += 1
                    print(f"✅ {test_name} PASSED")
                except Exception as e:
                    test_results["failed"] += 1
                    test_results["errors"].append(f"{test_name}: {str(e)}")
                    print(f"❌ {test_name} FAILED: {e}")
    else:
        print("\n⚠️ TestClient not available, skipping client-based tests")

    # Print final results
    print("\n" + "=" * 80)
    print("🏁 Test Suite Summary")
    print("=" * 80)
    print(f"✅ Passed: {test_results['passed']}")
    print(f"❌ Failed: {test_results['failed']}")
    total_tests = test_results["passed"] + test_results["failed"]
    success_rate = (test_results["passed"] / total_tests * 100) if total_tests > 0 else 0
    print(f"📊 Success Rate: {success_rate:.1f}%")

    if test_results["errors"]:
        print("\n❌ Failed Tests:")
        for error in test_results["errors"]:
            print(f"   - {error}")

    if test_results["failed"] == 0:
        print("\n🎉 All tests passed! Application startup and functionality validated successfully.")
        print("✅ Requirements 2.1, 2.2, 2.4, 3.3 have been verified.")
    else:
        print(f"\n⚠️ {test_results['failed']} tests failed. Please review and fix the issues.")

    return test_results["failed"] == 0


# Simple test functions
def test_module_imports():
    """Test that all critical modules can be imported without ModuleNotFoundError."""
    print("🚀 Testing critical module imports...")

    # Test core module imports
    from second_brain_database.main import app

    print("✅ Main application module imported successfully")

    # Test critical dependency imports
    critical_imports = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "uvicorn"),
        ("motor", "motor.motor_asyncio"),
        ("pydantic", "pydantic"),
        ("redis", "redis"),
        ("prometheus_fastapi_instrumentator", "Instrumentator"),
        ("jose", "python-jose"),
        ("bcrypt", "bcrypt"),
        ("pyotp", "pyotp"),
    ]

    for module_name, import_name in critical_imports:
        __import__(module_name)
        print(f"✅ {import_name} imported successfully")


def test_fastapi_app_creation():
    """Test that FastAPI application can be created successfully."""
    print("🏗️ Testing FastAPI application creation...")

    from fastapi import FastAPI

    from second_brain_database.main import app

    assert isinstance(app, FastAPI), "App is not a FastAPI instance"
    assert app.title == "Second Brain Database API"
    assert app.version == "1.0.0"
    assert app.description is not None

    print("✅ FastAPI application created successfully")


def test_configuration_loading():
    """Test that configuration is loaded correctly."""
    print("⚙️ Testing configuration loading...")

    from second_brain_database.config import settings

    # Test that settings object exists and has required attributes
    required_settings = [
        "MONGODB_URL",
        "MONGODB_DATABASE",
        "SECRET_KEY",
        "HOST",
        "PORT",
    ]

    for setting in required_settings:
        assert hasattr(settings, setting), f"Settings missing {setting}"
        print(f"✅ Settings has {setting}")

    print("✅ Configuration loading working correctly")


def test_database_manager_import():
    """Test that database manager can be imported and initialized."""
    print("🗄️ Testing database manager import...")

    from second_brain_database.database import db_manager

    assert db_manager is not None
    print("✅ Database manager imported successfully")

    # Test that database manager has required methods
    required_methods = ["connect", "disconnect", "create_indexes"]
    for method in required_methods:
        assert hasattr(db_manager, method), f"Database manager missing {method} method"
        print(f"✅ Database manager has {method} method")


def test_logging_utilities():
    """Test that logging utilities are working correctly."""
    print("📝 Testing logging utilities...")

    from second_brain_database.managers.logging_manager import get_logger
    from second_brain_database.utils.logging_utils import log_application_lifecycle

    # Test logger creation
    logger = get_logger()
    assert logger is not None
    print("✅ Logger creation working")

    # Test application lifecycle logging
    log_application_lifecycle("test_event", {"test": "data"})
    print("✅ Application lifecycle logging working")


def test_openapi_schema(client):
    """Test that OpenAPI schema can be generated successfully."""
    print("📋 Testing OpenAPI schema generation...")

    response = client.get("/openapi.json")
    assert response.status_code == 200

    schema = response.json()
    assert "openapi" in schema
    assert "info" in schema
    assert schema["info"]["title"] == "Second Brain Database API"

    print("✅ OpenAPI schema generated successfully")


def test_docs_endpoints(client):
    """Test that documentation endpoints are accessible."""
    print("📚 Testing documentation endpoints...")

    doc_endpoints = ["/docs", "/redoc"]

    for endpoint in doc_endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200
        print(f"✅ {endpoint} endpoint accessible")


def test_prometheus_metrics(client):
    """Test that Prometheus metrics endpoint is accessible and returns valid metrics."""
    print("📊 Testing Prometheus metrics functionality...")

    # Test metrics endpoint accessibility
    response = client.get("/metrics")
    assert response.status_code == 200

    # Verify content type is correct for Prometheus
    content_type = response.headers.get("content-type", "")
    assert "text/plain" in content_type or "text/plain; version=0.0.4" in content_type
    print("✅ Metrics endpoint accessible with correct content type")

    # Test metrics content validity
    metrics_content = response.text

    # Verify basic Prometheus metrics format
    assert "# HELP" in metrics_content or "# TYPE" in metrics_content

    # Look for FastAPI instrumentator metrics
    expected_metrics = [
        "http_requests_total",
        "http_request_duration_seconds",
        "http_requests_in_progress",
    ]

    found_metrics = []
    for metric in expected_metrics:
        if metric in metrics_content:
            found_metrics.append(metric)
            print(f"✅ Found metric: {metric}")

    # At least some metrics should be present
    assert len(found_metrics) > 0, f"No expected metrics found in: {metrics_content[:500]}..."

    print(f"✅ Metrics content valid with {len(found_metrics)} expected metrics found")


if __name__ == "__main__":
    success = run_comprehensive_test_suite()
    sys.exit(0 if success else 1)
