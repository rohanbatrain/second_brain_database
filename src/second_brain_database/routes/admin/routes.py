"""
Admin API endpoints for password reset abuse management, whitelist/blocklist, and abuse event review.

- PEP 8/257 compliant, MyPy strict compatible.
- All endpoints are typed, with docstrings for each route.
- Linting/tooling config at file end.
"""

from fastapi import APIRouter, Depends, Query

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.routes.admin.models import AbuseEvent, AbuseEventResolveRequest, EmailIpPair
from second_brain_database.routes.admin.service import (
    admin_add_blocklist_pair,
    admin_add_whitelist_pair,
    admin_list_abuse_events,
    admin_list_blocklist_pairs,
    admin_list_whitelist_pairs,
    admin_remove_blocklist_pair,
    admin_remove_whitelist_pair,
    admin_resolve_abuse_event,
    block_reset_pair,
    whitelist_reset_pair,
)
from second_brain_database.routes.auth import require_admin

logger = get_logger(prefix="[Admin Routes]")

router = APIRouter(prefix="/admin", tags=["admin"])


# --- Admin Endpoints for Password Reset Abuse Management ---
@router.post("/whitelist", dependencies=[Depends(require_admin)])
async def admin_add_whitelist(pair: EmailIpPair) -> dict:
    """Admin: Add an (email, ip) pair to the password reset whitelist.

    This endpoint allows an administrator to manually add a combination of an email address and an IP address to a whitelist in Redis.
    When a user with this email and IP address requests a password reset, the request will be allowed even if it would otherwise be blocked by abuse detection mechanisms.

    Args:
        pair (EmailIpPair): An object containing the email and IP address to whitelist.

    Returns:
        dict: A dictionary with a "success" key indicating whether the operation was successful.
    """
    result = await admin_add_whitelist_pair(pair.email, pair.ip)
    logger.info("Admin added whitelist pair: %s:%s", pair.email, pair.ip)
    return {"success": result}


@router.delete("/whitelist", dependencies=[Depends(require_admin)])
async def admin_remove_whitelist(pair: EmailIpPair) -> dict:
    """Admin: Remove an (email, ip) pair from the password reset whitelist.

    This endpoint allows an administrator to remove a combination of an email address and an IP address from the whitelist in Redis.
    Once removed, password reset requests from this pair will be subject to the standard abuse detection rules.

    Args:
        pair (EmailIpPair): An object containing the email and IP address to remove from the whitelist.

    Returns:
        dict: A dictionary with a "success" key indicating whether the operation was successful.
    """
    result = await admin_remove_whitelist_pair(pair.email, pair.ip)
    logger.info("Admin removed whitelist pair: %s:%s", pair.email, pair.ip)
    return {"success": result}


@router.get("/whitelist", dependencies=[Depends(require_admin)])
async def admin_list_whitelist() -> list[EmailIpPair]:
    """Admin: List all (email, ip) pairs in the password reset whitelist.

    This endpoint retrieves and returns all the email and IP address pairs that are currently in the password reset whitelist from Redis.

    Returns:
        list[EmailIpPair]: A list of objects, each containing an email and IP address pair from the whitelist.
    """
    logger.debug("Admin requested whitelist pairs.")
    pairs = await admin_list_whitelist_pairs()
    return [EmailIpPair(email=p["email"], ip=p["ip"]) for p in pairs]


@router.post("/blocklist", dependencies=[Depends(require_admin)])
async def admin_add_blocklist(pair: EmailIpPair) -> dict:
    """Admin: Add an (email, ip) pair to the password reset blocklist.

    This endpoint allows an administrator to manually add a combination of an email address and an IP address to a blocklist in Redis.
    When a user with this email and IP address attempts to reset their password, the request will be blocked.

    Args:
        pair (EmailIpPair): An object containing the email and IP address to block.

    Returns:
        dict: A dictionary with a "success" key indicating whether the operation was successful.
    """
    result = await admin_add_blocklist_pair(pair.email, pair.ip)
    logger.info("Admin added blocklist pair: %s:%s", pair.email, pair.ip)
    return {"success": result}


