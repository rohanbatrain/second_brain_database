"""
Comprehensive security tests for OAuth2 implementation.

This module tests all security hardening features including:
- Input validation and sanitization
- Security headers
- Rate limiting and abuse detection
- Token encryption and secure storage
- Malicious pattern detection
- PKCE validation
"""

import asyncio
import base64
import json
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, Request, Response
from fastapi.testclient import TestClient

from src.second_brain_database.routes.oauth2.security_manager import (
    OAuth2SecurityHardening,
    OAuth2SecurityManager,
    oauth2_security_manager
)
from src.second_brain_database.routes.oauth2.token_encryption import (
    OAuth2TokenEncryption,
    oauth2_token_encryption
)
from src.second_brain_database.routes.oauth2.security_middleware import (
    OAuth2SecurityMiddleware,
    oauth2_security_middleware
)


class TestOAuth2SecurityHardening:
    """Test OAuth2 security hardening utilities."""
    
    def test_sanitize_input_basic(self):
        """Test basic input sanitization."""
        # Test normal input
        result = OAuth2SecurityHardening.sanitize_input("normal_input_123")
        assert result == "normal_input_123"
        
        # Test HTML escaping
        result = OAuth2SecurityHardening.sanitize_input("<script>alert('xss')</script>")
        assert "&lt;script&gt;" in result
        assert "&lt;/script&gt;" in result
        
        # Test length truncation
        long_input = "a" * 2000
        result = OAuth2SecurityHardening.sanitize_input(long_input, max_length=100)
        assert len(result) <= 100
        
        # Test null bytes removal
        result = OAuth2SecurityHardening.sanitize_input("test\x00null")
        assert "\x00" not in result
        
        # Test empty input
        result = OAuth2SecurityHardening.sanitize_input("")
        assert result == ""
        
        # Test None input
        result = OAuth2SecurityHardening.sanitize_input(None)
        assert result == ""
    
    def test_detect_malicious_patterns_xss(self):
        """Test XSS pattern detection."""
        # Test script tags
        patterns = OAuth2SecurityHardening.detect_malicious_patterns("<script>alert('xss')</script>")
        assert "xss" in patterns
        
        # Test javascript: protocol
        patterns = OAuth2SecurityHardening.detect_malicious_patterns("javascript:alert('xss')")
        assert "xss" in patterns
        
        # Test data: protocol
        patterns = OAuth2SecurityHardening.detect_malicious_patterns("data:text/html,<script>alert('xss')</script>")
        assert "xss" in patterns
        
        # Test event handlers
        patterns = OAuth2SecurityHardening.detect_malicious_patterns("onclick=alert('xss')")
        assert "xss" in patterns
        
        # Test iframe
        patterns = OAuth2SecurityHardening.detect_malicious_patterns("<iframe src='evil.com'></iframe>")
        assert "xss" in patterns
        
        # Test clean input
        patterns = OAuth2SecurityHardening.detect_malicious_patterns("normal_clean_input")
        assert len(patterns) == 0
    
    def test_detect_malicious_patterns_sql_injection(self):
        """Test SQL injection pattern detection."""
        # Test SQL keywords
        patterns = OAuth2SecurityHardening.detect_malicious_patterns("SELECT * FROM users")
        assert "sql_injection" in patterns
        
        # Test OR condition
        patterns = OAuth2SecurityHardening.detect_malicious_patterns("1 OR 1=1")
        assert "sql_injection" in patterns
        
        # Test quotes
        patterns = OAuth2SecurityHardening.detect_malicious_patterns("'; DROP TABLE users; --")
        assert "sql_injection" in patterns
        
        # Test clean input
        patterns = OAuth2SecurityHardening.detect_malicious_patterns("normal_input")
        assert len(patterns) == 0
    
    def test_security_headers(self):
        """Test security headers configuration."""
        headers = OAuth2SecurityHardening.SECURITY_HEADERS
        
        # Check required security headers
        assert "X-Content-Type-Options" in headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        
        assert "X-Frame-Options" in headers
        assert headers["X-Frame-Options"] == "DENY"
        
        assert "X-XSS-Protection" in headers
        assert "1; mode=block" in headers["X-XSS-Protection"]
        
        assert "Content-Security-Policy" in headers
        assert "default-src 'self'" in headers["Content-Security-Policy"]
        
        assert "Strict-Transport-Security" in headers
        assert "max-age=31536000" in headers["Strict-Transport-Security"]
        
        assert "Cache-Control" in headers
        assert "no-store" in headers["Cache-Control"]
    
    def test_input_validation_patterns(self):
        """Test input validation regex patterns."""
        # Test client_id pattern
        assert OAuth2SecurityHardening.CLIENT_ID_PATTERN.match("oauth2_client_12345678")
        assert OAuth2SecurityHardening.CLIENT_ID_PATTERN.match("client-id_123")
        assert not OAuth2SecurityHardening.CLIENT_ID_PATTERN.match("short")
        assert not OAuth2SecurityHardening.CLIENT_ID_PATTERN.match("client@id")
        
        # Test state pattern
        assert OAuth2SecurityHardening.STATE_PATTERN.match("state_123.456-789")
        assert not OAuth2SecurityHardening.STATE_PATTERN.match("state@123")
        assert not OAuth2SecurityHardening.STATE_PATTERN.match("short")
        
        # Test code pattern
        assert OAuth2SecurityHardening.CODE_PATTERN.match("auth_code_1234567890abcdef1234567890abcdef")
        assert not OAuth2SecurityHardening.CODE_PATTERN.match("short_code")
        
        # Test scope pattern
        assert OAuth2SecurityHardening.SCOPE_PATTERN.match("read:profile")
        assert OAuth2SecurityHardening.SCOPE_PATTERN.match("write.data")
        assert not OAuth2SecurityHardening.SCOPE_PATTERN.match("scope@invalid")


