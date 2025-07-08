from fastapi import APIRouter, Request, Depends
from second_brain_database.database import db_manager
from second_brain_database.routes.auth.routes import get_current_user_dep
from datetime import datetime, timezone

router = APIRouter()

@router.get("/themes/rented", tags=["themes"], summary="Get rented themes for the authenticated user")
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

@router.get("/themes/owned", tags=["themes"], summary="Get currently owned emotion_tracker themes for the authenticated user")
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

