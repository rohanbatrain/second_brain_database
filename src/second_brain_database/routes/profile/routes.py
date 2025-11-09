from datetime import datetime, timezone
import re

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.routes.auth import enforce_all_lockdowns
from second_brain_database.utils.logging_utils import (
    ip_address_context,
    log_error_with_context,
    request_id_context,
    user_id_context,
)

router = APIRouter(prefix="/profile", tags=["User Profile"])
logger = get_logger(prefix="[PROFILE]")


@router.post("/update", tags=["User Profile"], summary="Update user profile fields")
async def update_profile(request: Request, data: dict = Body(...), current_user: dict = Depends(enforce_all_lockdowns)):
    """
    Update the profile information for the authenticated user.

    This endpoint allows a user to update various fields in their profile.
    The following fields can be updated:
    - `user_first_name` (string, max 50 chars)
    - `user_last_name` (string, max 50 chars)
    - `user_dob` (string, format YYYY-MM-DD)
    - `user_gender` (string, max 20 chars)
    - `user_bio` (string, max 200 chars)

    Args:
        request (Request): The incoming request object.
        data (dict): A dictionary containing the fields to be updated.
        current_user (dict): The authenticated user, injected by Depends.

    Returns:
        dict: A dictionary confirming the successful update and listing the updated fields.
    """
    request_id = str(datetime.now(timezone.utc).timestamp()).replace(".", "")[-8:]
    client_ip = security_manager.get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    username = current_user["username"]

    request_id_context.set(request_id)
    user_id_context.set(username)
    ip_address_context.set(client_ip)

    logger.info(
        "[%s] POST /profile/update - User: %s, IP: %s, User-Agent: %s",
        request_id,
        username,
        client_ip,
        user_agent[:100],
    )

    # Field definitions (username and email removed)
    fields = {
        "user_first_name": (str, 50),
        "user_last_name": (str, 50),
        "user_dob": (str, 10),
        "user_gender": (str, 20),
        "user_bio": (str, 200),
    }
    updates = {}
    errors = {}

    # Validate and collect updates
    for field, (ftype, maxlen) in fields.items():
        value = data.get(field)
        if value is not None:
            if not isinstance(value, ftype):
                errors[field] = f"Must be {ftype.__name__}"
                continue
            if maxlen and len(value) > maxlen:
                errors[field] = f"Max length is {maxlen}"
                continue
            updates[field] = value

    if errors:
        logger.warning("[%s] Profile update validation failed - User: %s, Errors: %s", request_id, username, errors)
        return JSONResponse({"status": "error", "detail": errors}, status_code=400)

    users_collection = db_manager.get_collection("users")
    try:
        result = await users_collection.update_one({"username": username}, {"$set": updates})
        logger.info("[%s] Profile updated for user: %s, Fields: %s", request_id, username, list(updates.keys()))
        return {"status": "success", "updated_fields": updates}
    except Exception as e:
        logger.error("[%s] Profile update failed for user: %s, Error: %s", request_id, username, str(e))
        log_error_with_context(
            e, context={"user": username, "ip": client_ip, "request_id": request_id}, operation="update_profile"
        )
        return JSONResponse({"status": "error", "detail": "Internal server error", "error": str(e)}, status_code=500)


@router.get("/info", tags=["User Profile"], summary="Get current user profile information")
async def get_profile_info(request: Request, current_user: dict = Depends(enforce_all_lockdowns)):
    """
    Get the profile information for the authenticated user.

    This endpoint retrieves a user's profile information. The following fields are returned:
    - `user_first_name`
    - `user_last_name`
    - `user_username`
    - `user_email`
    - `user_dob`
    - `user_gender`
    - `user_bio`

    Args:
        request (Request): The incoming request object.
        current_user (dict): The authenticated user, injected by Depends.

    Returns:
        dict: A dictionary containing the user's profile information.
    """
    request_id = str(datetime.now(timezone.utc).timestamp()).replace(".", "")[-8:]
    client_ip = security_manager.get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    username = current_user["username"]

    request_id_context.set(request_id)
    user_id_context.set(username)
    ip_address_context.set(client_ip)

    logger.info(
        "[%s] GET /profile/info - User: %s, IP: %s, User-Agent: %s", request_id, username, client_ip, user_agent[:100]
    )

    users_collection = db_manager.get_collection("users")
    try:
        user_doc = await users_collection.find_one({"username": username})
        if not user_doc:
            logger.warning("[%s] Profile info not found for user: %s", request_id, username)
            return JSONResponse({"status": "error", "detail": "Profile not found"}, status_code=404)
        # Only return safe fields
        profile_fields = [
            "user_first_name",
            "user_last_name",
            "user_username",
            "user_email",
            "user_dob",
            "user_gender",
            "user_bio",
        ]
        profile = {field: user_doc.get(field) for field in profile_fields}
        return {"status": "success", "profile": profile}
    except Exception as e:
        logger.error("[%s] Profile info fetch failed for user: %s, Error: %s", request_id, username, str(e))
        log_error_with_context(
            e, context={"user": username, "ip": client_ip, "request_id": request_id}, operation="get_profile_info"
        )
        return JSONResponse({"status": "error", "detail": "Internal server error", "error": str(e)}, status_code=500)
