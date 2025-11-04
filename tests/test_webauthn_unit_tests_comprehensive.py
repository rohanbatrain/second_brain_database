#!/usr/bin/env python3
"""
Comprehensive unit tests for WebAuthn functionality following existing patterns.

This test suite provides complete unit test coverage for all WebAuthn components
including challenge management, credential storage, cryptographic operations,
authentication flows, and monitoring infrastructure.
"""

import asyncio
import base64
import json
import os
import sys
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Dict, Any

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from second_brain_database.database import db_manager
from second_brain_database.routes.auth.services.webauthn.challenge import (
    clear_challenge,
    generate_secure_challenge,
    store_challenge,
    validate_challenge,
)
from second_brain_database.routes.auth.services.webauthn.credentials import (
    deactivate_credential,
    get_credential_by_id,
    get_user_credentials,
    store_credential,
    update_credential_usage,
    validate_credential_ownership,
)
from second_brain_database.routes.auth.services.webauthn.crypto import (
    base64url_decode,
    base64url_encode,
    extract_aaguid,
    extract_public_key,
    verify_assertion_signature,
)
from second_brain_database.routes.auth.services.webauthn.authentication import (
    begin_authentication,
    complete_authentication,
)
from second_brain_database.routes.auth.services.webauthn.monitoring import (
    webauthn_monitor,
    cleanup_monitoring_data,
)


class TestWebAuthnChallengeManagement:
    """Test WebAuthn challenge generation, storage, and validation following existing patterns."""

    def test_challenge_generation_basic(self):
        """Test basic challenge generation functionality."""
        # Test basic generation
        challenge1 = generate_secure_challenge()
        challenge2 = generate_secure_challenge()

        # Verify challenges are generated
        assert challenge1, "Challenge should not be empty"
        assert challenge2, "Challenge should not be empty"
        assert isinstance(challenge1, str), "Challenge should be string"
        assert isinstance(challenge2, str), "Challenge should be string"

        # Verify uniqueness
        assert challenge1 != challenge2, "Challenges should be unique"

        # Verify format (base64url)
        assert all(c.isalnum() or c in "-_" for c in challenge1), "Challenge should be base64url encoded"

        # Verify length (should be sufficient for security)
        assert len(challenge1) >= 40, "Challenge should be sufficiently long"

    def test_challenge_generation_entropy(self):
        """Test challenge generation entropy and randomness."""
        challenges = [generate_secure_challenge() for _ in range(100)]

        # Test uniqueness
        assert len(set(challenges)) == 100, "All challenges should be unique"

        # Test character distribution
        all_chars = "".join(challenges)
        char_counts = {}
        for char in all_chars:
            char_counts[char] = char_counts.get(char, 0) + 1

        # Should use diverse character set
        assert len(char_counts) >= 20, "Should use diverse character set"

        # No character should dominate (basic entropy check)
        max_char_frequency = max(char_counts.values())
        total_chars = len(all_chars)
        max_frequency_ratio = max_char_frequency / total_chars

        assert max_frequency_ratio < 0.15, "No single character should dominate"

    def test_challenge_generation_performance(self):
        """Test challenge generation performance."""
        start_time = time.time()
        challenges = []

        # Generate multiple challenges
        for _ in range(100):
            challenge = generate_secure_challenge()
            challenges.append(challenge)

        generation_time = time.time() - start_time

        # Verify all challenges are unique
        assert len(set(challenges)) == 100, "All challenges should be unique"

        # Performance should be reasonable (< 1 second for 100 challenges)
        assert generation_time < 1.0, f"Challenge generation too slow: {generation_time}s"

    @pytest.mark.asyncio
    async def test_challenge_storage_and_validation(self):
        """Test challenge storage and validation functionality."""
        await db_manager.connect()

        try:
            challenge = generate_secure_challenge()
            user_id = "507f1f77bcf86cd799439011"

            # Test storing registration challenge
            success = await store_challenge(challenge, user_id, "registration")
            assert success, "Challenge storage should succeed"

            # Test validating the challenge
            result = await validate_challenge(challenge, user_id, "registration")
            assert result is not None, "Challenge validation should succeed"
            assert result["type"] == "registration", "Challenge type should match"
            assert result["user_id"] == user_id, "User ID should match"

            # Test that challenge is consumed (one-time use)
            result2 = await validate_challenge(challenge, user_id, "registration")
            assert result2 is None, "Challenge should be consumed after first use"

        finally:
            await db_manager.disconnect()

    @pytest.mark.asyncio
    async def test_challenge_authentication_flow(self):
        """Test authentication challenge flow (no user_id)."""
        await db_manager.connect()

        try:
            challenge = generate_secure_challenge()

            # Store authentication challenge (no user_id)
            success = await store_challenge(challenge, None, "authentication")
            assert success, "Authentication challenge storage should succeed"

            # Validate authentication challenge
            result = await validate_challenge(challenge, None, "authentication")
            assert result is not None, "Authentication challenge validation should succeed"
            assert result["type"] == "authentication", "Challenge type should match"
            assert result["user_id"] is None, "User ID should be None for auth challenges"

        finally:
            await db_manager.disconnect()

    @pytest.mark.asyncio
    async def test_challenge_validation_edge_cases(self):
        """Test challenge validation edge cases and error handling."""
        await db_manager.connect()

        try:
            # Test invalid challenge
            result = await validate_challenge("invalid_challenge", None, "authentication")
            assert result is None, "Invalid challenge should return None"

            # Test wrong challenge type
            challenge = generate_secure_challenge()
            await store_challenge(challenge, None, "registration")
            result = await validate_challenge(challenge, None, "authentication")
            assert result is None, "Wrong challenge type should return None"

            # Clean up
            await clear_challenge(challenge)

            # Test wrong user ID
            challenge = generate_secure_challenge()
            user_id = "507f1f77bcf86cd799439011"
            wrong_user_id = "507f1f77bcf86cd799439012"

            await store_challenge(challenge, user_id, "registration")
            result = await validate_challenge(challenge, wrong_user_id, "registration")
            assert result is None, "Wrong user ID should return None"

            # Clean up
            await clear_challenge(challenge)

        finally:
            await db_manager.disconnect()

    @pytest.mark.asyncio
    async def test_challenge_cleanup(self):
        """Test challenge cleanup functionality."""
        await db_manager.connect()

        try:
            challenge = generate_secure_challenge()
            await store_challenge(challenge, None, "authentication")

            # Clear the challenge
            success = await clear_challenge(challenge)
            assert success, "Challenge cleanup should succeed"

            # Verify challenge is gone
            result = await validate_challenge(challenge, None, "authentication")
            assert result is None, "Cleared challenge should not validate"

        finally:
            await db_manager.disconnect()


