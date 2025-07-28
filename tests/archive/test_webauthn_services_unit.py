#!/usr/bin/env python3
"""
Unit tests for WebAuthn authentication and registration services.

This test suite focuses on testing the higher-level WebAuthn services that
orchestrate the challenge, credential, and crypto operations.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Dict, Any

import pytest
from bson import ObjectId

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestWebAuthnRegistrationService:
    """Test WebAuthn registration service functionality."""

    @pytest.mark.asyncio
    async def test_begin_registration_success(self):
        """Test successful registration initiation."""
        try:
            from second_brain_database.routes.auth.services.webauthn.registration import begin_registration
            
            user = {
                "_id": ObjectId(),
                "username": "testuser",
                "email": "test@example.com"
            }
            
            with patch("second_brain_database.routes.auth.services.webauthn.registration.generate_secure_challenge") as mock_gen_challenge, \
                 patch("second_brain_database.routes.auth.services.webauthn.registration.store_challenge") as mock_store_challenge, \
                 patch("second_brain_database.routes.auth.services.webauthn.registration.get_user_credentials") as mock_get_creds:
                
                mock_gen_challenge.return_value = "test_challenge_123"
                mock_store_challenge.return_value = True
                mock_get_creds.return_value = []  # No existing credentials
                
                result = await begin_registration(user, "Test Device")
                
                assert "challenge" in result
                assert "rp" in result
                assert "user" in result
                assert "pubKeyCredParams" in result
                assert result["challenge"] == "test_challenge_123"
                assert result["user"]["name"] == "testuser"
                
                mock_store_challenge.assert_called_once_with(
                    "test_challenge_123", 
                    str(user["_id"]), 
                    "registration"
                )
                
        except ImportError:
            pytest.skip("Registration service not implemented")

    @pytest.mark.asyncio
    async def test_begin_registration_with_existing_credentials(self):
        """Test registration initiation with existing credentials to exclude."""
        try:
            from second_brain_database.routes.auth.services.webauthn.registration import begin_registration
            
            user = {
                "_id": ObjectId(),
                "username": "testuser",
                "email": "test@example.com"
            }
            
            existing_credentials = [
                {"credential_id": "existing_cred_1"},
                {"credential_id": "existing_cred_2"}
            ]
            
            with patch("second_brain_database.routes.auth.services.webauthn.registration.generate_secure_challenge") as mock_gen_challenge, \
                 patch("second_brain_database.routes.auth.services.webauthn.registration.store_challenge") as mock_store_challenge, \
                 patch("second_brain_database.routes.auth.services.webauthn.registration.get_user_credentials") as mock_get_creds:
                
                mock_gen_challenge.return_value = "test_challenge_123"
                mock_store_challenge.return_value = True
                mock_get_creds.return_value = existing_credentials
                
                result = await begin_registration(user, "Test Device")
                
                assert "excludeCredentials" in result
                assert len(result["excludeCredentials"]) == 2
                assert result["excludeCredentials"][0]["id"] == "existing_cred_1"
                
        except ImportError:
            pytest.skip("Registration service not implemented")

    @pytest.mark.asyncio
    async def test_complete_registration_success(self):
        """Test successful registration completion."""
        try:
            from second_brain_database.routes.auth.services.webauthn.registration import complete_registration
            
            user = {
                "_id": ObjectId(),
                "username": "testuser",
                "email": "test@example.com"
            }
            
            credential_response = {
                "id": "test_credential_id",
                "rawId": "test_raw_id",
                "response": {
                    "attestationObject": "test_attestation",
                    "clientDataJSON": "test_client_data"
                },
                "type": "public-key"
            }
            
            with patch("second_brain_database.routes.auth.services.webauthn.registration.validate_challenge") as mock_validate, \
                 patch("second_brain_database.routes.auth.services.webauthn.registration.extract_public_key") as mock_extract_key, \
                 patch("second_brain_database.routes.auth.services.webauthn.registration.store_credential") as mock_store_cred:
                
                # Mock challenge validation
                mock_validate.return_value = {
                    "user_id": str(user["_id"]),
                    "type": "registration",
                    "created_at": datetime.utcnow().isoformat()
                }
                
                # Mock public key extraction
                mock_extract_key.return_value = "extracted_public_key"
                
                # Mock credential storage
                mock_store_cred.return_value = {
                    "credential_id": "test_credential_id",
                    "device_name": "Test Device",
                    "authenticator_type": "platform",
                    "created_at": datetime.utcnow()
                }
                
                result = await complete_registration(user, credential_response, "Test Device")
                
                assert result["credential_id"] == "test_credential_id"
                assert result["device_name"] == "Test Device"
                assert "message" in result
                
                mock_store_cred.assert_called_once()
                
        except ImportError:
            pytest.skip("Registration service not implemented")

    @pytest.mark.asyncio
    async def test_complete_registration_invalid_challenge(self):
        """Test registration completion with invalid challenge."""
        try:
            from second_brain_database.routes.auth.services.webauthn.registration import complete_registration
            from fastapi import HTTPException
            
            user = {
                "_id": ObjectId(),
                "username": "testuser",
                "email": "test@example.com"
            }
            
            credential_response = {
                "id": "test_credential_id",
                "response": {
                    "attestationObject": "test_attestation",
                    "clientDataJSON": "test_client_data"
                }
            }
            
            with patch("second_brain_database.routes.auth.services.webauthn.registration.validate_challenge") as mock_validate:
                
                # Mock invalid challenge
                mock_validate.return_value = None
                
                with pytest.raises(HTTPException) as exc_info:
                    await complete_registration(user, credential_response, "Test Device")
                
                assert exc_info.value.status_code == 400
                assert "Invalid or expired challenge" in str(exc_info.value.detail)
                
        except ImportError:
            pytest.skip("Registration service not implemented")


class TestWebAuthnAuthenticationService:
    """Test WebAuthn authentication service functionality."""

    @pytest.mark.asyncio
    async def test_begin_authentication_success(self):
        """Test successful authentication initiation."""
        try:
            from second_brain_database.routes.auth.services.webauthn.authentication import begin_authentication
            
            with patch("second_brain_database.routes.auth.services.webauthn.authentication.db_manager") as mock_db_manager, \
                 patch("second_brain_database.routes.auth.services.webauthn.authentication.generate_secure_challenge") as mock_gen_challenge, \
                 patch("second_brain_database.routes.auth.services.webauthn.authentication.store_challenge") as mock_store_challenge, \
                 patch("second_brain_database.routes.auth.services.webauthn.authentication.get_user_credentials") as mock_get_creds:
                
                # Mock user lookup
                mock_collection = AsyncMock()
                mock_db_manager.get_collection.return_value = mock_collection
                mock_collection.find_one.return_value = {
                    "_id": ObjectId(),
                    "username": "testuser",
                    "email": "test@example.com",
                    "is_verified": True,
                    "is_active": True
                }
                
                # Mock challenge generation and storage
                mock_gen_challenge.return_value = "test_auth_challenge"
                mock_store_challenge.return_value = True
                
                # Mock user credentials
                mock_get_creds.return_value = [
                    {
                        "credential_id": "cred1",
                        "transport": ["internal"]
                    },
                    {
                        "credential_id": "cred2", 
                        "transport": ["usb", "nfc"]
                    }
                ]
                
                result = await begin_authentication(username="testuser")
                
                assert "challenge" in result
                assert "allowCredentials" in result
                assert result["challenge"] == "test_auth_challenge"
                assert len(result["allowCredentials"]) == 2
                assert result["allowCredentials"][0]["id"] == "cred1"
                
                mock_store_challenge.assert_called_once_with(
                    "test_auth_challenge",
                    None,  # No user_id for auth challenges
                    "authentication"
                )
                
        except ImportError:
            pytest.skip("Authentication service not implemented")

    @pytest.mark.asyncio
    async def test_begin_authentication_user_not_found(self):
        """Test authentication initiation with non-existent user."""
        try:
            from second_brain_database.routes.auth.services.webauthn.authentication import begin_authentication
            from fastapi import HTTPException
            
            with patch("second_brain_database.routes.auth.services.webauthn.authentication.db_manager") as mock_db_manager:
                
                # Mock user not found
                mock_collection = AsyncMock()
                mock_db_manager.get_collection.return_value = mock_collection
                mock_collection.find_one.return_value = None
                
                with pytest.raises(HTTPException) as exc_info:
                    await begin_authentication(username="nonexistent")
                
                assert exc_info.value.status_code == 401
                assert "Invalid credentials" in str(exc_info.value.detail)
                
        except ImportError:
            pytest.skip("Authentication service not implemented")

    @pytest.mark.asyncio
    async def test_begin_authentication_no_credentials(self):
        """Test authentication initiation with user having no WebAuthn credentials."""
        try:
            from second_brain_database.routes.auth.services.webauthn.authentication import begin_authentication
            from fastapi import HTTPException
            
            with patch("second_brain_database.routes.auth.services.webauthn.authentication.db_manager") as mock_db_manager, \
                 patch("second_brain_database.routes.auth.services.webauthn.authentication.get_user_credentials") as mock_get_creds:
                
                # Mock user lookup
                mock_collection = AsyncMock()
                mock_db_manager.get_collection.return_value = mock_collection
                mock_collection.find_one.return_value = {
                    "_id": ObjectId(),
                    "username": "testuser",
                    "is_verified": True,
                    "is_active": True
                }
                
                # Mock no credentials
                mock_get_creds.return_value = []
                
                with pytest.raises(HTTPException) as exc_info:
                    await begin_authentication(username="testuser")
                
                assert exc_info.value.status_code == 404
                assert "No WebAuthn credentials found" in str(exc_info.value.detail)
                
        except ImportError:
            pytest.skip("Authentication service not implemented")

    @pytest.mark.asyncio
    async def test_complete_authentication_success(self):
        """Test successful authentication completion."""
        try:
            from second_brain_database.routes.auth.services.webauthn.authentication import complete_authentication
            
            with patch("second_brain_database.routes.auth.services.webauthn.authentication.validate_challenge") as mock_validate, \
                 patch("second_brain_database.routes.auth.services.webauthn.authentication.get_credential_by_id") as mock_get_cred, \
                 patch("second_brain_database.routes.auth.services.webauthn.authentication.verify_assertion_signature") as mock_verify_sig, \
                 patch("second_brain_database.routes.auth.services.webauthn.authentication.update_credential_usage") as mock_update_usage, \
                 patch("second_brain_database.routes.auth.services.webauthn.authentication.db_manager") as mock_db_manager, \
                 patch("second_brain_database.routes.auth.services.webauthn.authentication.create_access_token") as mock_create_token:
                
                # Mock challenge validation
                mock_validate.return_value = {
                    "type": "authentication",
                    "created_at": datetime.utcnow().isoformat()
                }
                
                # Mock credential retrieval
                user_id = str(ObjectId())
                mock_get_cred.return_value = {
                    "credential_id": "test_cred",
                    "user_id": user_id,
                    "device_name": "Test Device",
                    "authenticator_type": "platform",
                    "public_key": "test_public_key",
                    "sign_count": 5
                }
                
                # Mock signature verification
                mock_verify_sig.return_value = True
                
                # Mock credential usage update
                mock_update_usage.return_value = True
                
                # Mock user lookup for token creation
                mock_collection = AsyncMock()
                mock_db_manager.get_collection.return_value = mock_collection
                mock_collection.find_one.return_value = {
                    "_id": ObjectId(user_id),
                    "username": "testuser",
                    "email": "test@example.com",
                    "is_verified": True,
                    "role": "user",
                    "client_side_encryption": False
                }
                
                # Mock token creation
                mock_create_token.return_value = "jwt_token_123"
                
                result = await complete_authentication(
                    credential_id="test_cred",
                    authenticator_data="mock_auth_data",
                    client_data_json="mock_client_data",
                    signature="mock_signature",
                    ip_address="192.168.1.1"
                )
                
                assert result["access_token"] == "jwt_token_123"
                assert result["username"] == "testuser"
                assert result["credential_used"]["device_name"] == "Test Device"
                
                mock_update_usage.assert_called_once_with("test_cred", 6)  # sign_count + 1
                
        except ImportError:
            pytest.skip("Authentication service not implemented")

    @pytest.mark.asyncio
    async def test_complete_authentication_invalid_challenge(self):
        """Test authentication completion with invalid challenge."""
        try:
            from second_brain_database.routes.auth.services.webauthn.authentication import complete_authentication
            from fastapi import HTTPException
            
            with patch("second_brain_database.routes.auth.services.webauthn.authentication.validate_challenge") as mock_validate:
                
                # Mock invalid challenge
                mock_validate.return_value = None
                
                with pytest.raises(HTTPException) as exc_info:
                    await complete_authentication(
                        credential_id="test_cred",
                        authenticator_data="mock_auth_data",
                        client_data_json="mock_client_data",
                        signature="mock_signature"
                    )
                
                assert exc_info.value.status_code == 400
                assert "Invalid or expired challenge" in str(exc_info.value.detail)
                
        except ImportError:
            pytest.skip("Authentication service not implemented")

    @pytest.mark.asyncio
    async def test_complete_authentication_credential_not_found(self):
        """Test authentication completion with non-existent credential."""
        try:
            from second_brain_database.routes.auth.services.webauthn.authentication import complete_authentication
            from fastapi import HTTPException
            
            with patch("second_brain_database.routes.auth.services.webauthn.authentication.validate_challenge") as mock_validate, \
                 patch("second_brain_database.routes.auth.services.webauthn.authentication.get_credential_by_id") as mock_get_cred:
                
                # Mock valid challenge
                mock_validate.return_value = {
                    "type": "authentication",
                    "created_at": datetime.utcnow().isoformat()
                }
                
                # Mock credential not found
                mock_get_cred.return_value = None
                
                with pytest.raises(HTTPException) as exc_info:
                    await complete_authentication(
                        credential_id="nonexistent_cred",
                        authenticator_data="mock_auth_data",
                        client_data_json="mock_client_data",
                        signature="mock_signature"
                    )
                
                assert exc_info.value.status_code == 401
                assert "Invalid credential" in str(exc_info.value.detail)
                
        except ImportError:
            pytest.skip("Authentication service not implemented")

    @pytest.mark.asyncio
    async def test_complete_authentication_signature_verification_failed(self):
        """Test authentication completion with failed signature verification."""
        try:
            from second_brain_database.routes.auth.services.webauthn.authentication import complete_authentication
            from fastapi import HTTPException
            
            with patch("second_brain_database.routes.auth.services.webauthn.authentication.validate_challenge") as mock_validate, \
                 patch("second_brain_database.routes.auth.services.webauthn.authentication.get_credential_by_id") as mock_get_cred, \
                 patch("second_brain_database.routes.auth.services.webauthn.authentication.verify_assertion_signature") as mock_verify_sig:
                
                # Mock valid challenge
                mock_validate.return_value = {
                    "type": "authentication",
                    "created_at": datetime.utcnow().isoformat()
                }
                
                # Mock credential retrieval
                mock_get_cred.return_value = {
                    "credential_id": "test_cred",
                    "user_id": str(ObjectId()),
                    "public_key": "test_public_key",
                    "sign_count": 5
                }
                
                # Mock signature verification failure
                mock_verify_sig.return_value = False
                
                with pytest.raises(HTTPException) as exc_info:
                    await complete_authentication(
                        credential_id="test_cred",
                        authenticator_data="mock_auth_data",
                        client_data_json="mock_client_data",
                        signature="invalid_signature"
                    )
                
                assert exc_info.value.status_code == 401
                assert "Authentication failed" in str(exc_info.value.detail)
                
        except ImportError:
            pytest.skip("Authentication service not implemented")


class TestWebAuthnSecurityValidation:
    """Test WebAuthn security validation functionality."""

    @pytest.mark.asyncio
    async def test_validate_webauthn_request_success(self):
        """Test successful WebAuthn request validation."""
        try:
            from second_brain_database.routes.auth.services.webauthn.security_validation import webauthn_security_validator
            
            mock_request = Mock()
            mock_request.headers = {
                "origin": "https://example.com",
                "referer": "https://example.com/login",
                "user-agent": "Mozilla/5.0..."
            }
            mock_request.client = Mock()
            mock_request.client.host = "192.168.1.1"
            
            with patch("second_brain_database.routes.auth.services.webauthn.security_validation.settings") as mock_settings:
                mock_settings.WEBAUTHN_ALLOWED_ORIGINS = ["https://example.com"]
                
                result = await webauthn_security_validator.validate_webauthn_request(
                    request=mock_request,
                    operation_type="registration",
                    user_id="user123"
                )
                
                assert result is not None
                assert "origin_valid" in result
                assert result["origin_valid"] is True
                
        except ImportError:
            pytest.skip("Security validation service not implemented")

    @pytest.mark.asyncio
    async def test_validate_webauthn_request_invalid_origin(self):
        """Test WebAuthn request validation with invalid origin."""
        try:
            from second_brain_database.routes.auth.services.webauthn.security_validation import webauthn_security_validator
            from fastapi import HTTPException
            
            mock_request = Mock()
            mock_request.headers = {
                "origin": "https://malicious.com",
                "referer": "https://malicious.com/attack",
                "user-agent": "Mozilla/5.0..."
            }
            mock_request.client = Mock()
            mock_request.client.host = "192.168.1.1"
            
            with patch("second_brain_database.routes.auth.services.webauthn.security_validation.settings") as mock_settings:
                mock_settings.WEBAUTHN_ALLOWED_ORIGINS = ["https://example.com"]
                
                with pytest.raises(HTTPException) as exc_info:
                    await webauthn_security_validator.validate_webauthn_request(
                        request=mock_request,
                        operation_type="registration",
                        user_id="user123"
                    )
                
                assert exc_info.value.status_code == 403
                assert "Origin not allowed" in str(exc_info.value.detail)
                
        except ImportError:
            pytest.skip("Security validation service not implemented")

    def test_sanitize_webauthn_data(self):
        """Test WebAuthn data sanitization."""
        try:
            from second_brain_database.routes.auth.services.webauthn.security_validation import webauthn_security_validator
            
            input_data = {
                "device_name": "<script>alert('xss')</script>Device",
                "id": "credential_id_123",
                "response": {
                    "attestationObject": "safe_data",
                    "clientDataJSON": "safe_json"
                },
                "malicious_field": "<img src=x onerror=alert(1)>"
            }
            
            result = webauthn_security_validator.sanitize_webauthn_data(
                data=input_data,
                operation_type="registration"
            )
            
            # Should sanitize HTML/script content
            assert "<script>" not in result["device_name"]
            assert "Device" in result["device_name"]
            
            # Should preserve safe fields
            assert result["id"] == "credential_id_123"
            assert result["response"]["attestationObject"] == "safe_data"
            
            # Should remove or sanitize malicious fields
            if "malicious_field" in result:
                assert "<img" not in result["malicious_field"]
                
        except ImportError:
            pytest.skip("Security validation service not implemented")

    def test_add_security_headers(self):
        """Test adding security headers to WebAuthn responses."""
        try:
            from second_brain_database.routes.auth.services.webauthn.security_validation import webauthn_security_validator
            from fastapi.responses import JSONResponse
            
            response = JSONResponse(content={"message": "success"})
            
            enhanced_response = webauthn_security_validator.add_security_headers(
                response, 
                operation_type="registration"
            )
            
            # Should add WebAuthn-specific security headers
            assert "X-Content-Type-Options" in enhanced_response.headers
            assert "X-Frame-Options" in enhanced_response.headers
            assert "Content-Security-Policy" in enhanced_response.headers
            
            # Should include WebAuthn-specific CSP directives
            csp = enhanced_response.headers["Content-Security-Policy"]
            assert "webauthn-get" in csp or "webauthn-create" in csp
            
        except ImportError:
            pytest.skip("Security validation service not implemented")


class TestWebAuthnMonitoring:
    """Test WebAuthn monitoring and metrics functionality."""

    @pytest.mark.asyncio
    async def test_log_webauthn_operation(self):
        """Test WebAuthn operation logging."""
        try:
            from second_brain_database.routes.auth.services.webauthn.monitoring import log_webauthn_operation
            
            with patch("second_brain_database.routes.auth.services.webauthn.monitoring.get_logger") as mock_get_logger:
                mock_logger = Mock()
                mock_get_logger.return_value = mock_logger
                
                await log_webauthn_operation(
                    operation_type="registration",
                    user_id="user123",
                    success=True,
                    duration=0.5,
                    details={"device_name": "Test Device"}
                )
                
                mock_logger.info.assert_called_once()
                call_args = mock_logger.info.call_args[0][0]
                assert "registration" in call_args
                assert "user123" in call_args
                assert "0.500s" in call_args
                
        except ImportError:
            pytest.skip("Monitoring service not implemented")

    @pytest.mark.asyncio
    async def test_track_webauthn_metrics(self):
        """Test WebAuthn metrics tracking."""
        try:
            from second_brain_database.routes.auth.services.webauthn.monitoring import track_webauthn_metrics
            
            with patch("second_brain_database.routes.auth.services.webauthn.monitoring.redis_manager") as mock_redis_manager:
                mock_redis_conn = AsyncMock()
                mock_redis_manager.get_redis.return_value = mock_redis_conn
                mock_redis_conn.incr.return_value = 1
                mock_redis_conn.expire.return_value = True
                
                await track_webauthn_metrics(
                    metric_type="registration_success",
                    user_id="user123",
                    additional_data={"authenticator_type": "platform"}
                )
                
                mock_redis_conn.incr.assert_called()
                mock_redis_conn.expire.assert_called()
                
        except ImportError:
            pytest.skip("Monitoring service not implemented")

    @pytest.mark.asyncio
    async def test_get_webauthn_statistics(self):
        """Test WebAuthn statistics retrieval."""
        try:
            from second_brain_database.routes.auth.services.webauthn.monitoring import get_webauthn_statistics
            
            with patch("second_brain_database.routes.auth.services.webauthn.monitoring.redis_manager") as mock_redis_manager, \
                 patch("second_brain_database.routes.auth.services.webauthn.monitoring.db_manager") as mock_db_manager:
                
                # Mock Redis metrics
                mock_redis_conn = AsyncMock()
                mock_redis_manager.get_redis.return_value = mock_redis_conn
                mock_redis_conn.get.side_effect = ["10", "8", "2"]  # registration, auth success, auth failure
                
                # Mock database statistics
                mock_collection = AsyncMock()
                mock_db_manager.get_collection.return_value = mock_collection
                mock_collection.count_documents.return_value = 25  # total credentials
                
                result = await get_webauthn_statistics(time_period="24h")
                
                assert "registrations" in result
                assert "authentications" in result
                assert "total_credentials" in result
                assert result["registrations"] == 10
                assert result["total_credentials"] == 25
                
        except ImportError:
            pytest.skip("Monitoring service not implemented")


class TestWebAuthnErrorHandling:
    """Test WebAuthn error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_challenge_storage_failure_handling(self):
        """Test handling of challenge storage failures."""
        with patch("second_brain_database.routes.auth.services.webauthn.challenge.redis_manager") as mock_redis_manager, \
             patch("second_brain_database.routes.auth.services.webauthn.challenge.db_manager") as mock_db_manager:
            
            # Mock both Redis and database failures
            mock_redis_conn = AsyncMock()
            mock_redis_manager.get_redis.return_value = mock_redis_conn
            mock_redis_conn.set.side_effect = Exception("Redis connection failed")
            
            mock_collection = AsyncMock()
            mock_db_manager.get_collection.return_value = mock_collection
            mock_collection.insert_one.side_effect = Exception("Database connection failed")
            
            from second_brain_database.routes.auth.services.webauthn.challenge import store_challenge
            
            with pytest.raises(RuntimeError, match="Failed to store challenge in both Redis and database"):
                await store_challenge("test_challenge", "user123", "registration")

    @pytest.mark.asyncio
    async def test_credential_storage_failure_handling(self):
        """Test handling of credential storage failures."""
        with patch("second_brain_database.routes.auth.services.webauthn.credentials.db_manager") as mock_db_manager:
            
            mock_collection = AsyncMock()
            mock_db_manager.get_collection.return_value = mock_collection
            
            # Mock finding no existing credential
            mock_collection.find_one.return_value = None
            
            # Mock insert failure
            mock_collection.insert_one.side_effect = Exception("Database insert failed")
            
            from second_brain_database.routes.auth.services.webauthn.credentials import store_credential
            
            with pytest.raises(RuntimeError, match="Credential storage failed"):
                await store_credential("user123", "cred123", "key123")

    @pytest.mark.asyncio
    async def test_concurrent_challenge_validation(self):
        """Test handling of concurrent challenge validation attempts."""
        with patch("second_brain_database.routes.auth.services.webauthn.challenge.redis_manager") as mock_redis_manager:
            
            mock_redis_conn = AsyncMock()
            mock_redis_manager.get_redis.return_value = mock_redis_conn
            
            challenge_data = {
                "user_id": "user123",
                "type": "authentication",
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(minutes=5)).isoformat()
            }
            
            # First call returns data, second call returns None (already consumed)
            mock_redis_conn.get.side_effect = [json.dumps(challenge_data), None]
            mock_redis_conn.delete.return_value = 1
            
            from second_brain_database.routes.auth.services.webauthn.challenge import validate_challenge
            
            # First validation should succeed
            result1 = await validate_challenge("test_challenge", "user123", "authentication")
            assert result1 is not None
            
            # Second validation should fail (challenge already consumed)
            result2 = await validate_challenge("test_challenge", "user123", "authentication")
            assert result2 is None

    @pytest.mark.asyncio
    async def test_malformed_credential_response_handling(self):
        """Test handling of malformed credential responses."""
        try:
            from second_brain_database.routes.auth.services.webauthn.registration import complete_registration
            from fastapi import HTTPException
            
            user = {"_id": ObjectId(), "username": "testuser"}
            
            # Malformed credential response (missing required fields)
            malformed_response = {
                "id": "test_cred",
                # Missing 'response' field
                "type": "public-key"
            }
            
            with patch("second_brain_database.routes.auth.services.webauthn.registration.validate_challenge") as mock_validate:
                mock_validate.return_value = {"user_id": str(user["_id"]), "type": "registration"}
                
                with pytest.raises(HTTPException) as exc_info:
                    await complete_registration(user, malformed_response, "Test Device")
                
                assert exc_info.value.status_code == 400
                
        except ImportError:
            pytest.skip("Registration service not implemented")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])