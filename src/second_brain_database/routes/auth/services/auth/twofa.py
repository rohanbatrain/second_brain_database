import pyotp
import qrcode
import base64
import bcrypt
import secrets
from io import BytesIO
from datetime import datetime
from fastapi import HTTPException
from second_brain_database.database import db_manager
from second_brain_database.routes.auth.models import TwoFASetupRequest, TwoFAVerifyRequest, TwoFASetupResponse, TwoFAStatus
from second_brain_database.utils.crypto import encrypt_totp_secret, decrypt_totp_secret, is_encrypted_totp_secret, migrate_plaintext_secret
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.services.utils.redis_utils import store_backup_codes_temp, get_backup_codes_temp, delete_backup_codes_temp
from second_brain_database.config import settings

BACKUP_CODES_PENDING_TIME = getattr(settings, "BACKUP_CODES_PENDING_TIME", 600)

logger = get_logger()

async def setup_2fa(current_user: dict, request: TwoFASetupRequest):
    users = db_manager.get_collection("users")
    method = request.method

    # Check if 2FA is already enabled
    if current_user.get("two_fa_enabled", False):
        raise HTTPException(
            status_code=400, 
            detail="2FA is already enabled. Disable 2FA first before setting up again."
        )

    # Check for expired pending state and clean up if needed
    user = await users.find_one({"username": current_user["username"]})
    cleared = await clear_2fa_pending_if_expired(user)
    if cleared:
        user = await users.find_one({"username": current_user["username"]})

    # If setup is already pending, return existing setup info (but never backup codes)
    if user.get("two_fa_pending", False):
        try:
            secret = get_decrypted_totp_secret(user)
        except Exception:
            secret = None
        issuer = "Second Brain Database"
        account_name = f"{user['username']}@app.sbd.rohanbatra.in"
        provisioning_uri = None
        if secret:
            provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=issuer)
        qr_code_data = None
        try:
            from io import BytesIO
            import base64
            import qrcode
            if provisioning_uri:
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(provisioning_uri)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                qr_code_data = base64.b64encode(buffered.getvalue()).decode()
        except ImportError:
            qr_code_data = None
            logger.warning("QR code generation failed - qrcode library not available")
        except (OSError, ValueError) as qr_exc:
            qr_code_data = None
            logger.warning("QR code generation failed: %s", qr_exc)
        # Do NOT return backup codes here anymore
        return TwoFASetupResponse(
            enabled=False,
            methods=[],
            totp_secret=secret,
            provisioning_uri=provisioning_uri,
            qr_code_data=qr_code_data
        )

    if method != "totp":
        raise HTTPException(status_code=400, detail="Only TOTP 2FA is supported in this demo.")

    secret = pyotp.random_base32()
    encrypted_secret = encrypt_totp_secret(secret)

    # Generate backup codes (10 codes)
    backup_codes = [secrets.token_hex(4).upper() for _ in range(10)]
    hashed_backup_codes = [bcrypt.hashpw(code.encode('utf-8'), bcrypt.gensalt()).decode('utf-8') for code in backup_codes]

    # Store backup codes in Redis for 10 min
    try:
        await store_backup_codes_temp(current_user["username"], backup_codes)
    except Exception as e:
        logger.error(f"Failed to store backup codes in Redis for user {current_user['username']}: {e}")

    await users.update_one(
        {"username": current_user["username"]},
        {
            "$set": {
                "two_fa_enabled": False,  # Don't enable until verified!
                "two_fa_pending": True,   # Mark as pending verification
                "two_fa_pending_since": datetime.utcnow().isoformat(),
                "totp_secret": encrypted_secret, 
                "two_fa_methods": ["totp"],
                "backup_codes": hashed_backup_codes,
                "backup_codes_used": []
            }, 
            "$unset": {"email_otp_obj": "", "passkeys": ""}
        }
    )
    user = await users.find_one({"username": current_user["username"]})

    issuer = "Second Brain Database"
    account_name = f"{current_user['username']}@app.sbd.rohanbatra.in"
    provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=issuer)

    try:
        import qrcode
        from io import BytesIO
        import base64
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        qr_code_data = base64.b64encode(buffered.getvalue()).decode()
    except ImportError:
        qr_code_data = None
        logger.warning("QR code generation failed - qrcode library not available")
    except (OSError, ValueError) as qr_exc:
        qr_code_data = None
        logger.warning("QR code generation failed: %s", qr_exc)

    # Only return backup_codes on first setup call (they are in Redis)
    return TwoFASetupResponse(
        enabled=False,  # Not enabled until verified
        methods=[],     # No methods until verified
        totp_secret=secret,
        provisioning_uri=provisioning_uri,
        qr_code_data=qr_code_data
    )

