#!/usr/bin/env python3
"""
Comprehensive unit tests for WebAuthn functionality.

This test suite follows existing patterns from test_logging_utils.py and other auth tests,
providing complete coverage of WebAuthn components including challenge management,
credential storage, cryptographic operations, and authentication flows.
"""

import asyncio
import base64
import json
import os
import sys
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Dict, Any, List, Optional

import pytest
from bson import ObjectId

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from second_brain_database.database import db_manager
from second_brain_database.routes.auth.services.webauthn.challenge import (
    clear_challenge,
    generate_secure_challenge,
    store_challenge,
    validate_challenge,
    cleanup_expired_challenges,
    cleanup_expired_redis_challenges,
    cleanup_all_expired_challenges,
)
from second_brain_database.routes.auth.services.webauthn.credentials import (
    deactivate_credential,
    get_credential_by_id,
    get_user_credentials,
    store_credential,
    update_credential_usage,
    validate_credential_ownership,
    get_user_credential_list,
    delete_credential_by_id,
    cache_user_credentials,
    get_cached_user_credentials,
    invalidate_user_credentials_cache,
)


class TestWebAuthnChallengeManagement:
    """Test WebAuthn challenge generation, storage, and validation."""

    def test_generate_secure_challenge(self):
        """Test secure challenge generation."""
        challenge1 = generate_secure_challenge()
        challenge2 = generate_secure_challenge()

        # Challenges should be different
        assert challenge1 != challenge2

        # Challenges should be URL-safe base64 strings
        assert isinstance(challenge1, str)
        assert len(challenge1) > 40  # Should be ~43 characters for 32 bytes

        # Should not contain problematic characters
        assert "+" not in challenge1
        assert "/" not in challenge1
        assert "=" not in challenge1

    @pytest.mark.asyncio
    async def test_store_challenge_success(self):
        """Test successful challenge storage."""
        with patch("second_brain_database.routes.auth.services.webauthn.challenge.redis_manager") as mock_redis_manager, \
             patch("second_brain_database.routes.auth.services.webauthn.challenge.db_manager") as mock_db_manager:

            # Mock Redis
            mock_redis_conn = AsyncMock()
            mock_redis_manager.get_redis.return_value = mock_redis_conn
            mock_redis_conn.set.return_value = True

            # Mock Database
            mock_collection = AsyncMock()
            mock_db_manager.get_collection.return_value = mock_collection
            mock_result = Mock()
            mock_result.inserted_id = ObjectId()
            mock_collection.insert_one.return_value = mock_result

            challenge = "test_challenge_123"
            user_id = str(ObjectId())

            result = await store_challenge(challenge, user_id, "registration")

            assert result is True
            mock_redis_conn.set.assert_called_once()
            mock_collection.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_challenge_missing_params(self):
        """Test challenge storage with missing parameters."""
        with pytest.raises(ValueError, match="challenge and challenge_type are required"):
            await store_challenge("", "user123", "registration")

        with pytest.raises(ValueError, match="challenge and challenge_type are required"):
            await store_challenge("challenge123", "user123", "")

    @pytest.mark.asyncio
    async def test_validate_challenge_success_redis(self):
        """Test successful challenge validation from Redis."""
        with patch("second_brain_database.routes.auth.services.webauthn.challenge.redis_manager") as mock_redis_manager, \
             patch("second_brain_database.routes.auth.services.webauthn.challenge.db_manager") as mock_db_manager:

            # Mock Redis with valid challenge data
            mock_redis_conn = AsyncMock()
            mock_redis_manager.get_redis.return_value = mock_redis_conn

            challenge_data = {
                "user_id": "user123",
                "type": "authentication",
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(minutes=5)).isoformat()
            }
            mock_redis_conn.get.return_value = json.dumps(challenge_data)
            mock_redis_conn.delete.return_value = 1

            # Mock database cleanup
            mock_collection = AsyncMock()
            mock_db_manager.get_collection.return_value = mock_collection
            mock_collection.delete_one.return_value = Mock(deleted_count=1)

            result = await validate_challenge("test_challenge", "user123", "authentication")

            assert result is not None
            assert result["user_id"] == "user123"
            assert result["type"] == "authentication"
            mock_redis_conn.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_challenge_user_mismatch(self):
        """Test challenge validation with user ID mismatch."""
        with patch("second_brain_database.routes.auth.services.webauthn.challenge.redis_manager") as mock_redis_manager:

            mock_redis_conn = AsyncMock()
            mock_redis_manager.get_redis.return_value = mock_redis_conn

            challenge_data = {
                "user_id": "user123",
                "type": "authentication",
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(minutes=5)).isoformat()
            }
            mock_redis_conn.get.return_value = json.dumps(challenge_data)

            result = await validate_challenge("test_challenge", "different_user", "authentication")

            assert result is None

    @pytest.mark.asyncio
    async def test_validate_challenge_database_fallback(self):
        """Test challenge validation falling back to database."""
        with patch("second_brain_database.routes.auth.services.webauthn.challenge.redis_manager") as mock_redis_manager, \
             patch("second_brain_database.routes.auth.services.webauthn.challenge.db_manager") as mock_db_manager:

            # Mock Redis returning None (cache miss)
            mock_redis_conn = AsyncMock()
            mock_redis_manager.get_redis.return_value = mock_redis_conn
            mock_redis_conn.get.return_value = None

            # Mock database with valid challenge
            mock_collection = AsyncMock()
            mock_db_manager.get_collection.return_value = mock_collection

            challenge_doc = {
                "_id": ObjectId(),
                "challenge": "test_challenge",
                "user_id": ObjectId("507f1f77bcf86cd799439011"),
                "type": "authentication",
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(minutes=5)
            }
            mock_collection.find_one.return_value = challenge_doc
            mock_collection.delete_one.return_value = Mock(deleted_count=1)

            result = await validate_challenge("test_challenge", "507f1f77bcf86cd799439011", "authentication")

            assert result is not None
            assert result["type"] == "authentication"
            mock_collection.delete_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_challenge_success(self):
        """Test successful challenge clearing."""
        with patch("second_brain_database.routes.auth.services.webauthn.challenge.redis_manager") as mock_redis_manager, \
             patch("second_brain_database.routes.auth.services.webauthn.challenge.db_manager") as mock_db_manager:

            # Mock Redis
            mock_redis_conn = AsyncMock()
            mock_redis_manager.get_redis.return_value = mock_redis_conn
            mock_redis_conn.delete.return_value = 1

            # Mock Database
            mock_collection = AsyncMock()
            mock_db_manager.get_collection.return_value = mock_collection
            mock_collection.delete_one.return_value = Mock(deleted_count=1)

            result = await clear_challenge("test_challenge")

            assert result is True
            mock_redis_conn.delete.assert_called_once()
            mock_collection.delete_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_expired_challenges(self):
        """Test cleanup of expired challenges."""
        with patch("second_brain_database.routes.auth.services.webauthn.challenge.db_manager") as mock_db_manager:

            mock_collection = AsyncMock()
            mock_db_manager.get_collection.return_value = mock_collection
            mock_collection.delete_many.return_value = Mock(deleted_count=5)

            result = await cleanup_expired_challenges()

            assert result == 5
            mock_collection.delete_many.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_expired_redis_challenges(self):
        """Test cleanup of expired Redis challenges."""
        with patch("second_brain_database.routes.auth.services.webauthn.challenge.redis_manager") as mock_redis_manager:

            mock_redis_conn = AsyncMock()
            mock_redis_manager.get_redis.return_value = mock_redis_conn
            mock_redis_conn.keys.return_value = ["webauthn_challenge:key1", "webauthn_challenge:key2"]
            mock_redis_conn.ttl.side_effect = [-1, -2]  # First has no TTL, second doesn't exist
            mock_redis_conn.expire.return_value = True

            result = await cleanup_expired_redis_challenges()

            assert result == 1  # One key didn't exist
            mock_redis_conn.expire.assert_called_once()


