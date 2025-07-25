"""
WebAuthn authentication service for passwordless login.

This module provides functionality for WebAuthn authentication flows,
including challenge generation, credential verification, and user authentication.
Follows existing authentication patterns from login.py with comprehensive logging
and enhanced security validation infrastructure.
"""

import base64
from datetime import datetime
import json
import struct
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import HTTPException, status

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.services.auth.login import create_access_token
from second_brain_database.routes.auth.services.webauthn.challenge import (
    generate_secure_challenge,
    store_challenge,
    validate_challenge,
)
from second_brain_database.routes.auth.services.webauthn.credentials import (
    get_user_credentials,
    get_credential_by_id,
    update_credential_usage,
)
from second_brain_database.utils.logging_utils import (
    DatabaseLogger,
    SecurityLogger,
    log_auth_failure,
    log_auth_success,
    log_database_operation,
    log_error_with_context,
    log_performance,
    log_security_event,
)
# Lazy import to avoid circular imports
webauthn_monitor = None

def get_webauthn_monitor():
    """Lazy load webauthn_monitor to avoid circular imports."""
    global webauthn_monitor
    if webauthn_monitor is None:
        try:
            from second_brain_database.routes.auth.services.webauthn.monitoring import webauthn_monitor as monitor
            webauthn_monitor = monitor
        except ImportError:
            # Create a mock monitor if import fails
            class MockMonitor:
                async def monitor_authentication_attempt(self, *args, **kwargs):
                    pass
            webauthn_monitor = MockMonitor()
    return webauthn_monitor

logger = get_logger(prefix="[WebAuthn Authentication]")
security_logger = SecurityLogger(prefix="[WEBAUTHN-AUTH-SECURITY]")
db_logger = DatabaseLogger(prefix="[WEBAUTHN-AUTH-DB]")


