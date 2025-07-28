"""
Unit tests for OAuth2 configuration and settings management.

This module tests the OAuth2 configuration settings, validation,
and the OAuth2 provider metadata endpoint functionality.
"""

import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pydantic import ValidationError
from fastapi.testclient import TestClient
from fastapi import HTTPException

from second_brain_database.config import Settings


class TestOAuth2Configuration:
    """Test OAuth2 configuration settings and validation."""

    def test_oauth2_default_configuration(self):
        """Test OAuth2 default configuration values."""
        settings = Settings()
        
        # Test default OAuth2 settings
        assert settings.OAUTH2_ENABLED is True
        assert settings.OAUTH2_AUTHORIZATION_CODE_EXPIRE_MINUTES == 10
        assert settings.OAUTH2_ACCESS_TOKEN_EXPIRE_MINUTES == 60
        assert settings.OAUTH2_REFRESH_TOKEN_EXPIRE_DAYS == 30
        assert settings.OAUTH2_CONSENT_EXPIRE_DAYS == 365
        
        # Test security defaults
        assert settings.OAUTH2_REQUIRE_PKCE is True
        assert settings.OAUTH2_ALLOW_PLAIN_PKCE is False
        assert settings.OAUTH2_MAX_CLIENTS_PER_USER == 10
        
        # Test rate limiting defaults
        assert settings.OAUTH2_AUTHORIZE_RATE_LIMIT == 100
        assert settings.OAUTH2_AUTHORIZE_RATE_PERIOD == 300
        assert settings.OAUTH2_TOKEN_RATE_LIMIT == 50
        assert settings.OAUTH2_TOKEN_RATE_PERIOD == 300

    def test_oauth2_scope_configuration(self):
        """Test OAuth2 scope configuration."""
        settings = Settings()
        
        # Test default scopes
        assert settings.OAUTH2_DEFAULT_SCOPES == "read:profile"
        assert "read:profile" in settings.OAUTH2_AVAILABLE_SCOPES
        assert "write:profile" in settings.OAUTH2_AVAILABLE_SCOPES
        assert "admin" in settings.OAUTH2_ADMIN_ONLY_SCOPES

    def test_oauth2_endpoint_configuration(self):
        """Test OAuth2 endpoint path configuration."""
        settings = Settings()
        
        # Test endpoint paths
        assert settings.OAUTH2_AUTHORIZATION_ENDPOINT == "/oauth2/authorize"
        assert settings.OAUTH2_TOKEN_ENDPOINT == "/oauth2/token"
        assert settings.OAUTH2_REVOCATION_ENDPOINT == "/oauth2/revoke"
        assert settings.OAUTH2_INTROSPECTION_ENDPOINT == "/oauth2/introspect"
        assert settings.OAUTH2_USERINFO_ENDPOINT == "/oauth2/userinfo"
        assert settings.OAUTH2_JWKS_ENDPOINT == "/oauth2/jwks"

    def test_oauth2_client_management_configuration(self):
        """Test OAuth2 client management configuration."""
        settings = Settings()
        
        # Test client management settings
        assert settings.OAUTH2_CLIENT_REGISTRATION_ENABLED is True
        assert settings.OAUTH2_CLIENT_REGISTRATION_REQUIRE_AUTH is True
        assert settings.OAUTH2_CLIENT_MANAGEMENT_ENABLED is True
        assert settings.OAUTH2_AUTO_APPROVE_INTERNAL_CLIENTS is False

    def test_oauth2_maintenance_configuration(self):
        """Test OAuth2 cleanup and maintenance configuration."""
        settings = Settings()
        
        # Test maintenance settings
        assert settings.OAUTH2_CLEANUP_INTERVAL_HOURS == 6
        assert settings.OAUTH2_AUDIT_LOG_RETENTION_DAYS == 90
        assert settings.OAUTH2_METRICS_RETENTION_DAYS == 30


