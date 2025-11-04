"""
Two-factor authentication (2FA) management utilities for authentication workflows.

This module provides async functions for setting up, verifying, resetting, disabling,
and checking the status of 2FA for users. It supports TOTP and backup codes, and is
fully instrumented with production-grade logging and error handling.
"""

import base64
from datetime import datetime, timezone
from io import BytesIO
import secrets
from typing import Any, Dict

import bcrypt
from fastapi import HTTPException
import pyotp
import qrcode

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.models import (
    TwoFASetupRequest,
    TwoFASetupResponse,
    TwoFAStatus,
    TwoFAVerifyRequest,
)
from second_brain_database.routes.auth.services.utils.redis_utils import (
    delete_backup_codes_temp,
    get_backup_codes_temp,
    store_backup_codes_temp,
)
from second_brain_database.utils.crypto import (
    decrypt_totp_secret,
    encrypt_totp_secret,
    is_encrypted_totp_secret,
    migrate_plaintext_secret,
)
from second_brain_database.utils.logging_utils import (
    DatabaseLogger,
    SecurityLogger,
    log_database_operation,
    log_error_with_context,
    log_performance,
    log_security_event,
)

BACKUP_CODES_PENDING_TIME: int = getattr(settings, "BACKUP_CODES_PENDING_TIME", 600)
QR_ISSUER: str = "Second Brain Database"
QR_DOMAIN: str = "app.sbd.rohanbatra.in"
BACKUP_CODES_COUNT: int = 10

logger = get_logger(prefix="[Auth Service 2FA]")
security_logger = SecurityLogger(prefix="[2FA-SECURITY]")
db_logger = DatabaseLogger(prefix="[2FA-DB]")


