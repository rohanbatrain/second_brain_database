from second_brain_database.database import db_manager
from second_brain_database.managers.email import email_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.services.abuse.management import is_pair_whitelisted
from second_brain_database.routes.auth.services.utils.redis_utils import generate_abuse_action_token
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.config import settings

STRICTER_WHITELIST_LIMIT = getattr(settings, "STRICTER_WHITELIST_LIMIT", 3)
ABUSE_ACTION_TOKEN_EXPIRY = getattr(settings, "ABUSE_ACTION_TOKEN_EXPIRY", 1800)
ABUSE_ACTION_BLOCK_EXPIRY = getattr(settings, "ABUSE_ACTION_BLOCK_EXPIRY", 86400)

logger = get_logger()


async def notify_user_of_suspicious_reset(email: str, reasons: list, ip: str = None, user_agent: str = None, request_time: str = None, location: str = None, isp: str = None):
    """
    Notify the user by email if a suspicious password reset attempt is detected for their account.
    Includes secure links to whitelist or block the (email, IP) pair.
    Includes full request metadata for user context and security.
    """
    user = await db_manager.get_collection("users").find_one({"email": email})
    if not user:
        return
    subject = "Suspicious Password Reset Attempt Detected"
    reason_list = "<ul>" + "".join(f"<li>{r}</li>" for r in reasons) + "</ul>"
    # Generate secure tokens for whitelist/block actions
    whitelist_token = await generate_abuse_action_token(email, ip, "whitelist", expiry_seconds=ABUSE_ACTION_TOKEN_EXPIRY)  # 30 min
    block_token = await generate_abuse_action_token(email, ip, "block", expiry_seconds=ABUSE_ACTION_BLOCK_EXPIRY)  # 24h
    base_url = getattr(settings, "BASE_URL", "http://localhost:8000")
    whitelist_link = f"{base_url}auth/confirm-reset-abuse?token={whitelist_token}"
    block_link = f"{base_url}auth/block-reset-abuse?token={block_token}"
    # Compose metadata section (same as password reset email)
    meta = f"""
    <ul>
        <li><b>IP Address:</b> {ip or 'Unknown'}</li>
        <li><b>Location:</b> {location or 'Unknown'}</li>
        <li><b>Time:</b> {request_time or 'Unknown'}</li>
        <li><b>Device:</b> {user_agent or 'Unknown'}</li>
        <li><b>ISP:</b> {isp or 'Unknown'}</li>
    </ul>
    """
    # Add warnings for stricter rate limit and possible suspension
    redis_conn = await redis_manager.get_redis()
    warning_message = ""
    abuse_message = ""
    if ip and await is_pair_whitelisted(email, ip):
        key = f"abuse:reset:whitelist_limit:{email}:{ip}"
        count = await redis_conn.get(key)
        if count is not None:
            count = int(count)
            stricter_limit = STRICTER_WHITELIST_LIMIT
            if count >= stricter_limit:
                warning_message = "<b>Warning:</b> You have exceeded the allowed number of password reset requests from this device in 24 hours. Further requests are blocked for 24 hours."
                abuse_key = f"abuse:reset:whitelist_abuse:{email}:{ip}"
                abuse_count = await redis_conn.get(abuse_key)
                if abuse_count is not None and int(abuse_count) >= STRICTER_WHITELIST_LIMIT:
                    abuse_message = "<b>Notice:</b> Your account has been suspended due to repeated abuse of the password reset system. Please contact support."
                elif count == stricter_limit - 1:
                    warning_message = "<b>Warning:</b> You are about to reach the maximum allowed password reset requests from this device in 24 hours. Further requests will be blocked."
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
    logger.info("[SECURITY NOTIFY] To: %s | Subject: %s | Reasons: %s | IP: %s | UA: %s | Time: %s | Location: %s | ISP: %s", email, subject, reasons, ip, user_agent, request_time, location, isp)
    await email_manager._send_via_console(email, subject, html_content)