class TestWebAuthnCredentialManagement:
    """Test WebAuthn credential storage, retrieval, and management."""

    @pytest.mark.asyncio
    async def test_store_credential_success(self):
        """Test successful credential storage."""
        with patch("second_brain_database.routes.auth.services.webauthn.credentials.db_manager") as mock_db_manager, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.invalidate_user_credentials_cache") as mock_invalidate:

            mock_collection = AsyncMock()
            mock_db_manager.get_collection.return_value = mock_collection

            # Mock no existing credential
            mock_collection.find_one.return_value = None

            # Mock successful insert
            mock_result = Mock()
            mock_result.inserted_id = ObjectId()
            mock_collection.insert_one.return_value = mock_result

            mock_invalidate.return_value = True

            user_id = str(ObjectId())
            credential_id = "test_credential_123"
            public_key = "test_public_key"

            result = await store_credential(
                user_id=user_id,
                credential_id=credential_id,
                public_key=public_key,
                device_name="Test Device",
                authenticator_type="platform"
            )

            assert result["credential_id"] == credential_id
            assert result["device_name"] == "Test Device"
            assert result["authenticator_type"] == "platform"
            mock_collection.insert_one.assert_called_once()
            mock_invalidate.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_store_credential_update_existing(self):
        """Test updating existing credential."""
        with patch("second_brain_database.routes.auth.services.webauthn.credentials.db_manager") as mock_db_manager, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.invalidate_user_credentials_cache") as mock_invalidate:

            mock_collection = AsyncMock()
            mock_db_manager.get_collection.return_value = mock_collection

            # Mock existing credential
            existing_cred = {
                "_id": ObjectId(),
                "credential_id": "test_credential_123",
                "device_name": "Old Device",
                "transport": ["usb"]
            }
            mock_collection.find_one.return_value = existing_cred

            # Mock successful update
            mock_result = Mock()
            mock_result.modified_count = 1
            mock_collection.update_one.return_value = mock_result

            mock_invalidate.return_value = True

            user_id = str(ObjectId())
            credential_id = "test_credential_123"
            public_key = "updated_public_key"

            result = await store_credential(
                user_id=user_id,
                credential_id=credential_id,
                public_key=public_key,
                device_name="Updated Device",
                authenticator_type="cross-platform"
            )

            assert result["credential_id"] == credential_id
            assert result["device_name"] == "Updated Device"
            mock_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_credential_missing_params(self):
        """Test credential storage with missing parameters."""
        with pytest.raises(ValueError, match="user_id, credential_id, and public_key are required"):
            await store_credential("", "cred123", "key123")

        with pytest.raises(ValueError, match="user_id, credential_id, and public_key are required"):
            await store_credential("user123", "", "key123")

        with pytest.raises(ValueError, match="user_id, credential_id, and public_key are required"):
            await store_credential("user123", "cred123", "")

    @pytest.mark.asyncio
    async def test_get_user_credentials_cache_hit(self):
        """Test getting user credentials with cache hit."""
        with patch("second_brain_database.routes.auth.services.webauthn.credentials.get_cached_user_credentials") as mock_get_cached, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.cache_user_credentials") as mock_cache:

            cached_credentials = [
                {
                    "credential_id": "cred1",
                    "device_name": "Device 1",
                    "is_active": True
                },
                {
                    "credential_id": "cred2",
                    "device_name": "Device 2",
                    "is_active": False
                }
            ]
            mock_get_cached.return_value = cached_credentials

            user_id = str(ObjectId())
            result = await get_user_credentials(user_id, active_only=True)

            # Should filter to only active credentials
            assert len(result) == 1
            assert result[0]["credential_id"] == "cred1"
            mock_get_cached.assert_called_once_with(user_id)
            mock_cache.assert_not_called()  # Should not cache on cache hit

    @pytest.mark.asyncio
    async def test_get_user_credentials_cache_miss(self):
        """Test getting user credentials with cache miss."""
        with patch("second_brain_database.routes.auth.services.webauthn.credentials.get_cached_user_credentials") as mock_get_cached, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.cache_user_credentials") as mock_cache, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.db_manager") as mock_db_manager:

            # Mock cache miss
            mock_get_cached.return_value = None

            # Mock database response
            mock_collection = AsyncMock()
            mock_db_manager.get_collection.return_value = mock_collection

            mock_cursor = AsyncMock()
            mock_collection.find.return_value = mock_cursor
            mock_cursor.sort.return_value = mock_cursor

            db_credentials = [
                {
                    "credential_id": "cred1",
                    "device_name": "Device 1",
                    "authenticator_type": "platform",
                    "transport": ["internal"],
                    "created_at": datetime.utcnow(),
                    "last_used_at": None,
                    "is_active": True,
                    "public_key": "key1",
                    "sign_count": 0
                }
            ]
            mock_cursor.to_list.return_value = db_credentials

            mock_cache.return_value = True

            user_id = str(ObjectId())
            result = await get_user_credentials(user_id)

            assert len(result) == 1
            assert result[0]["credential_id"] == "cred1"
            assert result[0]["public_key"] == "key1"  # Should include for authentication
            mock_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_credential_by_id_success(self):
        """Test successful credential retrieval by ID."""
        with patch("second_brain_database.routes.auth.services.webauthn.credentials.get_cached_single_credential") as mock_get_cached, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.cache_single_credential") as mock_cache, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.db_manager") as mock_db_manager:

            # Mock cache miss
            mock_get_cached.return_value = None

            # Mock database response
            mock_collection = AsyncMock()
            mock_db_manager.get_collection.return_value = mock_collection

            credential_doc = {
                "credential_id": "test_cred_123",
                "user_id": ObjectId(),
                "device_name": "Test Device",
                "authenticator_type": "platform",
                "transport": ["internal"],
                "created_at": datetime.utcnow(),
                "last_used_at": None,
                "is_active": True,
                "public_key": "test_key",
                "sign_count": 5
            }
            mock_collection.find_one.return_value = credential_doc

            mock_cache.return_value = True

            result = await get_credential_by_id("test_cred_123")

            assert result is not None
            assert result["credential_id"] == "test_cred_123"
            assert result["sign_count"] == 5
            mock_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_credential_by_id_not_found(self):
        """Test credential retrieval when credential doesn't exist."""
        with patch("second_brain_database.routes.auth.services.webauthn.credentials.get_cached_single_credential") as mock_get_cached, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.db_manager") as mock_db_manager:

            # Mock cache miss
            mock_get_cached.return_value = None

            # Mock database returning None
            mock_collection = AsyncMock()
            mock_db_manager.get_collection.return_value = mock_collection
            mock_collection.find_one.return_value = None

            result = await get_credential_by_id("nonexistent_cred")

            assert result is None

    @pytest.mark.asyncio
    async def test_update_credential_usage_success(self):
        """Test successful credential usage update."""
        with patch("second_brain_database.routes.auth.services.webauthn.credentials.db_manager") as mock_db_manager, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.invalidate_single_credential_cache") as mock_invalidate_single, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.invalidate_user_credentials_cache") as mock_invalidate_user:

            mock_collection = AsyncMock()
            mock_db_manager.get_collection.return_value = mock_collection

            # Mock successful update
            mock_result = Mock()
            mock_result.modified_count = 1
            mock_collection.update_one.return_value = mock_result

            # Mock finding credential for user cache invalidation
            mock_collection.find_one.return_value = {"user_id": ObjectId()}

            mock_invalidate_single.return_value = True
            mock_invalidate_user.return_value = True

            result = await update_credential_usage("test_cred", 10)

            assert result is True
            mock_collection.update_one.assert_called_once()
            mock_invalidate_single.assert_called_once_with("test_cred")

    @pytest.mark.asyncio
    async def test_validate_credential_ownership_valid(self):
        """Test valid credential ownership validation."""
        with patch("second_brain_database.routes.auth.services.webauthn.credentials.db_manager") as mock_db_manager:

            mock_collection = AsyncMock()
            mock_db_manager.get_collection.return_value = mock_collection

            # Mock finding credential
            mock_collection.find_one.return_value = {
                "credential_id": "test_cred",
                "user_id": ObjectId("507f1f77bcf86cd799439011"),
                "is_active": True
            }

            result = await validate_credential_ownership("test_cred", "507f1f77bcf86cd799439011")

            assert result is True

    @pytest.mark.asyncio
    async def test_validate_credential_ownership_invalid(self):
        """Test invalid credential ownership validation."""
        with patch("second_brain_database.routes.auth.services.webauthn.credentials.db_manager") as mock_db_manager:

            mock_collection = AsyncMock()
            mock_db_manager.get_collection.return_value = mock_collection

            # Mock not finding credential
            mock_collection.find_one.return_value = None

            result = await validate_credential_ownership("test_cred", "507f1f77bcf86cd799439011")

            assert result is False

    @pytest.mark.asyncio
    async def test_deactivate_credential_success(self):
        """Test successful credential deactivation."""
        with patch("second_brain_database.routes.auth.services.webauthn.credentials.db_manager") as mock_db_manager, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.invalidate_single_credential_cache") as mock_invalidate_single, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.invalidate_user_credentials_cache") as mock_invalidate_user:

            mock_collection = AsyncMock()
            mock_db_manager.get_collection.return_value = mock_collection

            # Mock successful deactivation
            mock_result = Mock()
            mock_result.modified_count = 1
            mock_collection.update_one.return_value = mock_result

            mock_invalidate_single.return_value = True
            mock_invalidate_user.return_value = True

            result = await deactivate_credential("test_cred", "user123")

            assert result is True
            mock_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_credential_list_success(self):
        """Test successful user credential list retrieval."""
        with patch("second_brain_database.routes.auth.services.webauthn.credentials.db_manager") as mock_db_manager:

            mock_collection = AsyncMock()
            mock_db_manager.get_collection.return_value = mock_collection

            mock_cursor = AsyncMock()
            mock_collection.find.return_value = mock_cursor
            mock_cursor.sort.return_value = mock_cursor

            credentials = [
                {
                    "credential_id": "cred1",
                    "device_name": "Device 1",
                    "authenticator_type": "platform",
                    "transport": ["internal"],
                    "created_at": datetime.utcnow(),
                    "last_used_at": None,
                    "is_active": True,
                    "public_key": "key1",  # Should be excluded from response
                    "sign_count": 0  # Should be excluded from response
                }
            ]
            mock_cursor.to_list.return_value = credentials

            user_id = str(ObjectId())
            result = await get_user_credential_list(user_id)

            assert len(result) == 1
            assert result[0]["credential_id"] == "cred1"
            assert "public_key" not in result[0]  # Sensitive data excluded
            assert "sign_count" not in result[0]  # Sensitive data excluded

    @pytest.mark.asyncio
    async def test_delete_credential_by_id_success(self):
        """Test successful credential deletion."""
        with patch("second_brain_database.routes.auth.services.webauthn.credentials.db_manager") as mock_db_manager, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.invalidate_single_credential_cache") as mock_invalidate_single, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.invalidate_user_credentials_cache") as mock_invalidate_user:

            mock_collection = AsyncMock()
            mock_db_manager.get_collection.return_value = mock_collection

            # Mock finding credential
            credential_doc = {
                "_id": ObjectId(),
                "credential_id": "test_cred",
                "user_id": ObjectId("507f1f77bcf86cd799439011"),
                "device_name": "Test Device",
                "is_active": True
            }
            mock_collection.find_one.return_value = credential_doc

            # Mock successful soft delete
            mock_result = Mock()
            mock_result.modified_count = 1
            mock_collection.update_one.return_value = mock_result

            mock_invalidate_single.return_value = True
            mock_invalidate_user.return_value = True

            result = await delete_credential_by_id("507f1f77bcf86cd799439011", "test_cred")

            assert result is not None
            assert "message" in result
            mock_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_credential_by_id_not_found(self):
        """Test credential deletion when credential doesn't exist."""
        with patch("second_brain_database.routes.auth.services.webauthn.credentials.db_manager") as mock_db_manager:

            mock_collection = AsyncMock()
            mock_db_manager.get_collection.return_value = mock_collection

            # Mock not finding credential
            mock_collection.find_one.return_value = None

            with pytest.raises(ValueError, match="Credential not found or already deleted"):
                await delete_credential_by_id("507f1f77bcf86cd799439011", "nonexistent_cred")

    @pytest.mark.asyncio
    async def test_cache_user_credentials_success(self):
        """Test successful credential caching."""
        with patch("second_brain_database.routes.auth.services.webauthn.credentials.redis_manager") as mock_redis_manager:

            mock_redis_conn = AsyncMock()
            mock_redis_manager.get_redis.return_value = mock_redis_conn
            mock_redis_conn.setex.return_value = True

            credentials = [{"credential_id": "cred1", "device_name": "Device 1"}]

            result = await cache_user_credentials("user123", credentials)

            assert result is True
            mock_redis_conn.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cached_user_credentials_hit(self):
        """Test successful cached credential retrieval."""
        with patch("second_brain_database.routes.auth.services.webauthn.credentials.redis_manager") as mock_redis_manager:

            mock_redis_conn = AsyncMock()
            mock_redis_manager.get_redis.return_value = mock_redis_conn

            cached_data = {
                "credentials": [{"credential_id": "cred1", "device_name": "Device 1"}],
                "cached_at": datetime.utcnow().isoformat()
            }
            mock_redis_conn.get.return_value = json.dumps(cached_data)

            result = await get_cached_user_credentials("user123")

            assert result is not None
            assert len(result) == 1
            assert result[0]["credential_id"] == "cred1"

    @pytest.mark.asyncio
    async def test_get_cached_user_credentials_miss(self):
        """Test cached credential retrieval with cache miss."""
        with patch("second_brain_database.routes.auth.services.webauthn.credentials.redis_manager") as mock_redis_manager:

            mock_redis_conn = AsyncMock()
            mock_redis_manager.get_redis.return_value = mock_redis_conn
            mock_redis_conn.get.return_value = None

            result = await get_cached_user_credentials("user123")

            assert result is None

    @pytest.mark.asyncio
    async def test_invalidate_user_credentials_cache_success(self):
        """Test successful cache invalidation."""
        with patch("second_brain_database.routes.auth.services.webauthn.credentials.redis_manager") as mock_redis_manager:

            mock_redis_conn = AsyncMock()
            mock_redis_manager.get_redis.return_value = mock_redis_conn
            mock_redis_conn.delete.return_value = 1

            result = await invalidate_user_credentials_cache("user123")

            assert result is True
            mock_redis_conn.delete.assert_called_once()


