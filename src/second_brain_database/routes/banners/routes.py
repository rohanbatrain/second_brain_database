from datetime import datetime, timezone
import time
import uuid

from fastapi import APIRouter, Depends, Request

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
from second_brain_database.routes.auth import enforce_all_lockdowns
from second_brain_database.utils.logging_utils import (
    ip_address_context,
    log_database_operation,
    log_error_with_context,
    log_performance,
    request_id_context,
    user_id_context,
)

router = APIRouter()
logger = get_logger(prefix="[BANNERS]")


@router.get(
    "/banners/rented",
    tags=["User Profile"],
    summary="Get active rented banners",
    description="""
    Retrieve all currently active rented banners for the authenticated user.

    **Banner Rental System:**
    - Banners can be rented for temporary use (typically hours or days)
    - Only returns banners that are currently valid (not expired)
    - Rental periods are checked in real-time against current UTC time

    **Banner Types:**
    - Static banners: Traditional profile header images
    - Animated banners: Premium animated header backgrounds
    - Seasonal banners: Limited-time themed banners

    **Use Cases:**
    - Display available temporary banners in user interface
    - Check rental status before allowing banner selection
    - Manage temporary banner inventory for profile customization

    **Response:**
    Returns array of active rented banners with rental details including expiration times.
    """,
    responses={
        200: {
            "description": "Active rented banners retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "banners_rented": [
                            {
                                "banner_id": "emotion_tracker-static-banner-earth-1",
                                "unlocked_at": "2024-01-01T12:00:00Z",
                                "duration_hours": 24,
                                "valid_till": "2024-01-02T12:00:00Z",
                                "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
                            },
                            {
                                "banner_id": "emotion_tracker-seasonal-banner-winter-2024",
                                "unlocked_at": "2024-01-01T15:00:00Z",
                                "duration_hours": 168,
                                "valid_till": "2024-01-08T15:00:00Z",
                                "transaction_id": "550e8400-e29b-41d4-a716-446655440001",
                            },
                        ]
                    }
                }
            },
        },
        401: {"description": "Authentication required", "model": StandardErrorResponse},
        500: {"description": "Internal server error", "model": StandardErrorResponse},
    },
)
async def get_rented_banners(request: Request, current_user: dict = Depends(enforce_all_lockdowns)):
    # Set up logging context
    request_id = str(uuid.uuid4())[:8]
    client_ip = security_manager.get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    username = current_user["username"]

    request_id_context.set(request_id)
    user_id_context.set(username)
    ip_address_context.set(client_ip)

    start_time = time.time()

    logger.info(
        "[%s] GET /banners/rented - User: %s, IP: %s, User-Agent: %s", request_id, username, client_ip, user_agent[:100]
    )

    try:
        # Database operation with logging
        users_collection = db_manager.get_collection("users")

        db_start = time.time()
        user = await users_collection.find_one({"username": username}, {"_id": 0, "banners_rented": 1})
        db_duration = time.time() - db_start

        logger.info("[%s] DB find_one on users completed in %.3fs - User: %s", request_id, db_duration, username)

        if not user or "banners_rented" not in user:
            logger.info("[%s] No rented banners found for user: %s", request_id, username)
            duration = time.time() - start_time
            logger.info(
                "[%s] GET /banners/rented completed in %.3fs - User: %s, Returned: 0 banners",
                request_id,
                duration,
                username,
            )
            return {"banners_rented": []}

        # Filter active banners
        now = datetime.now(timezone.utc)
        total_rented = len(user.get("banners_rented", []))

        def is_active(banner):
            try:
                return datetime.fromisoformat(banner["valid_till"]) > now
            except Exception as e:
                logger.warning("[%s] Invalid banner expiry format for user %s: %s", request_id, username, str(e))
                return False

        filtered = [banner for banner in user["banners_rented"] if is_active(banner)]
        active_count = len(filtered)

        logger.info(
            "[%s] Filtered active banners - User: %s, Total: %d, Active: %d",
            request_id,
            username,
            total_rented,
            active_count,
        )

        duration = time.time() - start_time
        logger.info(
            "[%s] GET /banners/rented completed in %.3fs - User: %s, Returned: %d banners",
            request_id,
            duration,
            username,
            active_count,
        )

        return {"banners_rented": filtered}

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "[%s] GET /banners/rented failed after %.3fs - User: %s, Error: %s", request_id, duration, username, str(e)
        )
        log_error_with_context(
            e, context={"user": username, "ip": client_ip, "request_id": request_id}, operation="get_rented_banners"
        )
        raise


