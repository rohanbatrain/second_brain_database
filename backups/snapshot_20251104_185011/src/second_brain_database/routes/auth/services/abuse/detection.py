"""
Abuse detection logic for password reset and authentication workflows.

This module provides asynchronous functions to log password reset requests,
detect abuse patterns, and identify repeated violators. It uses Redis for
real-time detection and MongoDB for persistent event logging and admin review.
"""

from datetime import datetime, timedelta
import json
from typing import Any, Dict, List, Optional, Set, TypedDict

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.routes.auth.services.abuse.events import log_reset_abuse_event
from second_brain_database.routes.auth.services.abuse.management import is_pair_blocked, is_pair_whitelisted
from second_brain_database.routes.auth.services.abuse.notification import notify_user_of_suspicious_reset
from second_brain_database.utils.logging_utils import (
    DatabaseLogger,
    SecurityLogger,
    log_database_operation,
    log_error_with_context,
    log_performance,
    log_security_event,
)

# Constants
MAX_RESET_REQUESTS: int = getattr(settings, "MAX_RESET_REQUESTS", 8)
MAX_RESET_UNIQUE_IPS: int = getattr(settings, "MAX_RESET_UNIQUE_IPS", 4)
REDIS_EMAIL_KEY_FMT: str = "abuse:reset:email:{email}"
REDIS_PAIR_KEY_FMT: str = "abuse:reset:pair:{email}:{ip}"
REDIS_FLAGGED_KEY_FMT: str = "abuse:reset:flagged:{email}:{ip}"
REDIS_TTL_SECONDS: int = 900  # 15 minutes
EMAIL_LIST_MAXLEN: int = 50
PAIR_LIST_MAXLEN: int = 20

logger = get_logger(prefix="[Auth Service Abuse Detection]")
security_logger = SecurityLogger(prefix="[ABUSE-DETECTION-SECURITY]")
db_logger = DatabaseLogger(prefix="[ABUSE-DETECTION-DB]")


class AbuseDetectionResult(TypedDict):
    """
    TypedDict representing the result of password reset abuse detection.
    Fields:
        suspicious (bool): Whether abuse is detected.
        reasons (List[str]): Reasons for suspicion.
        ip_reputation (Optional[str]): IP reputation info or None.
    """

    suspicious: bool
    reasons: List[str]
    ip_reputation: Optional[str]


@log_performance("log_password_reset_request")
async def log_password_reset_request(email: str, ip: str, user_agent: str, timestamp: str) -> None:
    """
    Log a password reset request to Redis for real-time abuse detection.
    Stores a rolling window of requests per email and per (email, ip) pair.

    Args:
        email (str): The user's email address.
        ip (str): The requester's IP address.
        user_agent (str): The user agent string.
        timestamp (str): ISO8601 timestamp of the request.

    Side Effects:
        Writes to Redis. No sensitive data is stored. Only metadata for abuse detection.
    """
    logger.info("Logging password reset request for email=%s from IP=%s", email, ip)

    # Log security event for password reset request tracking
    log_security_event(
        event_type="password_reset_request_logged",
        user_id=email,
        ip_address=ip,
        success=True,
        details={"user_agent": user_agent, "timestamp": timestamp, "tracking_purpose": "abuse_detection"},
    )

    try:
        redis_conn = await redis_manager.get_redis()
        email_key = REDIS_EMAIL_KEY_FMT.format(email=email)

        # Store request data for email-based tracking
        request_data = {"ip": ip, "user_agent": user_agent, "timestamp": timestamp}
        await redis_conn.lpush(email_key, json.dumps(request_data))
        await redis_conn.ltrim(email_key, 0, EMAIL_LIST_MAXLEN - 1)
        await redis_conn.expire(email_key, REDIS_TTL_SECONDS)

        # Store request data for (email, ip) pair tracking
        pair_key = REDIS_PAIR_KEY_FMT.format(email=email, ip=ip)
        pair_data = {"user_agent": user_agent, "timestamp": timestamp}
        await redis_conn.lpush(pair_key, json.dumps(pair_data))
        await redis_conn.ltrim(pair_key, 0, PAIR_LIST_MAXLEN - 1)
        await redis_conn.expire(pair_key, REDIS_TTL_SECONDS)

        logger.debug(
            "Successfully logged password reset request for email=%s, ip=%s, user_agent=%s", email, ip, user_agent
        )

    except Exception as e:
        logger.error("Failed to log password reset request for email=%s, ip=%s: %s", email, ip, e, exc_info=True)
        log_error_with_context(
            e,
            context={"email": email, "ip": ip, "user_agent": user_agent, "timestamp": timestamp},
            operation="log_password_reset_request",
        )