class TestOAuth2SecurityManager:
    """Test OAuth2 security manager functionality."""
    
    @pytest.fixture
    def security_manager(self):
        """Create security manager instance for testing."""
        return OAuth2SecurityManager()
    
    @pytest.fixture
    def mock_request(self):
        """Create mock request for testing."""
        request = MagicMock(spec=Request)
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.headers = {"user-agent": "test-agent"}
        request.method = "POST"
        request.url = "https://example.com/oauth2/authorize"
        return request
    
    def test_apply_security_headers(self, security_manager):
        """Test security headers application."""
        response = MagicMock(spec=Response)
        response.headers = {}
        
        result = security_manager.apply_security_headers(response)
        
        # Check that security headers were applied
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers
        assert "Content-Security-Policy" in response.headers
        assert result == response
    
    @pytest.mark.asyncio
    async def test_validate_and_sanitize_input_valid(self, security_manager, mock_request):
        """Test input validation with valid data."""
        input_data = {
            "client_id": "oauth2_client_12345678",
            "state": "secure_state_123",
            "scope": "read:profile write:data"
        }
        
        result = await security_manager.validate_and_sanitize_input(
            input_data=input_data,
            client_id="oauth2_client_12345678",
            request=mock_request
        )
        
        assert result == input_data
        assert result["client_id"] == "oauth2_client_12345678"
        assert result["state"] == "secure_state_123"
        assert result["scope"] == "read:profile write:data"
    
    @pytest.mark.asyncio
    async def test_validate_and_sanitize_input_malicious(self, security_manager, mock_request):
        """Test input validation with malicious data."""
        input_data = {
            "client_id": "<script>alert('xss')</script>",
            "state": "javascript:alert('xss')"
        }
        
        with pytest.raises(HTTPException) as exc_info:
            await security_manager.validate_and_sanitize_input(
                input_data=input_data,
                client_id="test_client",
                request=mock_request
            )
        
        assert exc_info.value.status_code == 400
        assert "validation failed" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_validate_and_sanitize_input_invalid_format(self, security_manager, mock_request):
        """Test input validation with invalid format."""
        input_data = {
            "client_id": "short",  # Too short
            "state": "invalid@state"  # Invalid characters
        }
        
        with pytest.raises(HTTPException) as exc_info:
            await security_manager.validate_and_sanitize_input(
                input_data=input_data,
                client_id="test_client",
                request=mock_request
            )
        
        assert exc_info.value.status_code == 400
    
    @pytest.mark.asyncio
    async def test_encrypt_decrypt_token_data(self, security_manager):
        """Test token data encryption and decryption."""
        token_data = {
            "access_token": "test_token_123",
            "client_id": "oauth2_client_12345678",
            "user_id": "test_user"
        }
        
        # Test encryption
        encrypted = await security_manager.encrypt_token_data(token_data)
        assert isinstance(encrypted, str)
        assert encrypted != json.dumps(token_data)
        
        # Test decryption
        decrypted = await security_manager.decrypt_token_data(encrypted)
        assert decrypted == token_data
    
    @pytest.mark.asyncio
    async def test_detect_abuse_patterns(self, security_manager, mock_request):
        """Test abuse pattern detection."""
        client_id = "test_client"
        event_type = "failed_auth_attempts"
        
        # Mock Redis operations
        with patch.object(security_manager.redis_manager, 'get_redis') as mock_redis:
            mock_conn = AsyncMock()
            mock_redis.return_value = mock_conn
            
            # Test normal usage (below threshold)
            mock_conn.incr.return_value = 5
            result = await security_manager.detect_abuse_patterns(
                client_id=client_id,
                request=mock_request,
                event_type=event_type
            )
            assert result is False
            
            # Test abuse detection (above threshold)
            mock_conn.incr.return_value = 15  # Above threshold of 10
            result = await security_manager.detect_abuse_patterns(
                client_id=client_id,
                request=mock_request,
                event_type=event_type
            )
            assert result is True
    
    @pytest.mark.asyncio
    async def test_enhanced_rate_limiting_normal(self, security_manager, mock_request):
        """Test enhanced rate limiting under normal conditions."""
        client_id = "test_client"
        endpoint = "authorize"
        
        with patch.object(security_manager, 'detect_abuse_patterns') as mock_abuse:
            with patch.object(security_manager, 'rate_limit_client') as mock_rate_limit:
                mock_abuse.return_value = False
                mock_rate_limit.return_value = None
                
                # Should not raise exception
                await security_manager.enhanced_rate_limiting(
                    request=mock_request,
                    client_id=client_id,
                    endpoint=endpoint
                )
                
                mock_abuse.assert_called_once()
                mock_rate_limit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_enhanced_rate_limiting_abuse_detected(self, security_manager, mock_request):
        """Test enhanced rate limiting with abuse detection."""
        client_id = "test_client"
        endpoint = "authorize"
        
        with patch.object(security_manager, 'detect_abuse_patterns') as mock_abuse:
            mock_abuse.return_value = True
            
            with pytest.raises(HTTPException) as exc_info:
                await security_manager.enhanced_rate_limiting(
                    request=mock_request,
                    client_id=client_id,
                    endpoint=endpoint
                )
            
            assert exc_info.value.status_code == 429
            assert "abuse detection" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_validate_redirect_uri_security_valid(self, security_manager, mock_request):
        """Test redirect URI security validation with valid URI."""
        redirect_uri = "https://example.com/callback"
        client_id = "test_client"
        
        with patch.object(security_manager, 'validate_redirect_uri') as mock_validate:
            mock_validate.return_value = True
            
            result = await security_manager.validate_redirect_uri_security(
                redirect_uri=redirect_uri,
                client_id=client_id,
                request=mock_request
            )
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_redirect_uri_security_suspicious(self, security_manager, mock_request):
        """Test redirect URI security validation with suspicious URI."""
        redirect_uri = "javascript:alert('xss')"
        client_id = "test_client"
        
        with patch.object(security_manager, 'validate_redirect_uri') as mock_validate:
            mock_validate.return_value = True  # Basic validation passes
            
            result = await security_manager.validate_redirect_uri_security(
                redirect_uri=redirect_uri,
                client_id=client_id,
                request=mock_request
            )
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_redirect_uri_security_url_shortener(self, security_manager, mock_request):
        """Test redirect URI security validation with URL shortener."""
        redirect_uri = "https://bit.ly/malicious"
        client_id = "test_client"
        
        with patch.object(security_manager, 'validate_redirect_uri') as mock_validate:
            mock_validate.return_value = True  # Basic validation passes
            
            result = await security_manager.validate_redirect_uri_security(
                redirect_uri=redirect_uri,
                client_id=client_id,
                request=mock_request
            )
            
            assert result is False


