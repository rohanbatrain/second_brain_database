"""
Abuse detection logic for password reset and authentication workflows.

This module provides asynchronous functions to log password reset requests,
detect abuse patterns, and identify repeated violators. It uses Redis for
real-time detection and MongoDB for persistent event logging and admin review.
"""
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, TypedDict
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.config import settings
from second_brain_database.routes.auth.services.abuse.events import log_reset_abuse_event
from second_brain_database.routes.auth.services.abuse.management import is_pair_blocked, is_pair_whitelisted
from second_brain_database.routes.auth.services.abuse.notification import notify_user_of_suspicious_reset
from second_brain_database.database import db_manager

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

async def log_password_reset_request(
    email: str, ip: str, user_agent: str, timestamp: str
) -> None:
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
    try:
        redis_conn = await redis_manager.get_redis()
        email_key = REDIS_EMAIL_KEY_FMT.format(email=email)
        await redis_conn.lpush(
            email_key, json.dumps({"ip": ip, "user_agent": user_agent, "timestamp": timestamp})
        )
        await redis_conn.ltrim(email_key, 0, EMAIL_LIST_MAXLEN - 1)
        await redis_conn.expire(email_key, REDIS_TTL_SECONDS)
        pair_key = REDIS_PAIR_KEY_FMT.format(email=email, ip=ip)
        await redis_conn.lpush(
            pair_key, json.dumps({"user_agent": user_agent, "timestamp": timestamp})
        )
        await redis_conn.ltrim(pair_key, 0, PAIR_LIST_MAXLEN - 1)
        await redis_conn.expire(pair_key, REDIS_TTL_SECONDS)
        logger.debug(
            "Logged password reset request for email=%s, ip=%s, user_agent=%s",
            email, ip, user_agent
        )
    except Exception:
        logger.error("Failed to log password reset request", exc_info=True)

async def detect_password_reset_abuse(email: str, ip: str) -> AbuseDetectionResult:
    suspicious: bool = False
    reasons: List[str] = []
    ip_reputation: Optional[str] = None
    try:
        redis_conn = await redis_manager.get_redis()
        # Whitelist/blocklist checks
        if await is_pair_whitelisted(email, ip):
            logger.info(f"Pair whitelisted: {email}, {ip}")
            return {"suspicious": False, "reasons": ["Pair whitelisted"], "ip_reputation": None}
        if await is_pair_blocked(email, ip):
            logger.warning(f"Pair blocked: {email}, {ip}")
            return {"suspicious": True, "reasons": ["Pair blocked"], "ip_reputation": None}
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
        if len(recent_requests) >= MAX_RESET_REQUESTS:
            suspicious = True
            reasons.append(f"High volume: {len(recent_requests)} reset requests in 15 min")
            await log_reset_abuse_event(
                email=email,
                ip=ip,
                user_agent=None,
                event_type="self_abuse",
                details=f"{len(recent_requests)} reset requests in 15 min",
                whitelisted=False,
                action_taken="notified",
            )
            logger.info(f"Self-abuse detected for {email} from {ip}")
        if len(unique_ips) >= MAX_RESET_UNIQUE_IPS:
            suspicious = True
            reasons.append(f"Many unique IPs: {len(unique_ips)} for this email in 15 min")
            await log_reset_abuse_event(
                email=email,
                ip=ip,
                user_agent=None,
                event_type="targeted_abuse",
                details=f"{len(unique_ips)} unique IPs in 15 min for this email",
                whitelisted=False,
                action_taken="notified",
            )
            logger.info(f"Targeted abuse detected for {email} from {ip}")
        # IP reputation check
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(f"https://ipinfo.io/{ip}/json")
                data = resp.json()
                privacy = data.get("privacy", {})
                if privacy.get("vpn") or privacy.get("proxy"):
                    suspicious = True
                    ip_reputation = "vpn/proxy"
                    reasons.append("IP is VPN/proxy (IPinfo)")
                elif data.get("abuse") or privacy.get("relay"):
                    suspicious = True
                    ip_reputation = "abuse/relay"
                    reasons.append("IP flagged as abuse/relay (IPinfo)")
                else:
                    ip_reputation = data.get("org")
            logger.debug(f"IPinfo checked for {ip}: {ip_reputation}")
        except Exception:
            logger.error(f"IPinfo check failed for {ip}", exc_info=True)
            ip_reputation = None
        # Store flag in Redis and notify if suspicious
        if suspicious:
            flag_key = REDIS_FLAGGED_KEY_FMT.format(email=email, ip=ip)
            try:
                await redis_conn.set(
                    flag_key,
                    json.dumps({
                        "timestamp": datetime.utcnow().isoformat(),
                        "reasons": reasons,
                        "ip_reputation": ip_reputation
                    }),
                    ex=REDIS_TTL_SECONDS
                )
                await notify_user_of_suspicious_reset(email, reasons, ip)
                logger.info(f"Flagged and notified for {email}, {ip}")
            except Exception:
                logger.error("Failed to flag or notify user of suspicious reset", exc_info=True)
    except Exception:
        logger.error("Error in detect_password_reset_abuse", exc_info=True)
    return {"suspicious": suspicious, "reasons": reasons, "ip_reputation": ip_reputation}

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
            "timestamp": {"$gte": window_start.isoformat()}
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