@log_performance("detect_password_reset_abuse")
async def detect_password_reset_abuse(email: str, ip: str) -> AbuseDetectionResult:
    """
    Detect password reset abuse patterns for an email/IP combination.

    Args:
        email: User's email address
        ip: IP address of the request

    Returns:
        AbuseDetectionResult: Detection results with suspicious flag, reasons, and IP reputation
    """
    logger.info("Analyzing password reset abuse patterns for email=%s from IP=%s", email, ip)

    # TEST BYPASS: Skip abuse detection for test emails or test environment
    # ⚠️⚠️⚠️ WARNING: REMOVE THIS BYPASS BEFORE DEPLOYING TO PRODUCTION! ⚠️⚠️⚠️
    # This bypass is ONLY for testing purposes and should NEVER be in production code.
    # It allows unlimited password reset requests for emails containing 'test' or starting with 'test'.
    # Remove this entire if block and the associated logging before going live!
    if email and ("test" in email.lower() or email.startswith("test") or "@test." in email):
        logger.info("TEST BYPASS: Skipping abuse detection for test email: %s", email)
        return {"suspicious": False, "reasons": ["Test email bypass"], "ip_reputation": None}

    suspicious: bool = False
    reasons: List[str] = []
    ip_reputation: Optional[str] = None

    try:
        redis_conn = await redis_manager.get_redis()

        # Whitelist/blocklist checks
        if await is_pair_whitelisted(email, ip):
            logger.info("Pair whitelisted: %s, %s", email, ip)
            log_security_event(
                event_type="abuse_detection_whitelisted",
                user_id=email,
                ip_address=ip,
                success=True,
                details={"reason": "pair_whitelisted"},
            )
            return {"suspicious": False, "reasons": ["Pair whitelisted"], "ip_reputation": None}

        if await is_pair_blocked(email, ip):
            logger.warning("Pair blocked: %s, %s", email, ip)
            log_security_event(
                event_type="abuse_detection_blocked",
                user_id=email,
                ip_address=ip,
                success=True,
                details={"reason": "pair_blocked"},
            )
            return {"suspicious": True, "reasons": ["Pair blocked"], "ip_reputation": None}

        # Analyze recent requests
        abuse_key = REDIS_EMAIL_KEY_FMT.format(email=email)
        recent_requests: List[Any] = await redis_conn.lrange(abuse_key, 0, EMAIL_LIST_MAXLEN - 1) or []
        unique_ips: Set[str] = set()

        for entry in recent_requests:
            try:
                data = json.loads(entry)
                ip_val = data.get("ip")
                if ip_val:
                    unique_ips.add(ip_val)
            except Exception:
                logger.debug("Malformed entry in abuse log", exc_info=True)
                continue

        logger.debug(
            "Abuse analysis for %s: %d recent requests, %d unique IPs", email, len(recent_requests), len(unique_ips)
        )

        # Check for high volume abuse (self-abuse)
        if len(recent_requests) >= MAX_RESET_REQUESTS:
            suspicious = True
            reason = f"High volume: {len(recent_requests)} reset requests in 15 min"
            reasons.append(reason)

            await log_reset_abuse_event(
                email=email,
                ip=ip,
                user_agent=None,
                event_type="self_abuse",
                details=reason,
                whitelisted=False,
                action_taken="notified",
            )

            log_security_event(
                event_type="self_abuse_detected",
                user_id=email,
                ip_address=ip,
                success=True,
                details={
                    "request_count": len(recent_requests),
                    "threshold": MAX_RESET_REQUESTS,
                    "time_window": "15_minutes",
                },
            )

            logger.warning("Self-abuse detected for %s from %s: %d requests", email, ip, len(recent_requests))

        # Check for targeted abuse (many unique IPs)
        if len(unique_ips) >= MAX_RESET_UNIQUE_IPS:
            suspicious = True
            reason = f"Many unique IPs: {len(unique_ips)} for this email in 15 min"
            reasons.append(reason)

            await log_reset_abuse_event(
                email=email,
                ip=ip,
                user_agent=None,
                event_type="targeted_abuse",
                details=reason,
                whitelisted=False,
                action_taken="notified",
            )

            log_security_event(
                event_type="targeted_abuse_detected",
                user_id=email,
                ip_address=ip,
                success=True,
                details={
                    "unique_ip_count": len(unique_ips),
                    "threshold": MAX_RESET_UNIQUE_IPS,
                    "time_window": "15_minutes",
                    "unique_ips": list(unique_ips),
                },
            )

            logger.warning("Targeted abuse detected for %s from %s: %d unique IPs", email, ip, len(unique_ips))

        # IP reputation check
        try:
            import httpx

            logger.debug("Checking IP reputation for %s", ip)

            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(f"https://ipinfo.io/{ip}/json")
                data = resp.json()
                privacy = data.get("privacy", {})

                if privacy.get("vpn") or privacy.get("proxy"):
                    suspicious = True
                    ip_reputation = "vpn/proxy"
                    reasons.append("IP is VPN/proxy (IPinfo)")

                    log_security_event(
                        event_type="suspicious_ip_detected",
                        user_id=email,
                        ip_address=ip,
                        success=True,
                        details={"reputation": ip_reputation, "source": "ipinfo", "privacy_flags": privacy},
                    )

                elif data.get("abuse") or privacy.get("relay"):
                    suspicious = True
                    ip_reputation = "abuse/relay"
                    reasons.append("IP flagged as abuse/relay (IPinfo)")

                    log_security_event(
                        event_type="abusive_ip_detected",
                        user_id=email,
                        ip_address=ip,
                        success=True,
                        details={
                            "reputation": ip_reputation,
                            "source": "ipinfo",
                            "abuse_flags": {"abuse": data.get("abuse"), "relay": privacy.get("relay")},
                        },
                    )

                else:
                    ip_reputation = data.get("org")

            logger.debug("IP reputation check completed for %s: %s", ip, ip_reputation)

        except Exception as e:
            logger.error("IPinfo check failed for %s: %s", ip, e, exc_info=True)
            log_error_with_context(e, context={"ip": ip, "email": email}, operation="ip_reputation_check")
            ip_reputation = None

        # Store flag in Redis and notify if suspicious
        if suspicious:
            flag_key = REDIS_FLAGGED_KEY_FMT.format(email=email, ip=ip)
            flag_data = {"timestamp": datetime.utcnow().isoformat(), "reasons": reasons, "ip_reputation": ip_reputation}

            try:
                await redis_conn.set(flag_key, json.dumps(flag_data), ex=REDIS_TTL_SECONDS)
                await notify_user_of_suspicious_reset(email, reasons, ip)

                logger.warning(
                    "Flagged and notified suspicious activity for %s from %s: %s", email, ip, ", ".join(reasons)
                )

                log_security_event(
                    event_type="abuse_flagged_and_notified",
                    user_id=email,
                    ip_address=ip,
                    success=True,
                    details={"reasons": reasons, "ip_reputation": ip_reputation, "notification_sent": True},
                )

            except Exception as e:
                logger.error("Failed to flag or notify user of suspicious reset for %s: %s", email, e, exc_info=True)
                log_error_with_context(
                    e,
                    context={"email": email, "ip": ip, "reasons": reasons},
                    operation="flag_and_notify_suspicious_reset",
                )

        result = {"suspicious": suspicious, "reasons": reasons, "ip_reputation": ip_reputation}
        logger.info(
            "Abuse detection completed for %s from %s: suspicious=%s, reasons=%d", email, ip, suspicious, len(reasons)
        )

        return result

    except Exception as e:
        logger.error("Error in detect_password_reset_abuse for %s from %s: %s", email, ip, e, exc_info=True)
        log_error_with_context(e, context={"email": email, "ip": ip}, operation="detect_password_reset_abuse")
        return {"suspicious": False, "reasons": [], "ip_reputation": None}


