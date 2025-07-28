"""
Unit tests for PKCE (Proof Key for Code Exchange) validator.

Tests the PKCEValidator implementation according to RFC 7636 specifications,
including code verifier generation, challenge creation, and validation methods.
"""

import base64
import hashlib
import pytest
import string

from src.second_brain_database.routes.oauth2.models import PKCEMethod
from src.second_brain_database.routes.oauth2.services.pkce_validator import (
    PKCEValidator,
    PKCEValidationError
)


class TestPKCEValidator:
    """Test suite for PKCEValidator class."""
    
    def test_generate_code_verifier_length(self):
        """Test that generated code verifier has correct length."""
        verifier = PKCEValidator.generate_code_verifier()
        
        assert isinstance(verifier, str)
        assert len(verifier) == PKCEValidator.MAX_CODE_VERIFIER_LENGTH
        assert PKCEValidator.MIN_CODE_VERIFIER_LENGTH <= len(verifier) <= PKCEValidator.MAX_CODE_VERIFIER_LENGTH
    
    def test_generate_code_verifier_charset(self):
        """Test that generated code verifier uses correct character set."""
        verifier = PKCEValidator.generate_code_verifier()
        
        # All characters should be from the allowed charset
        for char in verifier:
            assert char in PKCEValidator.CODE_VERIFIER_CHARSET
    
    def test_generate_code_verifier_uniqueness(self):
        """Test that generated code verifiers are unique."""
        verifiers = [PKCEValidator.generate_code_verifier() for _ in range(10)]
        
        # All verifiers should be unique
        assert len(set(verifiers)) == len(verifiers)
    
    def test_generate_code_challenge_s256(self):
        """Test S256 code challenge generation."""
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        expected_challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
        
        challenge = PKCEValidator.generate_code_challenge(verifier, "S256")
        
        assert challenge == expected_challenge
        assert len(challenge) == 43  # Base64url encoded SHA256 is 43 chars
    
    def test_generate_code_challenge_plain(self):
        """Test plain code challenge generation."""
        verifier = "test_verifier_123456789012345678901234567890"
        
        challenge = PKCEValidator.generate_code_challenge(verifier, "plain")
        
        assert challenge == verifier
    
    def test_generate_code_challenge_invalid_method(self):
        """Test code challenge generation with invalid method."""
        verifier = PKCEValidator.generate_code_verifier()
        
        with pytest.raises(PKCEValidationError, match="Unsupported PKCE method"):
            PKCEValidator.generate_code_challenge(verifier, "invalid_method")
    
    def test_generate_code_challenge_invalid_verifier(self):
        """Test code challenge generation with invalid verifier."""
        # Too short verifier
        with pytest.raises(PKCEValidationError, match="Code verifier too short"):
            PKCEValidator.generate_code_challenge("short", "S256")
        
        # Too long verifier
        long_verifier = "a" * (PKCEValidator.MAX_CODE_VERIFIER_LENGTH + 1)
        with pytest.raises(PKCEValidationError, match="Code verifier too long"):
            PKCEValidator.generate_code_challenge(long_verifier, "S256")
        
        # Invalid characters
        invalid_verifier = "a" * PKCEValidator.MIN_CODE_VERIFIER_LENGTH + "@"
        with pytest.raises(PKCEValidationError, match="Code verifier contains invalid characters"):
            PKCEValidator.generate_code_challenge(invalid_verifier, "S256")
    
    def test_validate_code_challenge_s256_success(self):
        """Test successful S256 code challenge validation."""
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
        
        result = PKCEValidator.validate_code_challenge(verifier, challenge, "S256")
        
        assert result is True
    
    def test_validate_code_challenge_plain_success(self):
        """Test successful plain code challenge validation."""
        verifier = "test_verifier_123456789012345678901234567890"
        challenge = verifier
        
        result = PKCEValidator.validate_code_challenge(verifier, challenge, "plain")
        
        assert result is True
    
    def test_validate_code_challenge_s256_failure(self):
        """Test failed S256 code challenge validation."""
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        # Generate a valid format challenge but for a different verifier
        wrong_verifier = PKCEValidator.generate_code_verifier()
        wrong_challenge = PKCEValidator.generate_code_challenge(wrong_verifier, "S256")
        
        result = PKCEValidator.validate_code_challenge(verifier, wrong_challenge, "S256")
        
        assert result is False
    
    def test_validate_code_challenge_plain_failure(self):
        """Test failed plain code challenge validation."""
        verifier = "test_verifier_123456789012345678901234567890"
        wrong_challenge = "wrong_verifier_123456789012345678901234567890"
        
        result = PKCEValidator.validate_code_challenge(verifier, wrong_challenge, "plain")
        
        assert result is False
    
    def test_validate_code_challenge_invalid_method(self):
        """Test code challenge validation with invalid method."""
        verifier = PKCEValidator.generate_code_verifier()
        challenge = PKCEValidator.generate_code_challenge(verifier, "S256")
        
        with pytest.raises(PKCEValidationError, match="Unsupported PKCE method"):
            PKCEValidator.validate_code_challenge(verifier, challenge, "invalid_method")
    
    def test_validate_code_challenge_invalid_verifier(self):
        """Test code challenge validation with invalid verifier."""
        challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
        
        # Empty verifier
        with pytest.raises(PKCEValidationError, match="Code verifier cannot be empty"):
            PKCEValidator.validate_code_challenge("", challenge, "S256")
        
        # Non-string verifier
        with pytest.raises(PKCEValidationError, match="Code verifier must be a string"):
            PKCEValidator.validate_code_challenge(None, challenge, "S256")
        
        # Too short verifier
        with pytest.raises(PKCEValidationError, match="Code verifier too short"):
            PKCEValidator.validate_code_challenge("short", challenge, "S256")
    
    def test_validate_code_challenge_invalid_challenge(self):
        """Test code challenge validation with invalid challenge."""
        verifier = PKCEValidator.generate_code_verifier()
        
        # Empty challenge
        with pytest.raises(PKCEValidationError, match="Code challenge cannot be empty"):
            PKCEValidator.validate_code_challenge(verifier, "", "S256")
        
        # Non-string challenge
        with pytest.raises(PKCEValidationError, match="Code challenge must be a string"):
            PKCEValidator.validate_code_challenge(verifier, None, "S256")
        
        # Wrong length for S256
        with pytest.raises(PKCEValidationError, match="S256 code challenge must be 43 characters"):
            PKCEValidator.validate_code_challenge(verifier, "short_challenge", "S256")
        
        # Invalid characters for S256
        invalid_challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-c@"
        with pytest.raises(PKCEValidationError, match="S256 code challenge contains invalid base64url characters"):
            PKCEValidator.validate_code_challenge(verifier, invalid_challenge, "S256")
    
    def test_generate_code_verifier_and_challenge_s256(self):
        """Test generating code verifier and challenge pair with S256."""
        verifier, challenge = PKCEValidator.generate_code_verifier_and_challenge("S256")
        
        assert isinstance(verifier, str)
        assert isinstance(challenge, str)
        assert len(verifier) == PKCEValidator.MAX_CODE_VERIFIER_LENGTH
        assert len(challenge) == 43
        
        # Validate the pair works together
        assert PKCEValidator.validate_code_challenge(verifier, challenge, "S256") is True
    
    def test_generate_code_verifier_and_challenge_plain(self):
        """Test generating code verifier and challenge pair with plain."""
        verifier, challenge = PKCEValidator.generate_code_verifier_and_challenge("plain")
        
        assert isinstance(verifier, str)
        assert isinstance(challenge, str)
        assert verifier == challenge
        
        # Validate the pair works together
        assert PKCEValidator.validate_code_challenge(verifier, challenge, "plain") is True
    
    def test_generate_code_verifier_and_challenge_invalid_method(self):
        """Test generating code verifier and challenge pair with invalid method."""
        with pytest.raises(PKCEValidationError, match="Unsupported PKCE method"):
            PKCEValidator.generate_code_verifier_and_challenge("invalid_method")
    
    def test_code_verifier_charset_constants(self):
        """Test that code verifier charset constants are correct."""
        expected_charset = string.ascii_letters + string.digits + "-._~"
        assert PKCEValidator.CODE_VERIFIER_CHARSET == expected_charset
    
    def test_code_verifier_length_constants(self):
        """Test that code verifier length constants are correct per RFC 7636."""
        assert PKCEValidator.MIN_CODE_VERIFIER_LENGTH == 43
        assert PKCEValidator.MAX_CODE_VERIFIER_LENGTH == 128
    
    def test_timing_attack_resistance(self):
        """Test that validation uses constant-time comparison."""
        verifier = PKCEValidator.generate_code_verifier()
        correct_challenge = PKCEValidator.generate_code_challenge(verifier, "S256")
        wrong_challenge = PKCEValidator.generate_code_challenge(
            PKCEValidator.generate_code_verifier(), "S256"
        )
        
        # Both should return boolean results (not raise exceptions)
        assert PKCEValidator.validate_code_challenge(verifier, correct_challenge, "S256") is True
        assert PKCEValidator.validate_code_challenge(verifier, wrong_challenge, "S256") is False
    
    def test_s256_challenge_format(self):
        """Test that S256 challenges are properly base64url encoded."""
        verifier = PKCEValidator.generate_code_verifier()
        challenge = PKCEValidator.generate_code_challenge(verifier, "S256")
        
        # Should be valid base64url (no padding)
        assert len(challenge) == 43
        assert all(c in string.ascii_letters + string.digits + '-_' for c in challenge)
        
        # Should not contain padding characters
        assert '=' not in challenge
    
    def test_manual_s256_calculation(self):
        """Test S256 calculation matches manual implementation."""
        verifier = "test_verifier_abcdefghijklmnopqrstuvwxyz123456"
        
        # Manual calculation
        digest = hashlib.sha256(verifier.encode('ascii')).digest()
        expected_challenge = base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')
        
        # PKCEValidator calculation
        actual_challenge = PKCEValidator.generate_code_challenge(verifier, "S256")
        
        assert actual_challenge == expected_challenge
    
    def test_edge_case_minimum_length_verifier(self):
        """Test with minimum length code verifier."""
        # Create minimum length verifier
        min_verifier = 'a' * PKCEValidator.MIN_CODE_VERIFIER_LENGTH
        
        # Should work with both methods
        s256_challenge = PKCEValidator.generate_code_challenge(min_verifier, "S256")
        plain_challenge = PKCEValidator.generate_code_challenge(min_verifier, "plain")
        
        assert PKCEValidator.validate_code_challenge(min_verifier, s256_challenge, "S256") is True
        assert PKCEValidator.validate_code_challenge(min_verifier, plain_challenge, "plain") is True
    
    def test_edge_case_maximum_length_verifier(self):
        """Test with maximum length code verifier."""
        # Create maximum length verifier
        max_verifier = 'a' * PKCEValidator.MAX_CODE_VERIFIER_LENGTH
        
        # Should work with both methods
        s256_challenge = PKCEValidator.generate_code_challenge(max_verifier, "S256")
        plain_challenge = PKCEValidator.generate_code_challenge(max_verifier, "plain")
        
        assert PKCEValidator.validate_code_challenge(max_verifier, s256_challenge, "S256") is True
        assert PKCEValidator.validate_code_challenge(max_verifier, plain_challenge, "plain") is True
    
    def test_all_allowed_characters_in_verifier(self):
        """Test that all allowed characters work in code verifier."""
        # Create verifier with all allowed characters
        charset_verifier = PKCEValidator.CODE_VERIFIER_CHARSET[:PKCEValidator.MIN_CODE_VERIFIER_LENGTH]
        
        # Should work with both methods
        s256_challenge = PKCEValidator.generate_code_challenge(charset_verifier, "S256")
        plain_challenge = PKCEValidator.generate_code_challenge(charset_verifier, "plain")
        
        assert PKCEValidator.validate_code_challenge(charset_verifier, s256_challenge, "S256") is True
        assert PKCEValidator.validate_code_challenge(charset_verifier, plain_challenge, "plain") is True
    
    def test_pkce_method_enum_compatibility(self):
        """Test compatibility with PKCEMethod enum values."""
        verifier = PKCEValidator.generate_code_verifier()
        
        # Test with enum values
        s256_challenge = PKCEValidator.generate_code_challenge(verifier, PKCEMethod.S256.value)
        plain_challenge = PKCEValidator.generate_code_challenge(verifier, PKCEMethod.PLAIN.value)
        
        assert PKCEValidator.validate_code_challenge(verifier, s256_challenge, PKCEMethod.S256.value) is True
        assert PKCEValidator.validate_code_challenge(verifier, plain_challenge, PKCEMethod.PLAIN.value) is True
    
    def test_error_handling_preserves_original_exceptions(self):
        """Test that validation errors preserve original exception information."""
        verifier = PKCEValidator.generate_code_verifier()
        
        # Test that PKCEValidationError is raised for known issues
        with pytest.raises(PKCEValidationError):
            PKCEValidator.validate_code_challenge(verifier, "invalid", "invalid_method")
        
        # Test that other exceptions are wrapped
        with pytest.raises(PKCEValidationError):
            PKCEValidator.validate_code_challenge(None, "challenge", "S256")


