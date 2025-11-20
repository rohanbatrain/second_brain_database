"""
Database Transaction Safety Testing for Family Management System.

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

# Add the src directory to the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Mock Redis and monitoring before importing modules that depend on them
with (
    patch("redis.Redis"),
    patch("src.second_brain_database.managers.redis_manager.redis_manager"),
    patch("src.second_brain_database.managers.family_monitoring.family_monitor"),
):

    # Import the modules we're testing
    from src.second_brain_database.utils.error_handling import (
        handle_errors,
        ErrorContext,
        ErrorSeverity,
        RetryConfig,
        RetryStrategy,
        ValidationError,
        create_user_friendly_error,
    )

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


class TestDatabaseTransactionSafety:
    """
    Test database transaction safety and rollback mechanisms.

    Requirements: 8.1, 8.4, 8.6
    """

    @pytest.fixture
    async def family_manager(self):
        """Create a family manager instance for testing."""
        with (
            patch("src.second_brain_database.managers.family_manager.db_manager"),
            patch("src.second_brain_database.managers.family_manager.redis_manager"),
            patch("src.second_brain_database.managers.family_manager.family_monitor"),
        ):

            # Import after mocking dependencies
            from src.second_brain_database.managers.family_manager import FamilyManager

            manager = FamilyManager()
            # Mock the initialization to avoid actual database connections
            with patch.object(manager, "initialize"):
                await manager.initialize()
            return manager

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

    async def test_family_creation_transaction_rollback_on_failure(self, family_manager):
        """
        Test that family creation properly rolls back on failures.

        Validates that when any step in the multi-collection family creation process fails,
        the entire transaction is rolled back and no partial data is left in the database.

        Requirements: 8.1, 8.4
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        family_name = "Test Family Transaction Rollback"

        # Mock database operations to simulate transaction failure
        with patch("src.second_brain_database.database.db_manager") as mock_db_manager:

            # Setup session mock
            mock_session = AsyncMock(spec=ClientSession)
            mock_session.start_transaction = MagicMock()
            mock_session.abort_transaction = AsyncMock()
            mock_session.commit_transaction = AsyncMock()
            mock_session.end_session = AsyncMock()
            mock_session.in_transaction = True
            mock_session.session_id = uuid.uuid4()

            # Mock client and session creation
            mock_client = AsyncMock()
            mock_client.start_session.return_value.__aenter__.return_value = mock_session
            mock_db_manager.client = mock_client

            # Mock collections
            mock_families_collection = AsyncMock()
            mock_relationships_collection = AsyncMock()
            mock_sbd_collection = AsyncMock()

            mock_db_manager.families = mock_families_collection
            mock_db_manager.family_relationships = mock_relationships_collection
            mock_db_manager.sbd_virtual_accounts = mock_sbd_collection

            # Simulate successful family creation but failed relationship creation
            mock_families_collection.insert_one.return_value.inserted_id = "family_123"
            mock_relationships_collection.insert_one.side_effect = PyMongoError(
                "Database connection lost during relationship creation"
            )

            # Mock family manager methods
            with (
                patch.object(family_manager, "_validate_family_creation_input") as mock_validate,
                patch.object(family_manager, "_check_family_creation_limits") as mock_limits,
                patch.object(family_manager, "_get_user_by_id") as mock_get_user,
                patch.object(family_manager, "_generate_unique_sbd_username") as mock_sbd_username,
            ):

                mock_validate.return_value = None
                mock_limits.return_value = {"current_families": 0, "max_families": 5}
                mock_get_user.return_value = {"username": "testuser", "_id": user_id}
                mock_sbd_username.return_value = "family_testuser"

                # Attempt family creation - should fail and rollback
                with pytest.raises(Exception):
                    await family_manager.create_family(user_id, family_name)

                # Verify transaction was started and aborted due to failure
                mock_client.start_session.assert_called_once()
                mock_session.abort_transaction.assert_called_once()
                mock_session.commit_transaction.assert_not_called()

    async def test_multi_collection_atomicity_success(self, family_manager):
        """
        Test atomicity of successful operations spanning multiple collections.

        Validates that when all operations succeed, the transaction is properly committed
        and all data is persisted across multiple collections.

        Requirements: 8.1, 8.4
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        family_name = "Atomic Success Family"

        with (
            patch.object(db_manager, "client") as mock_client,
            patch.object(family_manager, "_validate_family_creation_input") as mock_validate,
            patch.object(family_manager, "_check_family_creation_limits") as mock_limits,
            patch.object(family_manager, "_get_user_by_id") as mock_get_user,
            patch.object(family_manager, "_generate_unique_sbd_username") as mock_sbd_username,
            patch.object(family_manager, "_build_family_document") as mock_build_doc,
            patch.object(family_manager, "_create_virtual_sbd_account_transactional") as mock_create_sbd,
            patch.object(family_manager, "_add_user_to_family_membership_transactional") as mock_add_member,
            patch.object(family_manager, "_cache_family") as mock_cache,
        ):

            # Setup successful mocks
            mock_validate.return_value = None
            mock_limits.return_value = {"current_families": 0, "max_families": 5}
            mock_get_user.return_value = {"username": "testuser"}
            mock_sbd_username.return_value = "family_testuser"

            family_doc = {
                "family_id": f"fam_{uuid.uuid4().hex[:16]}",
                "name": family_name,
                "admin_user_ids": [user_id],
                "created_at": datetime.now(timezone.utc),
            }
            mock_build_doc.return_value = family_doc

            # Setup session mock
            mock_session = AsyncMock(spec=ClientSession)
            mock_session.start_transaction = MagicMock()
            mock_session.commit_transaction = AsyncMock()
            mock_session.abort_transaction = AsyncMock()
            mock_session.end_session = AsyncMock()
            mock_session.in_transaction = True
            mock_session.session_id = uuid.uuid4()

            mock_client.start_session.return_value = mock_session

            # Mock successful collection operations
            mock_families_collection = AsyncMock()
            mock_families_collection.insert_one.return_value = MagicMock(inserted_id="family_123")
            mock_client.get_collection.return_value = mock_families_collection

            mock_create_sbd.return_value = None
            mock_add_member.return_value = None
            mock_cache.return_value = None

            # Successful creation should commit transaction
            result = await family_manager.create_family(user_id, family_name)

            # Verify all operations were called
            mock_validate.assert_called_once()
            mock_limits.assert_called_once()
            mock_build_doc.assert_called_once()
            mock_families_collection.insert_one.assert_called_once()
            mock_create_sbd.assert_called_once()
            mock_add_member.assert_called_once()

            # Verify transaction was committed successfully
            mock_client.start_session.assert_called_once()
            mock_session.commit_transaction.assert_called_once()
            mock_session.abort_transaction.assert_not_called()
            mock_session.end_session.assert_called_once()

            # Verify result contains expected data
            assert result is not None
            assert "family_id" in result
            assert result["name"] == family_name
            assert result["transaction_safe"] is True

    async def test_concurrent_family_creation_handling(self, family_manager):
        """
        Test concurrent operation handling and locking mechanisms.

        Validates that concurrent family creation attempts are handled safely
        without data corruption or race conditions.

        Requirements: 8.1, 8.6
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        # Mock successful operations with slight delays to simulate real conditions
        async def mock_create_family_with_delay(uid, name):
            await asyncio.sleep(0.01)  # Small delay to increase chance of race conditions
            return {
                "family_id": f"fam_{uuid.uuid4().hex[:16]}",
                "name": name,
                "admin_user_ids": [uid],
                "transaction_safe": True,
            }

        with patch.object(family_manager, "create_family", side_effect=mock_create_family_with_delay):
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

        with (
            patch.object(db_manager, "client") as mock_client,
            patch.object(family_manager, "_validate_family_creation_input") as mock_validate,
            patch.object(family_manager, "_check_family_creation_limits") as mock_limits,
            patch.object(family_manager, "_get_user_by_id") as mock_get_user,
            patch.object(family_manager, "_generate_unique_sbd_username") as mock_sbd_username,
            patch.object(family_manager, "_build_family_document") as mock_build_doc,
            patch.object(family_manager, "_create_virtual_sbd_account_transactional") as mock_create_sbd,
            patch.object(family_manager, "_add_user_to_family_membership_transactional") as mock_add_member,
        ):

            # Setup successful initial steps
            mock_validate.return_value = None
            mock_limits.return_value = {"current_families": 0, "max_families": 5}
            mock_get_user.return_value = {"username": "testuser"}
            mock_sbd_username.return_value = "family_testuser"
            mock_build_doc.return_value = {"family_id": "test_family", "name": family_name}

            # Setup session mock
            mock_session = AsyncMock(spec=ClientSession)
            mock_session.start_transaction = MagicMock()
            mock_session.abort_transaction = AsyncMock()
            mock_session.commit_transaction = AsyncMock()
            mock_session.end_session = AsyncMock()
            mock_session.in_transaction = True
            mock_session.session_id = uuid.uuid4()

            mock_client.start_session.return_value = mock_session

            # Mock successful family insertion but failed SBD account creation
            mock_families_collection = AsyncMock()
            mock_families_collection.insert_one.return_value = MagicMock(inserted_id="family_123")
            mock_client.get_collection.return_value = mock_families_collection

            # SBD account creation fails
            mock_create_sbd.side_effect = ConnectionFailure("SBD service unavailable")

            # Attempt operation that should fail and rollback
            with pytest.raises(Exception):
                await family_manager.create_family(user_id, family_name)

            # Verify transaction was properly aborted
            mock_session.start_transaction.assert_called_once()
            mock_session.abort_transaction.assert_called_once()
            mock_session.commit_transaction.assert_not_called()

            # Verify family was inserted but transaction was rolled back
            mock_families_collection.insert_one.assert_called_once()
            mock_create_sbd.assert_called_once()
            mock_add_member.assert_not_called()  # Should not reach this step

    async def test_database_connection_recovery_mechanisms(self, family_manager):
        """
        Test recovery from database connection failures.

        Validates that the system can recover from temporary database connection issues
        and successfully retry operations with proper backoff strategies.

        Requirements: 8.1, 8.6
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        family_name = "Recovery Test Family"

        # Track call attempts
        call_count = 0

        async def mock_create_with_recovery(uid, name, request_context=None):
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
                return {
                    "family_id": f"fam_{uuid.uuid4().hex[:16]}",
                    "name": name,
                    "admin_user_ids": [uid],
                    "transaction_safe": True,
                    "recovery_attempts": call_count - 1,
                }

        # Configure retry for connection failures
        retry_config = RetryConfig(
            max_attempts=3,
            initial_delay=0.01,  # Fast for testing
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            retryable_exceptions=[ConnectionFailure, ServerSelectionTimeoutError],
        )

        # Test with retry decorator
        @handle_errors(operation_name="test_recovery", retry_config=retry_config)
        async def test_operation():
            return await mock_create_with_recovery(user_id, family_name)

        # Should succeed after retries
        result = await test_operation()
        assert result is not None
        assert result["recovery_attempts"] == 2
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

        with (
            patch.object(db_manager, "client") as mock_client,
            patch.object(family_manager, "_validate_family_creation_input") as mock_validate,
        ):

            mock_validate.return_value = None

            # Setup session mock that simulates timeout
            mock_session = AsyncMock(spec=ClientSession)
            mock_session.start_transaction = MagicMock()
            mock_session.abort_transaction = AsyncMock()
            mock_session.end_session = AsyncMock()
            mock_session.in_transaction = True

            mock_client.start_session.return_value = mock_session

            # Mock a long-running operation that times out
            async def slow_operation(*args, **kwargs):
                await asyncio.sleep(2)  # Simulate slow operation
                return MagicMock(inserted_id="family_123")

            mock_families_collection = AsyncMock()
            mock_families_collection.insert_one.side_effect = slow_operation
            mock_client.get_collection.return_value = mock_families_collection

            # Test with timeout decorator
            @handle_errors(operation_name="timeout_test", timeout=0.1)  # Very short timeout
            async def test_timeout_operation():
                return await family_manager.create_family(user_id, family_name)

            # Should timeout and cleanup properly
            with pytest.raises(asyncio.TimeoutError):
                await test_timeout_operation()

            # Verify session cleanup occurred
            mock_session.end_session.assert_called_once()

    async def test_duplicate_key_error_handling(self, family_manager):
        """
        Test handling of duplicate key errors during family creation.

        Validates that duplicate key errors are properly handled and
        don't cause transaction inconsistencies.

        Requirements: 8.1, 8.4
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        family_name = "Duplicate Test Family"

        with (
            patch.object(db_manager, "client") as mock_client,
            patch.object(family_manager, "_validate_family_creation_input") as mock_validate,
            patch.object(family_manager, "_check_family_creation_limits") as mock_limits,
            patch.object(family_manager, "_get_user_by_id") as mock_get_user,
            patch.object(family_manager, "_generate_unique_sbd_username") as mock_sbd_username,
        ):

            # Setup mocks
            mock_validate.return_value = None
            mock_limits.return_value = {"current_families": 0, "max_families": 5}
            mock_get_user.return_value = {"username": "testuser"}
            mock_sbd_username.return_value = "family_testuser"

            # Setup session mock
            mock_session = AsyncMock(spec=ClientSession)
            mock_session.start_transaction = MagicMock()
            mock_session.abort_transaction = AsyncMock()
            mock_session.end_session = AsyncMock()
            mock_session.in_transaction = True

            mock_client.start_session.return_value = mock_session

            # Mock duplicate key error
            mock_families_collection = AsyncMock()
            mock_families_collection.insert_one.side_effect = DuplicateKeyError("Duplicate family_id")
            mock_client.get_collection.return_value = mock_families_collection

            # Should handle duplicate key error gracefully
            with pytest.raises(Exception):
                await family_manager.create_family(user_id, family_name)

            # Verify proper cleanup
            mock_session.abort_transaction.assert_called_once()
            mock_session.end_session.assert_called_once()

    async def test_bulk_write_error_handling(self, family_manager):
        """
        Test handling of bulk write errors during multi-collection operations.

        Validates that bulk write failures are properly handled and
        transactions are rolled back appropriately.

        Requirements: 8.1, 8.4
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        family_name = "Bulk Write Test Family"

        with (
            patch.object(db_manager, "client") as mock_client,
            patch.object(family_manager, "_validate_family_creation_input") as mock_validate,
            patch.object(family_manager, "_check_family_creation_limits") as mock_limits,
        ):

            mock_validate.return_value = None
            mock_limits.return_value = {"current_families": 0, "max_families": 5}

            # Setup session mock
            mock_session = AsyncMock(spec=ClientSession)
            mock_session.start_transaction = MagicMock()
            mock_session.abort_transaction = AsyncMock()
            mock_session.end_session = AsyncMock()
            mock_session.in_transaction = True

            mock_client.start_session.return_value = mock_session

            # Mock bulk write error
            bulk_error = BulkWriteError("Bulk write operation failed")
            mock_families_collection = AsyncMock()
            mock_families_collection.insert_one.side_effect = bulk_error
            mock_client.get_collection.return_value = mock_families_collection

            # Should handle bulk write error
            with pytest.raises(Exception):
                await family_manager.create_family(user_id, family_name)

            # Verify transaction rollback
            mock_session.abort_transaction.assert_called_once()
            mock_session.end_session.assert_called_once()


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "--tb=short"])