@log_performance("setup_2fa")
async def setup_2fa(current_user: Dict[str, Any], request: TwoFASetupRequest) -> TwoFASetupResponse:
    """
    Begin 2FA setup for a user, generating a TOTP secret and backup codes.
    Returns provisioning URI and QR code data for authenticator apps.

    Args:
        current_user (Dict[str, Any]): The current user document.
        request (TwoFASetupRequest): 2FA setup request object.

    Returns:
        TwoFASetupResponse: Setup response with QR code and secret.

    Raises:
        HTTPException: If 2FA is already enabled or method is unsupported.
    """
    username = current_user.get("username", "unknown")
    logger.info("2FA setup initiated for user %s with method %s", username, request.method)

    # Log security event for 2FA setup attempt
    log_security_event(
        event_type="2fa_setup_attempt",
        user_id=username,
        success=False,  # Will be updated to True on success
        details={"method": request.method, "already_enabled": current_user.get("two_fa_enabled", False)},
    )

    users = db_manager.get_collection("users")
    method = request.method
    if current_user.get("two_fa_enabled", False):
        logger.info("2FA setup attempted but already enabled for user %s", username)
        log_security_event(
            event_type="2fa_setup_already_enabled", user_id=username, success=False, details={"method": method}
        )
        raise HTTPException(
            status_code=400, detail="2FA is already enabled. Disable 2FA first before setting up again."
        )
    # Get current user state from database
    user = await users.find_one({"username": current_user["username"]})

    log_database_operation(
        operation="find_user_for_2fa_setup",
        collection="users",
        query={"username": username},
        result={"found": user is not None},
    )

    cleared = await clear_2fa_pending_if_expired(user)
    if cleared:
        logger.info("Cleared expired 2FA pending state for user %s", username)
        user = await users.find_one({"username": current_user["username"]})

    # Handle existing pending setup
    if user.get("two_fa_pending", False):
        logger.info("Returning existing 2FA pending setup for user %s", username)
        try:
            secret = get_decrypted_totp_secret(user)
            logger.debug("Successfully retrieved existing TOTP secret for user %s", username)
        except (ValueError, TypeError) as exc:
            logger.error("Failed to get decrypted TOTP secret for user %s: %s", username, exc, exc_info=True)
            log_error_with_context(
                exc, context={"username": username, "operation": "get_existing_totp_secret"}, operation="setup_2fa"
            )
            secret = None

        issuer = QR_ISSUER
        account_name = f"{user['username']}@{QR_DOMAIN}"
        provisioning_uri = None
        if secret:
            provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=issuer)
            logger.debug("Generated provisioning URI for existing setup for user %s", username)

        qr_code_data = None
        try:
            if provisioning_uri:
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(provisioning_uri)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                qr_code_data = base64.b64encode(buffered.getvalue()).decode()
                logger.debug("Generated QR code for existing setup for user %s", username)
        except (ImportError, OSError, ValueError) as qr_exc:
            qr_code_data = None
            logger.warning("QR code generation failed for user %s: %s", username, qr_exc, exc_info=True)

        log_security_event(
            event_type="2fa_setup_existing_pending",
            user_id=username,
            success=True,
            details={"method": method, "has_qr_code": qr_code_data is not None},
        )

        return TwoFASetupResponse(
            enabled=False, methods=[], totp_secret=secret, provisioning_uri=provisioning_uri, qr_code_data=qr_code_data
        )

    # Validate method
    if method != "totp":
        logger.warning("Unsupported 2FA method setup attempted for user %s: %s", username, method)
        log_security_event(
            event_type="2fa_setup_unsupported_method", user_id=username, success=False, details={"method": method}
        )
        raise HTTPException(status_code=400, detail="Only TOTP 2FA is supported in this demo.")

    # Generate new 2FA setup
    logger.info("Generating new 2FA setup for user %s", username)
    secret = pyotp.random_base32()
    encrypted_secret = encrypt_totp_secret(secret)
    backup_codes = [secrets.token_hex(4).upper() for _ in range(BACKUP_CODES_COUNT)]
    hashed_backup_codes = [
        bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8") for code in backup_codes
    ]

    logger.debug("Generated %d backup codes for user %s", len(backup_codes), username)

    # Store backup codes temporarily in Redis
    try:
        await store_backup_codes_temp(current_user["username"], backup_codes)
        logger.debug("Successfully stored backup codes in Redis for user %s", username)
    except RuntimeError as e:
        logger.error("Failed to store backup codes in Redis for user %s: %s", username, e, exc_info=True)
        log_error_with_context(
            e,
            context={"username": username, "backup_codes_count": len(backup_codes)},
            operation="store_backup_codes_temp",
        )

    # Update user in database with pending 2FA setup
    update_result = await users.update_one(
        {"username": current_user["username"]},
        {
            "$set": {
                "two_fa_enabled": False,
                "two_fa_pending": True,
                "two_fa_pending_since": datetime.now(timezone.utc).isoformat(),
                "totp_secret": encrypted_secret,
                "two_fa_methods": ["totp"],
                "backup_codes": hashed_backup_codes,
                "backup_codes_used": [],
            },
            "$unset": {"email_otp_obj": "", "passkeys": ""},
        },
    )

    log_database_operation(
        operation="update_user_2fa_pending",
        collection="users",
        query={"username": username},
        result={"modified_count": update_result.modified_count},
    )

    if update_result.modified_count == 0:
        logger.error("Failed to update user with 2FA pending setup for user %s", username)
        log_security_event(
            event_type="2fa_setup_database_update_failed", user_id=username, success=False, details={"method": method}
        )
        raise HTTPException(status_code=500, detail="Failed to initialize 2FA setup")

    # Generate QR code and provisioning URI
    user = await users.find_one({"username": current_user["username"]})
    issuer = QR_ISSUER
    account_name = f"{current_user['username']}@{QR_DOMAIN}"
    provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=issuer)

    logger.debug("Generated provisioning URI for new setup for user %s", username)

    qr_code_data = None
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        qr_code_data = base64.b64encode(buffered.getvalue()).decode()
        logger.debug("Generated QR code for new setup for user %s", username)
    except (ImportError, OSError, ValueError) as qr_exc:
        qr_code_data = None
        logger.warning("QR code generation failed for user %s: %s", username, qr_exc, exc_info=True)
        log_error_with_context(
            qr_exc,
            context={"username": username, "provisioning_uri_length": len(provisioning_uri)},
            operation="generate_qr_code",
        )

    # Log successful 2FA setup initiation
    log_security_event(
        event_type="2fa_setup_initiated",
        user_id=username,
        success=True,
        details={"method": method, "has_qr_code": qr_code_data is not None, "backup_codes_count": len(backup_codes)},
    )

    logger.info("Successfully initiated 2FA setup for user %s", username)

    return TwoFASetupResponse(
        enabled=False, methods=[], totp_secret=secret, provisioning_uri=provisioning_uri, qr_code_data=qr_code_data
    )