async def verify_2fa(current_user: dict, request: TwoFAVerifyRequest):
    # Check for expired pending state and clean up if needed
    users = db_manager.get_collection("users")
    user = await users.find_one({"username": current_user["username"]})
    cleared = await clear_2fa_pending_if_expired(user)
    if cleared:
        raise HTTPException(status_code=400, detail="2FA setup expired. Please set up 2FA again.")

    method = request.method
    code = request.code
    if method != "totp":
        raise HTTPException(status_code=400, detail="Only TOTP 2FA is supported in this demo.")
    secret = current_user.get("totp_secret")
    if not secret:
        raise HTTPException(status_code=400, detail="TOTP not set up. Please complete 2FA setup before verifying.")
    # Decrypt if needed
    if is_encrypted_totp_secret(secret):
        secret = decrypt_totp_secret(secret)
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(status_code=401, detail="Invalid TOTP code. Please check your authenticator app and try again.")
    # If verification successful and 2FA is pending, enable it now
    if current_user.get("two_fa_pending", False):
        await users.update_one(
            {"username": current_user["username"]},
            {
                "$set": {
                    "two_fa_enabled": True,
                    "two_fa_methods": ["totp"]
                },
                "$unset": {"two_fa_pending": "", "two_fa_pending_since": ""}
            }
        )
        backup_codes = await get_backup_codes_temp(current_user["username"])
        await delete_backup_codes_temp(current_user["username"])
        logger.info("2FA enabled for user %s after successful verification", current_user["username"])
        return TwoFAStatus(enabled=True, methods=["totp"], pending=False, backup_codes=backup_codes)
    return TwoFAStatus(
        enabled=current_user.get("two_fa_enabled", False), 
        methods=current_user.get("two_fa_methods", []),
        pending=current_user.get("two_fa_pending", False)
    )

async def get_2fa_status(current_user: dict):
    return TwoFAStatus(
        enabled=current_user.get("two_fa_enabled", False), 
        methods=current_user.get("two_fa_methods", []),
        pending=current_user.get("two_fa_pending", False)
    )



async def disable_2fa(current_user: dict):
    users = db_manager.get_collection("users")
    await users.update_one(
        {"username": current_user["username"]}, 
        {
            "$set": {"two_fa_enabled": False, "two_fa_methods": []}, 
            "$unset": {
                "totp_secret": "", 
                "email_otp_obj": "", 
                "passkeys": "",
                "two_fa_pending": "",  # Clear pending state too
                "backup_codes": "",
                "backup_codes_used": ""
            }
        }
    )
    user = await users.find_one({"username": current_user["username"]})
    return TwoFAStatus(enabled=user.get("two_fa_enabled", False), methods=user.get("two_fa_methods", []), pending=False)



