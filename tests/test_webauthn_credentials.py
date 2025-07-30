#!/usr/bin/env python3
"""
Test script for WebAuthn credential storage and retrieval functions.

This script tests the basic functionality of the WebAuthn credential service
to ensure it follows the existing patterns and works correctly.
"""
import asyncio
from datetime import datetime
import os
import sys

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Import database and redis managers directly
from second_brain_database.database import db_manager

# Import only the specific module to avoid loading the entire routes system
from second_brain_database.routes.auth.services.webauthn.credentials import (
    deactivate_credential,
    get_credential_by_id,
    get_user_credentials,
    store_credential,
    update_credential_usage,
    validate_credential_ownership,
)


async def test_credential_storage():
    """Test credential storage functionality."""
    print("Testing credential storage...")

    # Connect to database
    await db_manager.connect()

    # Test data
    user_id = "507f1f77bcf86cd799439011"  # Test ObjectId
    credential_id = "test_credential_123"
    public_key = "test_public_key_data_cbor_encoded"
    device_name = "Test iPhone"

    # Test storing credential
    result = await store_credential(
        user_id=user_id,
        credential_id=credential_id,
        public_key=public_key,
        device_name=device_name,
        authenticator_type="platform",
        transport=["internal"],
        aaguid="test-aaguid-123"
    )

    assert result is not None, "Credential storage should succeed"
    assert result["credential_id"] == credential_id, "Credential ID should match"
    assert result["device_name"] == device_name, "Device name should match"
    assert result["authenticator_type"] == "platform", "Authenticator type should match"
    assert result["is_active"] is True, "Credential should be active"

    print(f"✓ Credential stored successfully: {credential_id}")
    return user_id, credential_id, public_key


async def test_credential_retrieval():
    """Test credential retrieval functionality."""
    print("Testing credential retrieval...")

    user_id, credential_id, public_key = await test_credential_storage()

    # Test retrieving user credentials
    print("Testing user credentials retrieval...")
    credentials = await get_user_credentials(user_id)
    assert len(credentials) > 0, "Should retrieve at least one credential"
    
    found_credential = None
    for cred in credentials:
        if cred["credential_id"] == credential_id:
            found_credential = cred
            break
    
    assert found_credential is not None, "Should find the stored credential"
    assert found_credential["public_key"] == public_key, "Public key should match"
    assert found_credential["device_name"] == "Test iPhone", "Device name should match"
    print("✓ User credentials retrieved successfully")

    # Test retrieving single credential by ID
    print("Testing single credential retrieval...")
    single_cred = await get_credential_by_id(credential_id)
    assert single_cred is not None, "Should retrieve the credential by ID"
    assert single_cred["credential_id"] == credential_id, "Credential ID should match"
    assert single_cred["user_id"] == user_id, "User ID should match"
    assert single_cred["public_key"] == public_key, "Public key should match"
    print("✓ Single credential retrieved successfully")

    return user_id, credential_id


async def test_credential_caching():
    """Test credential caching functionality."""
    print("Testing credential caching...")

    user_id, credential_id = await test_credential_retrieval()

    # First call should hit database and cache the result
    print("Testing cache population...")
    credentials1 = await get_user_credentials(user_id)
    assert len(credentials1) > 0, "Should retrieve credentials from database"

    # Second call should hit cache
    print("Testing cache hit...")
    credentials2 = await get_user_credentials(user_id)
    assert len(credentials2) == len(credentials1), "Cached results should match database results"
    
    # Verify the data is the same
    cred1 = next((c for c in credentials1 if c["credential_id"] == credential_id), None)
    cred2 = next((c for c in credentials2 if c["credential_id"] == credential_id), None)
    assert cred1 is not None and cred2 is not None, "Should find credential in both results"
    assert cred1["public_key"] == cred2["public_key"], "Cached data should match database data"
    print("✓ Credential caching works correctly")

    return user_id, credential_id


async def test_credential_usage_update():
    """Test credential usage update functionality."""
    print("Testing credential usage update...")

    user_id, credential_id = await test_credential_caching()

    # Update credential usage
    new_sign_count = 42
    success = await update_credential_usage(credential_id, new_sign_count)
    assert success, "Credential usage update should succeed"
    print("✓ Credential usage updated successfully")

    # Verify the update
    updated_cred = await get_credential_by_id(credential_id)
    assert updated_cred is not None, "Should retrieve updated credential"
    assert updated_cred["sign_count"] == new_sign_count, "Sign count should be updated"
    assert updated_cred["last_used_at"] is not None, "Last used timestamp should be set"
    print("✓ Credential usage update verified")

    return user_id, credential_id


async def test_credential_ownership_validation():
    """Test credential ownership validation."""
    print("Testing credential ownership validation...")

    user_id, credential_id = await test_credential_usage_update()

    # Test valid ownership
    is_valid = await validate_credential_ownership(credential_id, user_id)
    assert is_valid, "Valid ownership should return True"
    print("✓ Valid ownership validated correctly")

    # Test invalid ownership (wrong user)
    wrong_user_id = "507f1f77bcf86cd799439012"  # Different ObjectId
    is_invalid = await validate_credential_ownership(credential_id, wrong_user_id)
    assert not is_invalid, "Invalid ownership should return False"
    print("✓ Invalid ownership rejected correctly")

    return user_id, credential_id


