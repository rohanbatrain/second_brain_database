"""
Integration tests for enterprise error handling and resilience system.

This test suite verifies the comprehensive error handling, recovery mechanisms,
and resilience patterns implemented for the family management system.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from second_brain_database.utils.error_handling import (
    BulkheadCapacityError,
    BulkheadSemaphore,
    CircuitBreaker,
    CircuitBreakerOpenError,
    ErrorContext,
    ErrorSeverity,
    RetryConfig,
    RetryExhaustedError,
    RetryStrategy,
    ValidationError,
    create_user_friendly_error,
    handle_errors,
    sanitize_sensitive_data,
    validate_input,
)
from second_brain_database.utils.error_monitoring import (
    Alert,
    AlertType,
    ErrorEvent,
    ErrorMonitor,
    ErrorPattern,
    EscalationLevel,
    error_monitor,
    record_error_event,
)
from second_brain_database.utils.error_recovery import (
    ErrorRecoveryManager,
    RecoveryStatus,
    RecoveryStrategy,
    recover_from_database_error,
    recover_from_redis_error,
    recover_with_graceful_degradation,
)


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    @pytest.fixture
    def circuit_breaker(self):
        """Create a circuit breaker for testing."""
        return CircuitBreaker("test_service", failure_threshold=3, recovery_timeout=1)

    async def test_circuit_breaker_closed_state(self, circuit_breaker):
        """Test circuit breaker in closed state allows calls."""

        async def success_func():
            return "success"

        result = await circuit_breaker.call(success_func)
        assert result == "success"
        assert circuit_breaker.state.value == "closed"
        assert circuit_breaker.failure_count == 0

    async def test_circuit_breaker_opens_on_failures(self, circuit_breaker):
        """Test circuit breaker opens after threshold failures."""

        async def failure_func():
            raise Exception("Test failure")

        # Trigger failures to open circuit breaker
        for i in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call(failure_func)

        assert circuit_breaker.state.value == "open"
        assert circuit_breaker.failure_count == 3

        # Circuit breaker should reject calls when open
        with pytest.raises(CircuitBreakerOpenError):
            await circuit_breaker.call(failure_func)

    async def test_circuit_breaker_half_open_recovery(self, circuit_breaker):
        """Test circuit breaker recovery through half-open state."""

        async def failure_func():
            raise Exception("Test failure")

        async def success_func():
            return "recovered"

        # Open the circuit breaker
        for i in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call(failure_func)

        assert circuit_breaker.state.value == "open"

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # Should move to half-open and allow one call
        result = await circuit_breaker.call(success_func)
        assert result == "recovered"
        assert circuit_breaker.state.value == "closed"
        assert circuit_breaker.failure_count == 0


class TestBulkheadSemaphore:
    """Test bulkhead semaphore functionality."""

    @pytest.fixture
    def bulkhead(self):
        """Create a bulkhead semaphore for testing."""
        return BulkheadSemaphore("test_resource", capacity=2)

    async def test_bulkhead_acquire_release(self, bulkhead):
        """Test basic acquire and release functionality."""
        # Should be able to acquire up to capacity
        assert await bulkhead.acquire() == True
        assert bulkhead.active_count == 1

        assert await bulkhead.acquire() == True
        assert bulkhead.active_count == 2

        # Should timeout when at capacity
        assert await bulkhead.acquire(timeout=0.1) == False
        assert bulkhead.rejected_requests == 1

        # Release and should be able to acquire again
        bulkhead.release()
        assert bulkhead.active_count == 1

        assert await bulkhead.acquire() == True
        assert bulkhead.active_count == 2

    async def test_bulkhead_statistics(self, bulkhead):
        """Test bulkhead statistics tracking."""
        await bulkhead.acquire()
        await bulkhead.acquire()
        await bulkhead.acquire(timeout=0.1)  # Should be rejected

        stats = bulkhead.get_stats()
        assert stats["capacity"] == 2
        assert stats["active_count"] == 2
        assert stats["total_requests"] == 3
        assert stats["rejected_requests"] == 1
        assert stats["rejection_rate"] == 1 / 3


class TestErrorHandlingDecorator:
    """Test the comprehensive error handling decorator."""

    async def test_successful_operation(self):
        """Test decorator with successful operation."""

        @handle_errors(operation_name="test_operation", user_friendly_errors=True)
        async def success_func():
            return "success"

        result = await success_func()
        assert result == "success"

    async def test_retry_with_exponential_backoff(self):
        """Test retry mechanism with exponential backoff."""
        call_count = 0

        @handle_errors(
            operation_name="test_retry",
            retry_config=RetryConfig(max_attempts=3, strategy=RetryStrategy.EXPONENTIAL_BACKOFF, initial_delay=0.1),
        )
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        result = await flaky_func()
        assert result == "success"
        assert call_count == 3

    async def test_circuit_breaker_integration(self):
        """Test circuit breaker integration in decorator."""

        @handle_errors(operation_name="test_circuit_breaker", circuit_breaker="test_cb")
        async def failure_func():
            raise Exception("Persistent failure")

        # Should fail normally first few times
        for i in range(5):
            with pytest.raises(Exception):
                await failure_func()

        # Circuit breaker should now be open and reject calls
        with pytest.raises(CircuitBreakerOpenError):
            await failure_func()

    async def test_user_friendly_error_creation(self):
        """Test user-friendly error message creation."""
        context = ErrorContext(operation="test_operation", user_id="test_user", request_id="test_request")

        error = ValidationError("Invalid input data")
        user_error = create_user_friendly_error(error, context)

        assert "error" in user_error
        assert user_error["error"]["code"] == "VALIDATIONERROR"
        assert "not valid" in user_error["error"]["message"].lower()
        assert user_error["error"]["request_id"] == "test_request"
        assert "support_reference" in user_error["error"]


class TestInputValidation:
    """Test input validation and sanitization."""

    def test_basic_validation(self):
        """Test basic input validation."""
        schema = {
            "name": {"required": True, "type": str, "min_length": 3, "max_length": 50},
            "age": {"required": False, "type": int, "min_value": 0, "max_value": 150},
        }

        context = ErrorContext(operation="test_validation")

        # Valid input
        data = {"name": "John Doe", "age": 30}
        result = validate_input(data, schema, context)
        assert result["name"] == "John Doe"
        assert result["age"] == 30

        # Invalid input - missing required field
        with pytest.raises(ValidationError):
            validate_input({"age": 30}, schema, context)

        # Invalid input - wrong type
        with pytest.raises(ValidationError):
            validate_input({"name": 123}, schema, context)

        # Invalid input - length violation
        with pytest.raises(ValidationError):
            validate_input({"name": "Jo"}, schema, context)

    def test_sensitive_data_sanitization(self):
        """Test sensitive data sanitization."""
        sensitive_data = {
            "username": "john_doe",
            "password": "secret123",
            "token": "abc123xyz",
            "email": "john@example.com",
            "nested": {"api_key": "key123", "public_info": "safe_data"},
        }

        sanitized = sanitize_sensitive_data(sensitive_data)

        assert sanitized["username"] == "john_doe"
        assert sanitized["password"] == "<REDACTED>"
        assert sanitized["token"] == "<REDACTED>"
        assert sanitized["email"] == "john@example.com"
        assert sanitized["nested"]["api_key"] == "<REDACTED>"
        assert sanitized["nested"]["public_info"] == "safe_data"


class TestErrorRecovery:
    """Test error recovery mechanisms."""

    @pytest.fixture
    def recovery_manager(self):
        """Create an error recovery manager for testing."""
        return ErrorRecoveryManager()

    async def test_exponential_backoff_recovery(self, recovery_manager):
        """Test exponential backoff recovery strategy."""
        call_count = 0

        async def recovery_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Still failing")
            return "recovered"

        context = ErrorContext(operation="test_recovery")
        error = ConnectionError("Initial failure")

        success, result = await recovery_manager.recover_from_error(
            error, context, RecoveryStrategy.EXPONENTIAL_BACKOFF, recovery_func, max_attempts=5
        )

        assert success == True
        assert result == "recovered"
        assert call_count == 3

    async def test_graceful_degradation_recovery(self, recovery_manager):
        """Test graceful degradation recovery strategy."""
        context = ErrorContext(operation="family_operation")
        error = Exception("Service unavailable")

        success, result = await recovery_manager.recover_from_error(
            error, context, RecoveryStrategy.GRACEFUL_DEGRADATION, max_attempts=1
        )

        assert success == True
        assert result is not None
        assert "status" in result
        assert result["status"] == "degraded"

    async def test_recovery_callback_registration(self, recovery_manager):
        """Test recovery callback registration and triggering."""
        callback_called = False
        callback_success = None
        callback_result = None

        async def recovery_callback(success, result):
            nonlocal callback_called, callback_success, callback_result
            callback_called = True
            callback_success = success
            callback_result = result

        recovery_manager.register_recovery_callback("test_operation", recovery_callback)

        async def success_recovery():
            return "recovered"

        context = ErrorContext(operation="test_operation")
        error = Exception("Test error")

        await recovery_manager.recover_from_error(
            error, context, RecoveryStrategy.IMMEDIATE_RETRY, success_recovery, max_attempts=1
        )

        # Give callbacks time to execute
        await asyncio.sleep(0.1)

        assert callback_called == True
        assert callback_success == True
        assert callback_result == "recovered"


class TestErrorMonitoring:
    """Test error monitoring and alerting."""

    @pytest.fixture
    def error_monitor(self):
        """Create an error monitor for testing."""
        monitor = ErrorMonitor()
        # Stop background monitoring for tests
        monitor.stop_monitoring()
        return monitor

    async def test_error_event_recording(self, error_monitor):
        """Test error event recording and pattern detection."""
        context = ErrorContext(operation="test_operation", user_id="test_user", family_id="test_family")

        error = ValueError("Test error")

        await error_monitor.record_error(error, context, ErrorSeverity.MEDIUM)

        assert len(error_monitor.error_events) == 1
        event = error_monitor.error_events[0]
        assert event.operation == "test_operation"
        assert event.error_type == "ValueError"
        assert event.user_id == "test_user"
        assert event.family_id == "test_family"

    async def test_error_pattern_detection(self, error_monitor):
        """Test error pattern detection and aggregation."""
        context = ErrorContext(operation="test_operation")
        error = ValueError("Repeated error")

        # Record the same error multiple times
        for i in range(5):
            await error_monitor.record_error(error, context, ErrorSeverity.MEDIUM)

        # Should create a pattern
        assert len(error_monitor.error_patterns) == 1
        pattern = list(error_monitor.error_patterns.values())[0]
        assert pattern.count == 5
        assert pattern.operation == "test_operation"
        assert pattern.error_type == "ValueError"

    async def test_monitoring_statistics(self, error_monitor):
        """Test monitoring statistics collection."""
        context = ErrorContext(operation="test_operation")

        # Record various errors
        await error_monitor.record_error(ValueError("Error 1"), context, ErrorSeverity.LOW)
        await error_monitor.record_error(ConnectionError("Error 2"), context, ErrorSeverity.HIGH)
        await error_monitor.record_error(ValueError("Error 3"), context, ErrorSeverity.CRITICAL)

        stats = error_monitor.get_monitoring_stats()

        assert stats["error_statistics"]["total_errors"] == 3
        assert stats["error_statistics"]["active_patterns"] >= 1
        assert stats["recovery_statistics"]["total_recovery_attempts"] == 0


class TestIntegrationScenarios:
    """Test complete integration scenarios."""

    async def test_family_creation_with_error_handling(self):
        """Test family creation with comprehensive error handling."""
        # This would test the actual family manager with error handling
        # For now, we'll test the error handling patterns in isolation

        @handle_errors(
            operation_name="create_family",
            circuit_breaker="family_operations",
            bulkhead="family_creation",
            retry_config=RetryConfig(max_attempts=3),
            user_friendly_errors=True,
        )
        async def mock_create_family(user_id: str, name: str = None):
            # Simulate various failure scenarios
            if user_id == "rate_limited_user":
                from second_brain_database.managers.family_manager import RateLimitExceeded

                raise RateLimitExceeded("Rate limit exceeded")
            elif user_id == "limit_exceeded_user":
                from second_brain_database.managers.family_manager import FamilyLimitExceeded

                raise FamilyLimitExceeded("Family limit exceeded")
            elif user_id == "db_error_user":
                from pymongo.errors import PyMongoError

                raise PyMongoError("Database connection failed")
            else:
                return {"family_id": "test_family", "name": name or "Test Family"}

        # Test successful creation
        result = await mock_create_family("valid_user", "My Family")
        assert result["family_id"] == "test_family"
        assert result["name"] == "My Family"

        # Test rate limit error
        with pytest.raises(Exception) as exc_info:
            await mock_create_family("rate_limited_user")

        # Test family limit error
        with pytest.raises(Exception) as exc_info:
            await mock_create_family("limit_exceeded_user")

        # Test database error with retry
        with pytest.raises(Exception) as exc_info:
            await mock_create_family("db_error_user")

    async def test_error_monitoring_integration(self):
        """Test error monitoring integration with actual operations."""
        context = ErrorContext(operation="integration_test", user_id="test_user")

        # Record various error types
        await record_error_event(ValueError("Validation failed"), context, ErrorSeverity.MEDIUM)

        await record_error_event(
            ConnectionError("Database unavailable"),
            context,
            ErrorSeverity.HIGH,
            recovery_attempted=True,
            recovery_successful=False,
        )

        # Check that errors were recorded
        stats = error_monitor.get_monitoring_stats()
        assert stats["error_statistics"]["total_errors"] >= 2

        patterns = error_monitor.get_error_patterns(limit=5)
        assert len(patterns) >= 1


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