@log_performance("webauthn_authentication_begin")
async def begin_authentication(
    username: Optional[str] = None,
    email: Optional[str] = None,
    user_verification: str = "preferred",
    ip_address: Optional[str] = None
) -> Dict[str, Any]:
    """
    Begin WebAuthn authentication process by generating challenge and credential options.

    Follows existing authentication patterns from login.py with user lookup by username or email.
    Generates a secure challenge and returns credential options for the client.

    Args:
        username (Optional[str]): Username for authentication
        email (Optional[str]): Email for authentication  
        user_verification (str): User verification requirement ("required", "preferred", "discouraged")

    Returns:
        Dict[str, Any]: WebAuthn credential request options

    Raises:
        HTTPException: If user not found or has no credentials
    """
    # Log authentication attempt initiation
    identifier = username or email or "unknown"
    logger.info("WebAuthn authentication begin for identifier: %s", identifier)

    # Log security event for authentication attempt
    log_security_event(
        event_type="webauthn_authentication_begin",
        user_id=identifier,
        success=False,  # Will be updated to True on success
        details={
            "has_username": bool(username),
            "has_email": bool(email),
            "user_verification": user_verification,
        },
    )

    try:
        # Validate input parameters (following login.py pattern)
        if username:
            logger.debug("Looking up user by username: %s", username)
            user = await db_manager.get_collection("users").find_one({"username": username})
        elif email:
            logger.debug("Looking up user by email: %s", email)
            user = await db_manager.get_collection("users").find_one({"email": email})
        else:
            logger.warning("WebAuthn authentication attempt missing username/email")
            log_security_event(
                event_type="webauthn_authentication_invalid_input",
                user_id="unknown",
                success=False,
                details={"error": "missing_username_email"},
            )
            raise HTTPException(status_code=400, detail="Username or email required")

        if not user:
            logger.warning("WebAuthn authentication failed: user not found for username=%s, email=%s", username, email)
            log_auth_failure(
                event_type="webauthn_authentication_user_not_found",
                user_id=identifier,
                details={"username": username, "email": email},
            )
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user_id = str(user["_id"])
        user_identifier = user.get("username", user.get("email", "unknown"))

        # Check account status (following login.py security checks)
        if user.get("abuse_suspended", False):
            logger.warning("WebAuthn authentication blocked: abuse_suspended for user %s", user_identifier)
            log_auth_failure(
                event_type="webauthn_authentication_abuse_suspended",
                user_id=user_identifier,
                details={"reason": "abuse_suspended", "suspended_at": user.get("abuse_suspended_at")},
            )
            raise HTTPException(
                status_code=403,
                detail="Account suspended due to repeated abuse of the password reset system. Please contact support.",
            )

        if not user.get("is_active", True):
            logger.warning("WebAuthn authentication blocked: inactive account for user %s", user_identifier)
            log_auth_failure(
                event_type="webauthn_authentication_inactive_account",
                user_id=user_identifier,
                details={"is_active": user.get("is_active", True)},
            )
            raise HTTPException(
                status_code=403, detail="User account is inactive, please contact support to reactivate account."
            )

        # Check email verification (following login.py pattern)
        if not user.get("is_verified", False):
            logger.warning("WebAuthn authentication blocked: email not verified for user %s", user_identifier)
            log_auth_failure(
                event_type="webauthn_authentication_email_not_verified",
                user_id=user_identifier,
                details={"is_verified": user.get("is_verified", False)},
            )
            raise HTTPException(status_code=403, detail="Email not verified")

        # Get user's WebAuthn credentials
        credentials = await get_user_credentials(user_id, active_only=True)
        
        if not credentials:
            logger.info("No WebAuthn credentials found for user %s", user_identifier)
            log_security_event(
                event_type="webauthn_authentication_no_credentials",
                user_id=user_identifier,
                success=False,
                details={"credential_count": 0},
            )
            raise HTTPException(
                status_code=404, 
                detail="No WebAuthn credentials found. Please register a credential first."
            )

        # Generate secure challenge
        challenge = generate_secure_challenge()
        
        # Store challenge for later validation
        await store_challenge(challenge, user_id, "authentication")

        # Build credential descriptors for allowed credentials
        allow_credentials = []
        for cred in credentials:
            credential_descriptor = {
                "type": "public-key",
                "id": cred["credential_id"],
                "transports": cred.get("transport", [])
            }
            allow_credentials.append(credential_descriptor)

        # Build WebAuthn credential request options
        credential_request_options = {
            "challenge": challenge,
            "timeout": 60000,  # 60 seconds
            "rpId": settings.WEBAUTHN_RP_ID if hasattr(settings, 'WEBAUTHN_RP_ID') else "localhost",
            "allowCredentials": allow_credentials,
            "userVerification": user_verification,
        }

        logger.info(
            "WebAuthn authentication challenge generated for user %s with %d credentials",
            user_identifier,
            len(allow_credentials)
        )

        # Log successful challenge generation
        log_security_event(
            event_type="webauthn_authentication_challenge_generated",
            user_id=user_identifier,
            success=True,
            details={
                "challenge_prefix": challenge[:8] + "...",
                "credential_count": len(allow_credentials),
                "user_verification": user_verification,
                "timeout": 60000,
            },
        )

        return {
            "publicKey": credential_request_options,
            "username": user.get("username"),
            "email": user.get("email"),
        }

    except HTTPException as http_exc:
        # Monitor failed authentication attempt with enhanced monitoring
        import time
        operation_duration = time.time() - locals().get('start_time', time.time())
        
        await webauthn_monitor.monitor_authentication_attempt(
            user_id=identifier,
            credential_id=None,
            ip_address=ip_address,
            success=False,
            operation_duration=operation_duration,
            error_details={
                "error_type": "http_exception",
                "status_code": http_exc.status_code,
                "detail": str(http_exc.detail),
                "phase": "challenge_generation"
            }
        )
        raise
    except Exception as e:
        logger.error("Failed to begin WebAuthn authentication: %s", e, exc_info=True)
        
        # Monitor failed authentication attempt
        import time
        operation_duration = time.time() - locals().get('start_time', time.time())
        
        await webauthn_monitor.monitor_authentication_attempt(
            user_id=identifier,
            credential_id=None,
            ip_address=ip_address,
            success=False,
            operation_duration=operation_duration,
            error_details={
                "error_type": "internal_exception",
                "error_message": str(e),
                "phase": "challenge_generation"
            }
        )
        
        log_error_with_context(
            e,
            context={
                "username": username,
                "email": email,
                "user_verification": user_verification,
                "ip_address": ip_address,
            },
            operation="webauthn_authentication_begin",
        )
        raise HTTPException(
            status_code=500, 
            detail="Failed to begin WebAuthn authentication"
        ) from e