@router.get(
    "/banners/owned",
    tags=["User Profile"],
    summary="Get permanently owned banners",
    description="""
    Retrieve all permanently owned banners for the authenticated user.

    **Banner Ownership System:**
    - Banners can be permanently owned through purchase or rewards
    - Owned banners never expire and can be used indefinitely
    - Includes banners obtained through bundles, individual purchases, or special events

    **Banner Categories:**
    - Static banners: Traditional profile header images
    - Animated banners: Premium animated header backgrounds
    - Seasonal banners: Limited-time themed banners
    - Achievement banners: Unlocked through specific accomplishments

    **Use Cases:**
    - Display user's permanent banner collection
    - Allow banner selection in profile customization
    - Show ownership status for banner management

    **Response:**
    Returns array of permanently owned banner IDs for efficient processing.
    """,
    responses={
        200: {
            "description": "Owned banners retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "banners_owned": [
                            "emotion_tracker-static-banner-earth-1",
                            "emotion_tracker-static-banner-ocean-waves",
                            "emotion_tracker-animated-banner-floating-clouds",
                        ]
                    }
                }
            },
        },
        401: {"description": "Authentication required", "model": StandardErrorResponse},
        500: {"description": "Internal server error", "model": StandardErrorResponse},
    },
)
async def get_owned_banners(request: Request, current_user: dict = Depends(enforce_all_lockdowns)):
    # Set up logging context
    request_id = str(uuid.uuid4())[:8]
    client_ip = security_manager.get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    username = current_user["username"]

    request_id_context.set(request_id)
    user_id_context.set(username)
    ip_address_context.set(client_ip)

    start_time = time.time()

    logger.info(
        "[%s] GET /banners/owned - User: %s, IP: %s, User-Agent: %s", request_id, username, client_ip, user_agent[:100]
    )

    try:
        # Database operation with logging
        users_collection = db_manager.get_collection("users")

        db_start = time.time()
        user = await users_collection.find_one({"username": username}, {"_id": 0, "banners_owned": 1})
        db_duration = time.time() - db_start

        logger.info("[%s] DB find_one on users completed in %.3fs - User: %s", request_id, db_duration, username)

        if not user or "banners_owned" not in user:
            logger.info("[%s] No owned banners found for user: %s", request_id, username)
            duration = time.time() - start_time
            logger.info(
                "[%s] GET /banners/owned completed in %.3fs - User: %s, Returned: 0 banners",
                request_id,
                duration,
                username,
            )
            return {"banners_owned": []}

        # Build banners_owned as a set of banner_id strings
        owned = set(b.get("banner_id") for b in user.get("banners_owned", []) if b.get("banner_id"))
        owned_count = len(owned)

        logger.info("[%s] Retrieved owned banners - User: %s, Count: %d", request_id, username, owned_count)

        duration = time.time() - start_time
        logger.info(
            "[%s] GET /banners/owned completed in %.3fs - User: %s, Returned: %d banners",
            request_id,
            duration,
            username,
            owned_count,
        )

        return {"banners_owned": list(owned)}

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "[%s] GET /banners/owned failed after %.3fs - User: %s, Error: %s", request_id, duration, username, str(e)
        )
        log_error_with_context(
            e, context={"user": username, "ip": client_ip, "request_id": request_id}, operation="get_owned_banners"
        )
        raise


