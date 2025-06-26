from second_brain_database.managers.redis_manager import redis_manager

async def blacklist_token(user_id=None, token: str = None):
    """
    Blacklist all tokens for a user (by user_id) or a specific token.
    Uses Redis for production-ready persistence and multi-instance support.
    """
    redis_conn = await redis_manager.get_redis()
    if user_id is not None:
        # Blacklist user by user_id for 7 days (adjust as needed)
        await redis_conn.set(f"blacklist:user:{user_id}", "1", ex=60*60*24*7)
    if token is not None:
        # Blacklist specific token for 1 day (adjust as needed)
        await redis_conn.set(f"blacklist:token:{token}", "1", ex=60*60*24)

async def is_token_blacklisted(token: str, user_id: str = None) -> bool:
    redis_conn = await redis_manager.get_redis()
    if user_id:
        if await redis_conn.get(f"blacklist:user:{user_id}"):
            return True
    if await redis_conn.get(f"blacklist:token:{token}"):
        return True
    return False