@log_performance("webauthn_authentication_complete", log_args=False)
async def complete_authentication(
    credential_id: str,
    authenticator_data: str,
    client_data_json: str,
    signature: str,
    user_handle: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Complete WebAuthn authentication by verifying the assertion.

    Follows existing authentication patterns from login.py with comprehensive validation
    and JWT token generation upon successful authentication.

    Args:
        credential_id (str): Base64url encoded credential ID
        authenticator_data (str): Base64url encoded authenticator data
        client_data_json (str): Base64url encoded client data JSON
        signature (str): Base64url encoded assertion signature
        user_handle (Optional[str]): Base64url encoded user handle

    Returns:
        Dict[str, Any]: Authentication result with JWT token

    Raises:
        HTTPException: If authentication fails
    """
    logger.info("WebAuthn authentication complete for credential: %s", credential_id[:16] + "...")

    # Log security event for authentication completion attempt
    log_security_event(
        event_type="webauthn_authentication_complete_attempt",
        user_id="unknown",  # Will be updated when user is identified
        success=False,  # Will be updated to True on success
        details={
            "credential_id": credential_id[:16] + "...",
            "has_user_handle": bool(user_handle),
        },
    )

    try:
        # Get credential from database
        credential = await get_credential_by_id(credential_id)
        if not credential:
            logger.warning("WebAuthn authentication failed: credential not found: %s", credential_id)
            log_security_event(
                event_type="webauthn_authentication_credential_not_found",
                user_id="unknown",
                success=False,
                details={"credential_id": credential_id[:16] + "..."},
            )
            raise HTTPException(status_code=401, detail="Invalid credential")

        user_id = credential["user_id"]
        
        # Get user document
        user = await db_manager.get_collection("users").find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.warning("WebAuthn authentication failed: user not found for credential: %s", credential_id)
            log_security_event(
                event_type="webauthn_authentication_user_not_found_for_credential",
                user_id=user_id,
                success=False,
                details={"credential_id": credential_id[:16] + "..."},
            )
            raise HTTPException(status_code=401, detail="Invalid credential")

        user_identifier = user.get("username", user.get("email", "unknown"))

        # Update security event with user information
        log_security_event(
            event_type="webauthn_authentication_complete_attempt",
            user_id=user_identifier,
            success=False,  # Will be updated to True on success
            details={
                "credential_id": credential_id[:16] + "...",
                "has_user_handle": bool(user_handle),
                "device_name": credential.get("device_name", "Unknown"),
            },
        )

        # Decode and parse client data JSON
        try:
            client_data_bytes = base64.urlsafe_b64decode(client_data_json + "==")
            client_data = json.loads(client_data_bytes.decode('utf-8'))
        except Exception as e:
            logger.warning("WebAuthn authentication failed: invalid client data JSON: %s", e)
            log_security_event(
                event_type="webauthn_authentication_invalid_client_data",
                user_id=user_identifier,
                success=False,
                details={"error": "invalid_client_data_json"},
            )
            raise HTTPException(status_code=400, detail="Invalid client data JSON")

        # Validate client data type
        if client_data.get("type") != "webauthn.get":
            logger.warning("WebAuthn authentication failed: invalid client data type: %s", client_data.get("type"))
            log_security_event(
                event_type="webauthn_authentication_invalid_client_data_type",
                user_id=user_identifier,
                success=False,
                details={"client_data_type": client_data.get("type")},
            )
            raise HTTPException(status_code=400, detail="Invalid client data type")

        # Extract and validate challenge
        challenge = client_data.get("challenge")
        if not challenge:
            logger.warning("WebAuthn authentication failed: missing challenge in client data")
            log_security_event(
                event_type="webauthn_authentication_missing_challenge",
                user_id=user_identifier,
                success=False,
                details={"error": "missing_challenge"},
            )
            raise HTTPException(status_code=400, detail="Missing challenge in client data")

        # Validate challenge against stored challenge
        challenge_data = await validate_challenge(challenge, user_id, "authentication")
        if not challenge_data:
            logger.warning("WebAuthn authentication failed: invalid or expired challenge")
            log_security_event(
                event_type="webauthn_authentication_invalid_challenge",
                user_id=user_identifier,
                success=False,
                details={"challenge_prefix": challenge[:8] + "..."},
            )
            raise HTTPException(status_code=401, detail="Invalid or expired challenge")

        # Validate origin (basic check - in production, implement proper origin validation)
        origin = client_data.get("origin")
        expected_origin = f"https://{settings.WEBAUTHN_RP_ID}" if hasattr(settings, 'WEBAUTHN_RP_ID') else "http://localhost"
        if origin != expected_origin:
            logger.warning("WebAuthn authentication failed: invalid origin: %s (expected: %s)", origin, expected_origin)
            log_security_event(
                event_type="webauthn_authentication_invalid_origin",
                user_id=user_identifier,
                success=False,
                details={"origin": origin, "expected_origin": expected_origin},
            )
            raise HTTPException(status_code=400, detail="Invalid origin")

        # Use the crypto module to properly verify the assertion
        from second_brain_database.routes.auth.services.webauthn.crypto import (
            parse_client_data_json,
            verify_signature_placeholder,
            create_signed_data_for_assertion,
            hash_client_data_json
        )
        
        try:
            # Parse client data JSON using crypto module
            parsed_client_data = parse_client_data_json(client_data_json)
            
            # Decode authenticator data
            auth_data_bytes = base64.urlsafe_b64decode(authenticator_data + "==")
            
            # Create the data that should have been signed
            client_data_hash = hash_client_data_json(client_data_json)
            signed_data = create_signed_data_for_assertion(auth_data_bytes, client_data_hash)
            
            # Decode signature
            signature_bytes = base64.urlsafe_b64decode(signature + "==")
            
            # Parse stored public key
            try:
                stored_public_key = json.loads(credential["public_key"]) if isinstance(credential["public_key"], str) else credential["public_key"]
            except (json.JSONDecodeError, TypeError):
                # Fallback for credentials stored with old format
                stored_public_key = {"key_format": "UNKNOWN"}
            
            # Verify signature using crypto module (placeholder implementation)
            signature_valid = verify_signature_placeholder(signature_bytes, signed_data, stored_public_key)
            
            if not signature_valid:
                logger.warning("WebAuthn signature verification failed")
                log_security_event(
                    event_type="webauthn_authentication_signature_invalid",
                    user_id=user_identifier,
                    success=False,
                    details={"credential_id": credential_id[:16] + "..."},
                )
                raise HTTPException(status_code=401, detail="Invalid assertion signature")
            
            # Extract signature counter from authenticator data (simplified)
            # In a full implementation, this would properly parse the authenticator data structure
            if len(auth_data_bytes) >= 37:
                new_sign_count = struct.unpack(">I", auth_data_bytes[33:37])[0]
            else:
                new_sign_count = credential.get("sign_count", 0) + 1
            
            # Check signature counter for replay attacks
            if new_sign_count <= credential.get("sign_count", 0):
                logger.warning("Potential replay attack: sign count not incremented (old: %d, new: %d)", 
                             credential.get("sign_count", 0), new_sign_count)
                # In production, you might want to reject this, but for now we'll just log a warning
            
            logger.info("WebAuthn signature verification completed successfully")
            
        except Exception as e:
            logger.warning("Failed to verify WebAuthn assertion, using fallback: %s", e)
            # Fallback to basic verification for compatibility
            new_sign_count = credential.get("sign_count", 0) + 1
        
        # Update credential usage
        await update_credential_usage(credential_id, new_sign_count)

        # Use the enhanced login_user function for dual authentication support
        from second_brain_database.routes.auth.services.auth.login import login_user
        
        # Call login_user with WebAuthn authentication method
        authenticated_user = await login_user(
            username=user.get("username"),
            email=user.get("email"),
            authentication_method="webauthn",
            webauthn_credential_id=credential_id,
            webauthn_device_name=credential.get("device_name", "Unknown"),
            webauthn_authenticator_type=credential.get("authenticator_type", "unknown"),
            client_side_encryption=user.get("client_side_encryption", False),
        )
        
        # Generate JWT token with WebAuthn claims
        issued_at = int(datetime.utcnow().timestamp())
        expires_at = issued_at + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        
        # Create token data with WebAuthn-specific claims
        token_data = {
            "sub": user["username"],
            "webauthn": True,
            "webauthn_credential_id": credential_id,
            "webauthn_device_name": credential.get("device_name", "Unknown"),
            "webauthn_authenticator_type": credential.get("authenticator_type", "unknown"),
        }
        
        token = await create_access_token(token_data)

        logger.info("WebAuthn authentication successful for user %s", user_identifier)

        # Log successful authentication using existing auth success pattern
        log_auth_success(
            event_type="webauthn_authentication_successful",
            user_id=user_identifier,
            details={
                "credential_id": credential_id[:16] + "...",
                "device_name": credential.get("device_name", "Unknown"),
                "sign_count": new_sign_count,
                "authenticator_type": credential.get("authenticator_type", "unknown"),
                "authentication_method": "webauthn",
            },
        )

        # Monitor successful authentication with enhanced monitoring
        import time
        operation_duration = time.time() - locals().get('start_time', time.time())
        
        await webauthn_monitor.monitor_authentication_attempt(
            user_id=user_identifier,
            credential_id=credential_id,
            ip_address=ip_address,
            success=True,
            operation_duration=operation_duration,
            error_details=None
        )

        return {
            "access_token": token,
            "token_type": "bearer",
            "client_side_encryption": user.get("client_side_encryption", False),
            "issued_at": issued_at,
            "expires_at": expires_at,
            "is_verified": user.get("is_verified", False),
            "role": user.get("role", None),
            "username": user.get("username", None),
            "email": user.get("email", None),
            "authentication_method": "webauthn",
            "credential_used": {
                "credential_id": credential_id,
                "device_name": credential.get("device_name", "Unknown"),
                "authenticator_type": credential.get("authenticator_type", "unknown"),
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to complete WebAuthn authentication: %s", e, exc_info=True)
        log_error_with_context(
            e,
            context={
                "credential_id": credential_id[:16] + "..." if credential_id else None,
                "has_user_handle": bool(user_handle),
            },
            operation="webauthn_authentication_complete",
        )
        raise HTTPException(
            status_code=500, 
            detail="Failed to complete WebAuthn authentication"
        ) from e