async def test_credential_deactivation():
    """Test credential deactivation functionality."""
    print("Testing credential deactivation...")

    user_id, credential_id = await test_credential_ownership_validation()

    # Deactivate the credential
    success = await deactivate_credential(credential_id, user_id)
    assert success, "Credential deactivation should succeed"
    print("✓ Credential deactivated successfully")

    # Verify credential is no longer active
    inactive_cred = await get_credential_by_id(credential_id)
    assert inactive_cred is None, "Deactivated credential should not be retrievable"
    print("✓ Deactivated credential properly hidden")

    # Verify it doesn't appear in user's active credentials
    active_credentials = await get_user_credentials(user_id, active_only=True)
    found_deactivated = any(cred["credential_id"] == credential_id for cred in active_credentials)
    assert not found_deactivated, "Deactivated credential should not appear in active list"
    print("✓ Deactivated credential excluded from active list")

    return user_id, credential_id


async def test_credential_edge_cases():
    """Test credential edge cases and error handling."""
    print("Testing credential edge cases...")

    # Test storing credential with missing required parameters
    try:
        await store_credential("", "test_cred", "test_key")
        assert False, "Should raise ValueError for empty user_id"
    except ValueError:
        print("✓ Empty user_id properly rejected")

    try:
        await store_credential("507f1f77bcf86cd799439011", "", "test_key")
        assert False, "Should raise ValueError for empty credential_id"
    except ValueError:
        print("✓ Empty credential_id properly rejected")

    try:
        await store_credential("507f1f77bcf86cd799439011", "test_cred", "")
        assert False, "Should raise ValueError for empty public_key"
    except ValueError:
        print("✓ Empty public_key properly rejected")

    # Test retrieving credentials for non-existent user
    empty_credentials = await get_user_credentials("507f1f77bcf86cd799439999")
    assert len(empty_credentials) == 0, "Non-existent user should have no credentials"
    print("✓ Non-existent user returns empty credentials list")

    # Test retrieving non-existent credential by ID
    non_existent_cred = await get_credential_by_id("non_existent_credential")
    assert non_existent_cred is None, "Non-existent credential should return None"
    print("✓ Non-existent credential properly returns None")

    # Test updating usage for non-existent credential
    update_success = await update_credential_usage("non_existent_credential", 10)
    assert not update_success, "Updating non-existent credential should fail"
    print("✓ Non-existent credential update properly fails")


async def test_credential_update_existing():
    """Test updating an existing credential."""
    print("Testing credential update functionality...")

    user_id = "507f1f77bcf86cd799439013"  # Different test user
    credential_id = "test_credential_update_123"
    original_public_key = "original_public_key_data"
    updated_public_key = "updated_public_key_data"

    # Store original credential
    result1 = await store_credential(
        user_id=user_id,
        credential_id=credential_id,
        public_key=original_public_key,
        device_name="Original Device",
        authenticator_type="cross-platform"
    )
    assert result1["device_name"] == "Original Device", "Original device name should be stored"
    print("✓ Original credential stored")

    # Update the same credential (same credential_id)
    result2 = await store_credential(
        user_id=user_id,
        credential_id=credential_id,
        public_key=updated_public_key,
        device_name="Updated Device",
        authenticator_type="platform"
    )
    assert result2["device_name"] == "Updated Device", "Device name should be updated"
    print("✓ Credential updated successfully")

    # Verify the credential was updated, not duplicated
    credentials = await get_user_credentials(user_id)
    matching_creds = [c for c in credentials if c["credential_id"] == credential_id]
    assert len(matching_creds) == 1, "Should have only one credential with this ID"
    
    updated_cred = matching_creds[0]
    assert updated_cred["public_key"] == updated_public_key, "Public key should be updated"
    assert updated_cred["device_name"] == "Updated Device", "Device name should be updated"
    assert updated_cred["authenticator_type"] == "platform", "Authenticator type should be updated"
    print("✓ Credential update verified - no duplicates created")

    # Clean up
    await deactivate_credential(credential_id, user_id)


async def main():
    """Run all tests."""
    print("Starting WebAuthn credential service tests...\n")

    try:
        # Test credential storage
        await test_credential_storage()
        print()

        # Test credential retrieval
        await test_credential_retrieval()
        print()

        # Test credential caching
        await test_credential_caching()
        print()

        # Test credential usage update
        await test_credential_usage_update()
        print()

        # Test ownership validation
        await test_credential_ownership_validation()
        print()

        # Test credential deactivation
        await test_credential_deactivation()
        print()

        # Test edge cases
        await test_credential_edge_cases()
        print()

        # Test credential updates
        await test_credential_update_existing()
        print()

        print("✅ All tests passed! WebAuthn credential service is working correctly.")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1

    finally:
        # Cleanup connections
        try:
            await db_manager.disconnect()
        except:
            pass

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)