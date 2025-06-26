import httpx
from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger()

async def verify_turnstile_captcha(token: str, remoteip: str = None) -> bool:
    """
    Verify a Cloudflare Turnstile CAPTCHA token. Returns True if valid, False otherwise.
    """
    import httpx
    secret_key = getattr(settings, "TURNSTILE_SECRET_KEY", None)
    if not secret_key:
        logger.error("Turnstile secret key not configured.")
        return False
    data = {
        "secret": secret_key,
        "response": token,
    }
    if remoteip:
        data["remoteip"] = remoteip
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post("https://challenges.cloudflare.com/turnstile/v0/siteverify", data=data)
            result = resp.json()
            return result.get("success", False)
    except Exception as e:
        logger.error(f"Turnstile CAPTCHA verification failed: {e}")
        return False