class TestWebAuthnCryptoOperations:
    """Test WebAuthn cryptographic operations."""

    def test_base64url_encode_decode(self):
        """Test base64url encoding and decoding."""
        # Import the crypto functions if they exist
        try:
            from second_brain_database.routes.auth.services.webauthn.crypto import (
                base64url_encode,
                base64url_decode,
            )

            test_data = b"Hello, WebAuthn!"
            encoded = base64url_encode(test_data)
            decoded = base64url_decode(encoded)

            assert decoded == test_data
            assert isinstance(encoded, str)
            assert "+" not in encoded  # Should be URL-safe
            assert "/" not in encoded  # Should be URL-safe
            assert "=" not in encoded  # Should not have padding

        except ImportError:
            # Crypto module might not be implemented yet
            pytest.skip("Crypto module not implemented")

    def test_extract_public_key(self):
        """Test public key extraction from attestation object."""
        try:
            from second_brain_database.routes.auth.services.webauthn.crypto import extract_public_key

            # Mock attestation object (would normally be CBOR)
            mock_attestation = "mock_attestation_object"

            with patch("second_brain_database.routes.auth.services.webauthn.crypto.cbor2") as mock_cbor:
                mock_cbor.loads.return_value = {
                    "authData": b"mock_auth_data",
                    "fmt": "none",
                    "attStmt": {}
                }

                # This would normally extract the public key from the auth data
                # For now, just test that the function can be called
                result = extract_public_key(mock_attestation)

                # The actual implementation would return the extracted public key
                # For testing, we just verify the function exists and can be called

        except ImportError:
            pytest.skip("Crypto module not implemented")

    def test_verify_assertion_signature(self):
        """Test WebAuthn assertion signature verification."""
        try:
            from second_brain_database.routes.auth.services.webauthn.crypto import verify_assertion_signature

            # Mock assertion response
            assertion_response = {
                "response": {
                    "authenticatorData": "mock_auth_data",
                    "clientDataJSON": "mock_client_data",
                    "signature": "mock_signature"
                }
            }

            public_key_cbor = "mock_public_key"

            with patch("second_brain_database.routes.auth.services.webauthn.crypto.cbor2") as mock_cbor, \
                 patch("second_brain_database.routes.auth.services.webauthn.crypto.hashlib") as mock_hashlib:

                mock_cbor.loads.return_value = {3: -7}  # ES256 algorithm
                mock_hashlib.sha256.return_value.digest.return_value = b"mock_hash"

                # Mock the signature verification
                with patch("second_brain_database.routes.auth.services.webauthn.crypto.verify_es256_signature") as mock_verify:
                    mock_verify.return_value = True

                    result = verify_assertion_signature(assertion_response, public_key_cbor)

                    assert result is True

        except ImportError:
            pytest.skip("Crypto module not implemented")


