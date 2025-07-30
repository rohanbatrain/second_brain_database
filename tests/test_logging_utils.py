"""
Tests for logging enhancement utilities.

This module tests the logging utilities including performance logging,
database operation logging, security event logging, and request context management.
"""

import asyncio
import os
import sys
import time
from unittest.mock import Mock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from second_brain_database.utils.logging_utils import (
    DatabaseContext,
    DatabaseLogger,
    PerformanceLogger,
    SecurityContext,
    SecurityLogger,
    ip_address_context,
    log_auth_failure,
    log_auth_success,
    log_database_operation,
    log_performance,
    log_security_event,
    request_id_context,
    user_id_context,
)


class TestPerformanceLogging:
    """Test performance logging functionality."""

    def test_performance_logger_basic(self):
        """Test basic performance logging."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            perf_logger = PerformanceLogger()
            perf_logger.log_operation("test_operation", 0.5)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "test_operation" in call_args
            assert "0.500s" in call_args

    def test_performance_logger_slow_operation(self):
        """Test slow operation logging."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            perf_logger = PerformanceLogger()
            perf_logger.log_slow_operation("slow_operation", 2.0, threshold=1.0)

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "SLOW OPERATION" in call_args
            assert "slow_operation" in call_args
            assert "2.000s" in call_args

    def test_performance_decorator_sync(self):
        """Test performance decorator on synchronous function."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            @log_performance("test_sync_operation")
            def test_function():
                time.sleep(0.1)
                return "result"

            result = test_function()

            assert result == "result"
            mock_logger.info.assert_called()
            call_args = mock_logger.info.call_args[0][0]
            assert "test_sync_operation" in call_args

    @pytest.mark.asyncio
    async def test_performance_decorator_async(self):
        """Test performance decorator on asynchronous function."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            @log_performance("test_async_operation")
            async def test_async_function():
                await asyncio.sleep(0.1)
                return "async_result"

            result = await test_async_function()

            assert result == "async_result"
            mock_logger.info.assert_called()
            call_args = mock_logger.info.call_args[0][0]
            assert "test_async_operation" in call_args

    def test_performance_decorator_with_args(self):
        """Test performance decorator with argument logging."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            @log_performance("test_with_args", include_args=True)
            def test_function(arg1, password="secret", normal_arg="value"):
                return f"{arg1}_{normal_arg}"

            result = test_function("test", password="secret123", normal_arg="data")

            assert result == "test_data"
            mock_logger.info.assert_called()
            call_args = mock_logger.info.call_args[0][0]
            assert "test_with_args" in call_args
            assert "[REDACTED]" in call_args  # Password should be redacted
            assert "data" in call_args  # Normal arg should be visible


class TestDatabaseLogging:
    """Test database operation logging functionality."""

    def test_database_logger_basic(self):
        """Test basic database logging."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            db_logger = DatabaseLogger()
            context = DatabaseContext(
                operation="find", collection="users", query={"username": "test"}, duration=0.1, result_count=1
            )

            db_logger.log_query(context)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "find" in call_args
            assert "users" in call_args
            assert "0.100s" in call_args
            assert "Results: 1" in call_args

    def test_database_logger_error(self):
        """Test database error logging."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            db_logger = DatabaseLogger()
            context = DatabaseContext(
                operation="insert",
                collection="users",
                query={"username": "test"},
                duration=0.05,
                error="Connection timeout",
            )

            db_logger.log_query(context)

            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args[0][0]
            assert "insert" in call_args
            assert "users" in call_args
            assert "FAILED" in call_args
            assert "Connection timeout" in call_args

    def test_database_logger_slow_query(self):
        """Test slow query logging."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            db_logger = DatabaseLogger()
            context = DatabaseContext(operation="find", collection="users", query={"complex": "query"}, duration=1.5)

            db_logger.log_slow_query(context, threshold=0.5)

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "SLOW QUERY" in call_args
            assert "1.500s" in call_args

    def test_database_decorator(self):
        """Test database operation decorator."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            @log_database_operation("find", "users")
            def mock_db_operation(query=None):
                # Simulate database result
                result = Mock()
                result.__len__ = Mock(return_value=5)
                return result

            result = mock_db_operation(query={"username": "test"})

            assert result is not None
            mock_logger.info.assert_called()
            call_args = mock_logger.info.call_args[0][0]
            assert "find" in call_args
            assert "users" in call_args

    def test_query_sanitization(self):
        """Test sensitive data sanitization in queries."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            db_logger = DatabaseLogger()
            context = DatabaseContext(
                operation="update",
                collection="users",
                query={"username": "test", "password": "secret123", "token": "abc123", "normal_field": "value"},
                duration=0.1,
            )

            db_logger.log_query(context)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "[REDACTED]" in call_args
            assert "secret123" not in call_args
            assert "abc123" not in call_args
            assert "value" in call_args  # Normal field should be visible