class TestWebAuthnCredentialManagement:
    """Test WebAuthn credential storage, retrieval, and management following existing patterns."""

    @pytest.mark.asyncio
    async def test_credential_storage_basic(self):
        """Test basic credential storage functionality."""
        await db_manager.connect()

        try:
            user_id = "507f1f77bcf86cd799439011"
            credential_id = "test_credential_unit_123"
            public_key = "test_public_key_data_cbor_encoded"
            device_name = "Test Unit Device"

            # Test storing credential
            result = await store_credential(
                user_id=user_id,
                credential_id=credential_id,
                public_key=public_key,
                device_name=device_name,
                authenticator_type="platform",
                transport=["internal"],
                aaguid="test-aaguid-unit-123"
            )

            assert result is not None, "Credential storage should succeed"
            assert result["credential_id"] == credential_id, "Credential ID should match"
            assert result["device_name"] == device_name, "Device name should match"
            assert result["authenticator_type"] == "platform", "Authenticator type should match"
            assert result["is_active"] is True, "Credential should be active"

            # Clean up
            await deactivate_credential(credential_id, user_id)

        finally:
            await db_manager.disconnect()

    @pytest.mark.asyncio
    async def test_credential_retrieval(self):
        """Test credential retrieval functionality."""
        await db_manager.connect()

        try:
            user_id = "507f1f77bcf86cd799439012"
            credential_id = "test_credential_retrieval_123"
            public_key = "test_public_key_retrieval"

            # Store test credential
            await store_credential(
                user_id=user_id,
                credential_id=credential_id,
                public_key=public_key,
                device_name="Test Retrieval Device",
                authenticator_type="cross-platform"
            )

            # Test retrieving user credentials
            credentials = await get_user_credentials(user_id)
            assert len(credentials) > 0, "Should retrieve at least one credential"

            found_credential = None
            for cred in credentials:
                if cred["credential_id"] == credential_id:
                    found_credential = cred
                    break

            assert found_credential is not None, "Should find the stored credential"
            assert found_credential["public_key"] == public_key, "Public key should match"
            assert found_credential["device_name"] == "Test Retrieval Device", "Device name should match"

            # Test retrieving single credential by ID
            single_cred = await get_credential_by_id(credential_id)
            assert single_cred is not None, "Should retrieve the credential by ID"
            assert single_cred["credential_id"] == credential_id, "Credential ID should match"
            assert single_cred["user_id"] == user_id, "User ID should match"
            assert single_cred["public_key"] == public_key, "Public key should match"

            # Clean up
            await deactivate_credential(credential_id, user_id)

        finally:
            await db_manager.disconnect()

    @pytest.mark.asyncio
    async def test_credential_usage_update(self):
        """Test credential usage update functionality."""
        await db_manager.connect()

        try:
            user_id = "507f1f77bcf86cd799439013"
            credential_id = "test_credential_usage_123"

            # Store test credential
            await store_credential(
                user_id=user_id,
                credential_id=credential_id,
                public_key="test_public_key_usage",
                device_name="Test Usage Device"
            )

            # Update credential usage
            new_sign_count = 42
            success = await update_credential_usage(credential_id, new_sign_count)
            assert success, "Credential usage update should succeed"

            # Verify the update
            updated_cred = await get_credential_by_id(credential_id)
            assert updated_cred is not None, "Should retrieve updated credential"
            assert updated_cred["sign_count"] == new_sign_count, "Sign count should be updated"
            assert updated_cred["last_used_at"] is not None, "Last used timestamp should be set"

            # Clean up
            await deactivate_credential(credential_id, user_id)

        finally:
            await db_manager.disconnect()

    @pytest.mark.asyncio
    async def test_credential_ownership_validation(self):
        """Test credential ownership validation."""
        await db_manager.connect()

        try:
            user_id = "507f1f77bcf86cd799439014"
            credential_id = "test_credential_ownership_123"

            # Store test credential
            await store_credential(
                user_id=user_id,
                credential_id=credential_id,
                public_key="test_public_key_ownership",
                device_name="Test Ownership Device"
            )

            # Test valid ownership
            is_valid = await validate_credential_ownership(credential_id, user_id)
            assert is_valid, "Valid ownership should return True"

            # Test invalid ownership (wrong user)
            wrong_user_id = "507f1f77bcf86cd799439015"
            is_invalid = await validate_credential_ownership(credential_id, wrong_user_id)
            assert not is_invalid, "Invalid ownership should return False"

            # Clean up
            await deactivate_credential(credential_id, user_id)

        finally:
            await db_manager.disconnect()

    @pytest.mark.asyncio
    async def test_credential_deactivation(self):
        """Test credential deactivation functionality."""
        await db_manager.connect()

        try:
            user_id = "507f1f77bcf86cd799439016"
            credential_id = "test_credential_deactivation_123"

            # Store test credential
            await store_credential(
                user_id=user_id,
                credential_id=credential_id,
                public_key="test_public_key_deactivation",
                device_name="Test Deactivation Device"
            )

            # Deactivate the credential
            success = await deactivate_credential(credential_id, user_id)
            assert success, "Credential deactivation should succeed"

            # Verify credential is no longer active
            inactive_cred = await get_credential_by_id(credential_id)
            assert inactive_cred is None, "Deactivated credential should not be retrievable"

            # Verify it doesn't appear in user's active credentials
            active_credentials = await get_user_credentials(user_id, active_only=True)
            found_deactivated = any(cred["credential_id"] == credential_id for cred in active_credentials)
            assert not found_deactivated, "Deactivated credential should not appear in active list"

        finally:
            await db_manager.disconnect()

    @pytest.mark.asyncio
    async def test_credential_edge_cases(self):
        """Test credential edge cases and error handling."""
        await db_manager.connect()

        try:
            # Test storing credential with missing required parameters
            with pytest.raises(ValueError):
                await store_credential("", "test_cred", "test_key")

            with pytest.raises(ValueError):
                await store_credential("507f1f77bcf86cd799439011", "", "test_key")

            with pytest.raises(ValueError):
                await store_credential("507f1f77bcf86cd799439011", "test_cred", "")

            # Test retrieving credentials for non-existent user
            empty_credentials = await get_user_credentials("507f1f77bcf86cd799439999")
            assert len(empty_credentials) == 0, "Non-existent user should have no credentials"

            # Test retrieving non-existent credential by ID
            non_existent_cred = await get_credential_by_id("non_existent_credential")
            assert non_existent_cred is None, "Non-existent credential should return None"

            # Test updating usage for non-existent credential
            update_success = await update_credential_usage("non_existent_credential", 10)
            assert not update_success, "Updating non-existent credential should fail"

        finally:
            await db_manager.disconnect()

    @pytest.mark.asyncio
    async def test_credential_security_isolation(self):
        """Test that users can only access their own credentials."""
        await db_manager.connect()

        try:
            user1_id = "507f1f77bcf86cd799439021"
            user2_id = "507f1f77bcf86cd799439022"

            # Store credentials for both users
            user1_credential = "user1_credential_123"
            user2_credential = "user2_credential_123"

            await store_credential(
                user_id=user1_id,
                credential_id=user1_credential,
                public_key="user1_public_key",
                device_name="User 1 Device"
            )

            await store_credential(
                user_id=user2_id,
                credential_id=user2_credential,
                public_key="user2_public_key",
                device_name="User 2 Device"
            )

            # Test credential isolation
            user1_credentials = await get_user_credentials(user1_id)
            user2_credentials = await get_user_credentials(user2_id)

            # Each user should only see their own credentials
            user1_cred_ids = [c["credential_id"] for c in user1_credentials]
            user2_cred_ids = [c["credential_id"] for c in user2_credentials]

            assert user1_credential in user1_cred_ids, "User 1 should see their credential"
            assert user2_credential not in user1_cred_ids, "User 1 should not see User 2's credential"

            assert user2_credential in user2_cred_ids, "User 2 should see their credential"
            assert user1_credential not in user2_cred_ids, "User 2 should not see User 1's credential"

            # Test ownership validation
            assert await validate_credential_ownership(user1_credential, user1_id), "User 1 should own their credential"
            assert not await validate_credential_ownership(user1_credential, user2_id), "User 2 should not own User 1's credential"

            # Clean up
            await deactivate_credential(user1_credential, user1_id)
            await deactivate_credential(user2_credential, user2_id)

        finally:
            await db_manager.disconnect()