@router.delete("/blocklist", dependencies=[Depends(require_admin)])
async def admin_remove_blocklist(pair: EmailIpPair) -> dict:
    """Admin: Remove an (email, ip) pair from the password reset blocklist.

    This endpoint allows an administrator to remove a combination of an email address and an IP address from the blocklist in Redis.
    Once removed, password reset requests from this pair will no longer be automatically blocked.

    Args:
        pair (EmailIpPair): An object containing the email and IP address to remove from the blocklist.

    Returns:
        dict: A dictionary with a "success" key indicating whether the operation was successful.
    """
    result = await admin_remove_blocklist_pair(pair.email, pair.ip)
    logger.info("Admin removed blocklist pair: %s:%s", pair.email, pair.ip)
    return {"success": result}


@router.get("/blocklist", dependencies=[Depends(require_admin)])
async def admin_list_blocklist() -> list[EmailIpPair]:
    """Admin: List all (email, ip) pairs in the password reset blocklist.

    This endpoint retrieves and returns all the email and IP address pairs that are currently in the password reset blocklist from Redis.

    Returns:
        list[EmailIpPair]: A list of objects, each containing an email and IP address pair from the blocklist.
    """
    logger.debug("Admin requested blocklist pairs.")
    pairs = await admin_list_blocklist_pairs()
    return [EmailIpPair(email=p["email"], ip=p["ip"]) for p in pairs]


@router.get("/abuse-events", dependencies=[Depends(require_admin)])
async def admin_list_abuse_events_api(
    email: str = Query(None), event_type: str = Query(None), resolved: bool = Query(None), limit: int = Query(100)
) -> list[AbuseEvent]:
    """Admin: List password reset abuse events.

    This endpoint allows administrators to query and list password reset abuse events that have been recorded in the database.
    Events can be filtered by email, event type, and resolution status.

    Args:
        email (str, optional): Filter events by email address. Defaults to None.
        event_type (str, optional): Filter events by type (e.g., 'excessive_resets'). Defaults to None.
        resolved (bool, optional): Filter events by their resolution status. Defaults to None.
        limit (int, optional): The maximum number of events to return. Defaults to 100.

    Returns:
        list[AbuseEvent]: A list of abuse event objects matching the filter criteria.
    """
    logger.debug(
        "Admin requested abuse events: email=%s, event_type=%s, resolved=%s, limit=%d",
        email,
        event_type,
        resolved,
        limit,
    )
    events = await admin_list_abuse_events(email=email, event_type=event_type, resolved=resolved, limit=limit)
    return [AbuseEvent(**e) for e in events]


@router.post("/abuse-events/resolve", dependencies=[Depends(require_admin)])
async def admin_resolve_abuse_event_api(req: AbuseEventResolveRequest) -> dict:
    """Admin: Mark a password reset abuse event as resolved.

    This endpoint allows an administrator to mark a specific abuse event as resolved in the database.
    This is used to track which events have been reviewed and handled.

    Args:
        req (AbuseEventResolveRequest): An object containing the ID of the event to resolve and any resolution notes.

    Returns:
        dict: A dictionary with a "success" key indicating whether the operation was successful.
    """
    result = await admin_resolve_abuse_event(req.event_id, req.notes)
    logger.info("Admin resolved abuse event: %s, notes=%s", req.event_id, req.notes)
    return {"success": result}


# Legacy endpoints for direct pair management (optional, for admin UI compatibility)
@router.get("/list-reset-whitelist")
async def admin_list_reset_whitelist() -> dict:
    """Admin: List all reset whitelist pairs (legacy).

    This is a legacy endpoint that lists all email:ip pairs in the password reset whitelist.
    It is maintained for compatibility with older admin interfaces.

    Returns:
        dict: A dictionary containing a "whitelist" key with a list of whitelisted pairs.
    """
    redis_conn = await redis_manager.get_redis()
    members = await redis_conn.smembers("abuse:reset:whitelist")
    logger.debug("Admin listed reset whitelist pairs.")
    return {"whitelist": [m.decode() if hasattr(m, "decode") else m for m in members]}


