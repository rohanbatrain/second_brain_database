"""Main routes module for the Second Brain Database API."""

import asyncio
import base64
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from uuid import uuid4

import aiohttp
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.serialization import load_der_public_key
from fastapi import APIRouter, Body, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED, HTTP_500_INTERNAL_SERVER_ERROR

from second_brain_database.database import db_manager
from second_brain_database.docs.models import (
    StandardErrorResponse,
    StandardSuccessResponse,
    ValidationErrorResponse,
    create_error_responses,
    create_standard_responses,
)
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.utils.logging_utils import log_error_with_context, log_performance, log_security_event

logger = get_logger(prefix="[AdMob SSV]")

router = APIRouter()

_admob_keys = {}
ADMOB_KEYS_URL = "https://www.gstatic.com/admob/reward/verifier-keys.json"
ADMOB_KEYS_REFRESH_INTERVAL = 60 * 60


async def fetch_admob_keys():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(ADMOB_KEYS_URL, timeout=10) as resp:
                resp.raise_for_status()
                data = await resp.json()
                keys = data.get("keys", [])
                key_dict = {str(k["keyId"]): k["base64"] for k in keys if "keyId" in k and "base64" in k}
                _admob_keys.clear()
                _admob_keys.update(key_dict)
                logger.info(f"Fetched {len(key_dict)} AdMob verifier keys.")
                return key_dict
    except Exception as e:
        logger.error(f"[ADMOB KEYS FETCH ERROR] {e}")
        return {}


def get_admob_key_base64(key_id: str):
    return _admob_keys.get(str(key_id))


@router.get(
    "/",
    summary="API Root Endpoint",
    description="""
    Root endpoint providing basic API information and status.
    
    **Purpose:**
    - Verify API is accessible and running
    - Get basic API information (name, version, status)
    - Quick connectivity test for client applications
    
    **Rate Limiting:**
    - 10 requests per 60 seconds per IP address
    - Designed for occasional connectivity checks
    
    **Use Cases:**
    - API health verification
    - Client application startup checks
    - Load balancer health probes
    - Basic API discovery
    """,
    responses={
        200: {
            "description": "API information retrieved successfully",
            "content": {
                "application/json": {
                    "example": {"message": "Second Brain Database API", "version": "1.0.0", "status": "running"}
                }
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "model": StandardErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": "rate_limit_exceeded",
                        "message": "Too many requests. Please try again later",
                        "details": {"retry_after": 60},
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                }
            },
        },
    },
    tags=["System"],
)
@log_performance("api_root_endpoint")
async def root(request: Request):
    """
    Get basic API information and status.

    Returns fundamental information about the Second Brain Database API
    including version, status, and welcome message.
    """
    try:
        await security_manager.check_rate_limit(request, "root", rate_limit_requests=10, rate_limit_period=60)

        response_data = {"message": "Second Brain Database API", "version": "1.0.0", "status": "running"}

        logger.info("API root endpoint accessed successfully")
        return response_data

    except Exception as e:
        log_error_with_context(
            e, {"operation": "api_root_endpoint", "client_ip": getattr(request.client, "host", "unknown")}
        )
        raise


