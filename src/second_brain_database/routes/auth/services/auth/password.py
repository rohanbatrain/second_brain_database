"""
Password management utilities for authentication workflows.

This module provides async functions for changing user passwords, sending password reset emails,
and enforcing stricter rate limits and abuse detection for password reset flows.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any, Dict, Optional

import bcrypt
from fastapi import HTTPException, status

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.email import email_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.routes.auth.models import PasswordChangeRequest, validate_password_strength
from second_brain_database.routes.auth.services.abuse.events import log_reset_abuse_event
from second_brain_database.routes.auth.services.abuse.management import block_reset_pair, is_pair_whitelisted
from second_brain_database.utils.logging_utils import (
    DatabaseLogger,
    SecurityLogger,
    log_database_operation,
    log_error_with_context,
    log_performance,
    log_security_event,
)

STRICTER_WHITELIST_LIMIT: int = getattr(settings, "STRICTER_WHITELIST_LIMIT", 3)
STRICTER_WHITELIST_PERIOD: int = getattr(settings, "STRICTER_WHITELIST_PERIOD", 86400)
ABUSE_SUSPEND_PERIOD: int = 604800  # 1 week in seconds

logger = get_logger(prefix="[Auth Service Password]")
security_logger = SecurityLogger(prefix="[AUTH-PASSWORD-SECURITY]")
db_logger = DatabaseLogger(prefix="[AUTH-PASSWORD-DB]")


@log_performance("change_user_password", log_args=False)
async def change_user_password(current_user: Dict[str, Any], password_request: PasswordChangeRequest) -> bool:
    """
    Change the password for the current user after validating the old password.
    Should require recent authentication.

    Args:
        current_user (Dict[str, Any]): The current user document.
        password_request (PasswordChangeRequest): Password change request object.

    Returns:
        bool: True if password was changed successfully.

    Raises:
        HTTPException: If validation fails or update fails.
    """
    if not validate_password_strength(password_request.new_password):
        logger.info("Password strength validation failed for user %s", current_user.get("username"))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long and contain "
            "uppercase, lowercase, digit, and special character",
        )
    if not bcrypt.checkpw(
        password_request.old_password.encode("utf-8"), current_user["hashed_password"].encode("utf-8")
    ):
        logger.info("Old password check failed for user %s", current_user.get("username"))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid old password")
    new_hashed_pw = bcrypt.hashpw(password_request.new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    result = await db_manager.get_collection("users").update_one(
        {"username": current_user["username"]}, {"$set": {"hashed_password": new_hashed_pw}}
    )
    if not result.modified_count:
        logger.error("Failed to update password for user %s", current_user.get("username"))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update password")
    logger.info("Password changed for user %s; tokens should be invalidated.", current_user["username"])
    return True


async def send_password_reset_email(
    email: str,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_time: Optional[str] = None,
    location: Optional[str] = None,
    isp: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    """
    Send a password reset email with metadata and a real token (hashed in DB).
    Enforces rate limits and stricter abuse detection for whitelisted pairs.

    Args:
        email (str): The user's email address.
        ip (Optional[str]): The requester's IP address.
        user_agent (Optional[str]): The user agent string.
        request_time (Optional[str]): Time of the request.
        location (Optional[str]): Geolocation of the request.
        isp (Optional[str]): ISP of the requester.

    Returns:
        Optional[Dict[str, str]]: None if successful, or a message dict if rate limited.

    Side Effects:
        Writes to Redis, updates user in DB, sends email.
    """
    try:
        redis_conn = await redis_manager.get_redis()
        fp_key = f"forgot_password:{email}"
        rv_key = f"resend_verification:{email}"
        combined_key = f"combined_reset_verify:{email}"
        fp_count = await redis_conn.incr(fp_key)
        if fp_count == 1:
            await redis_conn.expire(fp_key, 60)
        combined_count = await redis_conn.incr(combined_key)
        if combined_count == 1:
            await redis_conn.expire(combined_key, 60)
        if fp_count > 2 or combined_count > 3:
            logger.warning("Password reset email rate limited for %s", email)
            return {"message": "Password reset email did not sent"}
        base_url = getattr(settings, "BASE_URL", "http://localhost:8000")
        user = await db_manager.get_collection("users").find_one({"email": email})
        if not user:
            logger.info("Password reset requested for non-existent email: %s", email)
            return None  # Do not reveal user existence
        reset_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
        expiry = datetime.now(timezone.utc) + timedelta(minutes=30)
        await db_manager.get_collection("users").update_one(
            {"_id": user["_id"]},
            {"$set": {"password_reset_token": token_hash, "password_reset_token_expiry": expiry.isoformat()}},
        )
        reset_link = f"{base_url}/auth/reset-password?token={reset_token}"
        meta = f"""
        <ul>
            <li><b>IP Address:</b> {ip or 'Unknown'}</li>
            <li><b>Location:</b> {location or 'Unknown'}</li>
            <li><b>Time:</b> {request_time or 'Unknown'}</li>
            <li><b>Device:</b> {user_agent or 'Unknown'}</li>
            <li><b>ISP:</b> {isp or 'Unknown'}</li>
        </ul>
        """
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
                await block_reset_pair(email, ip)
                warning_message = (
                    "<b>Warning:</b> You have exceeded the allowed number of password reset requests from this device in 24 hours. "
                    "Further requests are blocked for 24 hours."
                )
                abuse_key = f"abuse:reset:whitelist_abuse:{email}:{ip}"
                abuse_count = await redis_conn.incr(abuse_key)
                if abuse_count == 1:
                    await redis_conn.expire(abuse_key, ABUSE_SUSPEND_PERIOD)
                await log_reset_abuse_event(
                    email=email,
                    ip=ip,
                    user_agent=user_agent,
                    event_type="self_abuse",
                    details="Exceeded whitelist limit for password resets",
                    whitelisted=True,
                    action_taken="blocked",
                )
                if abuse_count >= STRICTER_WHITELIST_LIMIT:
                    await db_manager.get_collection("users").update_one(
                        {"email": email},
                        {
                            "$set": {
                                "is_active": False,
                                "abuse_suspended": True,
                                "abuse_suspended_at": datetime.now(timezone.utc),
                            }
                        },
                    )
                    abuse_message = "<b>Notice:</b> Your account has been suspended due to repeated abuse of the password reset system. Please contact support."
                    await redis_conn.sadd("abuse:reset:abuse_ips", ip)
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
        logger.info(
            "Password reset metadata: IP=%s, UA=%s, Time=%s, Location=%s, ISP=%s",
            ip,
            user_agent,
            request_time,
            location,
            isp,
        )
        await email_manager._send_via_console(email, "Password Reset Requested", html_content)
        return None
    except RuntimeError:
        logger.error("Failed to send password reset email for %s", email, exc_info=True)
        return {"message": "Password reset email did not sent"}


async def send_password_reset_notification(email: str) -> None:
    """
    Send a notification email after successful password reset.

    Args:
        email (str): The user's email address.

    Side Effects:
        Sends an email to the user.
    """
    subject = "Your password was reset"
    html_content = (
        "<html><body>"
        "<h2>Password Changed</h2>"
        "<p>Your password was successfully reset. If this wasn't you, please contact support immediately.</p>"
        "</body></html>"
    )
    logger.info("[NOTIFY EMAIL] To: %s | Subject: %s", email, subject)
    await email_manager._send_via_console(email, subject, html_content)


async def send_trusted_ip_lockdown_code_email(
    email: str, code: str, action: str, trusted_ips: list[str], email_manager=None
):
    """
    Send a trusted IP lockdown confirmation code email with HTML template.
    Args:
        email (str): The user's email address.
        code (str): The confirmation code.
        action (str): 'enable' or 'disable'.
        trusted_ips (list[str]): List of IPs allowed to confirm.
        email_manager: Optional email manager for sending (defaults to global if not provided).
    """
    from second_brain_database.routes.auth.routes_html import render_trusted_ip_lockdown_email

    subject = f"Confirm Trusted IP Lockdown {action.title()}"
    html_content = render_trusted_ip_lockdown_email(code, action, trusted_ips)
    if email_manager is None:
        from second_brain_database.managers.email import email_manager as default_email_manager

        email_manager = default_email_manager
    await email_manager._send_via_console(email, subject, html_content)


async def send_user_agent_lockdown_code_email(
    email: str, code: str, action: str, trusted_user_agents: list[str], email_manager=None
):
    """
    Send a User Agent lockdown confirmation code email with HTML template.

    Args:
        email (str): The user's email address.
        code (str): The confirmation code.
        action (str): 'enable' or 'disable'.
        trusted_user_agents (list[str]): List of User Agents allowed to confirm.
        email_manager: Optional email manager for sending (defaults to global if not provided).
    """
    from second_brain_database.routes.auth.routes_html import render_trusted_user_agent_lockdown_email

    subject = f"Confirm User Agent Lockdown {action.title()}"
    html_content = render_trusted_user_agent_lockdown_email(code, action, trusted_user_agents)
    if email_manager is None:
        from second_brain_database.managers.email import email_manager as default_email_manager

        email_manager = default_email_manager
    await email_manager._send_via_console(email, subject, html_content)


@log_performance("send_blocked_ip_notification")
async def send_blocked_ip_notification(email: str, attempted_ip: str, trusted_ips: list[str], endpoint: str):
    """
    Send an email notification about a blocked access attempt due to IP Lockdown.

    Args:
        email (str): The user's email address.
        attempted_ip (str): The IP address that was blocked.
        trusted_ips (list[str]): List of trusted IP addresses.
        endpoint (str): The endpoint that was accessed.
    """
    from second_brain_database.routes.auth.routes_html import render_blocked_ip_notification_email
    from second_brain_database.routes.auth.services.temporary_access import generate_temporary_ip_access_token

    logger.info("Sending blocked IP notification to %s for IP %s", email, attempted_ip)

    # Generate temporary access tokens for action buttons
    allow_once_token = None
    add_to_trusted_token = None

    try:
        allow_once_token = await generate_temporary_ip_access_token(
            user_email=email, ip_address=attempted_ip, action="allow_once", endpoint=endpoint
        )
        logger.debug("Generated allow once token for %s", email)
    except Exception as e:
        logger.error("Failed to generate allow once token for %s: %s", email, e, exc_info=True)

    try:
        add_to_trusted_token = await generate_temporary_ip_access_token(
            user_email=email, ip_address=attempted_ip, action="add_to_trusted", endpoint=endpoint
        )
        logger.debug("Generated add to trusted token for %s", email)
    except Exception as e:
        logger.error("Failed to generate add to trusted token for %s: %s", email, e, exc_info=True)

    # Log security event for blocked IP attempt
    log_security_event(
        event_type="ip_lockdown_violation",
        user_id=email,
        ip_address=attempted_ip,
        success=False,
        details={
            "attempted_ip": attempted_ip,
            "trusted_ips": trusted_ips,
            "endpoint": endpoint,
            "action": "notification_sent",
            "tokens_generated": {
                "allow_once": allow_once_token is not None,
                "add_to_trusted": add_to_trusted_token is not None,
            },
        },
    )

    subject = "Blocked Access Attempt: IP Lockdown Active"
    timestamp = datetime.now(timezone.utc).isoformat()
    html_content = render_blocked_ip_notification_email(
        attempted_ip=attempted_ip,
        trusted_ips=trusted_ips,
        endpoint=endpoint,
        timestamp=timestamp,
        allow_once_token=allow_once_token,
        add_to_trusted_token=add_to_trusted_token,
    )

    try:
        await email_manager._send_via_console(email, subject, html_content)
        logger.info("Successfully sent blocked IP notification to %s", email)
    except RuntimeError as e:
        logger.error("Failed to send blocked IP notification to %s: %s", email, e, exc_info=True)
        log_error_with_context(
            e,
            context={"email": email, "attempted_ip": attempted_ip, "endpoint": endpoint},
            operation="send_blocked_ip_notification",
        )


@log_performance("send_blocked_user_agent_notification")
async def send_blocked_user_agent_notification(
    email: str, attempted_user_agent: str, trusted_user_agents: list[str], endpoint: str
):
    """
    Send an email notification about a blocked access attempt due to User Agent Lockdown.

    Args:
        email (str): The user's email address.
        attempted_user_agent (str): The User Agent that was blocked.
        trusted_user_agents (list[str]): List of trusted User Agents.
        endpoint (str): The endpoint that was accessed.
    """
    from second_brain_database.routes.auth.routes_html import render_blocked_user_agent_notification_email
    from second_brain_database.routes.auth.services.temporary_access import generate_temporary_user_agent_access_token

    logger.info("Sending blocked User Agent notification to %s for User Agent %s", email, attempted_user_agent)

    # Generate temporary access tokens for action buttons
    allow_once_token = None
    add_to_trusted_token = None

    try:
        allow_once_token = await generate_temporary_user_agent_access_token(
            user_email=email, user_agent=attempted_user_agent, action="allow_once", endpoint=endpoint
        )
        logger.debug("Generated allow once token for %s", email)
    except Exception as e:
        logger.error("Failed to generate allow once token for %s: %s", email, e, exc_info=True)

    try:
        add_to_trusted_token = await generate_temporary_user_agent_access_token(
            user_email=email, user_agent=attempted_user_agent, action="add_to_trusted", endpoint=endpoint
        )
        logger.debug("Generated add to trusted token for %s", email)
    except Exception as e:
        logger.error("Failed to generate add to trusted token for %s: %s", email, e, exc_info=True)

    # Log security event for blocked User Agent attempt
    log_security_event(
        event_type="user_agent_lockdown_violation",
        user_id=email,
        ip_address="unknown",  # IP not relevant for User Agent lockdown
        success=False,
        details={
            "attempted_user_agent": attempted_user_agent,
            "trusted_user_agents": trusted_user_agents,
            "endpoint": endpoint,
            "action": "notification_sent",
            "tokens_generated": {
                "allow_once": allow_once_token is not None,
                "add_to_trusted": add_to_trusted_token is not None,
            },
        },
    )

    subject = "Blocked Access Attempt: User Agent Lockdown Active"
    timestamp = datetime.now(timezone.utc).isoformat()
    html_content = render_blocked_user_agent_notification_email(
        attempted_user_agent=attempted_user_agent,
        trusted_user_agents=trusted_user_agents,
        endpoint=endpoint,
        timestamp=timestamp,
        allow_once_token=allow_once_token,
        add_to_trusted_token=add_to_trusted_token,
    )

    try:
        await email_manager._send_via_console(email, subject, html_content)
        logger.info("Successfully sent blocked User Agent notification to %s", email)
    except RuntimeError as e:
        logger.error("Failed to send blocked User Agent notification to %s: %s", email, e, exc_info=True)
        log_error_with_context(
            e,
            context={"email": email, "attempted_user_agent": attempted_user_agent, "endpoint": endpoint},
            operation="send_blocked_user_agent_notification",
        )