class TestOAuth2ConfigurationValidation:
    """Test OAuth2 configuration validation."""

    def test_oauth2_scopes_validation_valid(self):
        """Test valid OAuth2 scopes pass validation."""
        # Test valid scopes
        valid_scopes = "read:profile,write:profile,read:data,admin"
        
        with patch.dict(os.environ, {"OAUTH2_AVAILABLE_SCOPES": valid_scopes}):
            settings = Settings()
            assert settings.OAUTH2_AVAILABLE_SCOPES == valid_scopes

    def test_oauth2_scopes_validation_invalid(self):
        """Test invalid OAuth2 scopes fail validation."""
        # Test invalid scope format
        invalid_scopes = "read:profile,invalid-scope!,write:data"
        
        with patch.dict(os.environ, {"OAUTH2_AVAILABLE_SCOPES": invalid_scopes}):
            with pytest.raises(ValidationError) as exc_info:
                Settings()
            
            assert "Invalid OAuth2 scope format" in str(exc_info.value)

    def test_oauth2_authorization_code_expiry_validation_valid(self):
        """Test valid authorization code expiry passes validation."""
        # Test valid expiry (within RFC 6749 recommendation)
        with patch.dict(os.environ, {"OAUTH2_AUTHORIZATION_CODE_EXPIRE_MINUTES": "5"}):
            settings = Settings()
            assert settings.OAUTH2_AUTHORIZATION_CODE_EXPIRE_MINUTES == 5

    def test_oauth2_authorization_code_expiry_validation_invalid(self):
        """Test invalid authorization code expiry fails validation."""
        # Test expiry exceeding RFC 6749 recommendation
        with patch.dict(os.environ, {"OAUTH2_AUTHORIZATION_CODE_EXPIRE_MINUTES": "15"}):
            with pytest.raises(ValidationError) as exc_info:
                Settings()
            
            assert "should not exceed 10 minutes per RFC 6749" in str(exc_info.value)

    def test_oauth2_empty_scopes_validation(self):
        """Test empty OAuth2 scopes are handled correctly."""
        with patch.dict(os.environ, {"OAUTH2_AVAILABLE_SCOPES": ""}):
            settings = Settings()
            assert settings.OAUTH2_AVAILABLE_SCOPES == ""


class TestOAuth2ConfigurationProperties:
    """Test OAuth2 configuration properties."""

    def test_oauth2_issuer_url_property_with_custom_issuer(self):
        """Test oauth2_issuer_url property with custom issuer."""
        with patch.dict(os.environ, {
            "OAUTH2_ISSUER": "https://custom.example.com",
            "BASE_URL": "https://default.example.com"
        }):
            settings = Settings()
            assert settings.oauth2_issuer_url == "https://custom.example.com"

    def test_oauth2_issuer_url_property_with_default(self):
        """Test oauth2_issuer_url property defaults to BASE_URL."""
        with patch.dict(os.environ, {
            "OAUTH2_ISSUER": "",
            "BASE_URL": "https://default.example.com"
        }):
            settings = Settings()
            assert settings.oauth2_issuer_url == "https://default.example.com"

    def test_oauth2_available_scopes_list_property(self):
        """Test oauth2_available_scopes_list property."""
        with patch.dict(os.environ, {
            "OAUTH2_AVAILABLE_SCOPES": "read:profile, write:profile , read:data"
        }):
            settings = Settings()
            scopes = settings.oauth2_available_scopes_list
            
            assert scopes == ["read:profile", "write:profile", "read:data"]
            assert len(scopes) == 3

    def test_oauth2_default_scopes_list_property(self):
        """Test oauth2_default_scopes_list property."""
        with patch.dict(os.environ, {
            "OAUTH2_DEFAULT_SCOPES": "read:profile, read:data"
        }):
            settings = Settings()
            scopes = settings.oauth2_default_scopes_list
            
            assert scopes == ["read:profile", "read:data"]
            assert len(scopes) == 2

    def test_oauth2_admin_only_scopes_list_property(self):
        """Test oauth2_admin_only_scopes_list property."""
        with patch.dict(os.environ, {
            "OAUTH2_ADMIN_ONLY_SCOPES": "admin, system:admin"
        }):
            settings = Settings()
            scopes = settings.oauth2_admin_only_scopes_list
            
            assert scopes == ["admin", "system:admin"]
            assert len(scopes) == 2

    def test_oauth2_endpoints_property(self):
        """Test oauth2_endpoints property."""
        with patch.dict(os.environ, {
            "BASE_URL": "https://example.com",
            "OAUTH2_ISSUER": ""
        }):
            settings = Settings()
            endpoints = settings.oauth2_endpoints
            
            # Test all required endpoints
            assert endpoints["issuer"] == "https://example.com"
            assert endpoints["authorization_endpoint"] == "https://example.com/oauth2/authorize"
            assert endpoints["token_endpoint"] == "https://example.com/oauth2/token"
            assert endpoints["revocation_endpoint"] == "https://example.com/oauth2/revoke"
            assert endpoints["introspection_endpoint"] == "https://example.com/oauth2/introspect"
            assert endpoints["userinfo_endpoint"] == "https://example.com/oauth2/userinfo"
            assert endpoints["jwks_uri"] == "https://example.com/oauth2/jwks"

    def test_oauth2_endpoints_property_with_trailing_slash(self):
        """Test oauth2_endpoints property handles trailing slash correctly."""
        with patch.dict(os.environ, {
            "BASE_URL": "https://example.com/",
            "OAUTH2_ISSUER": ""
        }):
            settings = Settings()
            endpoints = settings.oauth2_endpoints
            
            # Should strip trailing slash
            assert endpoints["issuer"] == "https://example.com"
            assert endpoints["authorization_endpoint"] == "https://example.com/oauth2/authorize"