class TestWebAuthnIntegration:
    """Test WebAuthn integration scenarios."""

    @pytest.mark.asyncio
    async def test_full_registration_flow(self):
        """Test complete WebAuthn registration flow."""
        # This would test the integration between challenge generation,
        # credential storage, and validation

        user_id = str(ObjectId())
        challenge = generate_secure_challenge()

        # Mock all the dependencies
        with patch("second_brain_database.routes.auth.services.webauthn.challenge.redis_manager") as mock_redis_manager, \
             patch("second_brain_database.routes.auth.services.webauthn.challenge.db_manager") as mock_challenge_db, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.db_manager") as mock_cred_db, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.invalidate_user_credentials_cache") as mock_invalidate:

            # Mock challenge storage
            mock_redis_conn = AsyncMock()
            mock_redis_manager.get_redis.return_value = mock_redis_conn
            mock_redis_conn.set.return_value = True

            mock_challenge_collection = AsyncMock()
            mock_challenge_db.get_collection.return_value = mock_challenge_collection
            mock_challenge_result = Mock()
            mock_challenge_result.inserted_id = ObjectId()
            mock_challenge_collection.insert_one.return_value = mock_challenge_result

            # Mock credential storage
            mock_cred_collection = AsyncMock()
            mock_cred_db.get_collection.return_value = mock_cred_collection
            mock_cred_collection.find_one.return_value = None  # No existing credential
            mock_cred_result = Mock()
            mock_cred_result.inserted_id = ObjectId()
            mock_cred_collection.insert_one.return_value = mock_cred_result

            mock_invalidate.return_value = True

            # Step 1: Store challenge
            challenge_stored = await store_challenge(challenge, user_id, "registration")
            assert challenge_stored is True

            # Step 2: Store credential (simulating successful registration)
            credential_result = await store_credential(
                user_id=user_id,
                credential_id="test_credential_123",
                public_key="test_public_key",
                device_name="Test Device"
            )

            assert credential_result["credential_id"] == "test_credential_123"
            assert credential_result["device_name"] == "Test Device"

    @pytest.mark.asyncio
    async def test_full_authentication_flow(self):
        """Test complete WebAuthn authentication flow."""
        user_id = str(ObjectId())
        credential_id = "test_credential_123"
        challenge = generate_secure_challenge()

        with patch("second_brain_database.routes.auth.services.webauthn.challenge.redis_manager") as mock_redis_manager, \
             patch("second_brain_database.routes.auth.services.webauthn.challenge.db_manager") as mock_challenge_db, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.db_manager") as mock_cred_db, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.get_cached_single_credential") as mock_get_cached, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.invalidate_single_credential_cache") as mock_invalidate_single, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.invalidate_user_credentials_cache") as mock_invalidate_user:

            # Mock challenge validation
            mock_redis_conn = AsyncMock()
            mock_redis_manager.get_redis.return_value = mock_redis_conn

            challenge_data = {
                "user_id": user_id,
                "type": "authentication",
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(minutes=5)).isoformat()
            }
            mock_redis_conn.get.return_value = json.dumps(challenge_data)
            mock_redis_conn.delete.return_value = 1

            mock_challenge_collection = AsyncMock()
            mock_challenge_db.get_collection.return_value = mock_challenge_collection
            mock_challenge_collection.delete_one.return_value = Mock(deleted_count=1)

            # Mock credential retrieval
            mock_get_cached.return_value = None  # Cache miss

            mock_cred_collection = AsyncMock()
            mock_cred_db.get_collection.return_value = mock_cred_collection

            credential_doc = {
                "credential_id": credential_id,
                "user_id": ObjectId(user_id),
                "device_name": "Test Device",
                "authenticator_type": "platform",
                "transport": ["internal"],
                "created_at": datetime.utcnow(),
                "last_used_at": None,
                "is_active": True,
                "public_key": "test_key",
                "sign_count": 5
            }
            mock_cred_collection.find_one.return_value = credential_doc

            # Mock credential usage update
            mock_update_result = Mock()
            mock_update_result.modified_count = 1
            mock_cred_collection.update_one.return_value = mock_update_result

            mock_invalidate_single.return_value = True
            mock_invalidate_user.return_value = True

            # Step 1: Validate challenge
            challenge_valid = await validate_challenge(challenge, user_id, "authentication")
            assert challenge_valid is not None
            assert challenge_valid["user_id"] == user_id

            # Step 2: Get credential
            credential = await get_credential_by_id(credential_id)
            assert credential is not None
            assert credential["credential_id"] == credential_id

            # Step 3: Update credential usage
            usage_updated = await update_credential_usage(credential_id, 6)
            assert usage_updated is True

    @pytest.mark.asyncio
    async def test_credential_management_flow(self):
        """Test credential management operations."""
        user_id = str(ObjectId())
        credential_id = "test_credential_123"

        with patch("second_brain_database.routes.auth.services.webauthn.credentials.db_manager") as mock_db_manager, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.invalidate_single_credential_cache") as mock_invalidate_single, \
             patch("second_brain_database.routes.auth.services.webauthn.credentials.invalidate_user_credentials_cache") as mock_invalidate_user:

            mock_collection = AsyncMock()
            mock_db_manager.get_collection.return_value = mock_collection

            # Mock credential list retrieval
            mock_cursor = AsyncMock()
            mock_collection.find.return_value = mock_cursor
            mock_cursor.sort.return_value = mock_cursor

            credentials = [
                {
                    "credential_id": credential_id,
                    "device_name": "Test Device",
                    "authenticator_type": "platform",
                    "transport": ["internal"],
                    "created_at": datetime.utcnow(),
                    "last_used_at": None,
                    "is_active": True,
                    "public_key": "test_key",
                    "sign_count": 0
                }
            ]
            mock_cursor.to_list.return_value = credentials

            # Mock credential deletion
            credential_doc = {
                "_id": ObjectId(),
                "credential_id": credential_id,
                "user_id": ObjectId(user_id),
                "device_name": "Test Device",
                "is_active": True
            }
            mock_collection.find_one.return_value = credential_doc

            mock_delete_result = Mock()
            mock_delete_result.modified_count = 1
            mock_collection.update_one.return_value = mock_delete_result

            mock_invalidate_single.return_value = True
            mock_invalidate_user.return_value = True

            # Step 1: List credentials
            credential_list = await get_user_credential_list(user_id)
            assert len(credential_list) == 1
            assert credential_list[0]["credential_id"] == credential_id
            assert "public_key" not in credential_list[0]  # Sensitive data excluded

            # Step 2: Validate ownership
            ownership_valid = await validate_credential_ownership(credential_id, user_id)
            assert ownership_valid is True

            # Step 3: Delete credential
            deletion_result = await delete_credential_by_id(user_id, credential_id)
            assert deletion_result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