@router.post(
    "/banners/current",
    tags=["User Profile"],
    summary="Set current active banner",
    description="""
    Set the current active banner for the authenticated user and specific application.

    **Multi-Application Support:**
    - Each application can have its own active banner setting
    - Application is determined by User-Agent header
    - Allows users to have different banners across different apps

    **Ownership Verification:**
    - Verifies user owns or has valid rental for the banner
    - Checks rental expiration for temporary banners
    - Prevents setting banners the user doesn't have access to

    **Request Format:**
    ```json
    {
        "banner_id": "emotion_tracker-static-banner-earth-1"
    }
    ```

    **Use Cases:**
    - User selects banner in profile customization
    - Application startup banner loading
    - Profile header personalization workflows
    """,
    responses={
        200: {
            "description": "Banner set successfully",
            "content": {
                "application/json": {"example": {"success": True, "banner_id": "emotion_tracker-static-banner-earth-1"}}
            },
        },
        400: {
            "description": "Invalid request or banner not accessible",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_banner_id": {
                            "summary": "Missing banner ID",
                            "value": {"error": "banner_id is required"},
                        },
                        "not_owned": {
                            "summary": "Banner not owned or rental expired",
                            "value": {"error": "banner_id is not owned or validly rented"},
                        },
                    }
                }
            },
        },
        401: {"description": "Authentication required", "model": StandardErrorResponse},
        500: {"description": "Internal server error", "model": StandardErrorResponse},
    },
)
async def set_current_banner(request: Request, data: dict, current_user: dict = Depends(enforce_all_lockdowns)):
    """
    Set the current active banner for the user and application.

    Verifies ownership/rental status and updates the user's banner preference
    for the specific application determined by User-Agent header.
    """
    # Set up logging context
    request_id = str(uuid.uuid4())[:8]
    client_ip = security_manager.get_client_ip(request)
    user_agent = request.headers.get("user-agent", "unknown_app")
    username = current_user["username"]
    banner_id = data.get("banner_id")

    request_id_context.set(request_id)
    user_id_context.set(username)
    ip_address_context.set(client_ip)

    start_time = time.time()
    app_key = user_agent.split("/")[0].replace(" ", "_").lower() if user_agent else "unknown_app"

    logger.info(
        "[%s] POST /banners/current - User: %s, IP: %s, Banner: %s, App: %s",
        request_id,
        username,
        client_ip,
        banner_id,
        app_key,
    )

    try:
        if not banner_id:
            logger.warning(
                "[%s] POST /banners/current validation failed - User: %s, Missing banner_id", request_id, username
            )
            return {"error": "banner_id is required"}

        # Database operations with logging
        users_collection = db_manager.get_collection("users")

        db_start = time.time()
        user = await users_collection.find_one(
            {"username": username}, {"_id": 0, "banners": 1, "banners_owned": 1, "banners_rented": 1}
        )
        db_duration = time.time() - db_start

        logger.info(
            "[%s] DB find_one for banner verification completed in %.3fs - User: %s", request_id, db_duration, username
        )

        banners = user.get("banners", {}) if user else {}
        owned = set(b.get("banner_id") for b in user.get("banners_owned", []) if b.get("banner_id")) if user else set()
        rented = user.get("banners_rented", []) if user else []

        # Check ownership/rental
        if banner_id not in owned:
            now = datetime.now(timezone.utc)
            valid_rented = False
            for banner in rented:
                if banner.get("banner_id") == banner_id:
                    try:
                        if datetime.fromisoformat(banner["valid_till"]) > now:
                            valid_rented = True
                            break
                    except Exception as e:
                        logger.warning(
                            "[%s] Invalid rental expiry format for banner %s: %s", request_id, banner_id, str(e)
                        )
                        continue

            if not valid_rented:
                logger.warning(
                    "[%s] POST /banners/current access denied - User: %s, Banner: %s not owned/rented",
                    request_id,
                    username,
                    banner_id,
                )
                return {"error": "banner_id is not owned or validly rented"}

        # Update banner setting
        banners[app_key] = banner_id

        db_start = time.time()
        await users_collection.update_one({"username": username}, {"$set": {"banners": banners}})
        db_duration = time.time() - db_start

        logger.info(
            "[%s] DB update_one for banner setting completed in %.3fs - User: %s", request_id, db_duration, username
        )

        duration = time.time() - start_time
        logger.info(
            "[%s] POST /banners/current completed in %.3fs - User: %s, Banner: %s set for app: %s",
            request_id,
            duration,
            username,
            banner_id,
            app_key,
        )

        return {"success": True, "banner_id": banner_id}

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "[%s] POST /banners/current failed after %.3fs - User: %s, Error: %s",
            request_id,
            duration,
            username,
            str(e),
        )
        log_error_with_context(
            e,
            context={"user": username, "ip": client_ip, "request_id": request_id, "banner_id": banner_id},
            operation="set_current_banner",
        )
        return {"error": "Failed to set current banner", "details": str(e)}


