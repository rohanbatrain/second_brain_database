from datetime import datetime, timedelta
import hashlib
import secrets
import bcrypt
from fastapi import HTTPException, status
from second_brain_database.routes.auth.models import PasswordChangeRequest, validate_password_strength
from second_brain_database.database import db_manager
from second_brain_database.managers.email import email_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.config import settings
from second_brain_database.routes.auth.services.abuse.management import is_pair_whitelisted, block_reset_pair
from second_brain_database.routes.auth.services.abuse.events import log_reset_abuse_event

STRICTER_WHITELIST_LIMIT = getattr(settings, "STRICTER_WHITELIST_LIMIT", 3)
STRICTER_WHITELIST_PERIOD = getattr(settings, "STRICTER_WHITELIST_PERIOD", 86400)

logger = get_logger()

async def change_user_password(current_user: dict, password_request: PasswordChangeRequest):
    """Change the password for the current user after validating the old password. Should require recent authentication."""
    # Recent password confirmation or re-login should be enforced for sensitive actions in production
    if not validate_password_strength(password_request.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long and contain "
                   "uppercase, lowercase, digit, and special character"
        )
    if not bcrypt.checkpw(password_request.old_password.encode('utf-8'),
                          current_user["hashed_password"].encode('utf-8')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid old password"
        )
    new_hashed_pw = bcrypt.hashpw(password_request.new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    result = await db_manager.get_collection("users").update_one(
        {"username": current_user["username"]},
        {"$set": {"hashed_password": new_hashed_pw}}
    )
    if not result.modified_count:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password"
        )
    # Blacklist all tokens for this user (in prod, use Redis or DB)
    # Optionally, you could store a token version in the user doc and increment it here
    # For demo, just log
    logger.info("Password changed for user %s; tokens should be invalidated.", current_user["username"])
    return True


async def send_password_reset_email(email: str, ip=None, user_agent=None, request_time=None, location=None, isp=None):
    """Send a password reset email with metadata and a real token (hashed in DB)."""
    redis_conn = await redis_manager.get_redis()
    # Individual and combined rate limit keys
    fp_key = f"forgot_password:{email}"
    rv_key = f"resend_verification:{email}"
    combined_key = f"combined_reset_verify:{email}"
    # Increment all relevant counters
    fp_count = await redis_conn.incr(fp_key)
    if fp_count == 1:
        await redis_conn.expire(fp_key, 60)
    combined_count = await redis_conn.incr(combined_key)
    if combined_count == 1:
        await redis_conn.expire(combined_key, 60)
    # Check limits: individual and combined
    if fp_count > 2 or combined_count > 3:
        return {"message": "Password reset email did not sent"}
    base_url = getattr(settings, "BASE_URL", "http://localhost:8000")
    user = await db_manager.get_collection("users").find_one({"email": email})
    if not user:
        logger.info("Password reset requested for non-existent email: %s", email)
        return  # Do not reveal user existence
    # Generate a secure token and expiry
    reset_token = secrets.token_urlsafe(32)
    # Hash the token before storing in DB
    token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
    expiry = datetime.utcnow() + timedelta(minutes=30)  # 30 min expiry
    await db_manager.get_collection("users").update_one(
        {"_id": user["_id"]},
        {"$set": {"password_reset_token": token_hash, "password_reset_token_expiry": expiry.isoformat()}}
    )
    reset_link = f"{base_url}/auth/reset-password?token={reset_token}"
    # Compose metadata section
    meta = f"""
    <ul>
        <li><b>IP Address:</b> {ip or 'Unknown'}</li>
        <li><b>Location:</b> {location or 'Unknown'}</li>
        <li><b>Time:</b> {request_time or 'Unknown'}</li>
        <li><b>Device:</b> {user_agent or 'Unknown'}</li>
        <li><b>ISP:</b> {isp or 'Unknown'}</li>
    </ul>
    """
    # --- Stricter rate limit for whitelisted pairs ---
    redis_conn = await redis_manager.get_redis()
    stricter_limit = STRICTER_WHITELIST_LIMIT
    stricter_period = STRICTER_WHITELIST_PERIOD
    warning_message = ""
    abuse_message = ""
    if ip and await is_pair_whitelisted(email, ip):
        key = f"abuse:reset:whitelist_limit:{email}:{ip}"
        count = await redis_conn.incr(key)
        if count == 1:
            await redis_conn.expire(key, stricter_period)
        if count > stricter_limit:
            # Block further resets for 24h
            await block_reset_pair(email, ip)
            warning_message = "<b>Warning:</b> You have exceeded the allowed number of password reset requests from this device in 24 hours. Further requests are blocked for 24 hours."
            # Track abuse for this pair
            abuse_key = f"abuse:reset:whitelist_abuse:{email}:{ip}"
            abuse_count = await redis_conn.incr(abuse_key)
            if abuse_count == 1:
                await redis_conn.expire(abuse_key, 604800)  # 1 week
            # Log self_abuse event in abuse_events
            await log_reset_abuse_event(
                email=email,
                ip=ip,
                user_agent=user_agent,
                event_type="self_abuse",
                details="Exceeded whitelist limit for password resets",
                whitelisted=True,
                action_taken="blocked",
            )
            # Escalate to ban if repeated self_abuse (3+ times in a week)
            if abuse_count >= STRICTER_WHITELIST_LIMIT:
                await db_manager.get_collection("users").update_one(
                    {"email": email},
                    {"$set": {"is_active": False, "abuse_suspended": True, "abuse_suspended_at": datetime.utcnow()}}
                )
                abuse_message = "<b>Notice:</b> Your account has been suspended due to repeated abuse of the password reset system. Please contact support."
                await redis_conn.sadd("abuse:reset:abuse_ips", ip)
                # Log ban event
                await log_reset_abuse_event(
                    email=email,
                    ip=ip,
                    user_agent=user_agent,
                    event_type="self_abuse",
                    details="Account suspended due to repeated whitelist abuse",
                    whitelisted=True,
                    action_taken="banned",
                )
        elif count == stricter_limit:
            warning_message = "<b>Warning:</b> You are about to reach the maximum allowed password reset requests from this device in 24 hours. Further requests will be blocked."
    html_content = f"""
    <html>
    <body>
        <h2>Password Reset Requested</h2>
        <p>We received a request to reset your password.</p>
        {warning_message}
        {abuse_message}
        <b>Request details:</b>
        {meta}
        <p>If this was <b>you</b>, click the button below to reset your password:</p>
        <a href='{reset_link}' style='padding:10px 20px;background:#007bff;color:#fff;text-decoration:none;border-radius:5px;'>Reset Password</a>
        <p>If this wasn't you, we recommend securing your account.</p>
    </body>
    </html>
    """
    logger.info("Send password reset email to %s", email)
    logger.info("Password reset link: %s", reset_link)
    logger.info("Password reset metadata: IP=%s, UA=%s, Time=%s, Location=%s, ISP=%s", ip, user_agent, request_time, location, isp)
    await email_manager._send_via_console(email, "Password Reset Requested", html_content)

async def send_password_reset_notification(email: str):
    """Send a notification email after successful password reset (console log for now)."""
    subject = "Your password was reset"
    html_content = f"""
    <html><body>
    <h2>Password Changed</h2>
    <p>Your password was successfully reset. If this wasn't you, please contact support immediately.</p>
    </body></html>
    """
    logger.info(f"[NOTIFY EMAIL] To: {email}\nSubject: {subject}\nHTML:\n{html_content}")
    await email_manager._send_via_console(email, subject, html_content)

