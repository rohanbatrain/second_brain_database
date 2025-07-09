"""Main routes module for the Second Brain Database API."""
from fastapi import APIRouter, HTTPException, status, Request, Body
from fastapi.responses import JSONResponse
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED, HTTP_500_INTERNAL_SERVER_ERROR

from second_brain_database.database import db_manager
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.managers.logging_manager import get_logger
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa, ec
from cryptography.hazmat.primitives.serialization import load_der_public_key
from cryptography.exceptions import InvalidSignature
import aiohttp
import asyncio
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta
from uuid import uuid4

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

@router.get("/")
async def root(request: Request):
    await security_manager.check_rate_limit(request, "root", rate_limit_requests=10, rate_limit_period=60)
    return {
        "message": "Second Brain Database API",
        "version": "1.0.0",
        "status": "running"
    }

@router.get("/health")
async def health_check(request: Request):
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
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database or Redis connection failed"
            )

        return {
            "status": "healthy",
            "database": "connected" if db_healthy else "disconnected",
            "redis": "connected" if redis_healthy else "disconnected",
            "api": "running"
        }
    except Exception as e:
        logger.error("Health check failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unavailable"
        ) from e

@router.get("/healthz")
async def kubernetes_health(request: Request):
    await security_manager.check_rate_limit(request, "healthz", rate_limit_requests=20, rate_limit_period=60)
    return {"status": "ok"}

@router.get("/ready")
async def readiness_check(request: Request):
    await security_manager.check_rate_limit(request, "ready", rate_limit_requests=3, rate_limit_period=30)
    try:
        is_connected = await db_manager.health_check()
        if not is_connected:
            raise HTTPException(status_code=503, detail="Database not ready")
        return {"status": "ready"}
    except Exception as e:
        logger.error("Readiness check failed: %s", e)
        raise HTTPException(status_code=503, detail="Service not ready") from e

