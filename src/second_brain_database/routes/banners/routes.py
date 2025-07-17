from fastapi import APIRouter, Request, Depends
from second_brain_database.database import db_manager
from second_brain_database.routes.auth.routes import get_current_user_dep
from datetime import datetime, timezone

router = APIRouter()

@router.get("/banners/rented", tags=["banners"], summary="Get rented banners for the authenticated user")
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

@router.get("/banners/owned", tags=["banners"], summary="Get currently owned banners for the authenticated user")
async def get_owned_banners(request: Request, current_user: dict = Depends(get_current_user_dep)):
    users_collection = db_manager.get_collection("users")
    user = await users_collection.find_one({"username": current_user["username"]}, {"_id": 0, "banners_owned": 1})
    if not user or "banners_owned" not in user:
        return {"banners_owned": []}
    # Patch: always build banners_owned as a set of banner_id strings
    owned = set(b.get("banner_id") for b in user.get("banners_owned", []) if b.get("banner_id"))
    return {"banners_owned": list(owned)}

@router.post("/banners/current", tags=["banners"], summary="Set the current banner for the authenticated user and app (by user-agent)")
async def set_current_banner(request: Request, data: dict, current_user: dict = Depends(get_current_user_dep)):
    """
    Set the current banner for the user and app (determined by user-agent).
    Expects: {"banner_id": "..."}
    Stores in user.banners[app_key] = banner_id
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

@router.get("/banners/current", tags=["banners"], summary="Get the current banner for the authenticated user and app (by user-agent)")
async def get_current_banner(request: Request, current_user: dict = Depends(get_current_user_dep)):
    users_collection = db_manager.get_collection("users")
    user_agent = request.headers.get("user-agent", "unknown_app")
    app_key = user_agent.split("/")[0].replace(" ", "_").lower() if user_agent else "unknown_app"
    user = await users_collection.find_one({"username": current_user["username"]}, {"_id": 0, "banners": 1})
    banners = user.get("banners", {}) if user else {}
    banner_id = banners.get(app_key)
    return {"banner_id": banner_id}
