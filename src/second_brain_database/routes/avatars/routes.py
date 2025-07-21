from fastapi import APIRouter, Request, Depends
from second_brain_database.database import db_manager
from second_brain_database.routes.auth.routes import get_current_user_dep
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.docs.models import (
    StandardErrorResponse, StandardSuccessResponse, ValidationErrorResponse,
    create_error_responses, create_standard_responses
)
from datetime import datetime, timezone

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
                                "transaction_id": "550e8400-e29b-41d4-a716-446655440000"
                            },
                            {
                                "avatar_id": "emotion_tracker-animated-avatar-playful_eye",
                                "unlocked_at": "2024-01-01T15:00:00Z",
                                "duration_hours": 48,
                                "valid_till": "2024-01-03T15:00:00Z",
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
async def get_rented_avatars(request: Request, current_user: dict = Depends(get_current_user_dep)):
    users_collection = db_manager.get_collection("users")
    user = await users_collection.find_one({"username": current_user["username"]}, {"_id": 0, "avatars_rented": 1})
    if not user or "avatars_rented" not in user:
        return {"avatars_rented": []}
    now = datetime.now(timezone.utc)
    def is_active(avatar):
        try:
            return datetime.fromisoformat(avatar["valid_till"]) > now
        except Exception:
            return False
    filtered = [avatar for avatar in user["avatars_rented"] if is_active(avatar)]
    return {"avatars_rented": filtered}

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
                                "price": 100
                            },
                            {
                                "avatar_id": "emotion_tracker-animated-avatar-floating_brain",
                                "unlocked_at": "2024-01-01T14:00:00Z",
                                "permanent": True,
                                "source": "bundle:emotion_tracker-avatars-premium-bundle",
                                "transaction_id": "550e8400-e29b-41d4-a716-446655440001",
                                "note": "Unlocked via premium bundle",
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
async def get_owned_avatars(request: Request, current_user: dict = Depends(get_current_user_dep)):
    users_collection = db_manager.get_collection("users")
    user = await users_collection.find_one({"username": current_user["username"]}, {"_id": 0, "avatars_owned": 1})
    if not user or "avatars_owned" not in user:
        return {"avatars_owned": []}
    return {"avatars_owned": user["avatars_owned"]}

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
                "application/json": {
                    "example": {
                        "success": True,
                        "avatar_id": "emotion_tracker-static-avatar-cat-5"
                    }
                }
            }
        },
        400: {
            "description": "Invalid request or avatar not accessible",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_avatar_id": {
                            "summary": "Missing avatar ID",
                            "value": {
                                "error": "avatar_id is required"
                            }
                        },
                        "not_owned": {
                            "summary": "Avatar not owned or rental expired",
                            "value": {
                                "error": "avatar_id is not owned or validly rented"
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
            "description": "Failed to update avatar setting",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Failed to set current avatar",
                        "details": "Database update failed"
                    }
                }
            }
        }
    }
)
async def set_current_avatar(request: Request, data: dict, current_user: dict = Depends(get_current_user_dep)):
    """
    Set the current active avatar for the user and application.
    
    Verifies ownership/rental status and updates the user's avatar preference
    for the specific application determined by User-Agent header.
    """
    users_collection = db_manager.get_collection("users")
    user_agent = request.headers.get("user-agent", "unknown_app")
    app_key = user_agent.split("/")[0].replace(" ", "_").lower() if user_agent else "unknown_app"
    avatar_id = data.get("avatar_id")
    username = current_user["username"]
    logger.info(f"[SET CURRENT AVATAR] User: {username}, app_key: {app_key}, avatar_id: {avatar_id} - Attempting to set current avatar.")
    if not avatar_id:
        logger.warning(f"[SET CURRENT AVATAR] User: {username}, app_key: {app_key} - avatar_id is required.")
        return {"error": "avatar_id is required"}
    # Check if avatar_id is owned or rented and valid
    user = await users_collection.find_one({"username": username}, {"_id": 0, "avatars": 1, "avatars_owned": 1, "avatars_rented": 1})
    avatars = user.get("avatars", {}) if user else {}
    # Patch: always build avatars_owned as a set of avatar_id strings
    owned = set(a.get("avatar_id") for a in user.get("avatars_owned", []) if a.get("avatar_id")) if user else set()
    rented = user.get("avatars_rented", []) if user else []
    # Check owned
    if avatar_id not in owned:
        # Check rented and valid
        now = datetime.now(timezone.utc)
        valid_rented = False
        for avatar in rented:
            if avatar.get("avatar_id") == avatar_id:
                try:
                    if datetime.fromisoformat(avatar["valid_till"]) > now:
                        valid_rented = True
                        break
                except Exception:
                    continue
        if not valid_rented:
            logger.warning(f"[SET CURRENT AVATAR] User: {username}, app_key: {app_key}, avatar_id: {avatar_id} - Not owned or validly rented.")
            return {"error": "avatar_id is not owned or validly rented"}
    avatars[app_key] = avatar_id
    try:
        await users_collection.update_one({"username": username}, {"$set": {"avatars": avatars}})
        logger.info(f"[SET CURRENT AVATAR] User: {username}, app_key: {app_key}, avatar_id: {avatar_id} - Successfully set current avatar.")
        return {"success": True, "avatar_id": avatar_id}
    except Exception as e:
        logger.error(f"[SET CURRENT AVATAR ERROR] User: {username}, app_key: {app_key}, avatar_id: {avatar_id}, error: {e}")
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
                            "value": {
                                "avatar_id": "emotion_tracker-static-avatar-cat-5"
                            }
                        },
                        "no_avatar": {
                            "summary": "No avatar set",
                            "value": {
                                "avatar_id": None
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
async def get_current_avatar(request: Request, current_user: dict = Depends(get_current_user_dep)):
    users_collection = db_manager.get_collection("users")
    user_agent = request.headers.get("user-agent", "unknown_app")
    app_key = user_agent.split("/")[0].replace(" ", "_").lower() if user_agent else "unknown_app"
    user = await users_collection.find_one({"username": current_user["username"]}, {"_id": 0, "avatars": 1})
    avatars = user.get("avatars", {}) if user else {}
    avatar_id = avatars.get(app_key)
    return {"avatar_id": avatar_id}

