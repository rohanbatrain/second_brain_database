"""
Cloudflare Turnstile CAPTCHA verification utility.

This module provides an async function to verify Turnstile CAPTCHA tokens using the Cloudflare API.
It is instrumented with production-grade logging and error handling.
"""

from typing import Optional

import httpx

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.utils.logging_utils import (
    SecurityLogger,
    log_error_with_context,
    log_performance,
    log_security_event,
)

logger = get_logger(prefix="[Auth Service Security CAPTCHA]")
security_logger = SecurityLogger(prefix="[CAPTCHA-SECURITY]")

TURNSTILE_VERIFY_URL: str = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TURNSTILE_TIMEOUT: int = 5


@log_performance("verify_turnstile_captcha")
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
    logger.info("Verifying Turnstile CAPTCHA token from IP: %s", remoteip or "unknown")

    # Log security event for CAPTCHA verification attempt
    log_security_event(
        event_type="captcha_verification_attempt",
        user_id="unknown",
        ip_address=remoteip,
        success=False,  # Will be updated based on result
        details={
            "token_length": len(token) if token else 0,
            "has_remote_ip": bool(remoteip),
            "captcha_provider": "turnstile",
        },
    )

    secret_key = getattr(settings, "TURNSTILE_SECRET_KEY", None)
    if not secret_key:
        logger.error("Turnstile secret key not configured")
        log_security_event(
            event_type="captcha_configuration_error",
            user_id="unknown",
            ip_address=remoteip,
            success=False,
            details={"error": "missing_secret_key", "captcha_provider": "turnstile"},
        )
        return False

    data = {
        "secret": secret_key,
        "response": token,
    }
    if remoteip:
        data["remoteip"] = remoteip

    logger.debug("Sending CAPTCHA verification request to Turnstile API")

    try:
        async with httpx.AsyncClient(timeout=TURNSTILE_TIMEOUT) as client:
            resp = await client.post(TURNSTILE_VERIFY_URL, data=data)
            result = resp.json()

            success = result.get("success", False)
            error_codes = result.get("error-codes", [])

            logger.info("Turnstile CAPTCHA verification result: success=%s, errors=%s", success, error_codes)

            if success:
                log_security_event(
                    event_type="captcha_verification_success",
                    user_id="unknown",
                    ip_address=remoteip,
                    success=True,
                    details={
                        "captcha_provider": "turnstile",
                        "response_time_ms": resp.elapsed.total_seconds() * 1000 if hasattr(resp, "elapsed") else None,
                    },
                )
            else:
                log_security_event(
                    event_type="captcha_verification_failed",
                    user_id="unknown",
                    ip_address=remoteip,
                    success=False,
                    details={
                        "captcha_provider": "turnstile",
                        "error_codes": error_codes,
                        "response_time_ms": resp.elapsed.total_seconds() * 1000 if hasattr(resp, "elapsed") else None,
                    },
                )
                logger.warning("CAPTCHA verification failed from IP %s: %s", remoteip, error_codes)

            return success

    except (httpx.RequestError, httpx.TimeoutException) as exc:
        logger.error("Turnstile CAPTCHA API request failed from IP %s: %s", remoteip, exc, exc_info=True)

        log_error_with_context(
            exc,
            context={
                "remote_ip": remoteip,
                "token_length": len(token) if token else 0,
                "api_url": TURNSTILE_VERIFY_URL,
                "timeout": TURNSTILE_TIMEOUT,
            },
            operation="verify_turnstile_captcha_api_request",
        )

        log_security_event(
            event_type="captcha_api_error",
            user_id="unknown",
            ip_address=remoteip,
            success=False,
            details={"captcha_provider": "turnstile", "error_type": type(exc).__name__, "error_message": str(exc)},
        )

        return False

    except (ValueError, KeyError) as exc:
        logger.error("Turnstile CAPTCHA response parsing failed from IP %s: %s", remoteip, exc, exc_info=True)

        log_error_with_context(
            exc,
            context={
                "remote_ip": remoteip,
                "token_length": len(token) if token else 0,
                "response_status": resp.status_code if "resp" in locals() else None,
            },
            operation="verify_turnstile_captcha_response_parsing",
        )

        log_security_event(
            event_type="captcha_response_parsing_error",
            user_id="unknown",
            ip_address=remoteip,
            success=False,
            details={"captcha_provider": "turnstile", "error_type": type(exc).__name__, "error_message": str(exc)},
        )

        return False