async def reset_2fa(current_user: dict, request: TwoFASetupRequest):
    """
    Reset 2FA for a user who already has it enabled. This generates new secret and backup codes.
    This should require additional verification in production (like password confirmation).
    """
    users = db_manager.get_collection("users")
    method = request.method
    
    # Check if 2FA is enabled (required for reset)
    if not current_user.get("two_fa_enabled", False):
        raise HTTPException(
            status_code=400, 
            detail="2FA is not enabled. Use setup endpoint instead."
        )
    
    if method != "totp":
        raise HTTPException(status_code=400, detail="Only TOTP 2FA is supported in this demo.")
    
    # Recent password confirmation or re-login should be enforced for sensitive actions in production
    
    secret = pyotp.random_base32()
    encrypted_secret = encrypt_totp_secret(secret)
    
    # Generate new backup codes (10 codes)
    backup_codes = [secrets.token_hex(4).upper() for _ in range(10)]
    # Hash backup codes for storage
    hashed_backup_codes = [bcrypt.hashpw(code.encode('utf-8'), bcrypt.gensalt()).decode('utf-8') for code in backup_codes]
    
    await users.update_one(
        {"username": current_user["username"]},
        {
            "$set": {
                "two_fa_enabled": True, 
                "totp_secret": encrypted_secret, 
                "two_fa_methods": ["totp"],
                "backup_codes": hashed_backup_codes,
                "backup_codes_used": []  # Reset used backup codes
            }
        }
    )
    user = await users.find_one({"username": current_user["username"]})
    
    # Build provisioning URI for QR code
    username = user.get("username", "user")
    account_name = f"{username}@app.sbd.rohanbatra.in"
    
    provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=account_name,
        issuer_name="Second Brain Database"
    )
    
    # Generate QR code
    qr_code_data = None
    try:
        import qrcode
        from io import BytesIO
        import base64
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        qr_code_data = base64.b64encode(buffered.getvalue()).decode()
        
    except ImportError:
        qr_code_data = None
        logger.warning("QR code generation failed - qrcode library not available")
    except (OSError, ValueError) as qr_exc:
        qr_code_data = None
        logger.warning("QR code generation failed: %s", qr_exc)
    
    return TwoFASetupResponse(
        enabled=user.get("two_fa_enabled", False),
        methods=user.get("two_fa_methods", []),
        totp_secret=secret,
        provisioning_uri=provisioning_uri,
        qr_code_data=qr_code_data
    )

async def clear_2fa_pending_if_expired(user: dict):
    """
    If 2FA is pending for more than BACKUP_CODES_PENDING_TIME, clear all 2FA pending state from user.
    Logs cleanup actions and errors for auditability.
    """
    if user.get("two_fa_pending", False):
        pending_since = user.get("two_fa_pending_since")
        now = datetime.utcnow()
        if not pending_since:
            pending_since = user.get("updatedAt") or user.get("created_at") or now
        else:
            pending_since = pending_since if isinstance(pending_since, datetime) else datetime.fromisoformat(pending_since)
        if (now - pending_since).total_seconds() > BACKUP_CODES_PENDING_TIME:
            users = db_manager.get_collection("users")
            await users.update_one(
                {"_id": user["_id"]},
                {"$unset": {
                    "two_fa_pending": "", 
                    "totp_secret": "", 
                    "backup_codes": "", 
                    "backup_codes_used": "", 
                    "two_fa_pending_since": "",
                    "two_fa_methods": ""
                }}
            )
            try:
                await delete_backup_codes_temp(user["username"])
            except Exception as e:
                logger.error(f"Failed to delete backup codes from Redis for user {user['username']}: {e}")
            logger.info(f"Cleared expired 2FA pending state for user {user['username']}")
            return True
    return False


def get_decrypted_totp_secret(user: dict) -> str:
    """
    Safely get and decrypt a user's TOTP secret.
    Handles both encrypted and legacy plaintext secrets for migration.
    
    Args:
        user: User document from database
        
    Returns:
        Decrypted TOTP secret
        
    Raises:
        ValueError: If no TOTP secret exists or decryption fails
    """
    encrypted_secret = user.get("totp_secret")
    if not encrypted_secret:
        raise ValueError("No TOTP secret found")
    
    try:
        # Check if it's already encrypted
        if is_encrypted_totp_secret(encrypted_secret):
            return decrypt_totp_secret(encrypted_secret)
        else:
            # Legacy plaintext secret - log and migrate
            logger.warning("Found plaintext TOTP secret for user %s, migrating to encrypted format", user.get("username", "unknown"))
            # Migrate in-place for future use
            migrated_secret = migrate_plaintext_secret(encrypted_secret)
            # Update the database with encrypted version
            users = db_manager.get_collection("users")
            users.update_one(
                {"_id": user["_id"]},
                {"$set": {"totp_secret": migrated_secret}}
            )
            logger.info("Successfully migrated TOTP secret to encrypted format for user %s", user.get("username", "unknown"))
            return encrypted_secret  # Return original plaintext for immediate use
    except Exception as e:
        logger.error("Failed to decrypt TOTP secret for user %s: %s", user.get("username", "unknown"), e)
        raise ValueError("Failed to decrypt TOTP secret") from e
