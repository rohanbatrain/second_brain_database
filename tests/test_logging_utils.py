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
            # Should have at least 2 calls: Starting and Completed
            assert mock_logger.info.call_count >= 2
            # Check the completed call (last info call)
            completed_call = [call for call in mock_logger.info.call_args_list if "Completed" in str(call)]
            assert len(completed_call) > 0
            call_args = completed_call[0][0]
            format_string = call_args[0]
            args = call_args[1:]
            assert "Completed %s in %.3fs" in format_string
            assert args[1] == "test_sync_operation"

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
            # Should have at least 2 calls: Starting and Completed
            assert mock_logger.info.call_count >= 2
            # Check the completed call (last info call)
            completed_call = [call for call in mock_logger.info.call_args_list if "Completed" in str(call)]
            assert len(completed_call) > 0
            call_args = completed_call[0][0]
            format_string = call_args[0]
            args = call_args[1:]
            assert "Completed %s in %.3fs" in format_string
            assert args[1] == "test_async_operation"

    def test_performance_decorator_with_args(self):
        """Test performance decorator with argument logging."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            @log_performance("test_with_args", log_args=True)
            def test_function(arg1, password="secret", normal_arg="value"):
                return f"{arg1}_{normal_arg}"

            result = test_function("test", password="secret123", normal_arg="data")

            assert result == "test_data"
            # Should have at least 2 calls: Starting (with args) and Completed
            assert mock_logger.info.call_count >= 2
            # Check the starting call (first info call)
            starting_call = [call for call in mock_logger.info.call_args_list if "Starting" in str(call)]
            assert len(starting_call) > 0
            call_args = starting_call[0][0]
            format_string = call_args[0]
            args = call_args[1:]
            assert "Starting %s with args: %s" in format_string
            assert args[1] == "test_with_args"
            # Check that sensitive data is redacted
            args_data = str(args[2])
            assert "<REDACTED>" in args_data  # Password should be redacted
            assert "data" in args_data  # Normal arg should be visible


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

            db_logger.log_operation(context)

            mock_logger.info.assert_called_once()
            # Check the format string and arguments
            call_args = mock_logger.info.call_args[0]
            format_string = call_args[0]
            args = call_args[1:]
            
            assert "DB %s on %s completed in %.3fs - %s records affected" in format_string
            assert args[0] == "find"  # operation
            assert args[1] == "users"  # collection
            assert args[2] == 0.1  # duration
            assert args[3] == 1  # result_count

    def test_database_logger_without_result_count(self):
        """Test database logging without result count."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            db_logger = DatabaseLogger()
            context = DatabaseContext(
                operation="insert",
                collection="users",
                query={"username": "test"},
                duration=0.05,
            )

            db_logger.log_operation(context)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0]
            format_string = call_args[0]
            args = call_args[1:]
            
            assert "DB %s on %s completed in %.3fs" in format_string
            assert args[0] == "insert"  # operation
            assert args[1] == "users"  # collection
            assert args[2] == 0.05  # duration

    def test_database_logger_without_duration(self):
        """Test database operation logging without duration."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            db_logger = DatabaseLogger()
            context = DatabaseContext(operation="find", collection="users", query={"complex": "query"})

            db_logger.log_operation(context)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0]
            format_string = call_args[0]
            args = call_args[1:]
            
            assert "DB %s on %s" in format_string
            assert args[0] == "find"  # operation
            assert args[1] == "users"  # collection

    def test_database_decorator(self):
        """Test database operation decorator."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            @log_database_operation("users", "find")
            def mock_db_operation(query=None):
                # Simulate database result
                result = Mock()
                result.__len__ = Mock(return_value=5)
                return result

            result = mock_db_operation(query={"username": "test"})

            assert result is not None
            # Should have at least 2 calls: Starting and Completed
            assert mock_logger.info.call_count >= 2
            # Check the completed call
            completed_call = [call for call in mock_logger.info.call_args_list if "completed" in str(call)]
            assert len(completed_call) > 0
            call_args = completed_call[0][0]
            format_string = call_args[0]
            args = call_args[1:]
            assert "DB %s on %s completed in %.3fs" in format_string
            assert args[1] == "find"  # operation_type
            assert args[2] == "users"  # collection_name

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

            db_logger.log_operation(context)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0]
            # The log_data dictionary should contain sanitized query
            log_data = call_args[-1]  # Last argument is the log_data dict
            assert "<REDACTED>" in str(log_data)
            assert "secret123" not in str(log_data)
            assert "abc123" not in str(log_data)
            assert "value" in str(log_data)  # Normal field should be visible


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

            security_logger.log_event(context)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0]
            format_string = call_args[0]
            args = call_args[1:]
            
            assert "SECURITY EVENT [%s]: %s" in format_string
            assert args[0] == "SUCCESS"  # status
            assert args[1] == "login"  # event_type
            # Check that event_data contains expected values
            event_data = args[2]
            assert event_data["user_id"] == "user123"
            assert event_data["ip_address"] == "192.168.1.1"

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

            security_logger.log_event(context)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0]
            format_string = call_args[0]
            args = call_args[1:]
            
            assert "SECURITY EVENT [%s]: %s" in format_string
            assert args[0] == "FAILURE"  # status
            assert args[1] == "login"  # event_type
            # Check that event_data contains expected values
            event_data = args[2]
            assert event_data["user_id"] == "user123"
            assert event_data["success"] == False
            assert "invalid_password" in str(event_data["details"])




class TestConvenienceFunctions:
    """Test convenience logging functions."""

    def test_log_auth_success(self):
        """Test log_auth_success convenience function."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            log_auth_success("login", "user123", "192.168.1.1", {"method": "2fa"})

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0]
            format_string = call_args[0]
            args = call_args[1:]
            
            assert "SECURITY EVENT [%s]: %s" in format_string
            assert args[0] == "SUCCESS"  # status
            assert args[1] == "login"  # event_type
            # Check that event_data contains expected values
            event_data = args[2]
            assert event_data["user_id"] == "user123"
            assert event_data["ip_address"] == "192.168.1.1"

    def test_log_auth_failure(self):
        """Test log_auth_failure convenience function."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            log_auth_failure("login", "user123", "192.168.1.1", {"reason": "invalid_2fa"})

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0]
            format_string = call_args[0]
            args = call_args[1:]
            
            assert "SECURITY EVENT [%s]: %s" in format_string
            assert args[0] == "FAILURE"  # status
            assert args[1] == "login"  # event_type
            # Check that event_data contains expected values
            event_data = args[2]
            assert event_data["user_id"] == "user123"
            assert event_data["success"] == False
            assert "invalid_2fa" in str(event_data["details"])

    def test_log_security_event(self):
        """Test log_security_event convenience function."""
        with patch("second_brain_database.utils.logging_utils.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            log_security_event("suspicious_activity", "user123", "192.168.1.1", True, {"pattern": "unusual_login_times"})

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0]
            format_string = call_args[0]
            args = call_args[1:]
            
            assert "SECURITY EVENT [%s]: %s" in format_string
            assert args[0] == "SUCCESS"  # status
            assert args[1] == "suspicious_activity"  # event_type
            # Check that event_data contains expected values
            event_data = args[2]
            assert event_data["user_id"] == "user123"
            assert event_data["ip_address"] == "192.168.1.1"


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




if __name__ == "__main__":
    pytest.main([__file__])