@router.get("/live")
async def liveness_check(request: Request):
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
    request: Request = None
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
        "note": note
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
        return JSONResponse({"status": "error", "detail": "Signature parameter missing"}, status_code=HTTP_400_BAD_REQUEST)
    content_to_verify = query_string[:sig_idx-1].encode("utf-8")
    logger.debug(f"Content to verify (raw): {content_to_verify}")

    pubkey_b64 = get_admob_key_base64(key_id)
    if not pubkey_b64:
        logger.warning(f"[ADMOB KEY NOT FOUND] key_id={key_id}, refreshing keys...")
        await fetch_admob_keys()
        pubkey_b64 = get_admob_key_base64(key_id)
        if not pubkey_b64:
            logger.error(f"[ADMOB KEY STILL NOT FOUND] key_id={key_id}")
            return JSONResponse({"status": "error", "detail": "AdMob public key not found for key_id"}, status_code=HTTP_401_UNAUTHORIZED)
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
                if not pubkey_b64.startswith("-----BEGIN") else pubkey_b64
            )
            pubkey = serialization.load_pem_public_key(pubkey_pem.encode())
            logger.debug(f"Loaded public key as PEM: {type(pubkey)}")
        sig = signature
        logger.debug(f"Signature (raw): {sig}")
        sig = sig.replace('-', '+').replace('_', '/')
        sig += '=' * ((4 - len(sig) % 4) % 4)
        logger.debug(f"Signature (base64 padded): {sig}")
        signature_bytes = base64.b64decode(sig)
        logger.debug(f"Signature (decoded bytes): {signature_bytes.hex()}")
        if isinstance(pubkey, rsa.RSAPublicKey):
            logger.debug("Verifying with RSA public key.")
            pubkey.verify(
                signature_bytes,
                content_to_verify,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
        elif isinstance(pubkey, ec.EllipticCurvePublicKey):
            logger.debug("Verifying with EC public key.")
            pubkey.verify(
                signature_bytes,
                content_to_verify,
                ec.ECDSA(hashes.SHA256())
            )
        else:
            logger.error(f"[ADMOB KEY ERROR] Unsupported public key type: {type(pubkey)}")
            return JSONResponse({"status": "error", "detail": "AdMob key is not a supported public key type"}, status_code=HTTP_401_UNAUTHORIZED)
        logger.info(f"[ADMOB SIGNATURE VERIFIED] user_id={user_id}, tx={transaction_id}")
    except InvalidSignature:
        logger.warning(f"[ADMOB SIGNATURE INVALID] Invalid signature for user_id={user_id}, tx={transaction_id}")
        await fetch_admob_keys()
        return JSONResponse({"status": "error", "detail": "Invalid signature"}, status_code=HTTP_401_UNAUTHORIZED)
    except Exception as e:
        logger.error(f"[ADMOB SIGNATURE VERIFY ERROR] {e}")
        return JSONResponse({"status": "error", "detail": "Signature verification error"}, status_code=HTTP_500_INTERNAL_SERVER_ERROR)

    # Log and drop duplicate/fraudulent requests: check for existing transaction_id for this user
    users_collection = db_manager.get_collection("users")
    fraud_check = await users_collection.find_one({
        "username": user_id,
        "admob_ssv_transactions": {"$elemMatch": {"transaction_id": transaction_id}}
    })
    if fraud_check:
        logger.warning(f"[FRAUD DETECTED] Duplicate transaction_id for user_id={user_id}, tx={transaction_id}")
        return JSONResponse({"status": "error", "detail": "Duplicate or replayed transaction"}, status_code=HTTP_401_UNAUTHORIZED)

    # Only process if reward_item is 'token' and reward_amount is 10
    if reward_item == "token" and reward_amount == 10:
        user = await users_collection.find_one({"username": user_id})
        logger.debug(f"User lookup for reward: {user}")
        if user:
            now_iso = datetime.now(timezone.utc).isoformat()
            txn_id = transaction_id or str(uuid4())
            # Add transaction log to user (receive)
            receive_txn = {
                "type": "receive",
                "from": "sbd_ads",
                "amount": 10,
                "timestamp": now_iso,
                "transaction_id": txn_id
            }
            if note:
                receive_txn["note"] = note
            update_result = await users_collection.update_one(
                {"username": user_id},
                {
                    "$inc": {"sbd_tokens": 10},
                    "$push": {
                        "admob_ssv_transactions": {"transaction_id": txn_id, "timestamp": timestamp},
                        "sbd_tokens_transactions": receive_txn
                    }
                }
            )
            logger.debug(f"Update result: {update_result.raw_result}")
            if update_result.modified_count:
                logger.info(f"[SBD TOKENS UPDATED] User: {user_id}, +10 tokens, tx={txn_id}")
                # Log the send transaction for sbd_ads
                send_txn = {
                    "type": "send",
                    "to": user_id,
                    "amount": 10,
                    "timestamp": now_iso,
                    "transaction_id": txn_id
                }
                if note:
                    send_txn["note"] = note
                await users_collection.update_one(
                    {"username": "sbd_ads"},
                    {
                        "$push": {
                            "sbd_tokens_transactions": send_txn
                        }
                    },
                    upsert=True
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
        "emotion_tracker-royalOrangeDark"
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
                "transaction_id": txn_id
            }
            update_result = await users_collection.update_one(
                {"username": user_id},
                {"$push": {"themes_rented": theme_entry}}
            )
            logger.info(f"[THEME UNLOCKED] User: {user_id}, theme: {reward_item}, hours: {hours}, valid_till: {valid_till}, tx={txn_id}")
            logger.debug(f"Theme unlock update result: {update_result.raw_result}")
        else:
            logger.warning(f"[USER NOT FOUND] Username: {user_id} (theme reward)")
    # Process avatar rewards for supported avatars
    supported_avatars = set([
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
    ])
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
                "transaction_id": txn_id
            }
            update_result = await users_collection.update_one(
                {"username": user_id},
                {"$push": {"avatars_rented": avatar_entry}}
            )
            logger.info(f"[AVATAR UNLOCKED] User: {user_id}, avatar: {reward_item}, hours: {hours}, valid_till: {valid_till}, tx={txn_id}")
            logger.debug(f"Avatar unlock update result: {update_result.raw_result}")
        else:
            logger.warning(f"[USER NOT FOUND] Username: {user_id} (avatar reward)")
    # Process banner rewards for supported banners
    supported_banners = set([
        "emotion_tracker-static-banner-earth-1"
    ])
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
                "transaction_id": txn_id
            }
            update_result = await users_collection.update_one(
                {"username": user_id},
                {"$push": {"banners_rented": banner_entry}}
            )
            logger.info(f"[BANNER UNLOCKED] User: {user_id}, banner: {reward_item}, hours: {hours}, valid_till: {valid_till}, tx={txn_id}")
            logger.debug(f"Banner unlock update result: {update_result.raw_result}")
        else:
            logger.warning(f"[USER NOT FOUND] Username: {user_id} (banner reward)")
    return JSONResponse({"status": "success", "reward": reward_info})