class TestOAuth2FeatureToggle:
    """Test OAuth2 feature toggle functionality."""

    def test_oauth2_enabled_toggle(self):
        """Test OAuth2 can be enabled/disabled."""
        # Test enabled
        with patch.dict(os.environ, {"OAUTH2_ENABLED": "true"}):
            settings = Settings()
            assert settings.OAUTH2_ENABLED is True

        # Test disabled
        with patch.dict(os.environ, {"OAUTH2_ENABLED": "false"}):
            settings = Settings()
            assert settings.OAUTH2_ENABLED is False

    def test_oauth2_client_registration_toggle(self):
        """Test OAuth2 client registration can be toggled."""
        # Test enabled
        with patch.dict(os.environ, {"OAUTH2_CLIENT_REGISTRATION_ENABLED": "true"}):
            settings = Settings()
            assert settings.OAUTH2_CLIENT_REGISTRATION_ENABLED is True

        # Test disabled
        with patch.dict(os.environ, {"OAUTH2_CLIENT_REGISTRATION_ENABLED": "false"}):
            settings = Settings()
            assert settings.OAUTH2_CLIENT_REGISTRATION_ENABLED is False

    def test_oauth2_pkce_configuration(self):
        """Test PKCE configuration options."""
        # Test PKCE required
        with patch.dict(os.environ, {"OAUTH2_REQUIRE_PKCE": "true"}):
            settings = Settings()
            assert settings.OAUTH2_REQUIRE_PKCE is True

        # Test plain PKCE allowed
        with patch.dict(os.environ, {"OAUTH2_ALLOW_PLAIN_PKCE": "true"}):
            settings = Settings()
            assert settings.OAUTH2_ALLOW_PLAIN_PKCE is True