class TestWebAuthnCryptographicOperations:
    """Test WebAuthn cryptographic operations following existing patterns."""

    def test_base64url_encoding_decoding_basic(self):
        """Test basic base64url encoding and decoding."""
        # Test basic encoding/decoding
        test_data = b"Hello, WebAuthn!"
        encoded = base64url_encode(test_data)
        decoded = base64url_decode(encoded)

        assert isinstance(encoded, str), "Encoded data should be string"
        assert decoded == test_data, "Decoded data should match original"

        # Test URL-safe characters
        assert "+" not in encoded, "base64url should not contain '+'"
        assert "/" not in encoded, "base64url should not contain '/'"
        assert "=" not in encoded, "base64url should not contain padding"

    def test_base64url_encoding_edge_cases(self):
        """Test base64url encoding edge cases."""
        # Test empty data
        empty_encoded = base64url_encode(b"")
        empty_decoded = base64url_decode(empty_encoded)
        assert empty_decoded == b"", "Empty data should encode/decode correctly"

        # Test various data sizes
        test_cases = [
            b"a",  # 1 byte
            b"ab",  # 2 bytes
            b"abc",  # 3 bytes
            b"abcd",  # 4 bytes
            b"a" * 100,  # Large data
            b"\x00\x01\x02\x03",  # Binary data
        ]

        for test_data in test_cases:
            encoded = base64url_encode(test_data)
            decoded = base64url_decode(encoded)
            assert decoded == test_data, f"Failed for data: {test_data}"

    def test_extract_public_key_mocked(self):
        """Test public key extraction from attestation object with mocking."""
        # Mock attestation object with CBOR-encoded public key
        mock_attestation_object = base64url_encode(b"mock_cbor_attestation_data")

        with patch('second_brain_database.routes.auth.services.webauthn.crypto.cbor2.loads') as mock_cbor_loads:
            # Mock CBOR structure
            mock_cbor_loads.return_value = {
                "authData": b"mock_auth_data",
                "fmt": "none",
                "attStmt": {}
            }

            with patch('second_brain_database.routes.auth.services.webauthn.crypto.extract_credential_public_key') as mock_extract:
                mock_extract.return_value = "mock_public_key_cbor"

                result = extract_public_key(mock_attestation_object)
                assert result == "mock_public_key_cbor", "Should return extracted public key"

    def test_extract_aaguid_mocked(self):
        """Test AAGUID extraction from attestation object with mocking."""
        mock_attestation_object = base64url_encode(b"mock_cbor_attestation_data")

        with patch('second_brain_database.routes.auth.services.webauthn.crypto.cbor2.loads') as mock_cbor_loads:
            # Mock CBOR structure with auth data containing AAGUID
            mock_auth_data = b"mock_rp_id_hash" + b"\x01" + b"\x00\x00\x00\x00" + b"test_aaguid_16b" + b"mock_rest"
            mock_cbor_loads.return_value = {
                "authData": mock_auth_data,
                "fmt": "none"
            }

            result = extract_aaguid(mock_attestation_object)
            # Should extract AAGUID from bytes 37-53 of auth data
            expected_aaguid = base64url_encode(b"test_aaguid_16b")
            assert result == expected_aaguid, "Should extract AAGUID correctly"

    def test_verify_assertion_signature_es256(self):
        """Test ES256 signature verification with mocking."""
        # Mock assertion response
        mock_assertion_response = {
            "response": {
                "authenticatorData": base64url_encode(b"mock_auth_data"),
                "clientDataJSON": base64url_encode(b'{"type":"webauthn.get","challenge":"test"}'),
                "signature": base64url_encode(b"mock_signature")
            }
        }

        # Mock public key (ES256)
        mock_public_key_cbor = base64url_encode(b"mock_cbor_public_key")

        with patch('second_brain_database.routes.auth.services.webauthn.crypto.cbor2.loads') as mock_cbor_loads:
            # Mock ES256 public key structure
            mock_cbor_loads.return_value = {
                1: 2,  # kty: EC2
                3: -7,  # alg: ES256
                -1: 1,  # crv: P-256
                -2: b"mock_x_coordinate",  # x
                -3: b"mock_y_coordinate"   # y
            }

            with patch('second_brain_database.routes.auth.services.webauthn.crypto.verify_es256_signature') as mock_verify:
                mock_verify.return_value = True

                result = verify_assertion_signature(mock_assertion_response, mock_public_key_cbor)
                assert result is True, "ES256 signature verification should succeed"

    def test_verify_assertion_signature_rs256(self):
        """Test RS256 signature verification with mocking."""
        # Mock assertion response
        mock_assertion_response = {
            "response": {
                "authenticatorData": base64url_encode(b"mock_auth_data"),
                "clientDataJSON": base64url_encode(b'{"type":"webauthn.get","challenge":"test"}'),
                "signature": base64url_encode(b"mock_signature")
            }
        }

        # Mock public key (RS256)
        mock_public_key_cbor = base64url_encode(b"mock_cbor_public_key")

        with patch('second_brain_database.routes.auth.services.webauthn.crypto.cbor2.loads') as mock_cbor_loads:
            # Mock RS256 public key structure
            mock_cbor_loads.return_value = {
                1: 3,  # kty: RSA
                3: -257,  # alg: RS256
                -1: b"mock_n_modulus",  # n
                -2: b"mock_e_exponent"  # e
            }

            with patch('second_brain_database.routes.auth.services.webauthn.crypto.verify_rs256_signature') as mock_verify:
                mock_verify.return_value = True

                result = verify_assertion_signature(mock_assertion_response, mock_public_key_cbor)
                assert result is True, "RS256 signature verification should succeed"

    def test_verify_assertion_signature_unsupported_algorithm(self):
        """Test handling of unsupported signature algorithms."""
        mock_assertion_response = {
            "response": {
                "authenticatorData": base64url_encode(b"mock_auth_data"),
                "clientDataJSON": base64url_encode(b'{"type":"webauthn.get","challenge":"test"}'),
                "signature": base64url_encode(b"mock_signature")
            }
        }

        mock_public_key_cbor = base64url_encode(b"mock_cbor_public_key")

        with patch('second_brain_database.routes.auth.services.webauthn.crypto.cbor2.loads') as mock_cbor_loads:
            # Mock unsupported algorithm
            mock_cbor_loads.return_value = {
                1: 2,  # kty: EC2
                3: -999,  # alg: Unsupported
            }

            result = verify_assertion_signature(mock_assertion_response, mock_public_key_cbor)
            assert result is False, "Unsupported algorithm should return False"

    def test_verify_assertion_signature_error_handling(self):
        """Test error handling in signature verification."""
        mock_assertion_response = {
            "response": {
                "authenticatorData": base64url_encode(b"mock_auth_data"),
                "clientDataJSON": base64url_encode(b'{"type":"webauthn.get","challenge":"test"}'),
                "signature": base64url_encode(b"mock_signature")
            }
        }

        mock_public_key_cbor = "invalid_cbor_data"

        # Should handle CBOR decoding errors gracefully
        result = verify_assertion_signature(mock_assertion_response, mock_public_key_cbor)
        assert result is False, "Invalid CBOR should return False"