@router.get(
    "/health",
    summary="Comprehensive Health Check",
    description="""
    Comprehensive health check endpoint for monitoring system status.
    
    **Health Checks Performed:**
    - Database connectivity (MongoDB)
    - Redis cache connectivity
    - API service status
    
    **Response Codes:**
    - 200: All systems healthy
    - 503: One or more systems unhealthy
    
    **Rate Limiting:**
    - 5 requests per 30 seconds per IP address
    - Optimized for monitoring systems
    
    **Use Cases:**
    - Load balancer health checks
    - Monitoring system integration
    - Service dependency verification
    - Automated health monitoring
    
    **Monitoring Integration:**
    This endpoint is designed for integration with monitoring tools
    like Prometheus, Grafana, or cloud monitoring services.
    """,
    responses={
        200: {
            "description": "All systems healthy",
            "content": {
                "application/json": {
                    "example": {"status": "healthy", "database": "connected", "redis": "connected", "api": "running"}
                }
            },
        },
        503: {
            "description": "One or more systems unhealthy",
            "model": StandardErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": "service_unavailable",
                        "message": "Database or Redis connection failed",
                        "details": {"database": "disconnected", "redis": "connected"},
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                }
            },
        },
        429: {"description": "Rate limit exceeded", "model": StandardErrorResponse},
    },
    tags=["System"],
)
async def health_check(request: Request):
    """
    Perform comprehensive health check of all system components.

    Checks the health of database, Redis cache, and API service
    to ensure the system is fully operational.
    """
    await security_manager.check_rate_limit(request, "health", rate_limit_requests=5, rate_limit_period=30)
    try:
        # Check database connection
        db_healthy = await db_manager.health_check()
        # Check Redis connection
        try:
            redis_conn = await security_manager.get_redis()
            await redis_conn.ping()
            redis_healthy = True
        except Exception as e:
            logger.error("Redis health check failed: %s", e)
            redis_healthy = False

        if not db_healthy or not redis_healthy:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database or Redis connection failed"
            )

        return {
            "status": "healthy",
            "database": "connected" if db_healthy else "disconnected",
            "redis": "connected" if redis_healthy else "disconnected",
            "api": "running",
        }
    except Exception as e:
        logger.error("Health check failed: %s", e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable") from e


@router.get(
    "/healthz",
    summary="Kubernetes Health Check",
    description="""
    Lightweight health check endpoint optimized for Kubernetes health probes.
    
    **Purpose:**
    - Kubernetes liveness probe endpoint
    - Quick health verification without heavy checks
    - High-frequency monitoring support
    
    **Rate Limiting:**
    - 20 requests per 60 seconds per IP address
    - Optimized for frequent Kubernetes probe checks
    
    **Response:**
    Always returns 200 OK with simple status message unless rate limited.
    
    **Kubernetes Integration:**
    Configure as liveness probe in your Kubernetes deployment:
    ```yaml
    livenessProbe:
      httpGet:
        path: /healthz
        port: 8000
      initialDelaySeconds: 30
      periodSeconds: 10
    ```
    """,
    responses={
        200: {"description": "Service is alive", "content": {"application/json": {"example": {"status": "ok"}}}},
        429: {"description": "Rate limit exceeded", "model": StandardErrorResponse},
    },
    tags=["System"],
)
@log_performance("kubernetes_health_check")
async def kubernetes_health(request: Request):
    """
    Kubernetes liveness probe endpoint.

    Lightweight health check that indicates the service is alive
    and responding to requests.
    """
    try:
        await security_manager.check_rate_limit(request, "healthz", rate_limit_requests=20, rate_limit_period=60)
        return {"status": "ok"}
    except Exception as e:
        log_error_with_context(
            e, {"operation": "kubernetes_health_check", "client_ip": getattr(request.client, "host", "unknown")}
        )
        raise


@router.get(
    "/ready",
    summary="Kubernetes Readiness Check",
    description="""
    Kubernetes readiness probe endpoint that verifies service is ready to handle traffic.
    
    **Purpose:**
    - Kubernetes readiness probe endpoint
    - Verifies database connectivity before accepting traffic
    - Ensures service dependencies are available
    
    **Rate Limiting:**
    - 3 requests per 30 seconds per IP address
    - Conservative limit for readiness checks
    
    **Database Check:**
    Performs actual database connectivity test to ensure the service
    can handle requests that require database access.
    
    **Kubernetes Integration:**
    Configure as readiness probe in your Kubernetes deployment:
    ```yaml
    readinessProbe:
      httpGet:
        path: /ready
        port: 8000
      initialDelaySeconds: 5
      periodSeconds: 5
    ```
    """,
    responses={
        200: {
            "description": "Service is ready to handle traffic",
            "content": {"application/json": {"example": {"status": "ready"}}},
        },
        503: {
            "description": "Service not ready - database unavailable",
            "model": StandardErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": "service_unavailable",
                        "message": "Database not ready",
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                }
            },
        },
        429: {"description": "Rate limit exceeded", "model": StandardErrorResponse},
    },
    tags=["System"],
)
async def readiness_check(request: Request):
    """
    Kubernetes readiness probe that checks database connectivity.

    Verifies that the service is ready to handle traffic by checking
    that the database connection is available and functional.
    """
    await security_manager.check_rate_limit(request, "ready", rate_limit_requests=3, rate_limit_period=30)
    try:
        is_connected = await db_manager.health_check()
        if not is_connected:
            raise HTTPException(status_code=503, detail="Database not ready")
        return {"status": "ready"}
    except Exception as e:
        logger.error("Readiness check failed: %s", e)
        raise HTTPException(status_code=503, detail="Service not ready") from e


