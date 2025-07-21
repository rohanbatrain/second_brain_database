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
                                "transaction_id": "550e8400-e29b-41d4-a716-446655440000"
                            },
                            {
                                "banner_id": "emotion_tracker-seasonal-banner-winter-2024",
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
async def get_rented_banners(request: Request, current_user: dict = Depends(get_current_user_dep)):
    users_collection = db_manager.get_collection("users")
    user = await users_collection.find_one({"username": current_user["username"]}, {"_id": 0, "banners_rented": 1})
    if not user or "banners_rented" not in user:
        return {"banners_rented": []}
    now = datetime.now(timezone.utc)
    def is_active(banner):
        try:
            return datetime.fromisoformat(banner["valid_till"]) > now
        except Exception:
            return False
    filtered = [banner for banner in user["banners_rented"] if is_active(banner)]
    return {"banners_rented": filtered}

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
                            "emotion_tracker-animated-banner-floating-clouds"
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
async def get_owned_banners(request: Request, current_user: dict = Depends(get_current_user_dep)):
    users_collection = db_manager.get_collection("users")
    user = await users_collection.find_one({"username": current_user["username"]}, {"_id": 0, "banners_owned": 1})
    if not user or "banners_owned" not in user:
        return {"banners_owned": []}
    # Patch: always build banners_owned as a set of banner_id strings
    owned = set(b.get("banner_id") for b in user.get("banners_owned", []) if b.get("banner_id"))
    return {"banners_owned": list(owned)}

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
                "application/json": {
                    "example": {
                        "success": True,
                        "banner_id": "emotion_tracker-static-banner-earth-1"
                    }
                }
            }
        },
        400: {
            "description": "Invalid request or banner not accessible",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_banner_id": {
                            "summary": "Missing banner ID",
                            "value": {
                                "error": "banner_id is required"
                            }
                        },
                        "not_owned": {
                            "summary": "Banner not owned or rental expired",
                            "value": {
                                "error": "banner_id is not owned or validly rented"
                            }
                        }
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
async def set_current_banner(request: Request, data: dict, current_user: dict = Depends(get_current_user_dep)):
    """
    Set the current active banner for the user and application.
    
    Verifies ownership/rental status and updates the user's banner preference
    for the specific application determined by User-Agent header.
    """
    users_collection = db_manager.get_collection("users")
    user_agent = request.headers.get("user-agent", "unknown_app")
    app_key = user_agent.split("/")[0].replace(" ", "_").lower() if user_agent else "unknown_app"
    banner_id = data.get("banner_id")
    if not banner_id:
        return {"error": "banner_id is required"}
    # Check if banner_id is owned or rented and valid
    user = await users_collection.find_one({"username": current_user["username"]}, {"_id": 0, "banners": 1, "banners_owned": 1, "banners_rented": 1})
    banners = user.get("banners", {}) if user else {}
    # Patch: always build banners_owned as a set of banner_id strings
    owned = set(b.get("banner_id") for b in user.get("banners_owned", []) if b.get("banner_id")) if user else set()
    rented = user.get("banners_rented", []) if user else []
    if banner_id not in owned:
        now = datetime.now(timezone.utc)
        valid_rented = False
        for banner in rented:
            if banner.get("banner_id") == banner_id:
                try:
                    if datetime.fromisoformat(banner["valid_till"]) > now:
                        valid_rented = True
                        break
                except Exception:
                    continue
        if not valid_rented:
            return {"error": "banner_id is not owned or validly rented"}
    banners[app_key] = banner_id
    await users_collection.update_one({"username": current_user["username"]}, {"$set": {"banners": banners}})
    return {"success": True, "banner_id": banner_id}

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
                            "value": {
                                "banner_id": "emotion_tracker-static-banner-earth-1"
                            }
                        },
                        "no_banner": {
                            "summary": "No banner set",
                            "value": {
                                "banner_id": None
                            }
                        }
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
async def get_current_banner(request: Request, current_user: dict = Depends(get_current_user_dep)):
    users_collection = db_manager.get_collection("users")
    user_agent = request.headers.get("user-agent", "unknown_app")
    app_key = user_agent.split("/")[0].replace(" ", "_").lower() if user_agent else "unknown_app"
    user = await users_collection.find_one({"username": current_user["username"]}, {"_id": 0, "banners": 1})
    banners = user.get("banners", {}) if user else {}
    banner_id = banners.get(app_key)
    return {"banner_id": banner_id}