class TestOAuth2ConfigurationIntegration:
    """Test OAuth2 configuration integration with other components."""

    def test_oauth2_configuration_with_base_settings(self):
        """Test OAuth2 configuration integrates with base settings."""
        with patch.dict(os.environ, {
            "BASE_URL": "https://api.example.com",
            "DEBUG": "false",
            "OAUTH2_ENABLED": "true"
        }):
            settings = Settings()
            
            # Test integration
            assert settings.BASE_URL == "https://api.example.com"
            assert settings.is_production is True
            assert settings.OAUTH2_ENABLED is True
            assert settings.oauth2_issuer_url == "https://api.example.com"

    def test_oauth2_configuration_environment_override(self):
        """Test OAuth2 configuration can be overridden by environment."""
        # Test environment variables override defaults
        env_overrides = {
            "OAUTH2_AUTHORIZATION_CODE_EXPIRE_MINUTES": "5",
            "OAUTH2_ACCESS_TOKEN_EXPIRE_MINUTES": "30",
            "OAUTH2_REFRESH_TOKEN_EXPIRE_DAYS": "7",
            "OAUTH2_MAX_CLIENTS_PER_USER": "5"
        }
        
        with patch.dict(os.environ, env_overrides):
            settings = Settings()
            
            assert settings.OAUTH2_AUTHORIZATION_CODE_EXPIRE_MINUTES == 5
            assert settings.OAUTH2_ACCESS_TOKEN_EXPIRE_MINUTES == 30
            assert settings.OAUTH2_REFRESH_TOKEN_EXPIRE_DAYS == 7
            assert settings.OAUTH2_MAX_CLIENTS_PER_USER == 5