@router.get(
    "/live",
    summary="Liveness Check",
    description="""
    Simple liveness check endpoint that confirms the service is running.
    
    **Purpose:**
    - Basic liveness verification
    - Service availability confirmation
    - Lightweight health check without dependencies
    
    **Rate Limiting:**
    - 15 requests per 60 seconds per IP address
    - Balanced for regular monitoring
    
    **Response:**
    Always returns 200 OK with alive status unless rate limited.
    
    **Use Cases:**
    - Basic service monitoring
    - Load balancer health checks
    - Service discovery health verification
    - Uptime monitoring systems
    """,
    responses={
        200: {
            "description": "Service is alive and responding",
            "content": {"application/json": {"example": {"status": "alive"}}},
        },
        429: {"description": "Rate limit exceeded", "model": StandardErrorResponse},
    },
    tags=["System"],
)
async def liveness_check(request: Request):
    """
    Simple liveness check that confirms the service is running.

    Returns a basic alive status without performing any dependency checks.
    """
    await security_manager.check_rate_limit(request, "live", rate_limit_requests=15, rate_limit_period=60)
    return {"status": "alive"}


@router.get("/rewards/admob-ssv")
async def admob_ssv_reward(
    ad_network: str,
    ad_unit: str,
    reward_amount: int,
    reward_item: str,
    timestamp: str,
    transaction_id: str = None,
    user_id: str = None,
    signature: str = None,
    key_id: str = None,
    note: str = None,
    request: Request = None,
):
    reward_info = {
        "ad_network": ad_network,
        "ad_unit": ad_unit,
        "reward_amount": reward_amount,
        "reward_item": reward_item,
        "timestamp": timestamp,
        "transaction_id": transaction_id or "<generated>",
        "user_id": user_id,
        "signature": "<hidden>",  # Never log raw signature in prod
        "key_id": key_id,
        "note": note,
    }
    logger.info(f"[REWARD RECEIVED] {reward_info}")
    raw_url = str(request.url)
    logger.debug(f"Request URL: {raw_url}")
    parsed_url = urlparse(raw_url)
    query_string = parsed_url.query
    logger.debug(f"Query string: {query_string}")
    sig_idx = query_string.find("signature=")
    logger.debug(f"Signature index: {sig_idx}")
    if sig_idx == -1:
        logger.warning("[ADMOB SIGNATURE PARAM NOT FOUND]")
        return JSONResponse(
            {"status": "error", "detail": "Signature parameter missing"}, status_code=HTTP_400_BAD_REQUEST
        )
    content_to_verify = query_string[: sig_idx - 1].encode("utf-8")
    logger.debug(f"Content to verify (raw): {content_to_verify}")

    pubkey_b64 = get_admob_key_base64(key_id)
    if not pubkey_b64:
        logger.warning(f"[ADMOB KEY NOT FOUND] key_id={key_id}, refreshing keys...")
        await fetch_admob_keys()
        pubkey_b64 = get_admob_key_base64(key_id)
        if not pubkey_b64:
            logger.error(f"[ADMOB KEY STILL NOT FOUND] key_id={key_id}")
            return JSONResponse(
                {"status": "error", "detail": "AdMob public key not found for key_id"},
                status_code=HTTP_401_UNAUTHORIZED,
            )
    try:
        logger.debug(f"Using public key (base64): {pubkey_b64}")
        pubkey_der = base64.b64decode(pubkey_b64)
        try:
            pubkey = load_der_public_key(pubkey_der)
            logger.debug(f"Loaded public key as DER: {type(pubkey)}")
        except Exception as e:
            logger.warning(f"Failed to load DER public key, trying PEM. Error: {e}")
            import cryptography.hazmat.primitives.serialization as serialization

            pubkey_pem = (
                "-----BEGIN PUBLIC KEY-----\n" + pubkey_b64 + "\n-----END PUBLIC KEY-----"
                if not pubkey_b64.startswith("-----BEGIN")
                else pubkey_b64
            )
            pubkey = serialization.load_pem_public_key(pubkey_pem.encode())
            logger.debug(f"Loaded public key as PEM: {type(pubkey)}")
        sig = signature
        logger.debug(f"Signature (raw): {sig}")
        sig = sig.replace("-", "+").replace("_", "/")
        sig += "=" * ((4 - len(sig) % 4) % 4)
        logger.debug(f"Signature (base64 padded): {sig}")
        signature_bytes = base64.b64decode(sig)
        logger.debug(f"Signature (decoded bytes): {signature_bytes.hex()}")
        if isinstance(pubkey, rsa.RSAPublicKey):
            logger.debug("Verifying with RSA public key.")
            pubkey.verify(signature_bytes, content_to_verify, padding.PKCS1v15(), hashes.SHA256())
        elif isinstance(pubkey, ec.EllipticCurvePublicKey):
            logger.debug("Verifying with EC public key.")
            pubkey.verify(signature_bytes, content_to_verify, ec.ECDSA(hashes.SHA256()))
        else:
            logger.error(f"[ADMOB KEY ERROR] Unsupported public key type: {type(pubkey)}")
            return JSONResponse(
                {"status": "error", "detail": "AdMob key is not a supported public key type"},
                status_code=HTTP_401_UNAUTHORIZED,
            )
        logger.info(f"[ADMOB SIGNATURE VERIFIED] user_id={user_id}, tx={transaction_id}")
    except InvalidSignature:
        logger.warning(f"[ADMOB SIGNATURE INVALID] Invalid signature for user_id={user_id}, tx={transaction_id}")
        await fetch_admob_keys()
        return JSONResponse({"status": "error", "detail": "Invalid signature"}, status_code=HTTP_401_UNAUTHORIZED)
    except Exception as e:
        logger.error(f"[ADMOB SIGNATURE VERIFY ERROR] {e}")
        return JSONResponse(
            {"status": "error", "detail": "Signature verification error"}, status_code=HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Log and drop duplicate/fraudulent requests: check for existing transaction_id for this user
    users_collection = db_manager.get_collection("users")
    fraud_check = await users_collection.find_one(
        {"username": user_id, "admob_ssv_transactions": {"$elemMatch": {"transaction_id": transaction_id}}}
    )
    if fraud_check:
        logger.warning(f"[FRAUD DETECTED] Duplicate transaction_id for user_id={user_id}, tx={transaction_id}")
        return JSONResponse(
            {"status": "error", "detail": "Duplicate or replayed transaction"}, status_code=HTTP_401_UNAUTHORIZED
        )

    # Process token rewards - credit exactly reward_amount tokens
    if reward_item == "token" and reward_amount >= 1:
        user = await users_collection.find_one({"username": user_id})
        logger.debug(f"User lookup for reward: {user}")
        if user:
            now_iso = datetime.now(timezone.utc).isoformat()
            txn_id = transaction_id or str(uuid4())
            # Add transaction log to user (receive)
            receive_txn = {
                "type": "receive",
                "from": "sbd_ads",
                "amount": reward_amount,
                "timestamp": now_iso,
                "transaction_id": txn_id,
            }
            if note:
                receive_txn["note"] = note
            update_result = await users_collection.update_one(
                {"username": user_id},
                {
                    "$inc": {"sbd_tokens": reward_amount},
                    "$setOnInsert": {
                        "sbd_tokens_transactions": []
                    },
                    "$push": {
                        "admob_ssv_transactions": {"transaction_id": txn_id, "timestamp": timestamp},
                        "sbd_tokens_transactions": receive_txn,
                    },
                },
            )
            logger.debug(f"Update result: {update_result.raw_result}")
            if update_result.modified_count:
                logger.info(f"[SBD TOKENS UPDATED] User: {user_id}, +{reward_amount} tokens, tx={txn_id}")
                # Log the send transaction for sbd_ads
                send_txn = {"type": "send", "to": user_id, "amount": reward_amount, "timestamp": now_iso, "transaction_id": txn_id}
                if note:
                    send_txn["note"] = note
                await users_collection.update_one(
                    {"username": "sbd_ads"},
                    {
                        "$setOnInsert": {"email": "sbd_ads@rohanbatra.in"},
                        "$push": {"sbd_tokens_transactions": send_txn},
                    },
                    upsert=True,
                )
            else:
                logger.warning(f"[SBD TOKENS UPDATE FAILED] User: {user_id}")
        else:
            logger.warning(f"[USER NOT FOUND] Username: {user_id}")
    # Process theme rewards for supported emotion_tracker themes
    supported_themes = [
        "emotion_tracker-serenityGreen",
        "emotion_tracker-serenityGreenDark",
        "emotion_tracker-pacificBlue",
        "emotion_tracker-pacificBlueDark",
        "emotion_tracker-blushRose",
        "emotion_tracker-blushRoseDark",
        "emotion_tracker-cloudGray",
        "emotion_tracker-cloudGrayDark",
        "emotion_tracker-sunsetPeach",
        "emotion_tracker-sunsetPeachDark",
        "emotion_tracker-midnightLavender",
        "emotion_tracker-midnightLavenderLight",
        "emotion_tracker-crimsonRed",
        "emotion_tracker-crimsonRedDark",
        "emotion_tracker-forestGreen",
        "emotion_tracker-forestGreenDark",
        "emotion_tracker-goldenYellow",
        "emotion_tracker-goldenYellowDark",
        "emotion_tracker-deepPurple",
        "emotion_tracker-deepPurpleDark",
        "emotion_tracker-royalOrange",
        "emotion_tracker-royalOrangeDark",
    ]
    if reward_item in supported_themes and reward_amount == 1:
        user = await users_collection.find_one({"username": user_id})
        logger.debug(f"User lookup for theme reward: {user}")
        if user:
            now_iso = datetime.now(timezone.utc)
            txn_id = transaction_id or str(uuid4())
            try:
                hours = int(note) if note and note.isdigit() else 1
            except Exception:
                hours = 1
            valid_till = (now_iso + timedelta(hours=hours)).isoformat()
            theme_entry = {
                "theme_id": reward_item,
                "unlocked_at": now_iso.isoformat(),
                "duration_hours": hours,
                "valid_till": valid_till,
                "transaction_id": txn_id,
            }
            update_result = await users_collection.update_one(
                {"username": user_id}, {"$push": {"themes_rented": theme_entry}}
            )
            logger.info(
                f"[THEME UNLOCKED] User: {user_id}, theme: {reward_item}, hours: {hours}, valid_till: {valid_till}, tx={txn_id}"
            )
            logger.debug(f"Theme unlock update result: {update_result.raw_result}")
        else:
            logger.warning(f"[USER NOT FOUND] Username: {user_id} (theme reward)")
    # Process avatar rewards for supported avatars
    supported_avatars = set(
        [
            # Cat Avatars
            *[f"emotion_tracker-static-avatar-cat-{i}" for i in range(1, 21)],
            # Dog Avatars
            *[f"emotion_tracker-static-avatar-dog-{i}" for i in range(1, 18)],
            # Panda Avatars
            *[f"emotion_tracker-static-avatar-panda-{i}" for i in list(range(1, 10)) + list(range(10, 13))],
            # People Avatars
            *[f"emotion_tracker-static-avatar-person-{i}" for i in list(range(1, 9)) + list(range(10, 17))],
            # Animated Avatars
            "emotion_tracker-animated-avatar-playful_eye",
            "emotion_tracker-animated-avatar-floating_brain",
        ]
    )
    if reward_item in supported_avatars and reward_amount == 1:
        user = await users_collection.find_one({"username": user_id})
        logger.debug(f"User lookup for avatar reward: {user}")
        if user:
            now_iso = datetime.now(timezone.utc)
            txn_id = transaction_id or str(uuid4())
            try:
                hours = int(note) if note and note.isdigit() else 1
            except Exception:
                hours = 1
            valid_till = (now_iso + timedelta(hours=hours)).isoformat()
            avatar_entry = {
                "avatar_id": reward_item,
                "unlocked_at": now_iso.isoformat(),
                "duration_hours": hours,
                "valid_till": valid_till,
                "transaction_id": txn_id,
            }
            update_result = await users_collection.update_one(
                {"username": user_id}, {"$push": {"avatars_rented": avatar_entry}}
            )
            logger.info(
                f"[AVATAR UNLOCKED] User: {user_id}, avatar: {reward_item}, hours: {hours}, valid_till: {valid_till}, tx={txn_id}"
            )
            logger.debug(f"Avatar unlock update result: {update_result.raw_result}")
        else:
            logger.warning(f"[USER NOT FOUND] Username: {user_id} (avatar reward)")
    # Process banner rewards for supported banners
    supported_banners = set(["emotion_tracker-static-banner-earth-1"])
    if reward_item in supported_banners and reward_amount == 1:
        user = await users_collection.find_one({"username": user_id})
        logger.debug(f"User lookup for banner reward: {user}")
        if user:
            now_iso = datetime.now(timezone.utc)
            txn_id = transaction_id or str(uuid4())
            try:
                hours = int(note) if note and note.isdigit() else 1
            except Exception:
                hours = 1
            valid_till = (now_iso + timedelta(hours=hours)).isoformat()
            banner_entry = {
                "banner_id": reward_item,
                "unlocked_at": now_iso.isoformat(),
                "duration_hours": hours,
                "valid_till": valid_till,
                "transaction_id": txn_id,
            }
            update_result = await users_collection.update_one(
                {"username": user_id}, {"$push": {"banners_rented": banner_entry}}
            )
            logger.info(
                f"[BANNER UNLOCKED] User: {user_id}, banner: {reward_item}, hours: {hours}, valid_till: {valid_till}, tx={txn_id}"
            )
            logger.debug(f"Banner unlock update result: {update_result.raw_result}")
        else:
            logger.warning(f"[USER NOT FOUND] Username: {user_id} (banner reward)")
    return JSONResponse({"status": "success", "reward": reward_info})

@router.get(
    "/mcp/health",
    summary="MCP Server Health Check",
    description="""
    Comprehensive health check endpoint for the FastMCP server.
    
    **Health Checks Performed:**
    - MCP server initialization status
    - MCP server process status
    - MCP configuration validation
    - Tool, resource, and prompt registration status
    
    **Response Codes:**
    - 200: MCP server healthy and operational
    - 503: MCP server unhealthy or not running
    - 404: MCP server disabled or not available
    
    **Rate Limiting:**
    - 10 requests per 60 seconds per IP address
    - Optimized for monitoring systems
    
    **Use Cases:**
    - MCP server monitoring
    - Integration health verification
    - Automated MCP health checks
    - Load balancer health probes for MCP services
    """,
    responses={
        200: {
            "description": "MCP server healthy",
            "content": {
                "application/json": {
                    "example": {
                        "healthy": True,
                        "checks": {
                            "initialized": {"status": "pass", "message": "Server initialized"},
                            "process": {"status": "pass", "message": "Process running (PID: 12345)", "pid": 12345},
                            "configuration": {"status": "pass", "message": "Configuration valid"}
                        },
                        "timestamp": 1640995200.0
                    }
                }
            },
        },
        503: {
            "description": "MCP server unhealthy",
            "model": StandardErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": "mcp_server_unhealthy",
                        "message": "MCP server is not healthy",
                        "details": {"healthy": False, "checks": {}},
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                }
            },
        },
        404: {
            "description": "MCP server not available",
            "model": StandardErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": "mcp_server_not_available",
                        "message": "MCP server is disabled or not available",
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                }
            },
        },
        429: {"description": "Rate limit exceeded", "model": StandardErrorResponse},
    },
    tags=["System"],
)
@log_performance("mcp_health_check")
async def mcp_health_check(request: Request):
    """
    Perform comprehensive health check of the MCP server.

    Checks the health of MCP server initialization, process status,
    configuration validity, and registration status.
    """
    try:
        await security_manager.check_rate_limit(request, "mcp_health", rate_limit_requests=10, rate_limit_period=60)

        # Import MCP server manager
        try:
            from second_brain_database.integrations.mcp.server import mcp_server_manager
            from second_brain_database.config import settings
        except ImportError as e:
            logger.error("MCP server not available: %s", e)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="MCP server is not available"
            ) from e

        # Check if MCP is enabled
        if not settings.MCP_ENABLED:
            logger.info("MCP server health check requested but MCP is disabled")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="MCP server is disabled"
            )

        # Perform comprehensive health check
        health_result = await mcp_server_manager.get_comprehensive_health_status()
        health_result = await mcp_server_manager.health_check()
        
        if health_result["healthy"]:
            logger.info("MCP server health check passed")
            return health_result
        else:
            logger.warning("MCP server health check failed: %s", health_result)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MCP server is not healthy"
            )

    except HTTPException:
        raise
    except Exception as e:
        log_error_with_context(
            e, {"operation": "mcp_health_check", "client_ip": getattr(request.client, "host", "unknown")}
        )
        logger.error("MCP health check failed with error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP health check failed"
        ) from e


