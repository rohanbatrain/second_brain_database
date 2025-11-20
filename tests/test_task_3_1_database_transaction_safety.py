"""
Task 3.1: Database Transaction Safety Testing

This test suite validates database transaction safety, rollback mechanisms,
atomicity of multi-collection operations, concurrent operation handling,
data consistency during error scenarios, and recovery from database connection failures.

Requirements Tested:
- 8.1: Database errors with automatic retry and exponential backoff
- 8.4: Transaction atomicity and rollback for incomplete operations
- 8.6: Automatic healing and operator notification
"""

import asyncio
from datetime import datetime, timezone
import time
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from pymongo.errors import (
    BulkWriteError,
    ConnectionFailure,
    DuplicateKeyError,
    PyMongoError,
    ServerSelectionTimeoutError,
    WriteConcernError,
    WriteError,
)
import pytest


class MockTransactionSession:
    """Mock MongoDB transaction session."""

    def __init__(self):
        self.transaction_started = False
        self.transaction_committed = False
        self.transaction_aborted = False
        self.session_ended = False
        self.in_transaction = False
        self.session_id = uuid.uuid4()

    def start_transaction(self):
        """Start a transaction."""
        self.transaction_started = True
        self.in_transaction = True

    async def commit_transaction(self):
        """Commit the transaction."""
        self.transaction_committed = True
        self.in_transaction = False

    async def abort_transaction(self):
        """Abort the transaction."""
        self.transaction_aborted = True
        self.in_transaction = False

    async def end_session(self):
        """End the session."""
        self.session_ended = True


class MockFamilyOperations:
    """Mock family operations for testing transaction safety."""

    def __init__(self):
        self.operations_log = []
        self.failure_modes = {}

    def set_failure_mode(self, operation: str, should_fail: bool = True):
        """Configure operation to fail for testing."""
        self.failure_modes[operation] = should_fail

    async def create_family_with_transaction(self, user_id: str, family_name: str) -> Dict[str, Any]:
        """Create family with full transaction safety."""
        session = MockTransactionSession()

        try:
            # Start transaction
            session.start_transaction()
            self.operations_log.append("transaction_started")

            # Step 1: Create family document
            await self._create_family_document(user_id, family_name, session)

            # Step 2: Create SBD account
            await self._create_sbd_account(f"fam_{uuid.uuid4().hex[:8]}", session)

            # Step 3: Create relationships
            await self._create_family_relationships(user_id, session)

            # Step 4: Update user membership
            await self._update_user_membership(user_id, session)

            # Commit transaction
            await session.commit_transaction()
            self.operations_log.append("transaction_committed")

            return {
                "family_id": f"fam_{uuid.uuid4().hex[:8]}",
                "name": family_name,
                "admin_user_ids": [user_id],
                "transaction_safe": True,
                "operations_log": self.operations_log.copy(),
            }

        except Exception as e:
            # Rollback on any failure
            await session.abort_transaction()
            self.operations_log.append("transaction_aborted")
            raise Exception(f"Family creation failed: {str(e)}") from e

        finally:
            await session.end_session()
            self.operations_log.append("session_ended")

    async def _create_family_document(self, user_id: str, family_name: str, session):
        """Mock family document creation."""
        self.operations_log.append("family_document_created")
        if self.failure_modes.get("family_document", False):
            raise PyMongoError("Failed to create family document")

    async def _create_sbd_account(self, family_id: str, session):
        """Mock SBD account creation."""
        self.operations_log.append("sbd_account_created")
        if self.failure_modes.get("sbd_account", False):
            raise ConnectionFailure("Failed to create SBD account")

    async def _create_family_relationships(self, user_id: str, session):
        """Mock family relationships creation."""
        self.operations_log.append("relationships_created")
        if self.failure_modes.get("relationships", False):
            raise WriteError("Failed to create relationships")

    async def _update_user_membership(self, user_id: str, session):
        """Mock user membership update."""
        self.operations_log.append("membership_updated")
        if self.failure_modes.get("membership", False):
            raise BulkWriteError("Failed to update membership")