class TestWebAuthnAuthenticationFlows:
    """Test WebAuthn authentication flows following existing patterns."""

    @pytest.mark.asyncio
    async def test_begin_authentication_success(self):
        """Test successful authentication begin flow."""
        await db_manager.connect()

        try:
            # Create test user
            user_doc = {
                "_id": "507f1f77bcf86cd799439011",
                "username": "test_auth_user",
                "email": "test_auth@example.com",
                "is_verified": True,
                "is_active": True,
                "abuse_suspended": False
            }

            # Mock database operations
            with patch.object(db_manager, 'get_collection') as mock_get_collection:
                mock_collection = AsyncMock()
                mock_collection.find_one.return_value = user_doc
                mock_get_collection.return_value = mock_collection

                # Mock credential retrieval
                with patch('second_brain_database.routes.auth.services.webauthn.authentication.get_user_credentials') as mock_get_creds:
                    mock_get_creds.return_value = [
                        {
                            "credential_id": "test_cred_123",
                            "transport": ["usb", "nfc"]
                        }
                    ]

                    # Mock challenge operations
                    with patch('second_brain_database.routes.auth.services.webauthn.authentication.generate_secure_challenge') as mock_gen_challenge:
                        mock_gen_challenge.return_value = "test_challenge_123"

                        with patch('second_brain_database.routes.auth.services.webauthn.authentication.store_challenge') as mock_store_challenge:
                            mock_store_challenge.return_value = True

                            result = await begin_authentication(username="test_auth_user")

                            assert "publicKey" in result, "Should return publicKey options"
                            assert result["username"] == "test_auth_user", "Should return username"
                            assert result["email"] == "test_auth@example.com", "Should return email"

                            public_key = result["publicKey"]
                            assert public_key["challenge"] == "test_challenge_123", "Should include challenge"
                            assert len(public_key["allowCredentials"]) == 1, "Should include allowed credentials"

        finally:
            await db_manager.disconnect()

    @pytest.mark.asyncio
    async def test_begin_authentication_user_not_found(self):
        """Test authentication begin with non-existent user."""
        await db_manager.connect()

        try:
            # Mock database operations to return None (user not found)
            with patch.object(db_manager, 'get_collection') as mock_get_collection:
                mock_collection = AsyncMock()
                mock_collection.find_one.return_value = None
                mock_get_collection.return_value = mock_collection

                from fastapi import HTTPException
                with pytest.raises(HTTPException) as exc_info:
                    await begin_authentication(username="non_existent_user")

                assert exc_info.value.status_code == 401
                assert "Invalid credentials" in str(exc_info.value.detail)

        finally:
            await db_manager.disconnect()

    @pytest.mark.asyncio
    async def test_begin_authentication_no_credentials(self):
        """Test authentication begin with user having no credentials."""
        await db_manager.connect()

        try:
            # Create test user
            user_doc = {
                "_id": "507f1f77bcf86cd799439011",
                "username": "test_no_creds_user",
                "email": "test_no_creds@example.com",
                "is_verified": True,
                "is_active": True,
                "abuse_suspended": False
            }

            # Mock database operations
            with patch.object(db_manager, 'get_collection') as mock_get_collection:
                mock_collection = AsyncMock()
                mock_collection.find_one.return_value = user_doc
                mock_get_collection.return_value = mock_collection

                # Mock credential retrieval to return empty list
                with patch('second_brain_database.routes.auth.services.webauthn.authentication.get_user_credentials') as mock_get_creds:
                    mock_get_creds.return_value = []

                    from fastapi import HTTPException
                    with pytest.raises(HTTPException) as exc_info:
                        await begin_authentication(username="test_no_creds_user")

                    assert exc_info.value.status_code == 404
                    assert "No WebAuthn credentials found" in str(exc_info.value.detail)

        finally:
            await db_manager.disconnect()

    @pytest.mark.asyncio
    async def test_begin_authentication_account_suspended(self):
        """Test authentication begin with suspended account."""
        await db_manager.connect()

        try:
            # Create suspended test user
            user_doc = {
                "_id": "507f1f77bcf86cd799439011",
                "username": "test_suspended_user",
                "email": "test_suspended@example.com",
                "is_verified": True,
                "is_active": True,
                "abuse_suspended": True,
                "abuse_suspended_at": datetime.utcnow()
            }

            # Mock database operations
            with patch.object(db_manager, 'get_collection') as mock_get_collection:
                mock_collection = AsyncMock()
                mock_collection.find_one.return_value = user_doc
                mock_get_collection.return_value = mock_collection

                from fastapi import HTTPException
                with pytest.raises(HTTPException) as exc_info:
                    await begin_authentication(username="test_suspended_user")

                assert exc_info.value.status_code == 403
                assert "Account suspended" in str(exc_info.value.detail)

        finally:
            await db_manager.disconnect()

    @pytest.mark.asyncio
    async def test_complete_authentication_success(self):
        """Test successful authentication completion flow."""
        await db_manager.connect()

        try:
            # Mock credential retrieval
            mock_credential = {
                "credential_id": "test_cred_123",
                "user_id": "507f1f77bcf86cd799439011",
                "public_key": "mock_public_key",
                "device_name": "Test Device",
                "authenticator_type": "platform",
                "sign_count": 5
            }

            # Mock user document
            mock_user = {
                "_id": "507f1f77bcf86cd799439011",
                "username": "test_complete_user",
                "email": "test_complete@example.com",
                "is_verified": True,
                "client_side_encryption": False
            }

            with patch('second_brain_database.routes.auth.services.webauthn.authentication.get_credential_by_id') as mock_get_cred:
                mock_get_cred.return_value = mock_credential

                with patch.object(db_manager, 'get_collection') as mock_get_collection:
                    mock_collection = AsyncMock()
                    mock_collection.find_one.return_value = mock_user
                    mock_get_collection.return_value = mock_collection

                    # Mock challenge validation
                    with patch('second_brain_database.routes.auth.services.webauthn.authentication.validate_challenge') as mock_validate:
                        mock_validate.return_value = {"type": "authentication", "user_id": "507f1f77bcf86cd799439011"}

                        # Mock credential usage update
                        with patch('second_brain_database.routes.auth.services.webauthn.authentication.update_credential_usage') as mock_update:
                            mock_update.return_value = True

                            # Mock login_user function
                            with patch('second_brain_database.routes.auth.services.webauthn.authentication.login_user') as mock_login:
                                mock_login.return_value = mock_user

                                # Mock token creation
                                with patch('second_brain_database.routes.auth.services.webauthn.authentication.create_access_token') as mock_token:
                                    mock_token.return_value = "mock_jwt_token"

                                    # Create mock client data
                                    client_data = {
                                        "type": "webauthn.get",
                                        "challenge": "test_challenge",
                                        "origin": "http://localhost"
                                    }
                                    client_data_json = base64.urlsafe_b64encode(json.dumps(client_data).encode()).decode().rstrip("=")

                                    result = await complete_authentication(
                                        credential_id="test_cred_123",
                                        authenticator_data="mock_auth_data",
                                        client_data_json=client_data_json,
                                        signature="mock_signature"
                                    )

                                    assert result["access_token"] == "mock_jwt_token", "Should return JWT token"
                                    assert result["token_type"] == "bearer", "Should return bearer token type"
                                    assert result["username"] == "test_complete_user", "Should return username"
                                    assert result["authentication_method"] == "webauthn", "Should indicate WebAuthn auth"

        finally:
            await db_manager.disconnect()