async def is_repeated_violator(
    user: Dict[str, Any], window_minutes: Optional[int] = None, min_unique_ips: Optional[int] = None
) -> bool:
    """
    Determines if a user is a repeated password reset violator.

    Args:
        user (Dict[str, Any]): User dict with at least 'email'.
        window_minutes (Optional[int]): Time window in minutes.
        min_unique_ips (Optional[int]): Minimum unique IPs to consider.

    Returns:
        bool: True if user is a repeated violator, else False.

    Side Effects:
        Reads from MongoDB.
    """

    window_minutes = window_minutes or getattr(settings, "REPEATED_VIOLATOR_WINDOW_MINUTES", 10)
    min_unique_ips = min_unique_ips or getattr(settings, "REPEATED_VIOLATOR_MIN_UNIQUE_IPS", 3)
    try:
        collection = db_manager.get_collection("abuse_events")
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=window_minutes)
        query = {
            "email": user.get("email"),
            "event_type": "self_abuse",
            "timestamp": {"$gte": window_start.isoformat()},
        }
        cursor = collection.find(query)
        events: List[Dict[str, Any]] = []
        async for doc in cursor:
            events.append(doc)
        ip_to_times: Dict[str, List[datetime]] = {}
        for e in events:
            ts = e["timestamp"]
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except Exception:
                    logger.debug("Malformed timestamp in abuse_events", exc_info=True)
                    continue
            ip = e["ip"]
            ip_to_times.setdefault(ip, []).append(ts)
        if len(ip_to_times) < min_unique_ips:
            return False
        all_times = sorted([ts for times in ip_to_times.values() for ts in times])
        for t in all_times:
            count = sum(
                any(abs((t - ts).total_seconds()) < window_minutes * 60 for ts in times)
                for times in ip_to_times.values()
            )
            if count >= min_unique_ips:
                return True
    except Exception:
        logger.error("Error in is_repeated_violator", exc_info=True)
    return False