@router.get("/list-reset-blocklist")
async def admin_list_reset_blocklist() -> dict:
    """Admin: List all reset blocklist pairs (legacy).

    This is a legacy endpoint that lists all email:ip pairs in the password reset blocklist.
    It is maintained for compatibility with older admin interfaces.

    Returns:
        dict: A dictionary containing a "blocklist" key with a list of blocklisted pairs.
    """
    redis_conn = await redis_manager.get_redis()
    members = await redis_conn.smembers("abuse:reset:blocklist")
    logger.debug("Admin listed reset blocklist pairs.")
    return {"blocklist": [m.decode() if hasattr(m, "decode") else m for m in members]}


@router.post("/whitelist-reset-pair")
async def admin_whitelist_reset_pair(pair: EmailIpPair) -> dict:
    """Admin: Whitelist a reset pair (legacy).

    This is a legacy endpoint to add an email:ip pair to the password reset whitelist.
    It is maintained for compatibility with older admin interfaces.

    Args:
        pair (EmailIpPair): An object containing the email and IP address to whitelist.

    Returns:
        dict: A message confirming the action.
    """
    await whitelist_reset_pair(pair.email, pair.ip)
    logger.info("Admin whitelisted reset pair: %s:%s", pair.email, pair.ip)
    return {"message": f"Whitelisted {pair.email}:{pair.ip}"}


@router.post("/block-reset-pair")
async def admin_block_reset_pair(pair: EmailIpPair) -> dict:
    """Admin: Block a reset pair (legacy).

    This is a legacy endpoint to add an email:ip pair to the password reset blocklist.
    It is maintained for compatibility with older admin interfaces.

    Args:
        pair (EmailIpPair): An object containing the email and IP address to block.

    Returns:
        dict: A message confirming the action.
    """
    await block_reset_pair(pair.email, pair.ip)
    logger.info("Admin blocked reset pair: %s:%s", pair.email, pair.ip)
    return {"message": f"Blocked {pair.email}:{pair.ip}"}


@router.delete("/whitelist-reset-pair")
async def admin_remove_whitelist_reset_pair(pair: EmailIpPair) -> dict:
    """Admin: Remove a reset pair from whitelist (legacy).

    This is a legacy endpoint to remove an email:ip pair from the password reset whitelist.
    It is maintained for compatibility with older admin interfaces.

    Args:
        pair (EmailIpPair): An object containing the email and IP address to remove.

    Returns:
        dict: A message confirming the action.
    """
    redis_conn = await redis_manager.get_redis()
    await redis_conn.srem("abuse:reset:whitelist", f"{pair.email}:{pair.ip}")
    logger.info("Admin removed reset pair from whitelist: %s:%s", pair.email, pair.ip)
    return {"message": f"Removed {pair.email}:{pair.ip} from whitelist"}


@router.delete("/block-reset-pair")
async def admin_remove_block_reset_pair(pair: EmailIpPair) -> dict:
    """Admin: Remove a reset pair from blocklist (legacy).

    This is a legacy endpoint to remove an email:ip pair from the password reset blocklist.
    It is maintained for compatibility with older admin interfaces.

    Args:
        pair (EmailIpPair): An object containing the email and IP address to remove.

    Returns:
        dict: A message confirming the action.
    """
    redis_conn = await redis_manager.get_redis()
    await redis_conn.srem("abuse:reset:blocklist", f"{pair.email}:{pair.ip}")
    logger.info("Admin removed reset pair from blocklist: %s:%s", pair.email, pair.ip)
    return {"message": f"Removed {pair.email}:{pair.ip} from blocklist"}
