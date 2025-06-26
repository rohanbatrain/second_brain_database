"""
Notification utilities for password reset abuse detection.

This module provides async functions to notify users of suspicious password reset attempts,
including secure links to whitelist or block (email, IP) pairs and warnings for rate limit abuse.
"""
from typing import List, Optional
from second_brain_database.database import db_manager
from second_brain_database.managers.email import email_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.services.abuse.management import is_pair_whitelisted
from second_brain_database.routes.auth.services.utils.redis_utils import generate_abuse_action_token
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.config import settings

STRICTER_WHITELIST_LIMIT: int = getattr(settings, "STRICTER_WHITELIST_LIMIT", 3)
ABUSE_ACTION_TOKEN_EXPIRY: int = getattr(settings, "ABUSE_ACTION_TOKEN_EXPIRY", 1800)
ABUSE_ACTION_BLOCK_EXPIRY: int = getattr(settings, "ABUSE_ACTION_BLOCK_EXPIRY", 86400)

logger = get_logger(prefix="[Auth Service Abuse Notification]")

async def notify_user_of_suspicious_reset(
    email: str,
    reasons: List[str],
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_time: Optional[str] = None,
    location: Optional[str] = None,
    isp: Optional[str] = None
) -> None:
    """
    Notify the user by email if a suspicious password reset attempt is detected for their account.
    Includes secure links to whitelist or block the (email, IP) pair and request metadata.

    Args:
        email (str): The user's email address.
        reasons (List[str]): List of reasons for suspicion.
        ip (Optional[str]): The requester's IP address.
        user_agent (Optional[str]): The user agent string.
        request_time (Optional[str]): Time of the request.
        location (Optional[str]): Geolocation of the request.
        isp (Optional[str]): ISP of the requester.

    Side Effects:
        Sends an email to the user. Reads/writes to Redis for abuse tracking.
    """
    try:
        user = await db_manager.get_collection("users").find_one({"email": email})
        if not user:
            logger.warning("No user found for suspicious reset notification: %s", email)
            return
        subject = "Suspicious Password Reset Attempt Detected"
        reason_list = "<ul>" + "".join(f"<li>{r}</li>" for r in reasons) + "</ul>"
        whitelist_token = await generate_abuse_action_token(
            email, ip, "whitelist", expiry_seconds=ABUSE_ACTION_TOKEN_EXPIRY
        )
        block_token = await generate_abuse_action_token(
            email, ip, "block", expiry_seconds=ABUSE_ACTION_BLOCK_EXPIRY
        )
        base_url = getattr(settings, "BASE_URL", "http://localhost:8000")
        whitelist_link = f"{base_url}auth/confirm-reset-abuse?token={whitelist_token}"
        block_link = f"{base_url}auth/block-reset-abuse?token={block_token}"
        meta = f"""
        <ul>
            <li><b>IP Address:</b> {ip or 'Unknown'}</li>
            <li><b>Location:</b> {location or 'Unknown'}</li>
            <li><b>Time:</b> {request_time or 'Unknown'}</li>
            <li><b>Device:</b> {user_agent or 'Unknown'}</li>
            <li><b>ISP:</b> {isp or 'Unknown'}</li>
        </ul>
        """
        redis_conn = await redis_manager.get_redis()
        warning_message = ""
        abuse_message = ""
        if ip and await is_pair_whitelisted(email, ip):
            key = f"abuse:reset:whitelist_limit:{email}:{ip}"
            count = await redis_conn.get(key)
            if count is not None:
                try:
                    count_int = int(count)
                except (TypeError, ValueError):
                    logger.debug("Non-integer count for whitelist limit: %r", count, exc_info=True)
                    count_int = 0
                stricter_limit = STRICTER_WHITELIST_LIMIT
                if count_int >= stricter_limit:
                    warning_message = (
                        "<b>Warning:</b> You have exceeded the allowed number of password reset requests from this device in 24 hours. "
                        "Further requests are blocked for 24 hours."
                    )
                    abuse_key = f"abuse:reset:whitelist_abuse:{email}:{ip}"
                    abuse_count = await redis_conn.get(abuse_key)
                    if abuse_count is not None:
                        try:
                            abuse_count_int = int(abuse_count)
                        except (TypeError, ValueError):
                            logger.debug("Non-integer abuse count: %r", abuse_count, exc_info=True)
                            abuse_count_int = 0
                        if abuse_count_int >= STRICTER_WHITELIST_LIMIT:
                            abuse_message = (
                                "<b>Notice:</b> Your account has been suspended due to repeated abuse of the password reset system. Please contact support."
                            )
                    elif count_int == stricter_limit - 1:
                        warning_message = (
                            "<b>Warning:</b> You are about to reach the maximum allowed password reset requests from this device in 24 hours. Further requests will be blocked."
                        )
        html_content = f"""
        <html><body>
        <h2>Suspicious Password Reset Attempt</h2>
        <p>We detected a suspicious password reset attempt for your account.</p>
        {warning_message}
        {abuse_message}
        <b>Details:</b>
        {reason_list}
        <b>Request metadata:</b>
        {meta}
        <p>If this was <b>you</b>, you can <a href='{whitelist_link}'>confirm and allow password resets from this device</a> (valid for 30 minutes).</p>
        <p>If this was <b>not you</b>, you can <a href='{block_link}'>block password resets from this device for 24 hours</a>.</p>
        <p><i>These links are single-use and expire automatically for your security.</i></p>
        </body></html>
        """
        logger.info(
            "[SECURITY NOTIFY] To: %s | Subject: %s | Reasons: %s | IP: %s | UA: %s | Time: %s | Location: %s | ISP: %s",
            email, subject, reasons, ip, user_agent, request_time, location, isp
        )
        await email_manager.send_email(email, subject, html_content)
    except (ValueError, TypeError, AttributeError, RuntimeError) as e:
        logger.error("Failed to notify user of suspicious reset: %s", str(e), exc_info=True)
