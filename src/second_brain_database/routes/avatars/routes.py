from fastapi import APIRouter, Request, Depends
from second_brain_database.database import db_manager
from second_brain_database.routes.auth.routes import get_current_user_dep
from datetime import datetime, timezone

router = APIRouter()

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
