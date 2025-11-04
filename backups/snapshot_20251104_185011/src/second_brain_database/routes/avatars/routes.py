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
from second_brain_database.managers.family_manager import family_manager
from second_brain_database.utils.logging_utils import (
    ip_address_context,
    log_database_operation,
    log_error_with_context,
    log_performance,
    request_id_context,
    user_id_context,
)

router = APIRouter()
logger = get_logger(prefix="[AVATARS]")


@router.get(
    "/avatars/rented",
    tags=["User Profile"],
    summary="Get active rented avatars",
    description="""
    Retrieve all currently active rented avatars for the authenticated user.
    
    **Rental System:**
    - Avatars can be rented for temporary use (typically hours or days)
    - Only returns avatars that are currently valid (not expired)
    - Rental periods are checked in real-time
    
    **Use Cases:**
    - Display available temporary avatars in user interface
    - Check rental status before allowing avatar selection
    - Manage temporary avatar inventory
    
    **Response:**
    Returns array of active rented avatars with rental details including expiration times.
    """,
    responses={
        200: {
            "description": "Active rented avatars retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "avatars_rented": [
                            {
                                "avatar_id": "emotion_tracker-static-avatar-cat-1",
                                "unlocked_at": "2024-01-01T12:00:00Z",
                                "duration_hours": 24,
                                "valid_till": "2024-01-02T12:00:00Z",
                                "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
                            },
                            {
                                "avatar_id": "emotion_tracker-animated-avatar-playful_eye",
                                "unlocked_at": "2024-01-01T15:00:00Z",
                                "duration_hours": 48,
                                "valid_till": "2024-01-03T15:00:00Z",
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
async def get_rented_avatars(request: Request, current_user: dict = Depends(enforce_all_lockdowns)):
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
        "[%s] GET /avatars/rented - User: %s, IP: %s, User-Agent: %s", request_id, username, client_ip, user_agent[:100]
    )

    try:
        # Database operation with logging
        users_collection = db_manager.get_collection("users")

        db_start = time.time()
        user = await users_collection.find_one({"username": username}, {"_id": 0, "avatars_rented": 1})
        db_duration = time.time() - db_start

        logger.info("[%s] DB find_one on users completed in %.3fs - User: %s", request_id, db_duration, username)

        if not user or "avatars_rented" not in user:
            logger.info("[%s] No rented avatars found for user: %s", request_id, username)
            duration = time.time() - start_time
            logger.info(
                "[%s] GET /avatars/rented completed in %.3fs - User: %s, Returned: 0 avatars",
                request_id,
                duration,
                username,
            )
            return {"avatars_rented": []}

        # Filter active avatars
        now = datetime.now(timezone.utc)
        total_rented = len(user.get("avatars_rented", []))

        def is_active(avatar):
            try:
                return datetime.fromisoformat(avatar["valid_till"]) > now
            except Exception as e:
                logger.warning("[%s] Invalid avatar expiry format for user %s: %s", request_id, username, str(e))
                return False

        filtered = [avatar for avatar in user["avatars_rented"] if is_active(avatar)]
        active_count = len(filtered)

        logger.info(
            "[%s] Filtered active avatars - User: %s, Total: %d, Active: %d",
            request_id,
            username,
            total_rented,
            active_count,
        )

        duration = time.time() - start_time
        logger.info(
            "[%s] GET /avatars/rented completed in %.3fs - User: %s, Returned: %d avatars",
            request_id,
            duration,
            username,
            active_count,
        )

        return {"avatars_rented": filtered}

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "[%s] GET /avatars/rented failed after %.3fs - User: %s, Error: %s", request_id, duration, username, str(e)
        )
        log_error_with_context(
            e, context={"user": username, "ip": client_ip, "request_id": request_id}, operation="get_rented_avatars"
        )
        raise


@router.get(
    "/avatars/owned",
    tags=["User Profile"],
    summary="Get permanently owned avatars",
    description="""
    Retrieve all permanently owned avatars for the authenticated user.
    
    **Ownership System:**
    - Avatars can be permanently owned through purchase or rewards
    - Owned avatars never expire and can be used indefinitely
    - Includes avatars obtained through bundles, individual purchases, or special rewards
    
    **Avatar Types:**
    - Static avatars: Traditional profile pictures
    - Animated avatars: Premium animated profile pictures
    - Special edition avatars: Limited-time or achievement-based avatars
    
    **Use Cases:**
    - Display user's permanent avatar collection
    - Allow avatar selection in user interface
    - Show ownership status for avatar management
    
    **Response:**
    Returns array of permanently owned avatars with purchase/unlock details.
    """,
    responses={
        200: {
            "description": "Owned avatars retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "avatars_owned": [
                            {
                                "avatar_id": "emotion_tracker-static-avatar-cat-5",
                                "unlocked_at": "2024-01-01T10:00:00Z",
                                "permanent": True,
                                "source": "purchase",
                                "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
                                "note": "Bought from shop",
                                "price": 100,
                            },
                            {
                                "avatar_id": "emotion_tracker-animated-avatar-floating_brain",
                                "unlocked_at": "2024-01-01T14:00:00Z",
                                "permanent": True,
                                "source": "bundle:emotion_tracker-avatars-premium-bundle",
                                "transaction_id": "550e8400-e29b-41d4-a716-446655440001",
                                "note": "Unlocked via premium bundle",
                                "price": 0,
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
async def get_owned_avatars(request: Request, current_user: dict = Depends(enforce_all_lockdowns)):
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
        "[%s] GET /avatars/owned - User: %s, IP: %s, User-Agent: %s", request_id, username, client_ip, user_agent[:100]
    )

    try:
        # Database operation with logging
        users_collection = db_manager.get_collection("users")

        db_start = time.time()
        user = await users_collection.find_one({"username": username}, {"_id": 0, "avatars_owned": 1})
        db_duration = time.time() - db_start

        logger.info("[%s] DB find_one on users completed in %.3fs - User: %s", request_id, db_duration, username)

        if not user or "avatars_owned" not in user:
            logger.info("[%s] No owned avatars found for user: %s", request_id, username)
            duration = time.time() - start_time
            logger.info(
                "[%s] GET /avatars/owned completed in %.3fs - User: %s, Returned: 0 avatars",
                request_id,
                duration,
                username,
            )
            # Check family-owned avatars if user has family memberships
            try:
                family_entries = await family_manager.get_user_families(str(current_user["_id"]), username)
                combined = []
                for f in family_entries:
                    try:
                        fam_items = await family_manager.get_family_owned_items(f["family_id"], "avatar")
                        combined.extend(fam_items)
                    except Exception:
                        continue
                return {"avatars_owned": combined}
            except Exception:
                return {"avatars_owned": []}

        owned_list = list(user.get("avatars_owned", []))

        # Merge family-owned avatars (avoid duplicates by avatar_id)
        try:
            family_entries = await family_manager.get_user_families(str(current_user["_id"]), username)
            for f in family_entries:
                try:
                    fam_items = await family_manager.get_family_owned_items(f["family_id"], "avatar")
                    for it in fam_items:
                        if not any(existing.get("avatar_id") == it.get("avatar_id") for existing in owned_list):
                            owned_list.append(it)
                except Exception:
                    continue
        except Exception:
            # Ignore family merge failures
            pass

        owned_count = len(owned_list)
        logger.info("[%s] Retrieved owned avatars - User: %s, Count: %d", request_id, username, owned_count)

        duration = time.time() - start_time
        logger.info(
            "[%s] GET /avatars/owned completed in %.3fs - User: %s, Returned: %d avatars",
            request_id,
            duration,
            username,
            owned_count,
        )

        return {"avatars_owned": owned_list}

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "[%s] GET /avatars/owned failed after %.3fs - User: %s, Error: %s", request_id, duration, username, str(e)
        )
        log_error_with_context(
            e, context={"user": username, "ip": client_ip, "request_id": request_id}, operation="get_owned_avatars"
        )
        raise


@router.post(
    "/avatars/current",
    tags=["User Profile"],
    summary="Set current active avatar",
    description="""
    Set the current active avatar for the authenticated user and specific application.
    
    **Multi-Application Support:**
    - Each application can have its own active avatar setting
    - Application is determined by User-Agent header
    - Allows users to have different avatars across different apps
    
    **Ownership Verification:**
    - Verifies user owns or has valid rental for the avatar
    - Checks rental expiration for temporary avatars
    - Prevents setting avatars the user doesn't have access to
    
    **Request Format:**
    ```json
    {
        "avatar_id": "emotion_tracker-static-avatar-cat-5"
    }
    ```
    
    **Use Cases:**
    - User selects avatar in application settings
    - Application startup avatar loading
    - Profile customization workflows
    """,
    responses={
        200: {
            "description": "Avatar set successfully",
            "content": {
                "application/json": {"example": {"success": True, "avatar_id": "emotion_tracker-static-avatar-cat-5"}}
            },
        },
        400: {
            "description": "Invalid request or avatar not accessible",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_avatar_id": {
                            "summary": "Missing avatar ID",
                            "value": {"error": "avatar_id is required"},
                        },
                        "not_owned": {
                            "summary": "Avatar not owned or rental expired",
                            "value": {"error": "avatar_id is not owned or validly rented"},
                        },
                    }
                }
            },
        },
        401: {"description": "Authentication required", "model": StandardErrorResponse},
        500: {
            "description": "Failed to update avatar setting",
            "content": {
                "application/json": {
                    "example": {"error": "Failed to set current avatar", "details": "Database update failed"}
                }
            },
        },
    },
)
async def set_current_avatar(request: Request, data: dict, current_user: dict = Depends(enforce_all_lockdowns)):
    """
    Set the current active avatar for the user and application.

    Verifies ownership/rental status and updates the user's avatar preference
    for the specific application determined by User-Agent header.
    """
    # Set up logging context
    request_id = str(uuid.uuid4())[:8]
    client_ip = security_manager.get_client_ip(request)
    user_agent = request.headers.get("user-agent", "unknown_app")
    username = current_user["username"]
    avatar_id = data.get("avatar_id")

    request_id_context.set(request_id)
    user_id_context.set(username)
    ip_address_context.set(client_ip)

    start_time = time.time()
    app_key = user_agent.split("/")[0].replace(" ", "_").lower() if user_agent else "unknown_app"

    logger.info(
        "[%s] POST /avatars/current - User: %s, IP: %s, Avatar: %s, App: %s",
        request_id,
        username,
        client_ip,
        avatar_id,
        app_key,
    )

    try:
        if not avatar_id:
            logger.warning(
                "[%s] POST /avatars/current validation failed - User: %s, Missing avatar_id", request_id, username
            )
            return {"error": "avatar_id is required"}

        # Database operations with logging
        users_collection = db_manager.get_collection("users")

        db_start = time.time()
        user = await users_collection.find_one(
            {"username": username}, {"_id": 0, "avatars": 1, "avatars_owned": 1, "avatars_rented": 1}
        )
        db_duration = time.time() - db_start

        logger.info(
            "[%s] DB find_one for avatar verification completed in %.3fs - User: %s", request_id, db_duration, username
        )

        avatars = user.get("avatars", {}) if user else {}
        owned = set(a.get("avatar_id") for a in user.get("avatars_owned", []) if a.get("avatar_id")) if user else set()
        rented = user.get("avatars_rented", []) if user else []

        # Also include family-owned avatars in ownership checks
        try:
            family_entries = await family_manager.get_user_families(str(current_user["_id"]), username)
            for f in family_entries:
                try:
                    fam_items = await family_manager.get_family_owned_items(f["family_id"], "avatar")
                    for it in fam_items:
                        if it.get("avatar_id"):
                            owned.add(it.get("avatar_id"))
                except Exception:
                    continue
        except Exception:
            pass

        # Check ownership/rental
        if avatar_id not in owned:
            now = datetime.now(timezone.utc)
            valid_rented = False
            for avatar in rented:
                if avatar.get("avatar_id") == avatar_id:
                    try:
                        if datetime.fromisoformat(avatar["valid_till"]) > now:
                            valid_rented = True
                            break
                    except Exception as e:
                        logger.warning(
                            "[%s] Invalid rental expiry format for avatar %s: %s", request_id, avatar_id, str(e)
                        )
                        continue

            if not valid_rented:
                logger.warning(
                    "[%s] POST /avatars/current access denied - User: %s, Avatar: %s not owned/rented",
                    request_id,
                    username,
                    avatar_id,
                )
                return {"error": "avatar_id is not owned or validly rented"}

        # Update avatar setting
        avatars[app_key] = avatar_id

        db_start = time.time()
        await users_collection.update_one({"username": username}, {"$set": {"avatars": avatars}})
        db_duration = time.time() - db_start

        logger.info(
            "[%s] DB update_one for avatar setting completed in %.3fs - User: %s", request_id, db_duration, username
        )

        duration = time.time() - start_time
        logger.info(
            "[%s] POST /avatars/current completed in %.3fs - User: %s, Avatar: %s set for app: %s",
            request_id,
            duration,
            username,
            avatar_id,
            app_key,
        )

        return {"success": True, "avatar_id": avatar_id}

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "[%s] POST /avatars/current failed after %.3fs - User: %s, Error: %s",
            request_id,
            duration,
            username,
            str(e),
        )
        log_error_with_context(
            e,
            context={"user": username, "ip": client_ip, "request_id": request_id, "avatar_id": avatar_id},
            operation="set_current_avatar",
        )
        return {"error": "Failed to set current avatar", "details": str(e)}