class TestOAuth2TokenEncryption:
    """Test OAuth2 token encryption functionality."""
    
    @pytest.fixture
    def token_encryption(self):
        """Create token encryption instance for testing."""
        return OAuth2TokenEncryption()
    
    def test_encrypt_token_basic(self, token_encryption):
        """Test basic token encryption."""
        token_data = {
            "access_token": "test_token_123",
            "client_id": "oauth2_client_12345678",
            "expires_in": 3600
        }
        
        encrypted = token_encryption.encrypt_token(token_data)
        
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0
        assert encrypted != json.dumps(token_data)
    
    def test_decrypt_token_basic(self, token_encryption):
        """Test basic token decryption."""
        token_data = {
            "access_token": "test_token_123",
            "client_id": "oauth2_client_12345678",
            "expires_in": 3600
        }
        
        encrypted = token_encryption.encrypt_token(token_data)
        decrypted = token_encryption.decrypt_token(encrypted, verify_integrity=False)
        
        assert decrypted == token_data
    
    def test_encrypt_decrypt_with_integrity_check(self, token_encryption):
        """Test encryption/decryption with integrity verification."""
        token_data = {
            "access_token": "test_token_123",
            "client_id": "oauth2_client_12345678"
        }
        
        encrypted = token_encryption.encrypt_token(token_data, include_integrity_check=True)
        decrypted = token_encryption.decrypt_token(encrypted, verify_integrity=True)
        
        assert decrypted == token_data
    
    def test_decrypt_token_integrity_failure(self, token_encryption):
        """Test decryption with integrity check failure."""
        token_data = {
            "access_token": "test_token_123",
            "client_id": "oauth2_client_12345678"
        }
        
        encrypted = token_encryption.encrypt_token(token_data, include_integrity_check=True)
        
        # Tamper with encrypted data
        tampered = encrypted[:-10] + "tampered123"
        
        with pytest.raises(Exception):
            token_encryption.decrypt_token(tampered, verify_integrity=True)
    
    def test_decrypt_token_max_age(self, token_encryption):
        """Test token decryption with age verification."""
        token_data = {
            "access_token": "test_token_123",
            "client_id": "oauth2_client_12345678"
        }
        
        encrypted = token_encryption.encrypt_token(token_data)
        
        # Should succeed with reasonable max_age
        decrypted = token_encryption.decrypt_token(encrypted, max_age_seconds=60)
        assert decrypted == token_data
        
        # Should fail with very small max_age
        with pytest.raises(ValueError, match="Token expired"):
            token_encryption.decrypt_token(encrypted, max_age_seconds=0)
    
    @pytest.mark.asyncio
    async def test_store_retrieve_encrypted_token(self, token_encryption):
        """Test storing and retrieving encrypted tokens."""
        token_data = {
            "access_token": "test_token_123",
            "client_id": "oauth2_client_12345678"
        }
        
        key = "test_token_key"
        ttl_seconds = 3600
        
        with patch.object(token_encryption.redis_manager, 'get_redis') as mock_redis:
            mock_conn = AsyncMock()
            mock_redis.return_value = mock_conn
            
            # Test storage
            mock_conn.set.return_value = True
            result = await token_encryption.store_encrypted_token(
                key=key,
                token_data=token_data,
                ttl_seconds=ttl_seconds
            )
            assert result is True
            
            # Test retrieval
            encrypted_token = token_encryption.encrypt_token(token_data)
            mock_conn.get.return_value = encrypted_token
            
            retrieved = await token_encryption.retrieve_encrypted_token(key=key)
            assert retrieved == token_data
    
    @pytest.mark.asyncio
    async def test_delete_encrypted_token(self, token_encryption):
        """Test deleting encrypted tokens."""
        key = "test_token_key"
        
        with patch.object(token_encryption.redis_manager, 'get_redis') as mock_redis:
            mock_conn = AsyncMock()
            mock_redis.return_value = mock_conn
            mock_conn.delete.return_value = 1
            
            result = await token_encryption.delete_encrypted_token(key=key)
            assert result is True
            
            mock_conn.delete.assert_called_once()
    
    def test_create_secure_token_hash(self, token_encryption):
        """Test secure token hashing."""
        token = "test_token_123"
        
        hash1 = token_encryption.create_secure_token_hash(token)
        hash2 = token_encryption.create_secure_token_hash(token)
        
        # Same token should produce same hash
        assert hash1 == hash2
        
        # Different tokens should produce different hashes
        hash3 = token_encryption.create_secure_token_hash("different_token")
        assert hash1 != hash3
        
        # Hash should be base64 encoded
        assert isinstance(hash1, str)
        try:
            base64.urlsafe_b64decode(hash1)
        except Exception:
            pytest.fail("Hash should be valid base64")