class TestWebAuthnMonitoring:
    """Test WebAuthn monitoring and audit infrastructure following existing patterns."""

    @pytest.mark.asyncio
    async def test_monitor_authentication_attempt_success(self):
        """Test monitoring successful authentication attempts."""
        # Mock the monitoring function
        with patch('second_brain_database.routes.auth.services.webauthn.monitoring.log_security_event') as mock_log:
            await webauthn_monitor.monitor_authentication_attempt(
                user_id="test_user",
                credential_id="test_cred_123",
                ip_address="192.168.1.1",
                success=True,
                operation_duration=0.5,
                error_details=None
            )

            # Verify security event was logged
            mock_log.assert_called()
            call_args = mock_log.call_args[1]
            assert call_args["event_type"] == "webauthn_authentication_monitored"
            assert call_args["user_id"] == "test_user"
            assert call_args["success"] is True

    @pytest.mark.asyncio
    async def test_monitor_authentication_attempt_failure(self):
        """Test monitoring failed authentication attempts."""
        # Mock Redis operations
        with patch('second_brain_database.routes.auth.services.webauthn.monitoring.redis_manager.get_redis') as mock_redis:
            mock_redis_conn = AsyncMock()
            mock_redis_conn.incr.return_value = 3  # Below threshold
            mock_redis_conn.expire.return_value = True
            mock_redis.return_value = mock_redis_conn

            with patch('second_brain_database.routes.auth.services.webauthn.monitoring.log_security_event') as mock_log:
                await webauthn_monitor.monitor_authentication_attempt(
                    user_id="test_user",
                    credential_id="test_cred_123",
                    ip_address="192.168.1.1",
                    success=False,
                    operation_duration=1.5,
                    error_details={"error": "invalid_credential"}
                )

                # Verify security event was logged
                mock_log.assert_called()
                call_args = mock_log.call_args[1]
                assert call_args["event_type"] == "webauthn_authentication_monitored"
                assert call_args["success"] is False

    @pytest.mark.asyncio
    async def test_monitor_slow_operation_alert(self):
        """Test monitoring slow operation alerts."""
        with patch('second_brain_database.routes.auth.services.webauthn.monitoring.log_security_event') as mock_log:
            # Test slow operation (> 2.0 seconds threshold)
            await webauthn_monitor.monitor_authentication_attempt(
                user_id="test_user",
                credential_id="test_cred_123",
                ip_address="192.168.1.1",
                success=True,
                operation_duration=3.0,  # Slow operation
                error_details=None
            )

            # Should log both the slow operation event and the regular monitoring event
            assert mock_log.call_count >= 2

            # Check for slow operation event
            slow_op_calls = [call for call in mock_log.call_args_list
                           if call[1]["event_type"] == "webauthn_slow_authentication"]
            assert len(slow_op_calls) > 0, "Should log slow operation event"

    @pytest.mark.asyncio
    async def test_cleanup_monitoring_data(self):
        """Test monitoring data cleanup functionality."""
        # Mock Redis operations
        with patch('second_brain_database.routes.auth.services.webauthn.monitoring.redis_manager.get_redis') as mock_redis:
            mock_redis_conn = AsyncMock()
            mock_redis_conn.keys.return_value = ["key1", "key2"]
            mock_redis_conn.ttl.return_value = -2  # Expired key
            mock_redis.return_value = mock_redis_conn

            # Mock database operations
            with patch.object(db_manager, 'get_collection') as mock_get_collection:
                mock_collection = AsyncMock()
                mock_collection.delete_many.return_value = Mock(deleted_count=5)
                mock_get_collection.return_value = mock_collection

                result = await cleanup_monitoring_data()

                assert "redis_cleaned" in result, "Should return Redis cleanup count"
                assert "database_cleaned" in result, "Should return database cleanup count"
                assert result["database_cleaned"] == 5, "Should report correct database cleanup count"