class TestSecurityLogging:
    """Test security event logging functionality."""

    def test_security_logger_auth_success(self):
        """Test successful authentication logging."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            security_logger = SecurityLogger()
            context = SecurityContext(
                event_type="login",
                user_id="user123",
                ip_address="192.168.1.1",
                success=True,
                details={"method": "password"},
            )

            security_logger.log_auth_event(context)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "AUTH SUCCESS" in call_args
            assert "login" in call_args
            assert "user123" in call_args
            assert "192.168.1.1" in call_args

    def test_security_logger_auth_failure(self):
        """Test failed authentication logging."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            security_logger = SecurityLogger()
            context = SecurityContext(
                event_type="login",
                user_id="user123",
                ip_address="192.168.1.1",
                success=False,
                details={"reason": "invalid_password"},
            )

            security_logger.log_auth_event(context)

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "AUTH FAILED" in call_args
            assert "login" in call_args
            assert "invalid_password" in call_args

    def test_security_logger_violation(self):
        """Test security violation logging."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            security_logger = SecurityLogger()
            security_logger.log_security_violation(
                event_type="brute_force_attempt",
                details={"attempts": 10, "timeframe": "5min"},
                user_id="user123",
                ip_address="192.168.1.1",
            )

            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args[0][0]
            assert "SECURITY VIOLATION" in call_args
            assert "brute_force_attempt" in call_args
            assert "user123" in call_args

    def test_security_logger_access_granted(self):
        """Test access granted logging."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            security_logger = SecurityLogger()
            security_logger.log_access_attempt(
                resource="/admin/users", success=True, user_id="admin123", ip_address="192.168.1.1"
            )

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "ACCESS GRANTED" in call_args
            assert "/admin/users" in call_args
            assert "admin123" in call_args

    def test_security_logger_access_denied(self):
        """Test access denied logging."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            security_logger = SecurityLogger()
            security_logger.log_access_attempt(
                resource="/admin/users",
                success=False,
                user_id="user123",
                ip_address="192.168.1.1",
                details={"reason": "insufficient_permissions"},
            )

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "ACCESS DENIED" in call_args
            assert "/admin/users" in call_args
            assert "insufficient_permissions" in call_args


class TestConvenienceFunctions:
    """Test convenience logging functions."""

    def test_log_auth_success(self):
        """Test log_auth_success convenience function."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            log_auth_success("login", "user123", "192.168.1.1", {"method": "2fa"})

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "AUTH SUCCESS" in call_args
            assert "login" in call_args
            assert "user123" in call_args

    def test_log_auth_failure(self):
        """Test log_auth_failure convenience function."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            log_auth_failure("login", "user123", "192.168.1.1", {"reason": "invalid_2fa"})

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "AUTH FAILED" in call_args
            assert "login" in call_args
            assert "invalid_2fa" in call_args

    def test_log_security_event(self):
        """Test log_security_event convenience function."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            log_security_event("suspicious_activity", {"pattern": "unusual_login_times"}, "user123")

            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args[0][0]
            assert "SECURITY VIOLATION" in call_args
            assert "suspicious_activity" in call_args


class TestContextVariables:
    """Test context variable functionality."""

    def test_context_variables(self):
        """Test setting and getting context variables."""
        # Test initial empty state
        assert request_id_context.get("") == ""
        assert user_id_context.get("") == ""
        assert ip_address_context.get("") == ""

        # Test setting values
        request_id_context.set("req-123")
        user_id_context.set("user-456")
        ip_address_context.set("192.168.1.1")

        assert request_id_context.get("") == "req-123"
        assert user_id_context.get("") == "user-456"
        assert ip_address_context.get("") == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_request_context_manager(self):
        """Test request context manager."""
        from second_brain_database.utils.logging_utils import request_context

        # Initial state
        assert request_id_context.get("") == ""

        async with request_context(request_id="test-123", user_id="user-456"):
            assert request_id_context.get("") == "test-123"
            assert user_id_context.get("") == "user-456"

        # Context should be restored after exiting
        assert request_id_context.get("") == ""
        assert user_id_context.get("") == ""


if __name__ == "__main__":
    pytest.main([__file__])
