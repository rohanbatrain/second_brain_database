"""
Cloudflare Turnstile CAPTCHA verification utility.

This module provides an async function to verify Turnstile CAPTCHA tokens using the Cloudflare API.
It is instrumented with production-grade logging and error handling.
"""
from typing import Optional
import httpx
from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[Auth Service Security CAPTCHA]")

TURNSTILE_VERIFY_URL: str = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TURNSTILE_TIMEOUT: int = 5

async def verify_turnstile_captcha(token: str, remoteip: Optional[str] = None) -> bool:
    """
    Verify a Cloudflare Turnstile CAPTCHA token.

    Args:
        token (str): The CAPTCHA token from the client.
        remoteip (Optional[str]): The user's IP address (optional).

    Returns:
        bool: True if the CAPTCHA is valid, False otherwise.

    Side Effects:
        Makes an HTTP request to Cloudflare's API. Logs errors and results.
    """
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
        async with httpx.AsyncClient(timeout=TURNSTILE_TIMEOUT) as client:
            resp = await client.post(TURNSTILE_VERIFY_URL, data=data)
            result = resp.json()
            logger.debug("Turnstile CAPTCHA verification result: %s", result)
            return result.get("success", False)
    except (httpx.RequestError, httpx.TimeoutException, ValueError, KeyError) as exc:
        logger.error("Turnstile CAPTCHA verification failed: %s", exc, exc_info=True)
        return False