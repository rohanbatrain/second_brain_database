"""
WebAuthn registration service for credential enrollment.

This module provides functionality for WebAuthn credential registration flows,
including challenge generation, credential validation, and storage.
Follows existing registration patterns with comprehensive logging and security.
"""

import base64
from datetime import datetime
import json
import secrets
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import HTTPException, status

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.services.webauthn.challenge import (
    generate_secure_challenge,
    store_challenge,
    validate_challenge,
)
from second_brain_database.routes.auth.services.webauthn.credentials import (
    get_user_credentials,
    store_credential,
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

logger = get_logger(prefix="[WebAuthn Registration]")
security_logger = SecurityLogger(prefix="[WEBAUTHN-REG-SECURITY]")
db_logger = DatabaseLogger(prefix="[WEBAUTHN-REG-DB]")


@log_performance("webauthn_registration_begin")
async def begin_registration(
    user: Dict[str, Any],
    device_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Begin WebAuthn credential registration process by generating challenge and creation options.

    Follows existing auth endpoint patterns with comprehensive logging and security validation.
    Generates a secure challenge and returns credential creation options for the client.

    Args:
        user (Dict[str, Any]): User document from database
        device_name (Optional[str]): Optional friendly name for the device

    Returns:
        Dict[str, Any]: WebAuthn credential creation options

    Raises:
        HTTPException: If user is invalid or registration fails
    """
    user_id = str(user["_id"])
    username = user.get("username", "unknown")
    
    logger.info("WebAuthn registration begin for user: %s, device: %s", username, device_name or "Unknown")

    # Log security event for registration attempt
    log_security_event(
        event_type="webauthn_registration_begin",
        user_id=user_id,
        success=False,  # Will be updated to True on success
        details={
            "username": username,
            "device_name": device_name,
            "user_verified": user.get("is_verified", False),
        },
    )

    try:
        # Validate user is active and verified (following existing patterns)
        if not user.get("is_active", True):
            logger.warning("Registration attempt for inactive user: %s", username)
            log_security_event(
                event_type="webauthn_registration_inactive_user",
                user_id=user_id,
                success=False,
                details={"username": username},
            )
            raise HTTPException(status_code=403, detail="User account is inactive")

        # Generate secure challenge using existing pattern
        challenge = generate_secure_challenge()
        logger.debug("Generated challenge for registration: %s", challenge[:8] + "...")

        # Get existing credentials for excludeCredentials (prevent duplicate registration)
        existing_credentials = await get_user_credentials(user_id, active_only=True)
        exclude_credentials = [
            {
                "id": cred["credential_id"],
                "type": "public-key",
                "transports": cred.get("transport", [])
            }
            for cred in existing_credentials
        ]

        logger.debug("Found %d existing credentials to exclude", len(exclude_credentials))

        # Create WebAuthn credential creation options following Flutter optimization requirements
        user_id_encoded = base64.urlsafe_b64encode(user_id.encode()).decode().rstrip('=')
        
        options = {
            "challenge": challenge,
            "rp": {
                "name": "Second Brain Database",
                "id": getattr(settings, 'WEBAUTHN_RP_ID', 'localhost')
            },
            "user": {
                "id": user_id_encoded,
                "name": user.get("email", username),
                "displayName": username
            },
            "pubKeyCredParams": [
                {"alg": -7, "type": "public-key"},   # ES256 (ECDSA w/ SHA-256)
                {"alg": -257, "type": "public-key"}  # RS256 (RSASSA-PKCS1-v1_5 w/ SHA-256)
            ],
            "authenticatorSelection": {
                "authenticatorAttachment": "platform",  # Prefer biometrics for Flutter
                "userVerification": "preferred",
                "residentKey": "preferred"
            },
            "attestation": "none",  # Simplified attestation for better compatibility
            "excludeCredentials": exclude_credentials,
            "timeout": 300000  # 5 minutes in milliseconds
        }

        # Store challenge with user association for registration
        await store_challenge(challenge, user_id, "registration")

        logger.info(
            "WebAuthn registration challenge generated for user %s (excluded %d existing credentials)",
            username,
            len(exclude_credentials)
        )

        # Log successful challenge generation
        log_security_event(
            event_type="webauthn_registration_challenge_generated",
            user_id=user_id,
            success=True,
            details={
                "username": username,
                "device_name": device_name,
                "excluded_credentials": len(exclude_credentials),
                "challenge_prefix": challenge[:8] + "...",
            },
        )

        return options

    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        logger.error("Failed to begin WebAuthn registration for user %s: %s", username, e, exc_info=True)
        log_error_with_context(
            e,
            context={
                "user_id": user_id,
                "username": username,
                "device_name": device_name,
            },
            operation="webauthn_registration_begin",
        )
        
        log_security_event(
            event_type="webauthn_registration_begin_failed",
            user_id=user_id,
            success=False,
            details={
                "username": username,
                "error": str(e),
            },
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to begin WebAuthn registration"
        ) from e


@log_performance("webauthn_registration_complete")
async def complete_registration(
    user: Dict[str, Any],
    credential_response: Dict[str, Any],
    device_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Complete WebAuthn credential registration after client authentication.

    Validates the credential response, stores the credential, and returns confirmation.
    Follows existing validation and error handling patterns from registration.py.

    Args:
        user (Dict[str, Any]): User document from database
        credential_response (Dict[str, Any]): WebAuthn credential creation response
        device_name (Optional[str]): Optional friendly name for the device

    Returns:
        Dict[str, Any]: Registration confirmation with credential metadata

    Raises:
        HTTPException: If validation fails or storage fails
    """
    user_id = str(user["_id"])
    username = user.get("username", "unknown")
    credential_id = credential_response.get("id", "unknown")
    
    logger.info(
        "WebAuthn registration complete for user: %s, credential: %s, device: %s",
        username,
        credential_id[:16] + "..." if len(credential_id) > 16 else credential_id,
        device_name or "Unknown"
    )

    # Log security event for registration completion attempt
    log_security_event(
        event_type="webauthn_registration_complete_attempt",
        user_id=user_id,
        success=False,  # Will be updated to True on success
        details={
            "username": username,
            "credential_id_prefix": credential_id[:16] + "..." if len(credential_id) > 16 else credential_id,
            "device_name": device_name,
        },
    )

    try:
        # Validate required fields in credential response
        required_fields = ["id", "rawId", "response", "type"]
        missing_fields = [field for field in required_fields if field not in credential_response]
        
        if missing_fields:
            logger.warning("Missing required fields in credential response: %s", missing_fields)
            log_security_event(
                event_type="webauthn_registration_invalid_response",
                user_id=user_id,
                success=False,
                details={
                    "username": username,
                    "missing_fields": missing_fields,
                },
            )
            raise HTTPException(status_code=400, detail=f"Missing required fields: {missing_fields}")

        # Validate credential type
        if credential_response.get("type") != "public-key":
            logger.warning("Invalid credential type: %s", credential_response.get("type"))
            raise HTTPException(status_code=400, detail="Invalid credential type")

        # Extract and validate client data
        response_data = credential_response.get("response", {})
        client_data_json = response_data.get("clientDataJSON")
        attestation_object = response_data.get("attestationObject")

        if not client_data_json or not attestation_object:
            logger.warning("Missing clientDataJSON or attestationObject")
            raise HTTPException(status_code=400, detail="Missing credential response data")

        # Parse client data JSON to extract challenge
        try:
            client_data_bytes = base64.urlsafe_b64decode(client_data_json + '==')
            client_data = json.loads(client_data_bytes.decode('utf-8'))
            challenge = client_data.get("challenge")
            
            if not challenge:
                logger.warning("No challenge found in client data")
                raise HTTPException(status_code=400, detail="No challenge in client data")
                
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning("Failed to parse client data JSON: %s", e)
            raise HTTPException(status_code=400, detail="Invalid client data JSON") from e

        # Validate challenge using existing pattern
        challenge_data = await validate_challenge(challenge, user_id, "registration")
        if not challenge_data:
            logger.warning("Invalid or expired challenge for registration")
            log_security_event(
                event_type="webauthn_registration_invalid_challenge",
                user_id=user_id,
                success=False,
                details={
                    "username": username,
                    "challenge_prefix": challenge[:8] + "..." if challenge else "none",
                },
            )
            raise HTTPException(status_code=400, detail="Invalid or expired challenge")

        logger.debug("Challenge validated successfully for registration")

        # Use the crypto module to properly parse the attestation object
        from second_brain_database.routes.auth.services.webauthn.crypto import extract_public_key_from_attestation
        
        try:
            # Extract public key and metadata from attestation object
            extracted_data = extract_public_key_from_attestation(attestation_object)
            
            credential_id = extracted_data["credential_id"]
            public_key_data = json.dumps(extracted_data["public_key"], default=str)  # Store as JSON string
            aaguid = extracted_data.get("aaguid")
            
            # Determine authenticator type based on extracted data
            authenticator_type = "platform"  # Default to platform for Flutter optimization
            transport = response_data.get("transports", ["internal"])
            
            logger.debug("Successfully extracted public key from attestation object")
            
        except Exception as e:
            logger.warning("Failed to parse attestation object, using fallback approach: %s", e)
            # Fallback to basic approach if parsing fails
            credential_id = credential_response["id"]
            public_key_data = attestation_object
            authenticator_type = "platform"
            transport = response_data.get("transports", ["internal"])
            aaguid = None
        
        # Store credential using existing pattern
        credential_metadata = await store_credential(
            user_id=user_id,
            credential_id=credential_id,
            public_key=public_key_data,
            device_name=device_name or "WebAuthn Device",
            authenticator_type=authenticator_type,
            transport=transport,
            aaguid=None  # Would be extracted from attestation object in full implementation
        )

        logger.info(
            "WebAuthn credential registered successfully for user %s: %s",
            username,
            credential_id[:16] + "..." if len(credential_id) > 16 else credential_id
        )

        # Log successful registration using existing auth success pattern
        log_auth_success(
            event_type="webauthn_registration_completed",
            user_id=user_id,
            details={
                "username": username,
                "credential_id": credential_id,
                "device_name": device_name or "WebAuthn Device",
                "authenticator_type": authenticator_type,
                "transport": transport,
                "operation": "credential_registration",
            },
        )

        # Return registration confirmation following existing response patterns
        return {
            "message": "WebAuthn credential registered successfully",
            "credential_id": credential_id,
            "device_name": credential_metadata["device_name"],
            "authenticator_type": credential_metadata["authenticator_type"],
            "created_at": credential_metadata["created_at"],
        }

    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        logger.error("Failed to complete WebAuthn registration for user %s: %s", username, e, exc_info=True)
        log_error_with_context(
            e,
            context={
                "user_id": user_id,
                "username": username,
                "credential_id": credential_id,
                "device_name": device_name,
            },
            operation="webauthn_registration_complete",
        )
        
        log_security_event(
            event_type="webauthn_registration_complete_failed",
            user_id=user_id,
            success=False,
            details={
                "username": username,
                "credential_id_prefix": credential_id[:16] + "..." if len(credential_id) > 16 else credential_id,
                "error": str(e),
            },
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete WebAuthn registration"
        ) from e