@log_performance("verify_2fa")
async def verify_2fa(current_user: Dict[str, Any], request: TwoFAVerifyRequest) -> TwoFAStatus:
    """
    Verify a user's 2FA code and enable 2FA if pending.

    Args:
        current_user (Dict[str, Any]): The current user document.
        request (TwoFAVerifyRequest): 2FA verification request object.

    Returns:
        TwoFAStatus: The user's 2FA status after verification.

    Raises:
        HTTPException: If verification fails or method is unsupported.
    """
    username = current_user.get("username", "unknown")
    logger.info("2FA verification initiated for user %s with method %s", username, request.method)

    # Log security event for 2FA verification attempt
    log_security_event(
        event_type="2fa_verification_attempt",
        user_id=username,
        success=False,  # Will be updated to True on success
        details={"method": request.method, "is_pending": current_user.get("two_fa_pending", False)},
    )

    users = db_manager.get_collection("users")
    user = await users.find_one({"username": current_user["username"]})

    log_database_operation(
        operation="find_user_for_2fa_verification",
        collection="users",
        query={"username": username},
        result={"found": user is not None},
    )

    cleared = await clear_2fa_pending_if_expired(user)
    if cleared:
        logger.warning("2FA setup expired for user %s", username)
        log_security_event(
            event_type="2fa_verification_expired", user_id=username, success=False, details={"method": request.method}
        )
        raise HTTPException(status_code=400, detail="2FA setup expired. Please set up 2FA again.")

    method = request.method
    code = request.code

    # Validate method
    if method != "totp":
        logger.warning("Unsupported 2FA method verification attempted for user %s: %s", username, method)
        log_security_event(
            event_type="2fa_verification_unsupported_method",
            user_id=username,
            success=False,
            details={"method": method},
        )
        raise HTTPException(status_code=400, detail="Only TOTP 2FA is supported in this demo.")

    # Get and decrypt TOTP secret
    secret = current_user.get("totp_secret")
    if not secret:
        logger.warning("TOTP not set up for user %s", username)
        log_security_event(
            event_type="2fa_verification_no_secret", user_id=username, success=False, details={"method": method}
        )
        raise HTTPException(status_code=400, detail="TOTP not set up. Please complete 2FA setup before verifying.")

    try:
        if is_encrypted_totp_secret(secret):
            secret = decrypt_totp_secret(secret)
        logger.debug("Successfully decrypted TOTP secret for user %s", username)
    except Exception as e:
        logger.error("Failed to decrypt TOTP secret for user %s: %s", username, e, exc_info=True)
        log_error_with_context(
            e, context={"username": username, "method": method}, operation="decrypt_totp_secret_for_verification"
        )
        raise HTTPException(status_code=500, detail="Failed to process 2FA verification")

    # Verify TOTP code
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        logger.info("Invalid TOTP code for user %s", username)
        log_security_event(
            event_type="2fa_verification_invalid_code",
            user_id=username,
            success=False,
            details={"method": method, "code_length": len(code) if code else 0},
        )
        raise HTTPException(
            status_code=401, detail="Invalid TOTP code. Please check your authenticator app and try again."
        )

    logger.info("Valid TOTP code verified for user %s", username)

    # Handle pending 2FA activation
    if current_user.get("two_fa_pending", False):
        logger.info("Activating 2FA for user %s after successful verification", username)

        update_result = await users.update_one(
            {"username": current_user["username"]},
            {
                "$set": {"two_fa_enabled": True, "two_fa_methods": ["totp"]},
                "$unset": {"two_fa_pending": "", "two_fa_pending_since": ""},
            },
        )

        log_database_operation(
            operation="activate_2fa_after_verification",
            collection="users",
            query={"username": username},
            result={"modified_count": update_result.modified_count},
        )

        # Get backup codes from Redis and clean up
        backup_codes = await get_backup_codes_temp(current_user["username"])
        await delete_backup_codes_temp(current_user["username"])

        logger.info("2FA enabled for user %s after successful verification", username)

        log_security_event(
            event_type="2fa_activated",
            user_id=username,
            success=True,
            details={"method": method, "backup_codes_count": len(backup_codes) if backup_codes else 0},
        )

        return TwoFAStatus(enabled=True, methods=["totp"], pending=False, backup_codes=backup_codes)

    # Regular 2FA verification (already enabled)
    logger.info("2FA verification successful for user %s (already enabled)", username)

    log_security_event(
        event_type="2fa_verification_success",
        user_id=username,
        success=True,
        details={"method": method, "was_pending": False},
    )

    return TwoFAStatus(
        enabled=current_user.get("two_fa_enabled", False),
        methods=current_user.get("two_fa_methods", []),
        pending=current_user.get("two_fa_pending", False),
    )


