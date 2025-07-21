from fastapi import APIRouter, Request, Depends
from second_brain_database.database import db_manager
from second_brain_database.routes.auth.routes import get_current_user_dep
from second_brain_database.docs.models import (
    StandardErrorResponse, StandardSuccessResponse, ValidationErrorResponse,
    create_error_responses, create_standard_responses
)
from datetime import datetime, timezone

router = APIRouter()

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
                                "transaction_id": "550e8400-e29b-41d4-a716-446655440000"
                            },
                            {
                                "theme_id": "emotion_tracker-midnightLavender",
                                "unlocked_at": "2024-01-01T15:00:00Z",
                                "duration_hours": 168,
                                "valid_till": "2024-01-08T15:00:00Z",
                                "transaction_id": "550e8400-e29b-41d4-a716-446655440001"
                            }
                        ]
                    }
                }
            }
        },
        401: {
            "description": "Authentication required",
            "model": StandardErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": StandardErrorResponse
        }
    }
)
async def get_rented_themes(request: Request, current_user: dict = Depends(get_current_user_dep)):
    users_collection = db_manager.get_collection("users")
    user = await users_collection.find_one({"username": current_user["username"]}, {"_id": 0, "themes_rented": 1})
    if not user or "themes_rented" not in user:
        return {"themes_rented": []}
    user_agent = request.headers.get("user-agent", "")
    now = datetime.now(timezone.utc)
    def is_active(theme):
        try:
            return datetime.fromisoformat(theme["valid_till"]) > now
        except Exception:
            return False
    if "emotion_tracker" in user_agent:
        filtered = [
            theme for theme in user["themes_rented"]
            if theme["theme_id"].startswith("emotion_tracker-") and is_active(theme)
        ]
        return {"themes_rented": filtered}
    return {"themes_rented": []}

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
                                "price": 250
                            },
                            {
                                "theme_id": "emotion_tracker-midnightLavender",
                                "unlocked_at": "2024-01-01T14:00:00Z",
                                "permanent": True,
                                "source": "bundle:emotion_tracker-themes-dark",
                                "transaction_id": "550e8400-e29b-41d4-a716-446655440001",
                                "note": "Unlocked via dark theme bundle",
                                "price": 0
                            }
                        ]
                    }
                }
            }
        },
        401: {
            "description": "Authentication required",
            "model": StandardErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": StandardErrorResponse
        }
    }
)
async def get_owned_themes(request: Request, current_user: dict = Depends(get_current_user_dep)):
    users_collection = db_manager.get_collection("users")
    user = await users_collection.find_one({"username": current_user["username"]}, {"_id": 0, "themes_owned": 1})
    if not user or "themes_owned" not in user:
        return {"themes_owned": []}
    user_agent = request.headers.get("user-agent", "")
    if "emotion_tracker" in user_agent:
        owned = [theme for theme in user["themes_owned"] if theme["theme_id"].startswith("emotion_tracker-")]
        return {"themes_owned": owned}
    return {"themes_owned": []}