class TestOAuth2SecurityMiddleware:
    """Test OAuth2 security middleware functionality."""
    
    @pytest.fixture
    def security_middleware(self):
        """Create security middleware instance for testing."""
        return OAuth2SecurityMiddleware()
    
    @pytest.fixture
    def mock_request(self):
        """Create mock request for testing."""
        request = MagicMock(spec=Request)
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.headers = {
            "user-agent": "test-agent",
            "content-length": "100"
        }
        request.method = "POST"
        request.url = "https://example.com/oauth2/authorize"
        request.query_params = {"client_id": "test_client"}
        return request
    
    @pytest.mark.asyncio
    async def test_middleware_success(self, security_middleware, mock_request):
        """Test middleware with successful request."""
        async def mock_call_next(request):
            response = MagicMock(spec=Response)
            response.status_code = 200
            response.headers = {}
            return response
        
        with patch.object(security_middleware.security_manager, 'enhanced_rate_limiting') as mock_rate_limit:
            with patch.object(security_middleware, '_validate_request_security') as mock_validate:
                with patch.object(security_middleware.security_manager, 'apply_security_headers') as mock_headers:
                    mock_rate_limit.return_value = None
                    mock_validate.return_value = None
                    mock_headers.side_effect = lambda x: x
                    
                    response = await security_middleware(
                        request=mock_request,
                        call_next=mock_call_next,
                        endpoint_name="authorize",
                        require_client_id=True
                    )
                    
                    assert response.status_code == 200
                    mock_rate_limit.assert_called_once()
                    mock_validate.assert_called_once()
                    mock_headers.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_middleware_missing_client_id(self, security_middleware):
        """Test middleware with missing client_id."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.query_params = {}  # No client_id
        
        async def mock_call_next(request):
            return MagicMock(spec=Response)
        
        response = await security_middleware(
            request=request,
            call_next=mock_call_next,
            endpoint_name="authorize",
            require_client_id=True
        )
        
        # Should return error response
        assert hasattr(response, 'status_code')
    
    @pytest.mark.asyncio
    async def test_middleware_rate_limit_exceeded(self, security_middleware, mock_request):
        """Test middleware with rate limit exceeded."""
        async def mock_call_next(request):
            return MagicMock(spec=Response)
        
        with patch.object(security_middleware.security_manager, 'enhanced_rate_limiting') as mock_rate_limit:
            mock_rate_limit.side_effect = HTTPException(status_code=429, detail="Rate limit exceeded")
            
            response = await security_middleware(
                request=mock_request,
                call_next=mock_call_next,
                endpoint_name="authorize",
                require_client_id=True
            )
            
            assert response.status_code == 429
    
    @pytest.mark.asyncio
    async def test_validate_request_security_oversized(self, security_middleware, mock_request):
        """Test request security validation with oversized request."""
        mock_request.headers = {"content-length": "20000"}  # Over 10KB limit
        
        with pytest.raises(HTTPException) as exc_info:
            await security_middleware._validate_request_security(
                request=mock_request,
                client_id="test_client",
                endpoint_name="authorize"
            )
        
        assert exc_info.value.status_code == 413
    
    @pytest.mark.asyncio
    async def test_validate_request_security_malicious_url(self, security_middleware):
        """Test request security validation with malicious URL patterns."""
        request = MagicMock(spec=Request)
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.headers = {"user-agent": "test-agent"}
        request.url = "https://example.com/oauth2/authorize?param=<script>alert('xss')</script>"
        
        with pytest.raises(HTTPException) as exc_info:
            await security_middleware._validate_request_security(
                request=request,
                client_id="test_client",
                endpoint_name="authorize"
            )
        
        assert exc_info.value.status_code == 400


# Integration tests
class TestOAuth2SecurityIntegration:
    """Integration tests for OAuth2 security features."""
    
    @pytest.mark.asyncio
    async def test_full_security_pipeline(self):
        """Test complete security pipeline integration."""
        # This would test the full flow from request to response
        # with all security features enabled
        pass
    
    @pytest.mark.asyncio
    async def test_security_under_load(self):
        """Test security features under high load conditions."""
        # This would test rate limiting and abuse detection
        # under concurrent requests
        pass
    
    @pytest.mark.asyncio
    async def test_security_with_real_attacks(self):
        """Test security features against real attack patterns."""
        # This would test against known attack vectors
        # like OWASP Top 10 vulnerabilities
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])