#!/usr/bin/env python3
"""
Simple test for logging utilities without external dependencies.
"""

import os
import sys
import time
from unittest.mock import Mock, patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def test_basic_imports():
    """Test that we can import the basic logging utilities."""
    try:
        # Test basic imports that don't require FastAPI
        from second_brain_database.utils.logging_utils import (
            DatabaseContext,
            DatabaseLogger,
            PerformanceLogger,
            SecurityContext,
            SecurityLogger,
            ip_address_context,
            request_id_context,
            user_id_context,
        )

        print("✓ Successfully imported core logging utilities")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def test_performance_logger():
    """Test PerformanceLogger functionality."""
    try:
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            from second_brain_database.utils.logging_utils import PerformanceLogger

            perf_logger = PerformanceLogger()
            perf_logger.log_operation("test_operation", 0.5)

            # Verify logger was called
            assert mock_logger.info.called, "Logger info method should be called"
            call_args = mock_logger.info.call_args[0][0]
            assert "test_operation" in call_args, "Operation name should be in log"
            assert "0.500s" in call_args, "Duration should be in log"

        print("✓ PerformanceLogger test passed")
        return True
    except Exception as e:
        print(f"✗ PerformanceLogger test failed: {e}")
        return False


def test_database_logger():
    """Test DatabaseLogger functionality."""
    try:
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            from second_brain_database.utils.logging_utils import DatabaseContext, DatabaseLogger

            db_logger = DatabaseLogger()
            context = DatabaseContext(
                operation="find", collection="users", query={"username": "test"}, duration=0.1, result_count=1
            )

            db_logger.log_query(context)

            # Verify logger was called
            assert mock_logger.info.called, "Logger info method should be called"
            call_args = mock_logger.info.call_args[0][0]
            assert "find" in call_args, "Operation should be in log"
            assert "users" in call_args, "Collection should be in log"
            assert "0.100s" in call_args, "Duration should be in log"

        print("✓ DatabaseLogger test passed")
        return True
    except Exception as e:
        print(f"✗ DatabaseLogger test failed: {e}")
        return False


def test_security_logger():
    """Test SecurityLogger functionality."""
    try:
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            from second_brain_database.utils.logging_utils import SecurityContext, SecurityLogger

            security_logger = SecurityLogger()
            context = SecurityContext(
                event_type="login",
                user_id="user123",
                ip_address="192.168.1.1",
                success=True,
                details={"method": "password"},
            )

            security_logger.log_auth_event(context)

            # Verify logger was called
            assert mock_logger.info.called, "Logger info method should be called"
            call_args = mock_logger.info.call_args[0][0]
            assert "AUTH SUCCESS" in call_args, "Auth success should be in log"
            assert "login" in call_args, "Event type should be in log"
            assert "user123" in call_args, "User ID should be in log"

        print("✓ SecurityLogger test passed")
        return True
    except Exception as e:
        print(f"✗ SecurityLogger test failed: {e}")
        return False


def test_context_variables():
    """Test context variables functionality."""
    try:
        from second_brain_database.utils.logging_utils import ip_address_context, request_id_context, user_id_context

        # Test initial empty state
        assert request_id_context.get("") == "", "Initial request_id should be empty"
        assert user_id_context.get("") == "", "Initial user_id should be empty"
        assert ip_address_context.get("") == "", "Initial ip_address should be empty"

        # Test setting values
        request_id_context.set("req-123")
        user_id_context.set("user-456")
        ip_address_context.set("192.168.1.1")

        assert request_id_context.get("") == "req-123", "Request ID should be set"
        assert user_id_context.get("") == "user-456", "User ID should be set"
        assert ip_address_context.get("") == "192.168.1.1", "IP address should be set"

        print("✓ Context variables test passed")
        return True
    except Exception as e:
        print(f"✗ Context variables test failed: {e}")
        return False


def test_query_sanitization():
    """Test query sanitization functionality."""
    try:
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            from second_brain_database.utils.logging_utils import DatabaseContext, DatabaseLogger

            db_logger = DatabaseLogger()
            context = DatabaseContext(
                operation="update",
                collection="users",
                query={"username": "test", "password": "secret123", "token": "abc123", "normal_field": "value"},
                duration=0.1,
            )

            db_logger.log_query(context)

            # Verify logger was called and sensitive data was redacted
            assert mock_logger.info.called, "Logger info method should be called"
            call_args = mock_logger.info.call_args[0][0]
            assert "[REDACTED]" in call_args, "Sensitive data should be redacted"
            assert "secret123" not in call_args, "Password should not appear in log"
            assert "abc123" not in call_args, "Token should not appear in log"
            assert "value" in call_args, "Normal field should appear in log"

        print("✓ Query sanitization test passed")
        return True
    except Exception as e:
        print(f"✗ Query sanitization test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("Running logging utilities tests...")
    print("=" * 50)

    tests = [
        test_basic_imports,
        test_performance_logger,
        test_database_logger,
        test_security_logger,
        test_context_variables,
        test_query_sanitization,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    print("=" * 50)
    print(f"Tests passed: {passed}/{total}")

    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    exit(main())
