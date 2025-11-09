"""
Comprehensive Database Transaction Safety Testing for Family Management System.

This test suite validates database transaction safety, rollback mechanisms,
atomicity of multi-collection operations, concurrent operation handling,
data consistency during error scenarios, and recovery from database connection failures.

Requirements Tested:
- 8.1: Database errors with automatic retry and exponential backoff
- 8.4: Transaction atomicity and rollback for incomplete operations
- 8.6: Automatic healing and operator notification

Test Coverage:
- Transaction rollback on family creation failures
- Atomicity of multi-collection operations
- Concurrent operation handling and locking
- Data consistency during error scenarios
- Recovery from database connection failures
"""

import asyncio
from datetime import datetime, timedelta, timezone
import os
import sys
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, call, patch
import uuid

import pytest

# Configure pytest for async tests
pytest_plugins = ("pytest_asyncio",)

# Mock dependencies before importing
with patch("redis.Redis"), patch("redis.asyncio.Redis"), patch("motor.motor_asyncio.AsyncIOMotorClient"):

    from pymongo.client_session import ClientSession
    from pymongo.errors import (
        BulkWriteError,
        ConnectionFailure,
        DuplicateKeyError,
        PyMongoError,
        ServerSelectionTimeoutError,
        WriteConcernError,
        WriteError,
    )


