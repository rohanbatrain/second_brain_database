#!/usr/bin/env python3
"""
Comprehensive unit tests for WebAuthn functionality.

This test suite follows existing patterns and tests all WebAuthn components
including challenge management, credential storage, cryptographic operations,
and authentication flows.
"""

import asyncio
import base64
import json
import os
import sys
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
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


class TestWebAuthnChallengeManagement:
    """Test WebAuthn challenge generation, storage, and validation."""

    def test_challenge_generation(self):
        """Test secure challenge generation."""
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
    """Test WebAuthn credential storage, retrieval, and management."""

    @pytest.mark.asyncio
    async def test_credential_storage(self):
        """Test credential storage functionality."""
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
    async def test_credential_update_existing(self):
        """Test updating an existing credential."""
        await db_manager.connect()

        try:
            user_id = "507f1f77bcf86cd799439017"
            credential_id = "test_credential_update_unit_123"
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

            # Update the same credential (same credential_id)
            result2 = await store_credential(
                user_id=user_id,
                credential_id=credential_id,
                public_key=updated_public_key,
                device_name="Updated Device",
                authenticator_type="platform"
            )
            assert result2["device_name"] == "Updated Device", "Device name should be updated"

            # Verify the credential was updated, not duplicated
            credentials = await get_user_credentials(user_id)
            matching_creds = [c for c in credentials if c["credential_id"] == credential_id]
            assert len(matching_creds) == 1, "Should have only one credential with this ID"

            updated_cred = matching_creds[0]
            assert updated_cred["public_key"] == updated_public_key, "Public key should be updated"
            assert updated_cred["device_name"] == "Updated Device", "Device name should be updated"
            assert updated_cred["authenticator_type"] == "platform", "Authenticator type should be updated"

            # Clean up
            await deactivate_credential(credential_id, user_id)

        finally:
            await db_manager.disconnect()


class TestWebAuthnCryptographicOperations:
    """Test WebAuthn cryptographic operations."""

    def test_base64url_encoding_decoding(self):
        """Test base64url encoding and decoding."""
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

        # Test empty data
        empty_encoded = base64url_encode(b"")
        empty_decoded = base64url_decode(empty_encoded)
        assert empty_decoded == b"", "Empty data should encode/decode correctly"

    def test_extract_public_key(self):
        """Test public key extraction from attestation object."""
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

    def test_extract_aaguid(self):
        """Test AAGUID extraction from attestation object."""
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
        """Test ES256 signature verification."""
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
        """Test RS256 signature verification."""
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


class TestWebAuthnPerformanceAndSecurity:
    """Test performance and security aspects of WebAuthn implementation."""

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

        # Verify entropy (challenges should have good distribution)
        combined = "".join(challenges)
        unique_chars = set(combined)
        assert len(unique_chars) > 20, "Challenges should have good character distribution"

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

    def test_security_challenge_entropy(self):
        """Test challenge entropy and randomness."""
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
    async def test_security_credential_isolation(self):
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


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