@router.get(
    "/mcp/status",
    summary="MCP Server Status Information",
    description="""
    Detailed status information endpoint for the FastMCP server.
    
    **Status Information Provided:**
    - Server initialization and running status
    - Configuration details and settings
    - Tool, resource, and prompt counts
    - Server uptime and performance metrics
    - Process information and connection details
    
    **Rate Limiting:**
    - 5 requests per 60 seconds per IP address
    - Conservative limit for detailed status queries
    
    **Use Cases:**
    - MCP server monitoring dashboards
    - Integration status verification
    - Performance monitoring and analytics
    - Troubleshooting and diagnostics
    """,
    responses={
        200: {
            "description": "MCP server status retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "initialized": True,
                        "running": True,
                        "uptime_seconds": 3600.5,
                        "server_name": "SecondBrainMCP",
                        "server_version": "1.0.0",
                        "host": "localhost",
                        "port": 3001,
                        "debug_mode": False,
                        "tool_count": 25,
                        "resource_count": 12,
                        "prompt_count": 7,
                        "process_id": 12345,
                        "configuration": {
                            "security_enabled": True,
                            "audit_enabled": True,
                            "rate_limit_enabled": True,
                            "max_concurrent_tools": 50,
                            "request_timeout": 30
                        }
                    }
                }
            },
        },
        404: {
            "description": "MCP server not available",
            "model": StandardErrorResponse,
        },
        429: {"description": "Rate limit exceeded", "model": StandardErrorResponse},
    },
    tags=["System"],
)
@log_performance("mcp_status_check")
async def mcp_status_check(request: Request):
    """
    Get detailed status information for the MCP server.

    Returns comprehensive status information including configuration,
    performance metrics, and operational details.
    """
    try:
        await security_manager.check_rate_limit(request, "mcp_status", rate_limit_requests=5, rate_limit_period=60)

        # Import MCP server manager
        try:
            from second_brain_database.integrations.mcp.server import mcp_server_manager
            from second_brain_database.config import settings
        except ImportError as e:
            logger.error("MCP server not available: %s", e)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="MCP server is not available"
            ) from e

        # Check if MCP is enabled
        if not settings.MCP_ENABLED:
            logger.info("MCP server status requested but MCP is disabled")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="MCP server is disabled"
            )

        # Get server status
        status_result = await mcp_server_manager.get_server_status()
        
        logger.info("MCP server status retrieved successfully")
        return status_result

    except HTTPException:
        raise
    except Exception as e:
        log_error_with_context(
            e, {"operation": "mcp_status_check", "client_ip": getattr(request.client, "host", "unknown")}
        )
        logger.error("MCP status check failed with error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP status check failed"
        ) from e


