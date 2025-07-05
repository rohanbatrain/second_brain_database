from fastapi import APIRouter, Request, Depends
from second_brain_database.database import db_manager
from second_brain_database.routes.auth.routes import get_current_user_dep

router = APIRouter()

@router.get("/themes/rented", tags=["themes"], summary="Get rented themes for the authenticated user")
async def get_rented_themes(request: Request, current_user: dict = Depends(get_current_user_dep)):
    users_collection = db_manager.get_collection("users")
    user = await users_collection.find_one({"username": current_user["username"]}, {"_id": 0, "themes_rented": 1})
    if not user or "themes_rented" not in user:
        return {"themes_rented": []}
    user_agent = request.headers.get("user-agent", "")
    # Only return emotion_tracker-* themes if user agent matches
    if user_agent.startswith("emotion_tracker/1.0.0") and "platform=linux" in user_agent:
        filtered = [theme for theme in user["themes_rented"] if theme["theme_id"].startswith("emotion_tracker-")]
        return {"themes_rented": filtered}
    return {"themes_rented": user["themes_rented"]}
