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
    """Admin: Add (email, ip) pair to password reset whitelist (Redis)."""
    result = await admin_add_whitelist_pair(pair.email, pair.ip)
    logger.info("Admin added whitelist pair: %s:%s", pair.email, pair.ip)
    return {"success": result}


@router.delete("/whitelist", dependencies=[Depends(require_admin)])
async def admin_remove_whitelist(pair: EmailIpPair) -> dict:
    """Admin: Remove (email, ip) pair from password reset whitelist (Redis)."""
    result = await admin_remove_whitelist_pair(pair.email, pair.ip)
    logger.info("Admin removed whitelist pair: %s:%s", pair.email, pair.ip)
    return {"success": result}


@router.get("/whitelist", dependencies=[Depends(require_admin)])
async def admin_list_whitelist() -> list[EmailIpPair]:
    """Admin: List all (email, ip) pairs in password reset whitelist (Redis)."""
    logger.debug("Admin requested whitelist pairs.")
    pairs = await admin_list_whitelist_pairs()
    return [EmailIpPair(email=p["email"], ip=p["ip"]) for p in pairs]


@router.post("/blocklist", dependencies=[Depends(require_admin)])
async def admin_add_blocklist(pair: EmailIpPair) -> dict:
    """Admin: Add (email, ip) pair to password reset blocklist (Redis)."""
    result = await admin_add_blocklist_pair(pair.email, pair.ip)
    logger.info("Admin added blocklist pair: %s:%s", pair.email, pair.ip)
    return {"success": result}


@router.delete("/blocklist", dependencies=[Depends(require_admin)])
async def admin_remove_blocklist(pair: EmailIpPair) -> dict:
    """Admin: Remove (email, ip) pair from password reset blocklist (Redis)."""
    result = await admin_remove_blocklist_pair(pair.email, pair.ip)
    logger.info("Admin removed blocklist pair: %s:%s", pair.email, pair.ip)
    return {"success": result}


@router.get("/blocklist", dependencies=[Depends(require_admin)])
async def admin_list_blocklist() -> list[EmailIpPair]:
    """Admin: List all (email, ip) pairs in password reset blocklist (Redis)."""
    logger.debug("Admin requested blocklist pairs.")
    pairs = await admin_list_blocklist_pairs()
    return [EmailIpPair(email=p["email"], ip=p["ip"]) for p in pairs]


@router.get("/abuse-events", dependencies=[Depends(require_admin)])
async def admin_list_abuse_events_api(
    email: str = Query(None), event_type: str = Query(None), resolved: bool = Query(None), limit: int = Query(100)
) -> list[AbuseEvent]:
    """Admin: List password reset abuse events (MongoDB, persistent)."""
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
    """Admin: Mark a password reset abuse event as resolved (MongoDB)."""
    result = await admin_resolve_abuse_event(req.event_id, req.notes)
    logger.info("Admin resolved abuse event: %s, notes=%s", req.event_id, req.notes)
    return {"success": result}


# Legacy endpoints for direct pair management (optional, for admin UI compatibility)
@router.get("/list-reset-whitelist")
async def admin_list_reset_whitelist() -> dict:
    """Admin: List all reset whitelist pairs (legacy endpoint)."""
    redis_conn = await redis_manager.get_redis()
    members = await redis_conn.smembers("abuse:reset:whitelist")
    logger.debug("Admin listed reset whitelist pairs.")
    return {"whitelist": [m.decode() if hasattr(m, "decode") else m for m in members]}


@router.get("/list-reset-blocklist")
async def admin_list_reset_blocklist() -> dict:
    """Admin: List all reset blocklist pairs (legacy endpoint)."""
    redis_conn = await redis_manager.get_redis()
    members = await redis_conn.smembers("abuse:reset:blocklist")
    logger.debug("Admin listed reset blocklist pairs.")
    return {"blocklist": [m.decode() if hasattr(m, "decode") else m for m in members]}


@router.post("/whitelist-reset-pair")
async def admin_whitelist_reset_pair(pair: EmailIpPair) -> dict:
    """Admin: Whitelist a reset pair (legacy endpoint)."""
    await whitelist_reset_pair(pair.email, pair.ip)
    logger.info("Admin whitelisted reset pair: %s:%s", pair.email, pair.ip)
    return {"message": f"Whitelisted {pair.email}:{pair.ip}"}


@router.post("/block-reset-pair")
async def admin_block_reset_pair(pair: EmailIpPair) -> dict:
    """Admin: Block a reset pair (legacy endpoint)."""
    await block_reset_pair(pair.email, pair.ip)
    logger.info("Admin blocked reset pair: %s:%s", pair.email, pair.ip)
    return {"message": f"Blocked {pair.email}:{pair.ip}"}


@router.delete("/whitelist-reset-pair")
async def admin_remove_whitelist_reset_pair(pair: EmailIpPair) -> dict:
    """Admin: Remove a reset pair from whitelist (legacy endpoint)."""
    redis_conn = await redis_manager.get_redis()
    await redis_conn.srem("abuse:reset:whitelist", f"{pair.email}:{pair.ip}")
    logger.info("Admin removed reset pair from whitelist: %s:%s", pair.email, pair.ip)
    return {"message": f"Removed {pair.email}:{pair.ip} from whitelist"}


@router.delete("/block-reset-pair")
async def admin_remove_block_reset_pair(pair: EmailIpPair) -> dict:
    """Admin: Remove a reset pair from blocklist (legacy endpoint)."""
    redis_conn = await redis_manager.get_redis()
    await redis_conn.srem("abuse:reset:blocklist", f"{pair.email}:{pair.ip}")
    logger.info("Admin removed reset pair from blocklist: %s:%s", pair.email, pair.ip)
    return {"message": f"Removed {pair.email}:{pair.ip} from blocklist"}
