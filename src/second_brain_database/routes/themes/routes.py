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
from second_brain_database.routes.auth.routes import get_current_user_dep
from second_brain_database.utils.logging_utils import (
    ip_address_context,
    log_database_operation,
    log_error_with_context,
    log_performance,
    request_id_context,
    user_id_context,
)

router = APIRouter()
logger = get_logger(prefix="[THEMES]")


@router.get(
    "/themes/rented",
    tags=["User Profile"],
    summary="Get active rented themes",
    description="""
    Retrieve all currently active rented themes for the authenticated user.
    
    **Application-Specific Filtering:**
    - Only returns themes compatible with the requesting application
    - Application is determined by User-Agent header
    - Currently supports Emotion Tracker themes
    
    **Theme Rental System:**
    - Themes can be rented for temporary use (typically hours or days)
    - Only returns themes that are currently valid (not expired)
    - Rental periods are checked in real-time against current UTC time
    
    **Theme Categories:**
    - Light themes: Optimized for daytime use
    - Dark themes: Optimized for low-light environments
    - Seasonal themes: Limited-time themed appearances
    - Special edition themes: Event-based or achievement themes
    
    **Use Cases:**
    - Display available temporary themes in application settings
    - Check rental status before allowing theme selection
    - Manage temporary theme inventory for UI customization
    
    **Response:**
    Returns array of active rented themes with rental details including expiration times.
    """,
    responses={
        200: {
            "description": "Active rented themes retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "themes_rented": [
                            {
                                "theme_id": "emotion_tracker-serenityGreenDark",
                                "unlocked_at": "2024-01-01T12:00:00Z",
                                "duration_hours": 24,
                                "valid_till": "2024-01-02T12:00:00Z",
                                "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
                            },
                            {
                                "theme_id": "emotion_tracker-midnightLavender",
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
async def get_rented_themes(request: Request, current_user: dict = Depends(get_current_user_dep)):
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
        "[%s] GET /themes/rented - User: %s, IP: %s, User-Agent: %s", request_id, username, client_ip, user_agent[:100]
    )

    try:
        # Database operation with logging
        users_collection = db_manager.get_collection("users")

        db_start = time.time()
        user = await users_collection.find_one({"username": username}, {"_id": 0, "themes_rented": 1})
        db_duration = time.time() - db_start

        logger.info("[%s] DB find_one on users completed in %.3fs - User: %s", request_id, db_duration, username)

        if not user or "themes_rented" not in user:
            logger.info("[%s] No rented themes found for user: %s", request_id, username)
            return {"themes_rented": []}

        # Filter active themes
        now = datetime.now(timezone.utc)
        total_rented = len(user.get("themes_rented", []))

        def is_active(theme):
            try:
                return datetime.fromisoformat(theme["valid_till"]) > now
            except Exception as e:
                logger.warning("[%s] Invalid theme expiry format for user %s: %s", request_id, username, str(e))
                return False

        if "emotion_tracker" in user_agent:
            filtered = [
                theme
                for theme in user["themes_rented"]
                if theme["theme_id"].startswith("emotion_tracker-") and is_active(theme)
            ]
            active_count = len(filtered)

            logger.info(
                "[%s] Filtered themes for emotion_tracker - User: %s, Total: %d, Active: %d",
                request_id,
                username,
                total_rented,
                active_count,
            )

            duration = time.time() - start_time
            logger.info(
                "[%s] GET /themes/rented completed in %.3fs - User: %s, Returned: %d themes",
                request_id,
                duration,
                username,
                active_count,
            )

            return {"themes_rented": filtered}

        logger.info("[%s] No emotion_tracker user-agent, returning empty - User: %s", request_id, username)

        duration = time.time() - start_time
        logger.info(
            "[%s] GET /themes/rented completed in %.3fs - User: %s, Returned: 0 themes", request_id, duration, username
        )

        return {"themes_rented": []}

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "[%s] GET /themes/rented failed after %.3fs - User: %s, Error: %s", request_id, duration, username, str(e)
        )
        log_error_with_context(
            e, context={"user": username, "ip": client_ip, "request_id": request_id}, operation="get_rented_themes"
        )
        raise


@router.get(
    "/themes/owned",
    tags=["User Profile"],
    summary="Get permanently owned themes",
    description="""
    Retrieve all permanently owned themes for the authenticated user.
    
    **Application-Specific Filtering:**
    - Only returns themes compatible with the requesting application
    - Application is determined by User-Agent header
    - Currently supports Emotion Tracker themes
    
    **Theme Ownership System:**
    - Themes can be permanently owned through purchase or rewards
    - Owned themes never expire and can be used indefinitely
    - Includes themes obtained through bundles, individual purchases, or special events
    
    **Theme Categories:**
    - Light themes: Optimized for daytime use with bright, vibrant colors
    - Dark themes: Optimized for low-light environments with muted tones
    - Seasonal themes: Limited-time themed appearances for holidays/events
    - Premium themes: High-quality themes with advanced visual effects
    
    **Available Theme Collections:**
    - Serenity Green (Light/Dark variants)
    - Pacific Blue (Light/Dark variants)
    - Blush Rose (Light/Dark variants)
    - Midnight Lavender (Light variant)
    - And many more color schemes
    
    **Use Cases:**
    - Display user's permanent theme collection in settings
    - Allow theme selection in application customization
    - Show ownership status for theme management
    
    **Response:**
    Returns array of permanently owned themes with purchase/unlock details.
    """,
    responses={
        200: {
            "description": "Owned themes retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "themes_owned": [
                            {
                                "theme_id": "emotion_tracker-serenityGreen",
                                "unlocked_at": "2024-01-01T10:00:00Z",
                                "permanent": True,
                                "source": "purchase",
                                "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
                                "note": "Bought from shop",
                                "price": 250,
                            },
                            {
                                "theme_id": "emotion_tracker-midnightLavender",
                                "unlocked_at": "2024-01-01T14:00:00Z",
                                "permanent": True,
                                "source": "bundle:emotion_tracker-themes-dark",
                                "transaction_id": "550e8400-e29b-41d4-a716-446655440001",
                                "note": "Unlocked via dark theme bundle",
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
async def get_owned_themes(request: Request, current_user: dict = Depends(get_current_user_dep)):
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
        "[%s] GET /themes/owned - User: %s, IP: %s, User-Agent: %s", request_id, username, client_ip, user_agent[:100]
    )

    try:
        # Database operation with logging
        users_collection = db_manager.get_collection("users")

        db_start = time.time()
        user = await users_collection.find_one({"username": username}, {"_id": 0, "themes_owned": 1})
        db_duration = time.time() - db_start

        logger.info("[%s] DB find_one on users completed in %.3fs - User: %s", request_id, db_duration, username)

        if not user or "themes_owned" not in user:
            logger.info("[%s] No owned themes found for user: %s", request_id, username)
            duration = time.time() - start_time
            logger.info(
                "[%s] GET /themes/owned completed in %.3fs - User: %s, Returned: 0 themes",
                request_id,
                duration,
                username,
            )
            return {"themes_owned": []}

        total_owned = len(user.get("themes_owned", []))

        if "emotion_tracker" in user_agent:
            owned = [theme for theme in user["themes_owned"] if theme["theme_id"].startswith("emotion_tracker-")]
            filtered_count = len(owned)

            logger.info(
                "[%s] Filtered themes for emotion_tracker - User: %s, Total: %d, Filtered: %d",
                request_id,
                username,
                total_owned,
                filtered_count,
            )

            duration = time.time() - start_time
            logger.info(
                "[%s] GET /themes/owned completed in %.3fs - User: %s, Returned: %d themes",
                request_id,
                duration,
                username,
                filtered_count,
            )

            return {"themes_owned": owned}

        logger.info("[%s] No emotion_tracker user-agent, returning empty - User: %s", request_id, username)

        duration = time.time() - start_time
        logger.info(
            "[%s] GET /themes/owned completed in %.3fs - User: %s, Returned: 0 themes", request_id, duration, username
        )

        return {"themes_owned": []}

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "[%s] GET /themes/owned failed after %.3fs - User: %s, Error: %s", request_id, duration, username, str(e)
        )
        log_error_with_context(
            e, context={"user": username, "ip": client_ip, "request_id": request_id}, operation="get_owned_themes"
        )
        raise
