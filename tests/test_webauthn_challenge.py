#!/usr/bin/env python3
"""
Test script for WebAuthn challenge generation and storage functions.

This script tests the basic functionality of the WebAuthn challenge service
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
from second_brain_database.routes.auth.services.webauthn.challenge import (
    clear_challenge,
    generate_secure_challenge,
    store_challenge,
    validate_challenge,
)


async def test_challenge_generation():
    """Test challenge generation functionality."""
    print("Testing challenge generation...")

    # Test basic challenge generation
    challenge1 = generate_secure_challenge()
    challenge2 = generate_secure_challenge()

    # Verify challenges are generated
    assert challenge1, "Challenge 1 should not be empty"
    assert challenge2, "Challenge 2 should not be empty"

    # Verify challenges are unique
    assert challenge1 != challenge2, "Challenges should be unique"

    # Verify challenge format (base64url should be URL-safe)
    assert all(c.isalnum() or c in "-_" for c in challenge1), "Challenge should be base64url encoded"

    # Verify challenge length (should be reasonable for security)
    assert len(challenge1) > 40, "Challenge should be sufficiently long"

    print(f"✓ Generated unique challenges: {challenge1[:8]}... and {challenge2[:8]}...")
    return challenge1, challenge2


async def test_challenge_storage_and_validation():
    """Test challenge storage and validation functionality."""
    print("Testing challenge storage and validation...")

    # Connect to database and Redis
    await db_manager.connect()

    # Generate test challenge
    challenge = generate_secure_challenge()
    user_id = "507f1f77bcf86cd799439011"  # Test ObjectId

    # Test storing registration challenge
    print("Testing registration challenge storage...")
    success = await store_challenge(challenge, user_id, "registration")
    assert success, "Challenge storage should succeed"
    print("✓ Registration challenge stored successfully")

    # Test validating the challenge
    print("Testing challenge validation...")
    result = await validate_challenge(challenge, user_id, "registration")
    assert result is not None, "Challenge validation should succeed"
    assert result["type"] == "registration", "Challenge type should match"
    assert result["user_id"] == user_id, "User ID should match"
    print("✓ Challenge validated successfully")

    # Test that challenge is consumed (one-time use)
    print("Testing challenge consumption...")
    result2 = await validate_challenge(challenge, user_id, "registration")
    assert result2 is None, "Challenge should be consumed after first use"
    print("✓ Challenge properly consumed after use")

    # Test authentication challenge (no user_id)
    print("Testing authentication challenge...")
    auth_challenge = generate_secure_challenge()
    success = await store_challenge(auth_challenge, None, "authentication")
    assert success, "Authentication challenge storage should succeed"

    result = await validate_challenge(auth_challenge, None, "authentication")
    assert result is not None, "Authentication challenge validation should succeed"
    assert result["type"] == "authentication", "Challenge type should match"
    assert result["user_id"] is None, "User ID should be None for auth challenges"
    print("✓ Authentication challenge works correctly")


async def test_challenge_validation_edge_cases():
    """Test challenge validation edge cases."""
    print("Testing challenge validation edge cases...")

    # Test invalid challenge
    result = await validate_challenge("invalid_challenge", None, "authentication")
    assert result is None, "Invalid challenge should return None"
    print("✓ Invalid challenge properly rejected")

    # Test wrong challenge type
    challenge = generate_secure_challenge()
    await store_challenge(challenge, None, "registration")
    result = await validate_challenge(challenge, None, "authentication")  # Wrong type
    assert result is None, "Wrong challenge type should return None"
    print("✓ Wrong challenge type properly rejected")

    # Clean up the challenge
    await clear_challenge(challenge)

    # Test wrong user ID
    challenge = generate_secure_challenge()
    user_id = "507f1f77bcf86cd799439011"
    wrong_user_id = "507f1f77bcf86cd799439012"

    await store_challenge(challenge, user_id, "registration")
    result = await validate_challenge(challenge, wrong_user_id, "registration")
    assert result is None, "Wrong user ID should return None"
    print("✓ Wrong user ID properly rejected")

    # Clean up
    await clear_challenge(challenge)


async def test_challenge_cleanup():
    """Test challenge cleanup functionality."""
    print("Testing challenge cleanup...")

    # Create a challenge
    challenge = generate_secure_challenge()
    await store_challenge(challenge, None, "authentication")

    # Clear the challenge
    success = await clear_challenge(challenge)
    assert success, "Challenge cleanup should succeed"
    print("✓ Challenge cleared successfully")

    # Verify challenge is gone
    result = await validate_challenge(challenge, None, "authentication")
    assert result is None, "Cleared challenge should not validate"
    print("✓ Cleared challenge properly removed")


async def main():
    """Run all tests."""
    print("Starting WebAuthn challenge service tests...\n")

    try:
        # Test challenge generation
        await test_challenge_generation()
        print()

        # Test storage and validation
        await test_challenge_storage_and_validation()
        print()

        # Test edge cases
        await test_challenge_validation_edge_cases()
        print()

        # Test cleanup
        await test_challenge_cleanup()
        print()

        print("✅ All tests passed! WebAuthn challenge service is working correctly.")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1

    finally:
        # Cleanup connections
        try:
            await db_manager.disconnect()
        except Exception:  # TODO: Use specific exception type
            pass

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