async def get_2fa_status(current_user: Dict[str, Any]) -> TwoFAStatus:
    """
    Get the current 2FA status for a user.

    Args:
        current_user (Dict[str, Any]): The current user document.

    Returns:
        TwoFAStatus: The user's 2FA status.
    """
    return TwoFAStatus(
        enabled=current_user.get("two_fa_enabled", False),
        methods=current_user.get("two_fa_methods", []),
        pending=current_user.get("two_fa_pending", False),
    )


async def disable_2fa(current_user: Dict[str, Any]) -> TwoFAStatus:
    """
    Disable 2FA for a user and clear all related secrets and backup codes.

    Args:
        current_user (Dict[str, Any]): The current user document.

    Returns:
        TwoFAStatus: The user's 2FA status after disabling.
    """
    users = db_manager.get_collection("users")
    await users.update_one(
        {"username": current_user["username"]},
        {
            "$set": {"two_fa_enabled": False, "two_fa_methods": []},
            "$unset": {
                "totp_secret": "",
                "email_otp_obj": "",
                "passkeys": "",
                "two_fa_pending": "",
                "backup_codes": "",
                "backup_codes_used": "",
            },
        },
    )
    user = await users.find_one({"username": current_user["username"]})
    logger.info("2FA disabled for user %s", current_user.get("username"))
    return TwoFAStatus(enabled=user.get("two_fa_enabled", False), methods=user.get("two_fa_methods", []), pending=False)


async def reset_2fa(current_user: Dict[str, Any], request: TwoFASetupRequest) -> TwoFASetupResponse:
    """
    Reset 2FA for a user who already has it enabled. Generates new secret and backup codes.
    Should require additional verification in production (like password confirmation).

    Args:
        current_user (Dict[str, Any]): The current user document.
        request (TwoFASetupRequest): 2FA setup request object.

    Returns:
        TwoFASetupResponse: Setup response with QR code and secret.

    Raises:
        HTTPException: If 2FA is not enabled or method is unsupported.
    """
    users = db_manager.get_collection("users")
    method = request.method
    if not current_user.get("two_fa_enabled", False):
        logger.warning("2FA reset attempted but not enabled for user %s", current_user.get("username"))
        raise HTTPException(status_code=400, detail="2FA is not enabled. Use setup endpoint instead.")
    if method != "totp":
        logger.warning("Unsupported 2FA method reset attempted: %s", method)
        raise HTTPException(status_code=400, detail="Only TOTP 2FA is supported in this demo.")
    secret = pyotp.random_base32()
    encrypted_secret = encrypt_totp_secret(secret)
    backup_codes = [secrets.token_hex(4).upper() for _ in range(BACKUP_CODES_COUNT)]
    hashed_backup_codes = [
        bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8") for code in backup_codes
    ]
    await users.update_one(
        {"username": current_user["username"]},
        {
            "$set": {
                "two_fa_enabled": True,
                "totp_secret": encrypted_secret,
                "two_fa_methods": ["totp"],
                "backup_codes": hashed_backup_codes,
                "backup_codes_used": [],
            }
        },
    )
    user = await users.find_one({"username": current_user["username"]})
    username = user.get("username", "user")
    account_name = f"{username}@{QR_DOMAIN}"
    provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=QR_ISSUER)
    qr_code_data = None
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        qr_code_data = base64.b64encode(buffered.getvalue()).decode()
    except (ImportError, OSError, ValueError) as qr_exc:
        qr_code_data = None
        logger.warning("QR code generation failed: %s", qr_exc, exc_info=True)
    return TwoFASetupResponse(
        enabled=user.get("two_fa_enabled", False),
        methods=user.get("two_fa_methods", []),
        totp_secret=secret,
        provisioning_uri=provisioning_uri,
        qr_code_data=qr_code_data,
    )