@router.get(
    "/avatars/current",
    tags=["User Profile"],
    summary="Get current active avatar",
    description="""
    Retrieve the currently active avatar for the authenticated user and specific application.
    
    **Multi-Application Support:**
    - Returns the avatar currently set for the requesting application
    - Application is determined by User-Agent header
    - Each app can have its own active avatar setting
    
    **Use Cases:**
    - Application startup avatar loading
    - Profile display in user interface
    - Avatar synchronization across app sessions
    
    **Response:**
    Returns the avatar ID currently set for the application, or null if no avatar is set.
    """,
    responses={
        200: {
            "description": "Current avatar retrieved successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "with_avatar": {
                            "summary": "User has avatar set",
                            "value": {"avatar_id": "emotion_tracker-static-avatar-cat-5"},
                        },
                        "no_avatar": {"summary": "No avatar set", "value": {"avatar_id": None}},
                    }
                }
            },
        },
        401: {"description": "Authentication required", "model": StandardErrorResponse},
        500: {"description": "Internal server error", "model": StandardErrorResponse},
    },
)
async def get_current_avatar(request: Request, current_user: dict = Depends(enforce_all_lockdowns)):
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

    logger.info("[%s] GET /avatars/current - User: %s, IP: %s, App: %s", request_id, username, client_ip, app_key)

    try:
        # Database operation with logging
        users_collection = db_manager.get_collection("users")

        db_start = time.time()
        user = await users_collection.find_one({"username": username}, {"_id": 0, "avatars": 1})
        db_duration = time.time() - db_start

        logger.info(
            "[%s] DB find_one for current avatar completed in %.3fs - User: %s", request_id, db_duration, username
        )

        avatars = user.get("avatars", {}) if user else {}
        avatar_id = avatars.get(app_key)

        duration = time.time() - start_time
        logger.info(
            "[%s] GET /avatars/current completed in %.3fs - User: %s, App: %s, Avatar: %s",
            request_id,
            duration,
            username,
            app_key,
            avatar_id or "None",
        )

        return {"avatar_id": avatar_id}

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "[%s] GET /avatars/current failed after %.3fs - User: %s, Error: %s", request_id, duration, username, str(e)
        )
        log_error_with_context(
            e,
            context={"user": username, "ip": client_ip, "request_id": request_id, "app_key": app_key},
            operation="get_current_avatar",
        )
        raise