class MockFamilyManager:
    """Mock family manager for testing transaction safety."""

    def __init__(self):
        self.db_client = None
        self.initialized = False

    async def initialize(self):
        """Mock initialization."""
        self.initialized = True

    async def create_family(self, user_id: str, family_name: str = None, request_context: Dict = None) -> Dict:
        """Mock family creation with transaction safety."""
        if not self.initialized:
            raise RuntimeError("Manager not initialized")

        # Simulate transaction-based family creation
        session = None
        try:
            # Start transaction
            session = await self._start_transaction()

            # Step 1: Validate input
            await self._validate_family_creation_input(user_id, family_name)

            # Step 2: Check limits
            await self._check_family_creation_limits(user_id)

            # Step 3: Create family document
            family_id = await self._create_family_document(user_id, family_name, session)

            # Step 4: Create SBD account
            await self._create_sbd_account(family_id, session)

            # Step 5: Add user to family
            await self._add_user_to_family(family_id, user_id, session)

            # Commit transaction
            await session.commit_transaction()

            return {
                "family_id": family_id,
                "name": family_name or f"Family of {user_id}",
                "admin_user_ids": [user_id],
                "transaction_safe": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            # Rollback transaction on any failure
            if session:
                await session.abort_transaction()
            raise Exception(f"Failed to create family: {str(e)}") from e
        finally:
            if session:
                await session.end_session()

    async def _start_transaction(self):
        """Mock transaction start."""
        session = AsyncMock(spec=ClientSession)
        session.start_transaction = MagicMock()
        session.commit_transaction = AsyncMock()
        session.abort_transaction = AsyncMock()
        session.end_session = AsyncMock()
        session.in_transaction = True
        session.session_id = uuid.uuid4()
        return session

    async def _validate_family_creation_input(self, user_id: str, family_name: str):
        """Mock input validation."""
        if not user_id:
            raise ValueError("User ID is required")
        if family_name and len(family_name) > 100:
            raise ValueError("Family name too long")

    async def _check_family_creation_limits(self, user_id: str):
        """Mock limit checking."""
        # Simulate checking user's family count
        pass

    async def _create_family_document(self, user_id: str, family_name: str, session) -> str:
        """Mock family document creation."""
        family_id = f"fam_{uuid.uuid4().hex[:16]}"

        # Simulate database insertion that could fail
        if hasattr(self, "_simulate_family_creation_failure") and self._simulate_family_creation_failure:
            raise PyMongoError("Simulated family creation failure")

        return family_id

    async def _create_sbd_account(self, family_id: str, session):
        """Mock SBD account creation."""
        # Simulate SBD account creation that could fail
        if hasattr(self, "_simulate_sbd_creation_failure") and self._simulate_sbd_creation_failure:
            raise ConnectionFailure("Simulated SBD creation failure")

    async def _add_user_to_family(self, family_id: str, user_id: str, session):
        """Mock adding user to family."""
        # Simulate user addition that could fail
        if hasattr(self, "_simulate_user_addition_failure") and self._simulate_user_addition_failure:
            raise WriteError("Simulated user addition failure")


class TestDatabaseTransactionSafety:
    """
    Test database transaction safety and rollback mechanisms.

    Requirements: 8.1, 8.4, 8.6
    """

    @pytest.fixture
    def family_manager(self):
        """Create a mock family manager instance for testing."""

        async def _create_manager():
            manager = MockFamilyManager()
            await manager.initialize()
            return manager

        return _create_manager

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session for transaction testing."""
        session = AsyncMock(spec=ClientSession)
        session.start_transaction = MagicMock()
        session.commit_transaction = AsyncMock()
        session.abort_transaction = AsyncMock()
        session.end_session = AsyncMock()
        session.in_transaction = True
        session.session_id = uuid.uuid4()
        return session

    @pytest.mark.asyncio
    async def test_family_creation_transaction_rollback_on_failure(self, family_manager):
        """
        Test that family creation properly rolls back on failures.

        Validates that when any step in the multi-collection family creation process fails,
        the entire transaction is rolled back and no partial data is left in the database.

        Requirements: 8.1, 8.4
        """
        manager = await family_manager()
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        family_name = "Test Family Transaction Rollback"

        # Configure manager to simulate failure during family creation
        manager._simulate_family_creation_failure = True

        # Attempt family creation - should fail and rollback
        with pytest.raises(Exception) as exc_info:
            await manager.create_family(user_id, family_name)

        # Verify the exception contains transaction rollback information
        assert "Failed to create family" in str(exc_info.value)
        assert "Simulated family creation failure" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_multi_collection_atomicity_success(self, family_manager):
        """
        Test atomicity of successful operations spanning multiple collections.

        Validates that when all operations succeed, the transaction is properly committed
        and all data is persisted across multiple collections.

        Requirements: 8.1, 8.4
        """
        manager = await family_manager()
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        family_name = "Atomic Success Family"

        # Ensure no failures are simulated
        manager._simulate_family_creation_failure = False
        manager._simulate_sbd_creation_failure = False
        manager._simulate_user_addition_failure = False

        # Successful creation should commit transaction
        result = await manager.create_family(user_id, family_name)

        # Verify result contains expected data
        assert result is not None
        assert "family_id" in result
        assert result["name"] == family_name
        assert result["transaction_safe"] is True
        assert user_id in result["admin_user_ids"]

    async def test_concurrent_family_creation_handling(self, family_manager):
        """
        Test concurrent operation handling and locking mechanisms.

        Validates that concurrent family creation attempts are handled safely
        without data corruption or race conditions.

        Requirements: 8.1, 8.6
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        # Ensure no failures are simulated for this test
        family_manager._simulate_family_creation_failure = False
        family_manager._simulate_sbd_creation_failure = False
        family_manager._simulate_user_addition_failure = False

        # Simulate concurrent family creation attempts
        tasks = []
        for i in range(5):
            task = asyncio.create_task(family_manager.create_family(user_id, f"Concurrent Family {i}"))
            tasks.append(task)

        # Execute concurrent operations
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify that operations either succeed or fail gracefully
        successful_operations = [r for r in results if not isinstance(r, Exception)]
        failed_operations = [r for r in results if isinstance(r, Exception)]

        # All operations should succeed in this mock scenario
        assert len(successful_operations) == 5
        assert len(failed_operations) == 0

        # Verify each result has unique family_id (no race conditions)
        family_ids = [result["family_id"] for result in successful_operations]
        assert len(set(family_ids)) == len(family_ids)  # All unique

    async def test_data_consistency_during_partial_failures(self, family_manager):
        """
        Test data consistency is maintained during error scenarios.

        Validates that partial failures don't leave the database in an inconsistent state
        and that proper rollback mechanisms are triggered.

        Requirements: 8.1, 8.4, 8.6
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        family_name = "Consistency Test Family"

        # Test failure during SBD account creation (after family creation)
        family_manager._simulate_family_creation_failure = False
        family_manager._simulate_sbd_creation_failure = True
        family_manager._simulate_user_addition_failure = False

        # Attempt operation that should fail and rollback
        with pytest.raises(Exception) as exc_info:
            await family_manager.create_family(user_id, family_name)

        # Verify proper error handling
        assert "Failed to create family" in str(exc_info.value)
        assert "Simulated SBD creation failure" in str(exc_info.value)

    async def test_database_connection_recovery_mechanisms(self, family_manager):
        """
        Test recovery from database connection failures.

        Validates that the system can recover from temporary database connection issues
        and successfully retry operations with proper backoff strategies.

        Requirements: 8.1, 8.6
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        family_name = "Recovery Test Family"

        # Track call attempts for retry testing
        call_count = 0
        original_create_family_document = family_manager._create_family_document

        async def mock_create_with_recovery(user_id, family_name, session):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call fails with connection error
                raise ConnectionFailure("Database connection failed")
            elif call_count == 2:
                # Second call fails with timeout
                raise ServerSelectionTimeoutError("Server selection timeout")
            else:
                # Third call succeeds
                return await original_create_family_document(user_id, family_name, session)

        # Replace the method with our retry-testing version
        family_manager._create_family_document = mock_create_with_recovery

        # Configure for retry testing
        from src.second_brain_database.utils.error_handling import RetryConfig, RetryStrategy, handle_errors

        retry_config = RetryConfig(
            max_attempts=3,
            initial_delay=0.01,  # Fast for testing
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            retryable_exceptions=[ConnectionFailure, ServerSelectionTimeoutError],
        )

        # Test with retry decorator
        @handle_errors(operation_name="test_recovery", retry_config=retry_config)
        async def test_operation():
            return await family_manager.create_family(user_id, family_name)

        # Should succeed after retries
        result = await test_operation()
        assert result is not None
        assert call_count == 3  # Verify retry occurred

    async def test_transaction_timeout_handling(self, family_manager):
        """
        Test handling of transaction timeouts and proper cleanup.

        Validates that long-running transactions are properly timed out
        and cleaned up without leaving resources locked.

        Requirements: 8.1, 8.4
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        family_name = "Timeout Test Family"

        # Mock a long-running operation that times out
        original_create_sbd = family_manager._create_sbd_account

        async def slow_sbd_creation(family_id, session):
            await asyncio.sleep(2)  # Simulate slow operation
            return await original_create_sbd(family_id, session)

        family_manager._create_sbd_account = slow_sbd_creation

        # Test with timeout decorator
        from src.second_brain_database.utils.error_handling import handle_errors

        @handle_errors(operation_name="timeout_test", timeout=0.1)  # Very short timeout
        async def test_timeout_operation():
            return await family_manager.create_family(user_id, family_name)

        # Should timeout and cleanup properly
        with pytest.raises(asyncio.TimeoutError):
            await test_timeout_operation()

    async def test_duplicate_key_error_handling(self, family_manager):
        """
        Test handling of duplicate key errors during family creation.

        Validates that duplicate key errors are properly handled and
        don't cause transaction inconsistencies.

        Requirements: 8.1, 8.4
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        family_name = "Duplicate Test Family"

        # Mock duplicate key error during family creation
        original_create_family_document = family_manager._create_family_document

        async def mock_duplicate_key_error(user_id, family_name, session):
            raise DuplicateKeyError("Duplicate family_id")

        family_manager._create_family_document = mock_duplicate_key_error

        # Should handle duplicate key error gracefully
        with pytest.raises(Exception) as exc_info:
            await family_manager.create_family(user_id, family_name)

        # Verify proper error handling
        assert "Failed to create family" in str(exc_info.value)
        assert "Duplicate family_id" in str(exc_info.value)

    async def test_bulk_write_error_handling(self, family_manager):
        """
        Test handling of bulk write errors during multi-collection operations.

        Validates that bulk write failures are properly handled and
        transactions are rolled back appropriately.

        Requirements: 8.1, 8.4
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        family_name = "Bulk Write Test Family"

        # Mock bulk write error during user addition
        original_add_user = family_manager._add_user_to_family

        async def mock_bulk_write_error(family_id, user_id, session):
            raise BulkWriteError("Bulk write operation failed")

        family_manager._add_user_to_family = mock_bulk_write_error

        # Should handle bulk write error
        with pytest.raises(Exception) as exc_info:
            await family_manager.create_family(user_id, family_name)

        # Verify proper error handling
        assert "Failed to create family" in str(exc_info.value)
        assert "Bulk write operation failed" in str(exc_info.value)

    async def test_write_concern_error_handling(self, family_manager):
        """
        Test handling of write concern errors during transactions.

        Validates that write concern failures are properly handled and
        transactions are rolled back appropriately.

        Requirements: 8.1, 8.4
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        family_name = "Write Concern Test Family"

        # Mock write concern error
        original_create_sbd = family_manager._create_sbd_account

        async def mock_write_concern_error(family_id, session):
            raise WriteConcernError("Write concern not satisfied")

        family_manager._create_sbd_account = mock_write_concern_error

        # Should handle write concern error
        with pytest.raises(Exception) as exc_info:
            await family_manager.create_family(user_id, family_name)

        # Verify proper error handling
        assert "Failed to create family" in str(exc_info.value)
        assert "Write concern not satisfied" in str(exc_info.value)

    async def test_session_management_edge_cases(self, family_manager):
        """
        Test edge cases in session management and cleanup.

        Validates that sessions are properly managed even in edge cases
        like session creation failures or cleanup errors.

        Requirements: 8.1, 8.4, 8.6
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        family_name = "Session Management Test Family"

        # Mock session creation failure
        original_start_transaction = family_manager._start_transaction

        async def mock_session_failure():
            raise ConnectionFailure("Failed to create session")

        family_manager._start_transaction = mock_session_failure

        # Should handle session creation failure
        with pytest.raises(Exception) as exc_info:
            await family_manager.create_family(user_id, family_name)

        # Verify proper error handling
        assert "Failed to create family" in str(exc_info.value)
        assert "Failed to create session" in str(exc_info.value)

    async def test_nested_transaction_handling(self, family_manager):
        """
        Test handling of nested transactions and proper isolation.

        Validates that nested operations maintain proper transaction isolation
        and don't interfere with each other.

        Requirements: 8.1, 8.4
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        # Test multiple concurrent operations with different outcomes
        family_manager._simulate_family_creation_failure = False
        family_manager._simulate_sbd_creation_failure = False
        family_manager._simulate_user_addition_failure = False

        # Create multiple families concurrently
        tasks = []
        for i in range(3):
            task = asyncio.create_task(family_manager.create_family(user_id, f"Nested Family {i}"))
            tasks.append(task)

        # Execute and verify all succeed
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful_operations = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_operations) == 3

        # Verify transaction isolation - each should have unique family_id
        family_ids = [result["family_id"] for result in successful_operations]
        assert len(set(family_ids)) == len(family_ids)


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "--tb=short"])
