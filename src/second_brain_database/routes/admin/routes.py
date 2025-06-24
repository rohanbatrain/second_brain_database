"""
Admin API endpoints for password reset abuse management, whitelist/blocklist, and abuse event review.
"""
from fastapi import APIRouter, Depends, Body, Query
from second_brain_database.routes.admin.service import (
    admin_add_whitelist_pair, admin_remove_whitelist_pair, admin_list_whitelist_pairs,
    admin_add_blocklist_pair, admin_remove_blocklist_pair, admin_list_blocklist_pairs,
    admin_list_abuse_events, admin_resolve_abuse_event,
    whitelist_reset_pair, block_reset_pair
)
from second_brain_database.routes.admin.models import AbuseEvent
from second_brain_database.routes.auth.routes import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])

# --- Admin Endpoints for Password Reset Abuse Management ---
@router.post("/whitelist", dependencies=[Depends(require_admin)])
async def admin_add_whitelist(email: str = Body(...), ip: str = Body(...)):
    """Admin: Add (email, ip) pair to password reset whitelist (Redis)."""
    result = await admin_add_whitelist_pair(email, ip)
    return {"success": result}

@router.delete("/whitelist", dependencies=[Depends(require_admin)])
async def admin_remove_whitelist(email: str = Body(...), ip: str = Body(...)):
    """Admin: Remove (email, ip) pair from password reset whitelist (Redis)."""
    result = await admin_remove_whitelist_pair(email, ip)
    return {"success": result}

@router.get("/whitelist", dependencies=[Depends(require_admin)])
async def admin_list_whitelist():
    """Admin: List all (email, ip) pairs in password reset whitelist (Redis)."""
    return await admin_list_whitelist_pairs()

@router.post("/blocklist", dependencies=[Depends(require_admin)])
async def admin_add_blocklist(email: str = Body(...), ip: str = Body(...)):
    """Admin: Add (email, ip) pair to password reset blocklist (Redis)."""
    result = await admin_add_blocklist_pair(email, ip)
    return {"success": result}

@router.delete("/blocklist", dependencies=[Depends(require_admin)])
async def admin_remove_blocklist(email: str = Body(...), ip: str = Body(...)):
    """Admin: Remove (email, ip) pair from password reset blocklist (Redis)."""
    result = await admin_remove_blocklist_pair(email, ip)
    return {"success": result}

@router.get("/blocklist", dependencies=[Depends(require_admin)])
async def admin_list_blocklist():
    """Admin: List all (email, ip) pairs in password reset blocklist (Redis)."""
    return await admin_list_blocklist_pairs()

@router.get("/abuse-events", dependencies=[Depends(require_admin)])
async def admin_list_abuse_events_api(
    email: str = Query(None),
    event_type: str = Query(None),
    resolved: bool = Query(None),
    limit: int = Query(100)
):
    """Admin: List password reset abuse events (MongoDB, persistent)."""
    return await admin_list_abuse_events(email=email, event_type=event_type, resolved=resolved, limit=limit)

@router.post("/abuse-events/resolve", dependencies=[Depends(require_admin)])
async def admin_resolve_abuse_event_api(event_id: str = Body(...), notes: str = Body(None)):
    """Admin: Mark a password reset abuse event as resolved (MongoDB)."""
    result = await admin_resolve_abuse_event(event_id, notes)
    return {"success": result}

# Legacy endpoints for direct pair management (optional, for admin UI compatibility)
@router.get("/list-reset-whitelist")
async def admin_list_reset_whitelist(current_user: dict = Depends(require_admin)):
    from second_brain_database.managers.redis_manager import redis_manager
    redis_conn = await redis_manager.get_redis()
    members = await redis_conn.smembers("abuse:reset:whitelist")
    return {"whitelist": [m.decode() if hasattr(m, 'decode') else m for m in members]}

@router.get("/list-reset-blocklist")
async def admin_list_reset_blocklist(current_user: dict = Depends(require_admin)):
    from second_brain_database.managers.redis_manager import redis_manager
    redis_conn = await redis_manager.get_redis()
    members = await redis_conn.smembers("abuse:reset:blocklist")
    return {"blocklist": [m.decode() if hasattr(m, 'decode') else m for m in members]}

@router.post("/whitelist-reset-pair")
async def admin_whitelist_reset_pair(email: str, ip: str, current_user: dict = Depends(require_admin)):
    await whitelist_reset_pair(email, ip)
    return {"message": f"Whitelisted {email}:{ip}"}

@router.post("/block-reset-pair")
async def admin_block_reset_pair(email: str, ip: str, current_user: dict = Depends(require_admin)):
    await block_reset_pair(email, ip)
    return {"message": f"Blocked {email}:{ip}"}

@router.delete("/whitelist-reset-pair")
async def admin_remove_whitelist_reset_pair(email: str, ip: str, current_user: dict = Depends(require_admin)):
    from second_brain_database.managers.redis_manager import redis_manager
    redis_conn = await redis_manager.get_redis()
    await redis_conn.srem("abuse:reset:whitelist", f"{email}:{ip}")
    return {"message": f"Removed {email}:{ip} from whitelist"}

@router.delete("/block-reset-pair")
async def admin_remove_block_reset_pair(email: str, ip: str, current_user: dict = Depends(require_admin)):
    from second_brain_database.managers.redis_manager import redis_manager
    redis_conn = await redis_manager.get_redis()
    await redis_conn.srem("abuse:reset:blocklist", f"{email}:{ip}")
    return {"message": f"Removed {email}:{ip} from blocklist"}