async def clear_2fa_pending_if_expired(user: Dict[str, Any]) -> bool:
    """
    If 2FA is pending for more than BACKUP_CODES_PENDING_TIME, clear all 2FA pending state from user.
    Logs cleanup actions and errors for auditability.

    Args:
        user (Dict[str, Any]): The user document.

    Returns:
        bool: True if pending state was cleared, else False.
    """
    if user.get("two_fa_pending", False):
        pending_since = user.get("two_fa_pending_since")
        now = datetime.now(timezone.utc)
        if not pending_since:
            pending_since = user.get("updatedAt") or user.get("created_at") or now
        else:
            pending_since = (
                pending_since if isinstance(pending_since, datetime) else datetime.fromisoformat(pending_since)
            )
        if (now - pending_since).total_seconds() > BACKUP_CODES_PENDING_TIME:
            users = db_manager.get_collection("users")
            await users.update_one(
                {"_id": user["_id"]},
                {
                    "$unset": {
                        "two_fa_pending": "",
                        "totp_secret": "",
                        "backup_codes": "",
                        "backup_codes_used": "",
                        "two_fa_pending_since": "",
                        "two_fa_methods": "",
                    }
                },
            )
            try:
                await delete_backup_codes_temp(user["username"])
            except RuntimeError as e:
                logger.error(
                    "Failed to delete backup codes from Redis for user %s: %s", user["username"], e, exc_info=True
                )
            logger.info("Cleared expired 2FA pending state for user %s", user["username"])
            return True
    return False


def get_decrypted_totp_secret(user: Dict[str, Any]) -> str:
    """
    Safely get and decrypt a user's TOTP secret.
    Handles both encrypted and legacy plaintext secrets for migration.

    Args:
        user (Dict[str, Any]): User document from database.

    Returns:
        str: Decrypted TOTP secret.

    Raises:
        ValueError: If no TOTP secret exists or decryption fails.
    """
    encrypted_secret = user.get("totp_secret")
    if not encrypted_secret:
        logger.error("No TOTP secret found for user %s", user.get("username", "unknown"))
        raise ValueError("No TOTP secret found")
    try:
        if is_encrypted_totp_secret(encrypted_secret):
            return decrypt_totp_secret(encrypted_secret)
        else:
            logger.warning(
                "Found plaintext TOTP secret for user %s, migrating to encrypted format",
                user.get("username", "unknown"),
            )
            migrated_secret = migrate_plaintext_secret(encrypted_secret)
            users = db_manager.get_collection("users")
            users.update_one({"_id": user["_id"]}, {"$set": {"totp_secret": migrated_secret}})
            logger.info(
                "Successfully migrated TOTP secret to encrypted format for user %s", user.get("username", "unknown")
            )
            return encrypted_secret
    except (ValueError, TypeError, KeyError, RuntimeError) as e:
        logger.error("Failed to decrypt TOTP secret for user %s: %s", user.get("username", "unknown"), e, exc_info=True)
        raise ValueError("Failed to decrypt TOTP secret") from e