class TestOAuth2ProviderMetadataEndpoint:
    """Test OAuth2 provider metadata endpoint."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch('second_brain_database.routes.oauth2.routes.settings') as mock:
            mock.BASE_URL = "https://example.com"
            mock.OAUTH2_REQUIRE_PKCE = True
            mock.OAUTH2_ALLOW_PLAIN_PKCE = False
            mock.OAUTH2_CLIENT_REGISTRATION_ENABLED = True
            mock.oauth2_available_scopes_list = ["read:profile", "write:profile", "read:data", "write:data", "admin"]
            mock.oauth2_endpoints = {
                "issuer": "https://example.com",
                "authorization_endpoint": "https://example.com/oauth2/authorize",
                "token_endpoint": "https://example.com/oauth2/token",
                "revocation_endpoint": "https://example.com/oauth2/revoke",
                "introspection_endpoint": "https://example.com/oauth2/introspect",
                "userinfo_endpoint": "https://example.com/oauth2/userinfo",
                "jwks_uri": "https://example.com/oauth2/jwks",
            }
            yield mock

    @pytest.mark.asyncio
    async def test_oauth2_metadata_endpoint_success(self, mock_settings):
        """Test successful OAuth2 metadata endpoint response."""
        from second_brain_database.routes.oauth2.routes import oauth2_authorization_server_metadata
        
        # Call the endpoint function directly
        result = await oauth2_authorization_server_metadata()
        
        # Verify required fields per RFC 8414
        assert result["issuer"] == "https://example.com"
        assert result["authorization_endpoint"] == "https://example.com/oauth2/authorize"
        assert result["token_endpoint"] == "https://example.com/oauth2/token"
        assert result["response_types_supported"] == ["code"]
        assert result["grant_types_supported"] == ["authorization_code", "refresh_token"]
        
        # Verify optional but recommended fields
        assert "scopes_supported" in result
        assert "token_endpoint_auth_methods_supported" in result
        assert "code_challenge_methods_supported" in result
        
        # Verify additional endpoints
        assert result["revocation_endpoint"] == "https://example.com/oauth2/revoke"
        assert result["introspection_endpoint"] == "https://example.com/oauth2/introspect"
        assert result["userinfo_endpoint"] == "https://example.com/oauth2/userinfo"
        assert result["jwks_uri"] == "https://example.com/oauth2/jwks"

    @pytest.mark.asyncio
    async def test_oauth2_metadata_endpoint_scopes(self, mock_settings):
        """Test OAuth2 metadata endpoint includes correct scopes."""
        from second_brain_database.routes.oauth2.routes import oauth2_authorization_server_metadata
        
        result = await oauth2_authorization_server_metadata()
        
        # Verify scopes are included
        assert "scopes_supported" in result
        scopes = result["scopes_supported"]
        assert "read:profile" in scopes
        assert "write:profile" in scopes
        assert "read:data" in scopes
        assert "write:data" in scopes
        assert "admin" in scopes

    @pytest.mark.asyncio
    async def test_oauth2_metadata_endpoint_pkce_configuration(self, mock_settings):
        """Test OAuth2 metadata endpoint reflects PKCE configuration."""
        from second_brain_database.routes.oauth2.routes import oauth2_authorization_server_metadata
        
        # Test with PKCE required and plain not allowed
        result = await oauth2_authorization_server_metadata()
        assert result["code_challenge_methods_supported"] == ["S256"]
        assert result["sbd_features"]["pkce_required"] is True
        
        # Test with plain PKCE allowed
        mock_settings.OAUTH2_ALLOW_PLAIN_PKCE = True
        result = await oauth2_authorization_server_metadata()
        assert "S256" in result["code_challenge_methods_supported"]
        assert "plain" in result["code_challenge_methods_supported"]

    @pytest.mark.asyncio
    async def test_oauth2_metadata_endpoint_client_registration(self, mock_settings):
        """Test OAuth2 metadata endpoint includes client registration when enabled."""
        from second_brain_database.routes.oauth2.routes import oauth2_authorization_server_metadata
        
        # Test with client registration enabled
        mock_settings.OAUTH2_CLIENT_REGISTRATION_ENABLED = True
        result = await oauth2_authorization_server_metadata()
        assert "registration_endpoint" in result
        assert result["registration_endpoint"] == "https://example.com/oauth2/clients"
        assert result["sbd_features"]["client_registration_enabled"] is True
        
        # Test with client registration disabled
        mock_settings.OAUTH2_CLIENT_REGISTRATION_ENABLED = False
        result = await oauth2_authorization_server_metadata()
        assert "registration_endpoint" not in result
        assert result["sbd_features"]["client_registration_enabled"] is False

    @pytest.mark.asyncio
    async def test_oauth2_metadata_endpoint_custom_features(self, mock_settings):
        """Test OAuth2 metadata endpoint includes custom SBD features."""
        from second_brain_database.routes.oauth2.routes import oauth2_authorization_server_metadata
        
        result = await oauth2_authorization_server_metadata()
        
        # Verify custom SBD features
        assert "sbd_oauth2_version" in result
        assert result["sbd_oauth2_version"] == "1.0"
        
        assert "sbd_features" in result
        sbd_features = result["sbd_features"]
        assert "pkce_required" in sbd_features
        assert "client_registration_enabled" in sbd_features
        assert "consent_management_enabled" in sbd_features
        assert "refresh_token_rotation" in sbd_features
        
        assert sbd_features["consent_management_enabled"] is True
        assert sbd_features["refresh_token_rotation"] is True

    @pytest.mark.asyncio
    async def test_oauth2_metadata_endpoint_security_features(self, mock_settings):
        """Test OAuth2 metadata endpoint includes security features."""
        from second_brain_database.routes.oauth2.routes import oauth2_authorization_server_metadata
        
        result = await oauth2_authorization_server_metadata()
        
        # Verify security-related fields
        assert result["token_endpoint_auth_methods_supported"] == ["client_secret_post", "client_secret_basic"]
        assert result["subject_types_supported"] == ["public"]
        assert result["id_token_signing_alg_values_supported"] == ["HS256"]
        assert result["response_modes_supported"] == ["query", "fragment"]
        assert result["token_endpoint_auth_signing_alg_values_supported"] == ["HS256"]

    @pytest.mark.asyncio
    async def test_oauth2_metadata_endpoint_error_handling(self):
        """Test OAuth2 metadata endpoint error handling."""
        from second_brain_database.routes.oauth2.routes import oauth2_authorization_server_metadata
        
        # Mock logger.info to raise an exception to trigger the except block
        with patch('second_brain_database.routes.oauth2.routes.logger') as mock_logger:
            mock_logger.info.side_effect = Exception("Test error")
            
            # Should raise HTTPException on error
            with pytest.raises(HTTPException) as exc_info:
                await oauth2_authorization_server_metadata()
            
            assert exc_info.value.status_code == 500
            assert "Failed to generate authorization server metadata" in str(exc_info.value.detail)


class TestOAuth2ConfigurationValidationIntegration:
    """Test OAuth2 configuration validation in integration scenarios."""

    def test_oauth2_configuration_with_invalid_environment(self):
        """Test OAuth2 configuration handles invalid environment gracefully."""
        # Test with invalid scope format
        with patch.dict(os.environ, {
            "OAUTH2_AVAILABLE_SCOPES": "read:profile,invalid@scope,write:data"
        }):
            with pytest.raises(ValidationError):
                Settings()

    def test_oauth2_configuration_with_missing_required_fields(self):
        """Test OAuth2 configuration with missing required base fields."""
        # Test that OAuth2 config doesn't break when base required fields are missing
        # (This should still fail due to base validation, not OAuth2 validation)
        with patch.dict(os.environ, {
            "SECRET_KEY": "",  # This should trigger base validation error
            "OAUTH2_ENABLED": "true"
        }, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                Settings()
            
            # Should fail on SECRET_KEY validation, not OAuth2
            assert "SECRET_KEY" in str(exc_info.value)

    def test_oauth2_configuration_comprehensive_validation(self):
        """Test comprehensive OAuth2 configuration validation."""
        # Test with all OAuth2 settings configured
        oauth2_env = {
            "SECRET_KEY": "test-secret-key-for-oauth2-testing",
            "FERNET_KEY": "test-fernet-key-for-oauth2-testing-32b",
            "MONGODB_URL": "mongodb://localhost:27017/test",
            "REDIS_URL": "redis://localhost:6379/0",
            "TURNSTILE_SITEKEY": "test-turnstile-sitekey",
            "TURNSTILE_SECRET": "test-turnstile-secret",
            "BASE_URL": "https://oauth2.example.com",
            "OAUTH2_ENABLED": "true",
            "OAUTH2_AUTHORIZATION_CODE_EXPIRE_MINUTES": "5",
            "OAUTH2_ACCESS_TOKEN_EXPIRE_MINUTES": "30",
            "OAUTH2_REFRESH_TOKEN_EXPIRE_DAYS": "7",
            "OAUTH2_REQUIRE_PKCE": "true",
            "OAUTH2_ALLOW_PLAIN_PKCE": "false",
            "OAUTH2_AVAILABLE_SCOPES": "read:profile,write:profile,read:data,write:data,admin",
            "OAUTH2_DEFAULT_SCOPES": "read:profile",
            "OAUTH2_ADMIN_ONLY_SCOPES": "admin",
            "OAUTH2_CLIENT_REGISTRATION_ENABLED": "true",
            "OAUTH2_ISSUER": "https://custom-oauth2.example.com"
        }
        
        with patch.dict(os.environ, oauth2_env):
            settings = Settings()
            
            # Verify all OAuth2 settings are properly configured
            assert settings.OAUTH2_ENABLED is True
            assert settings.OAUTH2_AUTHORIZATION_CODE_EXPIRE_MINUTES == 5
            assert settings.OAUTH2_ACCESS_TOKEN_EXPIRE_MINUTES == 30
            assert settings.OAUTH2_REFRESH_TOKEN_EXPIRE_DAYS == 7
            assert settings.OAUTH2_REQUIRE_PKCE is True
            assert settings.OAUTH2_ALLOW_PLAIN_PKCE is False
            assert settings.OAUTH2_CLIENT_REGISTRATION_ENABLED is True
            assert settings.oauth2_issuer_url == "https://custom-oauth2.example.com"
            
            # Verify scope lists
            assert len(settings.oauth2_available_scopes_list) == 5
            assert "admin" in settings.oauth2_available_scopes_list
            assert settings.oauth2_default_scopes_list == ["read:profile"]
            assert settings.oauth2_admin_only_scopes_list == ["admin"]


if __name__ == "__main__":
    pytest.main([__file__])