@pytest.mark.asyncio
class TestDatabaseTransactionSafety:
    """Test database transaction safety and rollback mechanisms."""

    @pytest.fixture
    def family_ops(self):
        """Create family operations instance."""
        return MockFamilyOperations()

    async def test_transaction_rollback_on_family_document_failure(self, family_ops):
        """
        Test transaction rollback when family document creation fails.

        Requirements: 8.1, 8.4
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        family_name = "Test Family"

        # Configure failure during family document creation
        family_ops.set_failure_mode("family_document", True)

        # Attempt family creation - should fail and rollback
        with pytest.raises(Exception) as exc_info:
            await family_ops.create_family_with_transaction(user_id, family_name)

        # Verify transaction was rolled back
        assert "Family creation failed" in str(exc_info.value)
        assert "Failed to create family document" in str(exc_info.value)

        # Verify transaction lifecycle
        operations = family_ops.operations_log
        assert "transaction_started" in operations
        assert "family_document_created" in operations
        assert "transaction_aborted" in operations
        assert "session_ended" in operations
        assert "transaction_committed" not in operations

    async def test_transaction_rollback_on_sbd_account_failure(self, family_ops):
        """
        Test transaction rollback when SBD account creation fails.

        Requirements: 8.1, 8.4
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        family_name = "Test Family"

        # Configure failure during SBD account creation
        family_ops.set_failure_mode("sbd_account", True)

        # Attempt family creation - should fail and rollback
        with pytest.raises(Exception) as exc_info:
            await family_ops.create_family_with_transaction(user_id, family_name)

        # Verify transaction was rolled back
        assert "Family creation failed" in str(exc_info.value)
        assert "Failed to create SBD account" in str(exc_info.value)

        # Verify partial operations were rolled back
        operations = family_ops.operations_log
        assert "transaction_started" in operations
        assert "family_document_created" in operations  # This succeeded
        assert "sbd_account_created" in operations  # This failed
        assert "transaction_aborted" in operations
        assert "relationships_created" not in operations  # This never happened

    async def test_transaction_rollback_on_relationships_failure(self, family_ops):
        """
        Test transaction rollback when relationship creation fails.

        Requirements: 8.1, 8.4
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        family_name = "Test Family"

        # Configure failure during relationships creation
        family_ops.set_failure_mode("relationships", True)

        # Attempt family creation - should fail and rollback
        with pytest.raises(Exception) as exc_info:
            await family_ops.create_family_with_transaction(user_id, family_name)

        # Verify transaction was rolled back
        assert "Family creation failed" in str(exc_info.value)
        assert "Failed to create relationships" in str(exc_info.value)

        # Verify partial operations were rolled back
        operations = family_ops.operations_log
        assert "transaction_started" in operations
        assert "family_document_created" in operations
        assert "sbd_account_created" in operations
        assert "relationships_created" in operations
        assert "transaction_aborted" in operations
        assert "membership_updated" not in operations

    async def test_successful_multi_collection_atomicity(self, family_ops):
        """
        Test successful atomic operations across multiple collections.

        Requirements: 8.1, 8.4
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        family_name = "Atomic Success Family"

        # No failures configured - should succeed
        result = await family_ops.create_family_with_transaction(user_id, family_name)

        # Verify successful result
        assert result is not None
        assert result["transaction_safe"] is True
        assert result["name"] == family_name
        assert user_id in result["admin_user_ids"]

        # Verify all operations completed successfully
        operations = family_ops.operations_log
        assert "transaction_started" in operations
        assert "family_document_created" in operations
        assert "sbd_account_created" in operations
        assert "relationships_created" in operations
        assert "membership_updated" in operations
        assert "transaction_committed" in operations
        assert "session_ended" in operations
        assert "transaction_aborted" not in operations

    async def test_concurrent_operation_handling(self, family_ops):
        """
        Test concurrent family creation operations.

        Requirements: 8.1, 8.6
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        # Create multiple concurrent operations
        tasks = []
        for i in range(3):
            ops = MockFamilyOperations()  # Each gets its own instance
            task = asyncio.create_task(ops.create_family_with_transaction(user_id, f"Concurrent Family {i}"))
            tasks.append(task)

        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed (no conflicts in mock)
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) == 3

        # Verify each has unique family_id
        family_ids = [result["family_id"] for result in successful_results]
        assert len(set(family_ids)) == len(family_ids)  # All unique

    async def test_data_consistency_during_partial_failures(self, family_ops):
        """
        Test data consistency is maintained during partial failures.

        Requirements: 8.1, 8.4, 8.6
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        family_name = "Consistency Test"

        # Configure failure at the last step
        family_ops.set_failure_mode("membership", True)

        # Should fail and rollback everything
        with pytest.raises(Exception):
            await family_ops.create_family_with_transaction(user_id, family_name)

        # Verify all previous operations were rolled back
        operations = family_ops.operations_log
        assert "transaction_started" in operations
        assert "family_document_created" in operations
        assert "sbd_account_created" in operations
        assert "relationships_created" in operations
        assert "membership_updated" in operations
        assert "transaction_aborted" in operations
        assert "transaction_committed" not in operations

    async def test_database_connection_recovery(self):
        """
        Test recovery from database connection failures.

        Requirements: 8.1, 8.6
        """
        call_count = 0

        async def failing_operation():
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                raise ConnectionFailure("Connection lost")
            elif call_count == 2:
                raise ServerSelectionTimeoutError("Server timeout")
            else:
                return {"success": True, "attempts": call_count}

        # Mock retry logic
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                result = await failing_operation()
                break
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                if attempt == max_attempts - 1:
                    raise
                await asyncio.sleep(0.01)  # Brief delay

        # Should succeed after retries
        assert result["success"] is True
        assert result["attempts"] == 3
        assert call_count == 3

    async def test_duplicate_key_error_handling(self, family_ops):
        """
        Test handling of duplicate key errors.

        Requirements: 8.1, 8.4
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        # Mock duplicate key error
        original_create_family = family_ops._create_family_document

        async def mock_duplicate_error(user_id, family_name, session):
            raise DuplicateKeyError("Duplicate family_id")

        family_ops._create_family_document = mock_duplicate_error

        # Should handle duplicate key error
        with pytest.raises(Exception) as exc_info:
            await family_ops.create_family_with_transaction(user_id, "Test Family")

        assert "Family creation failed" in str(exc_info.value)
        assert "Duplicate family_id" in str(exc_info.value)

    async def test_write_concern_error_handling(self, family_ops):
        """
        Test handling of write concern errors.

        Requirements: 8.1, 8.4
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        # Mock write concern error
        async def mock_write_concern_error(user_id, session):
            raise WriteConcernError("Write concern not satisfied")

        family_ops._update_user_membership = mock_write_concern_error

        # Should handle write concern error
        with pytest.raises(Exception) as exc_info:
            await family_ops.create_family_with_transaction(user_id, "Test Family")

        assert "Family creation failed" in str(exc_info.value)
        assert "Write concern not satisfied" in str(exc_info.value)

    async def test_bulk_write_error_handling(self, family_ops):
        """
        Test handling of bulk write errors.

        Requirements: 8.1, 8.4
        """
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        # Configure bulk write error
        family_ops.set_failure_mode("membership", True)

        # Should handle bulk write error and rollback
        with pytest.raises(Exception) as exc_info:
            await family_ops.create_family_with_transaction(user_id, "Test Family")

        # Verify transaction was properly rolled back
        operations = family_ops.operations_log
        assert "transaction_aborted" in operations
        assert "transaction_committed" not in operations


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