@router.get(
    "/mcp/metrics",
    summary="MCP Server Metrics",
    description="""
    Performance and operational metrics endpoint for the FastMCP server.
    
    **Metrics Provided:**
    - Server performance statistics
    - Tool execution metrics and success rates
    - Resource and prompt usage statistics
    - Error rates and response times
    - Connection and request statistics
    
    **Rate Limiting:**
    - 3 requests per 60 seconds per IP address
    - Conservative limit for metrics collection
    
    **Use Cases:**
    - Performance monitoring and alerting
    - Capacity planning and optimization
    - Integration with monitoring systems (Prometheus, Grafana)
    - Operational analytics and reporting
    """,
    responses={
        200: {
            "description": "MCP server metrics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "server_metrics": {
                            "uptime_seconds": 3600.5,
                            "requests_total": 1250,
                            "requests_per_minute": 15.2,
                            "error_rate": 0.02,
                            "average_response_time_ms": 45.3
                        },
                        "tool_metrics": {
                            "total_executions": 850,
                            "success_rate": 0.98,
                            "average_execution_time_ms": 125.7,
                            "most_used_tools": ["get_family_info", "get_user_profile", "list_shop_items"]
                        },
                        "resource_metrics": {
                            "total_requests": 320,
                            "cache_hit_rate": 0.85,
                            "most_accessed_resources": ["family_info", "user_profile", "shop_catalog"]
                        },
                        "prompt_metrics": {
                            "total_requests": 180,
                            "most_used_prompts": ["family_management_guide", "shop_navigation", "security_setup"]
                        }
                    }
                }
            },
        },
        404: {
            "description": "MCP server not available",
            "model": StandardErrorResponse,
        },
        429: {"description": "Rate limit exceeded", "model": StandardErrorResponse},
    },
    tags=["System"],
)
@log_performance("mcp_metrics_check")
async def mcp_metrics_check(request: Request):
    """
    Get performance and operational metrics for the MCP server.

    Returns comprehensive metrics including performance statistics,
    usage analytics, and operational data for monitoring purposes.
    """
    try:
        await security_manager.check_rate_limit(request, "mcp_metrics", rate_limit_requests=3, rate_limit_period=60)

        # Import MCP server manager
        try:
            from second_brain_database.integrations.mcp.server import mcp_server_manager
            from second_brain_database.config import settings
        except ImportError as e:
            logger.error("MCP server not available: %s", e)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="MCP server is not available"
            ) from e

        # Check if MCP is enabled
        if not settings.MCP_ENABLED:
            logger.info("MCP server metrics requested but MCP is disabled")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="MCP server is disabled"
            )

        # Get server status for basic metrics
        status_result = await mcp_server_manager.get_server_status()
        
        # Build metrics response (placeholder implementation)
        # In a full implementation, these would come from actual metrics collection
        metrics = {
            "server_metrics": {
                "uptime_seconds": status_result.get("uptime_seconds", 0),
                "initialized": status_result.get("initialized", False),
                "running": status_result.get("running", False),
                "process_id": status_result.get("process_id"),
                "configuration_valid": True  # Based on successful status retrieval
            },
            "tool_metrics": {
                "registered_tools": status_result.get("tool_count", 0),
                "tools_enabled": settings.MCP_TOOLS_ENABLED,
                "security_enabled": settings.MCP_SECURITY_ENABLED,
                "rate_limit_enabled": settings.MCP_RATE_LIMIT_ENABLED
            },
            "resource_metrics": {
                "registered_resources": status_result.get("resource_count", 0),
                "resources_enabled": settings.MCP_RESOURCES_ENABLED,
                "cache_enabled": settings.MCP_CACHE_ENABLED,
                "cache_ttl_seconds": settings.MCP_CACHE_TTL
            },
            "prompt_metrics": {
                "registered_prompts": status_result.get("prompt_count", 0),
                "prompts_enabled": settings.MCP_PROMPTS_ENABLED
            },
            "configuration_metrics": {
                "max_concurrent_tools": settings.MCP_MAX_CONCURRENT_TOOLS,
                "request_timeout": settings.MCP_REQUEST_TIMEOUT,
                "tool_execution_timeout": settings.MCP_TOOL_EXECUTION_TIMEOUT,
                "retry_enabled": settings.MCP_RETRY_ENABLED,
                "circuit_breaker_enabled": settings.MCP_CIRCUIT_BREAKER_ENABLED
            }
        }
        
        logger.info("MCP server metrics retrieved successfully")
        return metrics

    except HTTPException:
        raise
    except Exception as e:
        log_error_with_context(
            e, {"operation": "mcp_metrics_check", "client_ip": getattr(request.client, "host", "unknown")}
        )
        logger.error("MCP metrics check failed with error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP metrics check failed"
        ) from e


@router.get("/favicon.ico")
async def favicon():
    """Simple favicon to prevent browser errors."""
    # Return a simple 1x1 transparent PNG
    import base64
    transparent_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jU77zgAAAABJRU5ErkJggg=="
    )
    return Response(content=transparent_png, media_type="image/png")