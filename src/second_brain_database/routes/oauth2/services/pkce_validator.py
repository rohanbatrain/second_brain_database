"""
PKCE (Proof Key for Code Exchange) validator implementation.

This module implements PKCE validation as specified in RFC 7636 to prevent
authorization code interception attacks in OAuth2 flows. It supports both
S256 (SHA256) and plain text code challenge methods.
"""

import base64
import hashlib
import secrets
import string
from typing import Tuple

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.oauth2.models import PKCEMethod

logger = get_logger(prefix="[PKCE Validator]")


class PKCEValidationError(Exception):
    """Exception raised when PKCE validation fails."""
    pass


class PKCEValidator:
    """
    PKCE (Proof Key for Code Exchange) validation implementation.
    
    Provides methods for generating and validating PKCE code verifiers and challenges
    according to RFC 7636 specifications. Supports both S256 (SHA256) and plain text
    challenge methods.
    """
    
    # RFC 7636 specifies code verifier length requirements
    MIN_CODE_VERIFIER_LENGTH = 43
    MAX_CODE_VERIFIER_LENGTH = 128
    
    # Character set for code verifier generation (RFC 7636)
    CODE_VERIFIER_CHARSET = string.ascii_letters + string.digits + "-._~"
    
    @staticmethod
    def generate_code_verifier() -> str:
        """
        Generate a cryptographically secure code verifier.
        
        Creates a random string of 128 characters using the character set
        specified in RFC 7636: [A-Z] / [a-z] / [0-9] / "-" / "." / "_" / "~"
        
        Returns:
            str: A secure code verifier string
            
        Example:
            >>> verifier = PKCEValidator.generate_code_verifier()
            >>> len(verifier)
            128
            >>> all(c in PKCEValidator.CODE_VERIFIER_CHARSET for c in verifier)
            True
        """
        logger.debug("Generating new PKCE code verifier")
        
        # Generate maximum length verifier for best security
        verifier = ''.join(
            secrets.choice(PKCEValidator.CODE_VERIFIER_CHARSET) 
            for _ in range(PKCEValidator.MAX_CODE_VERIFIER_LENGTH)
        )
        
        logger.debug(f"Generated code verifier of length {len(verifier)}")
        return verifier
    
    @staticmethod
    def generate_code_challenge(verifier: str, method: str = "S256") -> str:
        """
        Generate a code challenge from a code verifier.
        
        Creates a code challenge using the specified method:
        - S256: SHA256 hash of the verifier, base64url-encoded
        - plain: The verifier itself (not recommended for production)
        
        Args:
            verifier: The code verifier string
            method: Challenge method ("S256" or "plain")
            
        Returns:
            str: The code challenge string
            
        Raises:
            PKCEValidationError: If the method is unsupported or verifier is invalid
            
        Example:
            >>> verifier = PKCEValidator.generate_code_verifier()
            >>> challenge = PKCEValidator.generate_code_challenge(verifier, "S256")
            >>> len(challenge) == 43  # Base64url encoded SHA256 is 43 chars
            True
        """
        logger.debug(f"Generating code challenge using method: {method}")
        
        # Validate method
        if method not in [PKCEMethod.S256.value, PKCEMethod.PLAIN.value]:
            error_msg = f"Unsupported PKCE method: {method}"
            logger.error(error_msg)
            raise PKCEValidationError(error_msg)
        
        # Validate verifier
        PKCEValidator._validate_code_verifier(verifier)
        
        if method == PKCEMethod.S256.value:
            # SHA256 hash the verifier and base64url encode
            digest = hashlib.sha256(verifier.encode('ascii')).digest()
            challenge = base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')
            logger.debug("Generated S256 code challenge")
        else:  # plain method
            challenge = verifier
            logger.debug("Generated plain code challenge")
        
        return challenge
    
    @staticmethod
    def validate_code_challenge(verifier: str, challenge: str, method: str) -> bool:
        """
        Validate a code verifier against a code challenge.
        
        Verifies that the provided code verifier matches the code challenge
        using the specified method. This is used during token exchange to
        ensure the client that initiated the authorization flow is the same
        one exchanging the authorization code.
        
        Args:
            verifier: The code verifier provided by the client
            challenge: The code challenge from the authorization request
            method: The challenge method used ("S256" or "plain")
            
        Returns:
            bool: True if the verifier matches the challenge, False otherwise
            
        Raises:
            PKCEValidationError: If the method is unsupported or parameters are invalid
            
        Example:
            >>> verifier = PKCEValidator.generate_code_verifier()
            >>> challenge = PKCEValidator.generate_code_challenge(verifier, "S256")
            >>> PKCEValidator.validate_code_challenge(verifier, challenge, "S256")
            True
            >>> PKCEValidator.validate_code_challenge("wrong", challenge, "S256")
            False
        """
        logger.debug(f"Validating code challenge using method: {method}")
        
        try:
            # Validate method
            if method not in [PKCEMethod.S256.value, PKCEMethod.PLAIN.value]:
                error_msg = f"Unsupported PKCE method: {method}"
                logger.error(error_msg)
                raise PKCEValidationError(error_msg)
            
            # Validate verifier
            PKCEValidator._validate_code_verifier(verifier)
            
            # Validate challenge
            PKCEValidator._validate_code_challenge(challenge, method)
            
            # Generate expected challenge from verifier
            expected_challenge = PKCEValidator.generate_code_challenge(verifier, method)
            
            # Constant-time comparison to prevent timing attacks
            is_valid = secrets.compare_digest(challenge, expected_challenge)
            
            if is_valid:
                logger.debug("PKCE validation successful")
            else:
                logger.warning("PKCE validation failed - challenge mismatch")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"PKCE validation error: {str(e)}")
            if isinstance(e, PKCEValidationError):
                raise
            raise PKCEValidationError(f"PKCE validation failed: {str(e)}")
    
    @staticmethod
    def generate_code_verifier_and_challenge(method: str = "S256") -> Tuple[str, str]:
        """
        Generate a code verifier and corresponding challenge pair.
        
        Convenience method that generates both the code verifier and challenge
        in one call. Useful for testing and client implementations.
        
        Args:
            method: Challenge method to use ("S256" or "plain")
            
        Returns:
            Tuple[str, str]: (code_verifier, code_challenge)
            
        Raises:
            PKCEValidationError: If the method is unsupported
            
        Example:
            >>> verifier, challenge = PKCEValidator.generate_code_verifier_and_challenge("S256")
            >>> PKCEValidator.validate_code_challenge(verifier, challenge, "S256")
            True
        """
        logger.debug(f"Generating code verifier and challenge pair with method: {method}")
        
        verifier = PKCEValidator.generate_code_verifier()
        challenge = PKCEValidator.generate_code_challenge(verifier, method)
        
        logger.debug("Generated code verifier and challenge pair")
        return verifier, challenge
    
    @staticmethod
    def _validate_code_verifier(verifier: str) -> None:
        """
        Validate a code verifier according to RFC 7636 requirements.
        
        Args:
            verifier: The code verifier to validate
            
        Raises:
            PKCEValidationError: If the verifier is invalid
        """
        if not verifier:
            raise PKCEValidationError("Code verifier cannot be empty")
        
        if not isinstance(verifier, str):
            raise PKCEValidationError("Code verifier must be a string")
        
        # Check length requirements
        if len(verifier) < PKCEValidator.MIN_CODE_VERIFIER_LENGTH:
            raise PKCEValidationError(
                f"Code verifier too short. Minimum length: {PKCEValidator.MIN_CODE_VERIFIER_LENGTH}"
            )
        
        if len(verifier) > PKCEValidator.MAX_CODE_VERIFIER_LENGTH:
            raise PKCEValidationError(
                f"Code verifier too long. Maximum length: {PKCEValidator.MAX_CODE_VERIFIER_LENGTH}"
            )
        
        # Check character set
        invalid_chars = set(verifier) - set(PKCEValidator.CODE_VERIFIER_CHARSET)
        if invalid_chars:
            raise PKCEValidationError(
                f"Code verifier contains invalid characters: {invalid_chars}"
            )
    
    @staticmethod
    def _validate_code_challenge(challenge: str, method: str) -> None:
        """
        Validate a code challenge according to RFC 7636 requirements.
        
        Args:
            challenge: The code challenge to validate
            method: The challenge method ("S256" or "plain")
            
        Raises:
            PKCEValidationError: If the challenge is invalid
        """
        if not challenge:
            raise PKCEValidationError("Code challenge cannot be empty")
        
        if not isinstance(challenge, str):
            raise PKCEValidationError("Code challenge must be a string")
        
        if method == PKCEMethod.S256.value:
            # S256 challenges should be 43 characters (base64url encoded SHA256)
            if len(challenge) != 43:
                raise PKCEValidationError(
                    f"S256 code challenge must be 43 characters, got {len(challenge)}"
                )
            
            # Check base64url character set
            base64url_chars = set(string.ascii_letters + string.digits + '-_')
            invalid_chars = set(challenge) - base64url_chars
            if invalid_chars:
                raise PKCEValidationError(
                    f"S256 code challenge contains invalid base64url characters: {invalid_chars}"
                )
        
        elif method == PKCEMethod.PLAIN.value:
            # Plain challenges have same requirements as verifiers
            PKCEValidator._validate_code_verifier(challenge)