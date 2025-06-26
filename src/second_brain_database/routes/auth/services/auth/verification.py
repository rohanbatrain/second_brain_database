from fastapi import HTTPException
import secrets
from datetime import datetime
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.database import db_manager
from second_brain_database.managers.email import email_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger()


async def send_verification_email(email: str, verification_link: str, username: str = None):
    """Send the verification email using the EmailManager (HTML, multi-provider)."""
    await email_manager.send_verification_email(email, verification_link, username=username)



async def resend_verification_email_service(email: str = None, username: str = None, base_url: str = None):
    """Resend verification email to a user if not already verified. Accepts email or username."""
    if not email and not username:
        raise HTTPException(status_code=400, detail="Email or username required.")
    user = None
    identifier = email or username
    redis_conn = await redis_manager.get_redis()
    # Individual and combined rate limit keys
    rv_key = f"resend_verification:{identifier}"
    fp_key = f"forgot_password:{identifier}"
    combined_key = f"combined_reset_verify:{identifier}"
    rv_count = await redis_conn.incr(rv_key)
    if rv_count == 1:
        await redis_conn.expire(rv_key, 60)
    combined_count = await redis_conn.incr(combined_key)
    if combined_count == 1:
        await redis_conn.expire(combined_key, 60)
    # Check limits: individual and combined
    if rv_count > 2 or combined_count > 3:
        return {"message": "Verification email did not sent"}
    if email:
        user = await db_manager.get_collection("users").find_one({"email": email})
    elif username:
        user = await db_manager.get_collection("users").find_one({"username": username})
    if not user:
        # Do not reveal if user exists for security
        return {"message": "Verification email sent"}
    if user.get("is_verified", False):
        return {"message": "Account already verified"}
    verification_token = secrets.token_urlsafe(32)
    await db_manager.get_collection("users").update_one(
        {"_id": user["_id"]},
        {"$set": {"verification_token": verification_token}}
    )
    verification_link = f"{base_url}auth/verify-email?token={verification_token}"
    logger.info("Verification link (resend): %s", verification_link)
    await send_verification_email(user["email"], verification_link, username=user.get("username"))
    return {"message": "Verification email sent"}


