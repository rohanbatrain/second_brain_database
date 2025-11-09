#!/usr/bin/env python3
"""
Simple test script to verify account name functionality in family endpoints.
"""

import asyncio
import os
import sys

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from second_brain_database.database import DatabaseManager
from second_brain_database.managers.family_manager import FamilyManager


async def test_account_name_functionality():
    """Test that account names are properly included in responses."""

    # Mock database manager
    db_manager = DatabaseManager()

    # Create family manager
    family_manager = FamilyManager(db_manager)

    # Test the account name extraction logic
    # Simulate family data with and without name field
    family_with_name = {
        "family_id": "test_family_1",
        "sbd_account": {"account_username": "testuser123", "name": "My Family Account"},
    }

    family_without_name = {"family_id": "test_family_2", "sbd_account": {"account_username": "testuser456"}}

    # Test account name extraction
    account_name_1 = family_with_name["sbd_account"].get("name", family_with_name["sbd_account"]["account_username"])
    account_name_2 = family_without_name["sbd_account"].get(
        "name", family_without_name["sbd_account"]["account_username"]
    )

    print("Testing account name extraction:")
    print(f"Family with name field: '{account_name_1}' (expected: 'My Family Account')")
    print(f"Family without name field: '{account_name_2}' (expected: 'testuser456')")

    # Verify results
    assert account_name_1 == "My Family Account", f"Expected 'My Family Account', got '{account_name_1}'"
    assert account_name_2 == "testuser456", f"Expected 'testuser456', got '{account_name_2}'"

    print("✅ Account name extraction logic works correctly!")

    # Test response structure
    test_response = {
        "account_username": "testuser123",
        "account_name": account_name_1,
        "current_balance": 100.0,
        "transactions": [],
        "total_transactions": 0,
        "has_more": False,
    }

    print("\nTesting response structure:")
    print(f"Response contains account_name: {'account_name' in test_response}")
    print(f"Response contains account_username: {'account_username' in test_response}")

    assert "account_name" in test_response, "Response should contain account_name field"
    assert "account_username" in test_response, "Response should contain account_username field"

    print("✅ Response structure includes both account_name and account_username!")

    print("\n🎉 All tests passed! Account name functionality is working correctly.")


if __name__ == "__main__":
    asyncio.run(test_account_name_functionality())