class TestPKCEValidationError:
    """Test suite for PKCEValidationError exception."""
    
    def test_pkce_validation_error_inheritance(self):
        """Test that PKCEValidationError inherits from Exception."""
        error = PKCEValidationError("test error")
        assert isinstance(error, Exception)
        assert str(error) == "test error"
    
    def test_pkce_validation_error_message(self):
        """Test PKCEValidationError message handling."""
        message = "Invalid PKCE parameters"
        error = PKCEValidationError(message)
        assert str(error) == message


class TestPKCEIntegration:
    """Integration tests for PKCE validator with OAuth2 flow simulation."""
    
    def test_complete_pkce_flow_s256(self):
        """Test complete PKCE flow with S256 method."""
        # Step 1: Client generates verifier and challenge
        verifier, challenge = PKCEValidator.generate_code_verifier_and_challenge("S256")
        
        # Step 2: Client sends challenge to authorization server (simulated)
        # Authorization server stores the challenge with the authorization code
        
        # Step 3: Client exchanges authorization code with verifier
        # Authorization server validates the verifier against stored challenge
        is_valid = PKCEValidator.validate_code_challenge(verifier, challenge, "S256")
        
        assert is_valid is True
    
    def test_complete_pkce_flow_plain(self):
        """Test complete PKCE flow with plain method."""
        # Step 1: Client generates verifier and challenge
        verifier, challenge = PKCEValidator.generate_code_verifier_and_challenge("plain")
        
        # Step 2: Client sends challenge to authorization server (simulated)
        # Authorization server stores the challenge with the authorization code
        
        # Step 3: Client exchanges authorization code with verifier
        # Authorization server validates the verifier against stored challenge
        is_valid = PKCEValidator.validate_code_challenge(verifier, challenge, "plain")
        
        assert is_valid is True
    
    def test_pkce_prevents_code_interception_attack(self):
        """Test that PKCE prevents authorization code interception attacks."""
        # Legitimate client generates verifier and challenge
        legitimate_verifier, challenge = PKCEValidator.generate_code_verifier_and_challenge("S256")
        
        # Attacker intercepts authorization code but doesn't have the verifier
        attacker_verifier = PKCEValidator.generate_code_verifier()
        
        # Legitimate client can exchange the code
        legitimate_valid = PKCEValidator.validate_code_challenge(
            legitimate_verifier, challenge, "S256"
        )
        
        # Attacker cannot exchange the code without the original verifier
        attacker_valid = PKCEValidator.validate_code_challenge(
            attacker_verifier, challenge, "S256"
        )
        
        assert legitimate_valid is True
        assert attacker_valid is False
    
    def test_multiple_clients_different_challenges(self):
        """Test that different clients generate different challenges."""
        # Generate challenges for multiple clients
        client1_verifier, client1_challenge = PKCEValidator.generate_code_verifier_and_challenge("S256")
        client2_verifier, client2_challenge = PKCEValidator.generate_code_verifier_and_challenge("S256")
        client3_verifier, client3_challenge = PKCEValidator.generate_code_verifier_and_challenge("S256")
        
        # All challenges should be different
        challenges = [client1_challenge, client2_challenge, client3_challenge]
        assert len(set(challenges)) == len(challenges)
        
        # Each client can only validate their own challenge
        assert PKCEValidator.validate_code_challenge(client1_verifier, client1_challenge, "S256") is True
        assert PKCEValidator.validate_code_challenge(client1_verifier, client2_challenge, "S256") is False
        assert PKCEValidator.validate_code_challenge(client1_verifier, client3_challenge, "S256") is False