class TestWebAuthnPerformanceAndSecurity:
    """Test performance and security aspects of WebAuthn implementation."""

    @pytest.mark.asyncio
    async def test_credential_storage_performance(self):
        """Test credential storage performance."""
        await db_manager.connect()

        try:
            user_id = "507f1f77bcf86cd799439020"
            credentials_to_store = 10

            start_time = time.time()

            # Store multiple credentials
            stored_credentials = []
            for i in range(credentials_to_store):
                credential_id = f"perf_test_credential_{i}"
                result = await store_credential(
                    user_id=user_id,
                    credential_id=credential_id,
                    public_key=f"test_public_key_{i}",
                    device_name=f"Test Device {i}"
                )
                stored_credentials.append(credential_id)
                assert result is not None, f"Credential {i} storage should succeed"

            storage_time = time.time() - start_time

            # Performance should be reasonable
            assert storage_time < 5.0, f"Credential storage too slow: {storage_time}s"

            # Test retrieval performance
            start_time = time.time()
            retrieved_credentials = await get_user_credentials(user_id)
            retrieval_time = time.time() - start_time

            assert len(retrieved_credentials) >= credentials_to_store, "Should retrieve all stored credentials"
            assert retrieval_time < 1.0, f"Credential retrieval too slow: {retrieval_time}s"

            # Clean up
            for credential_id in stored_credentials:
                await deactivate_credential(credential_id, user_id)

        finally:
            await db_manager.disconnect()

    def test_challenge_generation_security(self):
        """Test challenge generation security properties."""
        challenges = [generate_secure_challenge() for _ in range(1000)]

        # Test uniqueness
        assert len(set(challenges)) == 1000, "All challenges should be unique"

        # Test character distribution
        all_chars = "".join(challenges)
        char_counts = {}
        for char in all_chars:
            char_counts[char] = char_counts.get(char, 0) + 1

        # Should use most of the base64url character set
        assert len(char_counts) >= 50, "Should use diverse character set"

        # No character should dominate (basic entropy check)
        max_char_frequency = max(char_counts.values())
        total_chars = len(all_chars)
        max_frequency_ratio = max_char_frequency / total_chars

        assert max_frequency_ratio < 0.1, "No single character should dominate"

    @pytest.mark.asyncio
    async def test_concurrent_credential_operations(self):
        """Test concurrent credential operations for race conditions."""
        await db_manager.connect()

        try:
            user_id = "507f1f77bcf86cd799439030"
            credential_id = "concurrent_test_credential"

            # Test concurrent credential storage
            async def store_credential_task():
                return await store_credential(
                    user_id=user_id,
                    credential_id=credential_id,
                    public_key="concurrent_test_key",
                    device_name="Concurrent Test Device"
                )

            # Run multiple concurrent storage operations
            tasks = [store_credential_task() for _ in range(5)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # At least one should succeed, others might fail due to uniqueness constraints
            successful_results = [r for r in results if not isinstance(r, Exception)]
            assert len(successful_results) >= 1, "At least one concurrent operation should succeed"

            # Clean up
            await deactivate_credential(credential_id, user_id)

        finally:
            await db_manager.disconnect()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
