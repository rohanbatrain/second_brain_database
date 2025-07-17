from fastapi import APIRouter, Request, Depends
from second_brain_database.database import db_manager
from second_brain_database.routes.auth.routes import get_current_user_dep
from second_brain_database.managers.logging_manager import get_logger
from datetime import datetime, timezone

router = APIRouter()
logger = get_logger(prefix="[AVATARS]")

@router.get("/avatars/rented", tags=["avatars"], summary="Get rented avatars for the authenticated user")
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

@router.get("/avatars/owned", tags=["avatars"], summary="Get currently owned avatars for the authenticated user")
async def get_owned_avatars(request: Request, current_user: dict = Depends(get_current_user_dep)):
    users_collection = db_manager.get_collection("users")
    user = await users_collection.find_one({"username": current_user["username"]}, {"_id": 0, "avatars_owned": 1})
    if not user or "avatars_owned" not in user:
        return {"avatars_owned": []}
    return {"avatars_owned": user["avatars_owned"]}

@router.post("/avatars/current", tags=["avatars"], summary="Set the current avatar for the authenticated user and app (by user-agent)")
async def set_current_avatar(request: Request, data: dict, current_user: dict = Depends(get_current_user_dep)):
    """
    Set the current avatar for the user and app (determined by user-agent).
    Expects: {"avatar_id": "..."}
    Stores in user.avatars[app_key] = avatar_id
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

@router.get("/avatars/current", tags=["avatars"], summary="Get the current avatar for the authenticated user and app (by user-agent)")
async def get_current_avatar(request: Request, current_user: dict = Depends(get_current_user_dep)):
    users_collection = db_manager.get_collection("users")
    user_agent = request.headers.get("user-agent", "unknown_app")
    app_key = user_agent.split("/")[0].replace(" ", "_").lower() if user_agent else "unknown_app"
    user = await users_collection.find_one({"username": current_user["username"]}, {"_id": 0, "avatars": 1})
    avatars = user.get("avatars", {}) if user else {}
    avatar_id = avatars.get(app_key)
    return {"avatar_id": avatar_id}