@router.get(
    "/banners/current",
    tags=["User Profile"],
    summary="Get current active banner",
    description="""
    Retrieve the currently active banner for the authenticated user and specific application.

    **Multi-Application Support:**
    - Returns the banner currently set for the requesting application
    - Application is determined by User-Agent header
    - Each app can have its own active banner setting

    **Use Cases:**
    - Application startup banner loading
    - Profile header display in user interface
    - Banner synchronization across app sessions

    **Response:**
    Returns the banner ID currently set for the application, or null if no banner is set.
    """,
    responses={
        200: {
            "description": "Current banner retrieved successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "with_banner": {
                            "summary": "User has banner set",
                            "value": {"banner_id": "emotion_tracker-static-banner-earth-1"},
                        },
                        "no_banner": {"summary": "No banner set", "value": {"banner_id": None}},
                    }
                }
            },
        },
        401: {"description": "Authentication required", "model": StandardErrorResponse},
        500: {"description": "Internal server error", "model": StandardErrorResponse},
    },
)
async def get_current_banner(request: Request, current_user: dict = Depends(enforce_all_lockdowns)):
    # Set up logging context
    request_id = str(uuid.uuid4())[:8]
    client_ip = security_manager.get_client_ip(request)
    user_agent = request.headers.get("user-agent", "unknown_app")
    username = current_user["username"]

    request_id_context.set(request_id)
    user_id_context.set(username)
    ip_address_context.set(client_ip)

    start_time = time.time()
    app_key = user_agent.split("/")[0].replace(" ", "_").lower() if user_agent else "unknown_app"

    logger.info("[%s] GET /banners/current - User: %s, IP: %s, App: %s", request_id, username, client_ip, app_key)

    try:
        # Database operation with logging
        users_collection = db_manager.get_collection("users")

        db_start = time.time()
        user = await users_collection.find_one({"username": username}, {"_id": 0, "banners": 1})
        db_duration = time.time() - db_start

        logger.info(
            "[%s] DB find_one for current banner completed in %.3fs - User: %s", request_id, db_duration, username
        )

        banners = user.get("banners", {}) if user else {}
        banner_id = banners.get(app_key)

        duration = time.time() - start_time
        logger.info(
            "[%s] GET /banners/current completed in %.3fs - User: %s, App: %s, Banner: %s",
            request_id,
            duration,
            username,
            app_key,
            banner_id or "None",
        )

        return {"banner_id": banner_id}

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "[%s] GET /banners/current failed after %.3fs - User: %s, Error: %s", request_id, duration, username, str(e)
        )
        log_error_with_context(
            e,
            context={"user": username, "ip": client_ip, "request_id": request_id, "app_key": app_key},
            operation="get_current_banner",
        )
        raise
