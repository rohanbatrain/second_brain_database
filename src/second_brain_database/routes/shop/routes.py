from fastapi import APIRouter, Request, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from second_brain_database.database import db_manager
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.routes import get_current_user_dep
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

logger = get_logger(prefix="[SHOP]")

router = APIRouter()

SHOP_COLLECTION = "shop"

# Server-side registry for shop items to ensure prices are not client-controlled.
# In a real-world application, this would be a separate collection in the database.
async def get_item_details(item_id: str, item_type: str):
    # This is a mock implementation. Replace with a real database lookup.
    if item_type == "theme":
        if item_id.startswith("emotion_tracker-"):
            return {"theme_id": item_id, "name": "Emotion Tracker Theme", "price": 250, "type": "theme"}
    elif item_type == "avatar":
        # Premium animated avatars
        if item_id == "emotion_tracker-animated-avatar-playful_eye":
            return {"avatar_id": item_id, "name": "Playful Eye", "price": 2500, "type": "avatar"}
        if item_id == "emotion_tracker-animated-avatar-floating_brain":
            return {"avatar_id": item_id, "name": "Floating Brain", "price": 5000, "type": "avatar"}
        
        # In a real app, you'd look up the avatar's price
        name = "User Avatar"  # Default name
        try:
            # Attempt to create a more descriptive name from the ID
            # e.g., "emotion_tracker-static-avatar-cat-1" -> "Cat 1"
            name_part = item_id.split("avatar-")[1]
            name = name_part.replace("-", " ").title()
        except IndexError:
            # If the ID format is not as expected, fall back to the default name
            pass
        return {"avatar_id": item_id, "name": name, "price": 100, "type": "avatar"}
    elif item_type == "bundle":
        bundles = {
            "emotion_tracker-avatars-cat-bundle": {"name": "Cat Lovers Pack", "price": 2000},
            "emotion_tracker-avatars-dog-bundle": {"name": "Dog Lovers Pack", "price": 2000},
            "emotion_tracker-avatars-panda-bundle": {"name": "Panda Lovers Pack", "price": 1500},
            "emotion_tracker-avatars-people-bundle": {"name": "People Pack", "price": 2000},
            "emotion_tracker-themes-dark": {"name": "Dark Theme Pack", "price": 2500},
            "emotion_tracker-themes-light": {"name": "Light Theme Pack", "price": 2500},
        }
        if item_id in bundles:
            bundle_info = bundles[item_id]
            return {"bundle_id": item_id, "name": bundle_info["name"], "price": bundle_info["price"], "type": "bundle"}
    elif item_type == "banner":
        if item_id == "emotion_tracker-static-banner-earth-1":
            return {"banner_id": item_id, "name": "Earth Banner", "price": 100, "type": "banner"}
        # Fallback for other banners
        return {"banner_id": item_id, "name": "User Banner", "price": 100, "type": "banner"}
    return None

# Utility to get or create a user's shop doc
async def get_or_create_shop_doc(username):
    shop_collection = db_manager.get_collection(SHOP_COLLECTION)
    doc = await shop_collection.find_one({"username": username})
    if not doc:
        doc = {"username": username, "carts": {}}
        await shop_collection.insert_one(doc)
    return doc

BUNDLE_CONTENTS = {
    "emotion_tracker-avatars-cat-bundle": {
        "avatars": [
            "emotion_tracker-static-avatar-cat-1",
            "emotion_tracker-static-avatar-cat-2",
            "emotion_tracker-static-avatar-cat-3",
            "emotion_tracker-static-avatar-cat-4",
            "emotion_tracker-static-avatar-cat-5",
            "emotion_tracker-static-avatar-cat-6",
            "emotion_tracker-static-avatar-cat-7",
            "emotion_tracker-static-avatar-cat-8",
            "emotion_tracker-static-avatar-cat-9",
            "emotion_tracker-static-avatar-cat-10",
            "emotion_tracker-static-avatar-cat-11",
            "emotion_tracker-static-avatar-cat-12",
            "emotion_tracker-static-avatar-cat-13",
            "emotion_tracker-static-avatar-cat-14",
            "emotion_tracker-static-avatar-cat-15",
            "emotion_tracker-static-avatar-cat-16",
            "emotion_tracker-static-avatar-cat-17",
            "emotion_tracker-static-avatar-cat-18",
            "emotion_tracker-static-avatar-cat-19",
            "emotion_tracker-static-avatar-cat-20",
        ]
    },
    "emotion_tracker-avatars-dog-bundle": {
        "avatars": [
            "emotion_tracker-static-avatar-dog-1",
            "emotion_tracker-static-avatar-dog-2",
            "emotion_tracker-static-avatar-dog-3",
            "emotion_tracker-static-avatar-dog-4",
            "emotion_tracker-static-avatar-dog-5",
            "emotion_tracker-static-avatar-dog-6",
            "emotion_tracker-static-avatar-dog-7",
            "emotion_tracker-static-avatar-dog-8",
            "emotion_tracker-static-avatar-dog-9",
            "emotion_tracker-static-avatar-dog-10",
            "emotion_tracker-static-avatar-dog-11",
            "emotion_tracker-static-avatar-dog-12",
            "emotion_tracker-static-avatar-dog-13",
            "emotion_tracker-static-avatar-dog-14",
            "emotion_tracker-static-avatar-dog-15",
            "emotion_tracker-static-avatar-dog-16",
            "emotion_tracker-static-avatar-dog-17",
        ]
    },
    "emotion_tracker-avatars-panda-bundle": {
        "avatars": [
            "emotion_tracker-static-avatar-panda-1",
            "emotion_tracker-static-avatar-panda-2",
            "emotion_tracker-static-avatar-panda-3",
            "emotion_tracker-static-avatar-panda-4",
            "emotion_tracker-static-avatar-panda-5",
            "emotion_tracker-static-avatar-panda-6",
            "emotion_tracker-static-avatar-panda-7",
            "emotion_tracker-static-avatar-panda-8",
            "emotion_tracker-static-avatar-panda-9",
            "emotion_tracker-static-avatar-panda-10",
            "emotion_tracker-static-avatar-panda-11",
            "emotion_tracker-static-avatar-panda-12",
        ]
    },
    "emotion_tracker-avatars-people-bundle": {
        "avatars": [
            "emotion_tracker-static-avatar-person-1",
            "emotion_tracker-static-avatar-person-2",
            "emotion_tracker-static-avatar-person-3",
            "emotion_tracker-static-avatar-person-4",
            "emotion_tracker-static-avatar-person-5",
            "emotion_tracker-static-avatar-person-6",
            "emotion_tracker-static-avatar-person-7",
            "emotion_tracker-static-avatar-person-8",
            "emotion_tracker-static-avatar-person-9",
            "emotion_tracker-static-avatar-person-10",
            "emotion_tracker-static-avatar-person-11",
            "emotion_tracker-static-avatar-person-12",
            "emotion_tracker-static-avatar-person-13",
            "emotion_tracker-static-avatar-person-14",
            "emotion_tracker-static-avatar-person-15",
            "emotion_tracker-static-avatar-person-16",
        ]
    },
    "emotion_tracker-themes-dark": {
        "themes": [
            "emotion_tracker-serenityGreenDark",
            "emotion_tracker-pacificBlueDark",
            "emotion_tracker-blushRoseDark",
            "emotion_tracker-cloudGrayDark",
            "emotion_tracker-sunsetPeachDark",
            "emotion_tracker-goldenYellowDark",
            "emotion_tracker-forestGreenDark",
            "emotion_tracker-midnightLavender",
            "emotion_tracker-crimsonRedDark",
            "emotion_tracker-deepPurpleDark",
            "emotion_tracker-royalOrangeDark",
        ]
    },
    "emotion_tracker-themes-light": {
        "themes": [
            "emotion_tracker-serenityGreen",
            "emotion_tracker-pacificBlue",
            "emotion_tracker-blushRose",
            "emotion_tracker-cloudGray",
            "emotion_tracker-sunsetPeach",
            "emotion_tracker-goldenYellow",
            "emotion_tracker-forestGreen",
            "emotion_tracker-midnightLavenderLight",
            "emotion_tracker-royalOrange",
            "emotion_tracker-crimsonRed",
            "emotion_tracker-deepPurple",
        ]
    },
}

@router.post("/shop/themes/buy", tags=["shop"], summary="Buy a theme with SBD tokens")
async def buy_theme(
    request: Request,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user_dep)
):
    users_collection = db_manager.get_collection("users")
    theme_id = data.get("theme_id")
    user_agent = request.headers.get("user-agent", "")
    username = current_user["username"]
    if not theme_id or not theme_id.startswith("emotion_tracker-"):
        return JSONResponse({"status": "error", "detail": "Invalid or missing theme_id"}, status_code=400)
    if "emotion_tracker" not in user_agent:
        return JSONResponse({"status": "error", "detail": "Shop access denied: invalid client"}, status_code=403)
    # Get theme details from server-side registry
    theme_details = await get_item_details(theme_id, "theme")
    if not theme_details:
        return JSONResponse({"status": "error", "detail": "Theme not found"}, status_code=404)
    price = theme_details["price"]
    # Check if user already owns the theme
    user = await users_collection.find_one({"username": username}, {"themes_owned": 1, "sbd_tokens": 1})
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    for owned in user.get("themes_owned", []):
        if owned["theme_id"] == theme_id:
            return JSONResponse({"status": "error", "detail": "Theme already owned"}, status_code=400)
    sbd_tokens = user.get("sbd_tokens", 0)
    if sbd_tokens < price:
        return JSONResponse({"status": "error", "detail": "Not enough SBD tokens"}, status_code=400)
    # Deduct tokens and add theme to owned
    now_iso = datetime.now(timezone.utc).isoformat()
    transaction_id = str(uuid4())
    theme_entry = {
        "theme_id": theme_id,
        "unlocked_at": now_iso,
        "permanent": True,
        "source": "purchase",
        "transaction_id": transaction_id,
        "note": "Bought from shop",
        "price": price
    }
    # Transaction log for user
    send_txn = {
        "type": "send",
        "to": "emotion_tracker_shop",
        "amount": price,
        "timestamp": now_iso,
        "transaction_id": transaction_id,
        "note": f"Bought theme {theme_id}"
    }
    # Transaction log for shop
    receive_txn = {
        "type": "receive",
        "from": username,
        "amount": price,
        "timestamp": now_iso,
        "transaction_id": transaction_id,
        "note": f"User bought theme {theme_id}"
    }
    # Atomically update user and shop
    try:
        # Deduct tokens and add theme to owned and log transaction
        result = await users_collection.update_one(
            {"username": username, "sbd_tokens": {"$gte": price}},
            {"$inc": {"sbd_tokens": -price},
             "$push": {"themes_owned": theme_entry, "sbd_tokens_transactions": send_txn}}
        )
        if result.modified_count == 0:
            return JSONResponse({"status": "error", "detail": "Insufficient SBD tokens or race condition"}, status_code=400)
        # Log the receive transaction for the shop (create shop user if not exists)
        await users_collection.update_one(
            {"username": "emotion_tracker_shop"},
            {"$push": {"sbd_tokens_transactions": receive_txn}},
            upsert=True
        )
        logger.info(f"[THEME PURCHASE] User: {username} bought {theme_id} for {price} SBD tokens (txn_id={transaction_id})")
        return {"status": "success", "theme": theme_entry}
    except Exception as e:
        logger.error(f"[THEME PURCHASE ERROR] {e}")
        return JSONResponse({"status": "error", "detail": "Internal server error", "error": str(e)}, status_code=500)

@router.post("/shop/avatars/buy", tags=["shop"], summary="Buy an avatar with SBD tokens")
async def buy_avatar(
    request: Request,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user_dep)
):
    users_collection = db_manager.get_collection("users")
    avatar_id = data.get("avatar_id")
    username = current_user["username"]
    if not avatar_id:
        return JSONResponse({"status": "error", "detail": "Invalid or missing avatar_id"}, status_code=400)
    # Get avatar details from server-side registry
    avatar_details = await get_item_details(avatar_id, "avatar")
    if not avatar_details:
        return JSONResponse({"status": "error", "detail": "Avatar not found"}, status_code=404)
    price = avatar_details["price"]
    # Check if user already owns the avatar
    user = await users_collection.find_one({"username": username}, {"avatars_owned": 1, "sbd_tokens": 1})
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    if any(owned.get("avatar_id") == avatar_id for owned in user.get("avatars_owned", [])):
        return JSONResponse({"status": "error", "detail": "Avatar already owned"}, status_code=400)
    sbd_tokens = user.get("sbd_tokens", 0)
    if sbd_tokens < price:
        return JSONResponse({"status": "error", "detail": "Not enough SBD tokens"}, status_code=400)
    # Deduct tokens and add avatar to owned
    now_iso = datetime.now(timezone.utc).isoformat()
    transaction_id = str(uuid4())
    avatar_entry = {
        "avatar_id": avatar_id,
        "unlocked_at": now_iso,
        "permanent": True,
        "source": "purchase",
        "transaction_id": transaction_id,
        "note": "Bought from shop",
        "price": price
    }
    try:
        logger.info(f"[AVATAR BUY] User: {username} attempting to buy avatar_id={avatar_id} for price={price}")
        send_txn = {
            "type": "send",
            "to": "emotion_tracker_shop",
            "amount": price,
            "timestamp": now_iso,
            "transaction_id": transaction_id,
            "note": f"Bought avatar {avatar_id}"
        }
        receive_txn = {
            "type": "receive",
            "from": username,
            "amount": price,
            "timestamp": now_iso,
            "transaction_id": transaction_id,
            "note": f"User bought avatar {avatar_id}"
        }
        result = await users_collection.update_one(
            {"username": username, "sbd_tokens": {"$gte": price}},
            {"$inc": {"sbd_tokens": -price}, "$push": {"avatars_owned": avatar_entry, "sbd_tokens_transactions": send_txn}}
        )
        logger.info(f"[AVATAR BUY] Update result for user {username}: modified_count={result.modified_count}")
        if result.modified_count == 0:
            logger.warning(f"[AVATAR BUY] Insufficient SBD tokens or race condition for user {username} buying avatar_id={avatar_id}")
            return JSONResponse({"status": "error", "detail": "Insufficient SBD tokens or race condition"}, status_code=400)
        await users_collection.update_one(
            {"username": "emotion_tracker_shop"},
            {"$push": {"sbd_tokens_transactions": receive_txn}},
            upsert=True
        )
        logger.info(f"[AVATAR BUY] User: {username} successfully bought avatar_id={avatar_id} (txn_id={transaction_id})")
        return {"status": "success", "avatar": avatar_entry}
    except Exception as e:
        logger.error(f"[AVATAR BUY ERROR] User: {username}, avatar_id={avatar_id}, error={e}")
        return JSONResponse({"status": "error", "detail": "Internal server error", "error": str(e)}, status_code=500)

@router.post("/shop/banners/buy", tags=["shop"], summary="Buy a banner with SBD tokens")
async def buy_banner(
    request: Request,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user_dep)
):
    users_collection = db_manager.get_collection("users")
    banner_id = data.get("banner_id")
    username = current_user["username"]
    if not banner_id:
        return JSONResponse({"status": "error", "detail": "Invalid or missing banner_id"}, status_code=400)
    # Get banner details from server-side registry
    banner_details = await get_item_details(banner_id, "banner")
    if not banner_details:
        return JSONResponse({"status": "error", "detail": "Banner not found"}, status_code=404)
    price = banner_details["price"]
    # Check if user already owns the banner
    user = await users_collection.find_one({"username": username}, {"banners_owned": 1, "sbd_tokens": 1})
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    if any(owned.get("banner_id") == banner_id for owned in user.get("banners_owned", [])):
        return JSONResponse({"status": "error", "detail": "Banner already owned"}, status_code=400)
    sbd_tokens = user.get("sbd_tokens", 0)
    if sbd_tokens < price:
        return JSONResponse({"status": "error", "detail": "Not enough SBD tokens"}, status_code=400)
    # Deduct tokens and add banner to owned
    now_iso = datetime.now(timezone.utc).isoformat()
    transaction_id = str(uuid4())
    banner_entry = {
        "banner_id": banner_id,
        "unlocked_at": now_iso,
        "permanent": True,
        "source": "purchase",
        "transaction_id": transaction_id,
        "note": "Bought from shop",
        "price": price
    }
    try:
        logger.info(f"[BANNER BUY] User: {username} attempting to buy banner_id={banner_id} for price={price}")
        send_txn = {
            "type": "send",
            "to": "emotion_tracker_shop",
            "amount": price,
            "timestamp": now_iso,
            "transaction_id": transaction_id,
            "note": f"Bought banner {banner_id}"
        }
        receive_txn = {
            "type": "receive",
            "from": username,
            "amount": price,
            "timestamp": now_iso,
            "transaction_id": transaction_id,
            "note": f"User bought banner {banner_id}"
        }
        result = await users_collection.update_one(
            {"username": username, "sbd_tokens": {"$gte": price}},
            {"$inc": {"sbd_tokens": -price}, "$push": {"banners_owned": banner_entry, "sbd_tokens_transactions": send_txn}}
        )
        logger.info(f"[BANNER BUY] Update result for user {username}: modified_count={result.modified_count}")
        if result.modified_count == 0:
            logger.warning(f"[BANNER BUY] Insufficient SBD tokens or race condition for user {username} buying banner_id={banner_id}")
            return JSONResponse({"status": "error", "detail": "Insufficient SBD tokens or race condition"}, status_code=400)
        await users_collection.update_one(
            {"username": "emotion_tracker_shop"},
            {"$push": {"sbd_tokens_transactions": receive_txn}},
            upsert=True
        )
        logger.info(f"[BANNER BUY] User: {username} successfully bought banner_id={banner_id} (txn_id={transaction_id})")
        return {"status": "success", "banner": banner_entry}
    except Exception as e:
        logger.error(f"[BANNER BUY ERROR] User: {username}, banner_id={banner_id}, error={e}")
        return JSONResponse({"status": "error", "detail": "Internal server error", "error": str(e)}, status_code=500)

@router.post("/shop/bundles/buy", tags=["shop"], summary="Buy a bundle with SBD tokens")
async def buy_bundle(
    request: Request,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user_dep)
):
    users_collection = db_manager.get_collection("users")
    bundle_id = data.get("bundle_id")
    username = current_user["username"]
    if not bundle_id:
        return JSONResponse({"status": "error", "detail": "Invalid or missing bundle_id"}, status_code=400)
    # Get bundle details from server-side registry
    bundle_details = await get_item_details(bundle_id, "bundle")
    if not bundle_details:
        return JSONResponse({"status": "error", "detail": "Bundle not found"}, status_code=404)
    price = bundle_details["price"]
    # Check if user already owns the bundle
    user = await users_collection.find_one({"username": username}, {"bundles_owned": 1, "avatars_owned": 1, "themes_owned": 1, "banners_owned": 1, "sbd_tokens": 1})
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    if bundle_id in user.get("bundles_owned", []):
        return JSONResponse({"status": "error", "detail": "Bundle already owned"}, status_code=400)
    sbd_tokens = user.get("sbd_tokens", 0)
    if sbd_tokens < price:
        return JSONResponse({"status": "error", "detail": "Not enough SBD tokens"}, status_code=400)
    # Deduct tokens and add bundle to owned
    now_iso = datetime.now(timezone.utc).isoformat()
    transaction_id = str(uuid4())
    bundle_entry = {
        "bundle_id": bundle_id,
        "unlocked_at": now_iso,
        "permanent": True,
        "source": "purchase",
        "transaction_id": transaction_id,
        "note": "Bought from shop",
        "price": price
    }
    try:
        result = await users_collection.update_one(
            {"username": username, "sbd_tokens": {"$gte": price}},
            {"$inc": {"sbd_tokens": -price}, "$push": {"bundles_owned": bundle_entry}}
        )
        if result.modified_count == 0:
            return JSONResponse({"status": "error", "detail": "Insufficient SBD tokens or race condition"}, status_code=400)
        # --- Auto-populate bundle contents ---
        bundle_contents = BUNDLE_CONTENTS.get(bundle_id, {})
        update_ops = {}
        # Add avatars from bundle
        for avatar_id in bundle_contents.get("avatars", []):
            if not any(owned.get("avatar_id") == avatar_id for owned in user.get("avatars_owned", [])):
                avatar_entry = {
                    "avatar_id": avatar_id,
                    "unlocked_at": now_iso,
                    "permanent": True,
                    "source": f"bundle:{bundle_id}",
                    "transaction_id": transaction_id,
                    "note": f"Unlocked via bundle {bundle_id}",
                    "price": 0
                }
                update_ops.setdefault("avatars_owned", []).append(avatar_entry)
        # Add themes from bundle
        for theme_id in bundle_contents.get("themes", []):
            if not any(owned.get("theme_id") == theme_id for owned in user.get("themes_owned", [])):
                theme_entry = {
                    "theme_id": theme_id,
                    "unlocked_at": now_iso,
                    "permanent": True,
                    "source": f"bundle:{bundle_id}",
                    "transaction_id": transaction_id,
                    "note": f"Unlocked via bundle {bundle_id}",
                    "price": 0
                }
                update_ops.setdefault("themes_owned", []).append(theme_entry)
        # Add banners from bundle (if you have such bundles)
        for banner_id in bundle_contents.get("banners", []):
            if not any(owned.get("banner_id") == banner_id for owned in user.get("banners_owned", [])):
                banner_entry = {
                    "banner_id": banner_id,
                    "unlocked_at": now_iso,
                    "permanent": True,
                    "source": f"bundle:{bundle_id}",
                    "transaction_id": transaction_id,
                    "note": f"Unlocked via bundle {bundle_id}",
                    "price": 0
                }
                update_ops.setdefault("banners_owned", []).append(banner_entry)
        # Perform the update for each owned type
        for field, entries in update_ops.items():
            await users_collection.update_one(
                {"username": username},
                {"$push": {field: {"$each": entries}}}
            )
        return {"status": "success", "bundle": bundle_entry, "unlocked_items": update_ops}
    except Exception as e:
        return JSONResponse({"status": "error", "detail": "Internal server error", "error": str(e)}, status_code=500)

@router.post("/shop/cart/add", tags=["shop"], summary="Add an item to the cart by ID")
async def add_to_cart(request: Request, data: dict = Body(...), current_user: dict = Depends(get_current_user_dep)):
    shop_collection = db_manager.get_collection(SHOP_COLLECTION)
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    item_id = data.get("item_id")
    item_type = data.get("item_type") # "theme", "avatar", "bundle", "banner"
    user_agent = request.headers.get("user-agent", "unknown").lower()
    app_name = user_agent.split('/')[0].strip() if '/' in user_agent else user_agent

    if not all([item_id, item_type]):
        return JSONResponse({"status": "error", "detail": "Missing item_id or item_type"}, status_code=400)

    # Check if user already owns the item
    user = await users_collection.find_one({"username": username})
    owned_field = f"{item_type}s_owned"
    id_key = f"{item_type}_id"
    if any(owned_item.get(id_key) == item_id for owned_item in user.get(owned_field, [])):
        return JSONResponse({"status": "error", "detail": "You already own this item."}, status_code=400)

    # Get item details securely from the server-side registry
    item_details = await get_item_details(item_id, item_type)
    if not item_details:
        return JSONResponse({"status": "error", "detail": "Item not found"}, status_code=404)

    item_details["added_at"] = datetime.now(timezone.utc).isoformat()

    await get_or_create_shop_doc(username)
    # Use $addToSet to prevent duplicate items in the cart
    await shop_collection.update_one(
        {"username": username},
        {"$addToSet": {f"carts.{app_name}": item_details}}
    )
    return {"status": "success", "added": item_details, "app": app_name}

@router.delete("/shop/cart/remove", tags=["shop"], summary="Remove item from a cart")
async def remove_from_cart(request: Request, data: dict = Body(...), current_user: dict = Depends(get_current_user_dep)):
    shop_collection = db_manager.get_collection(SHOP_COLLECTION)
    username = current_user["username"]
    item_id = data.get("item_id")
    item_type = data.get("item_type")
    user_agent = request.headers.get("user-agent", "").lower()
    app_name = user_agent.split('/')[0].strip() if user_agent and '/' in user_agent else user_agent

    if not all([item_id, item_type, app_name]):
        return JSONResponse({"status": "error", "detail": "Missing item_id, item_type, or a valid user-agent header"}, status_code=400)

    # Normalize item_type to be singular for key construction
    if item_type.endswith('s'):
        item_type = item_type[:-1]

    id_key = f"{item_type}_id"
    item_to_remove = {id_key: item_id}
    
    # Remove from a specific app's cart
    result = await shop_collection.update_one(
        {"username": username},
        {"$pull": {f"carts.{app_name}": item_to_remove}}
    )
    if result.modified_count > 0:
        return {"status": "success", "removed_id": item_id, "app": app_name}
    else:
        return JSONResponse({"status": "error", "detail": f"Item not found in cart for app '{app_name}'"}, status_code=404)

@router.delete("/shop/cart/clear", tags=["shop"], summary="Clear all items from a cart")
async def clear_cart(request: Request, current_user: dict = Depends(get_current_user_dep)):
    """
    Clears items from a user's shopping cart for a specific app, identified by user-agent.
    """
    shop_collection = db_manager.get_collection(SHOP_COLLECTION)
    username = current_user["username"]
    user_agent = request.headers.get("user-agent", "").lower()
    app_name = user_agent.split('/')[0].strip() if user_agent and '/' in user_agent else user_agent

    if not app_name:
        return JSONResponse({"status": "error", "detail": "The 'user-agent' header is required and must be in a valid format."}, status_code=400)

    # Clear a specific app's cart
    result = await shop_collection.update_one(
        {"username": username, f"carts.{app_name}": {"$exists": True}},
        {"$set": {f"carts.{app_name}": []}}
    )
    if result.modified_count > 0:
        return {"status": "success", "detail": f"Cart for app '{app_name}' has been cleared."}
    else:
        # This can mean the cart didn't exist or was already empty.
        return {"status": "success", "detail": f"Cart for app '{app_name}' is now empty."}

@router.get("/shop/cart", tags=["shop"], summary="Get a specific app cart")
async def get_cart(request: Request, current_user: dict = Depends(get_current_user_dep)):
    shop_collection = db_manager.get_collection(SHOP_COLLECTION)
    username = current_user["username"]
    user_agent = request.headers.get("user-agent", "").lower()
    app_name = user_agent.split('/')[0].strip() if user_agent and '/' in user_agent else user_agent

    if not app_name:
        return JSONResponse({"status": "error", "detail": "The 'user-agent' header is required and must be in a valid format."}, status_code=400)
        
    doc = await get_or_create_shop_doc(username)
    carts = doc.get("carts", {})

    # Return a specific app's cart
    cart = carts.get(app_name, [])
    return {"status": "success", "app": app_name, "cart": cart}

@router.post("/shop/cart/checkout", tags=["shop"], summary="Checkout a specific app cart")
async def checkout_cart(request: Request, current_user: dict = Depends(get_current_user_dep)):
    shop_collection = db_manager.get_collection(SHOP_COLLECTION)
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    
    user_agent = request.headers.get("user-agent", "").lower()
    app_name = user_agent.split('/')[0].strip() if user_agent and '/' in user_agent else user_agent
    if not app_name:
        return JSONResponse({"status": "error", "detail": "The 'user-agent' header is required and must be in a valid format."}, status_code=400)

    doc = await get_or_create_shop_doc(username)
    carts = doc.get("carts", {})
    
    items_to_checkout = carts.get(app_name, [])
    if not items_to_checkout:
        return JSONResponse({"status": "error", "detail": f"Cart for app '{app_name}' not found or is empty."}, status_code=404)

    # Calculate total price from server-side details
    total_price = sum(item.get("price", 0) for item in items_to_checkout)
    
    # Check user's token balance
    user = await users_collection.find_one({"username": username}, {"sbd_tokens": 1})
    if not user or user.get("sbd_tokens", 0) < total_price:
        return JSONResponse({"status": "error", "detail": "Not enough SBD tokens"}, status_code=400)

    # Atomically deduct tokens and log transaction
    now_iso = datetime.now(timezone.utc).isoformat()
    transaction_id = str(uuid4())
    shop_name = f"{app_name}_shop"
    
    result = await users_collection.update_one(
        {"username": username, "sbd_tokens": {"$gte": total_price}},
        {"$inc": {"sbd_tokens": -total_price},
         "$push": {"sbd_tokens_transactions": {
             "type": "send", "to": shop_name, "amount": total_price,
             "timestamp": now_iso, "transaction_id": transaction_id,
             "note": f"Checkout cart for {shop_name}"
         }}}
    )
    if result.modified_count == 0:
        return JSONResponse({"status": "error", "detail": "Insufficient SBD tokens or race condition"}, status_code=400)

    # Log receive transaction for the shop
    await users_collection.update_one(
        {"username": shop_name},
        {"$push": {"sbd_tokens_transactions": {
            "type": "receive", "from": username, "amount": total_price,
            "timestamp": now_iso, "transaction_id": transaction_id,
            "note": f"User checked out cart for {shop_name}"
        }}},
        upsert=True
    )

    # Distribute purchased items to the correct `*_owned` arrays
    update_operations = {}
    now_iso_checkout = datetime.now(timezone.utc).isoformat()

    for item in items_to_checkout:
        item_type = item.get("type")
        if not item_type:
            continue

        id_key = f"{item_type}_id"
        owned_field = f"{item_type}s_owned"

        owned_item_entry = {
            id_key: item.get(id_key),
            "unlocked_at": now_iso_checkout,
            "permanent": True,
            "source": "purchase_cart",
            "transaction_id": transaction_id,
            "note": f"Purchased via cart checkout from {app_name}",
            "price": item.get("price")
        }

        if owned_field not in update_operations:
            update_operations[owned_field] = {"$each": []}
        
        update_operations[owned_field]["$each"].append(owned_item_entry)

    # Perform all updates in a single operation if possible, or one per type
    for owned_field, push_value in update_operations.items():
        await users_collection.update_one(
            {"username": username},
            {"$push": {owned_field: push_value}}
        )

    # Clear the relevant cart(s)
    await shop_collection.update_one({"username": username}, {"$set": {f"carts.{app_name}": []}})

    return {"status": "success", "checked_out": items_to_checkout, "total_price": total_price, "transaction_id": transaction_id}

@router.get("/shop/avatars/owned", tags=["shop"], summary="Get user's owned avatars")
async def get_owned_avatars(current_user: dict = Depends(get_current_user_dep)):
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user = await users_collection.find_one({"username": username}, {"avatars_owned": 1, "_id": 0})
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    return {"status": "success", "avatars_owned": user.get("avatars_owned", [])}

@router.get("/shop/banners/owned", tags=["shop"], summary="Get user's owned banners")
async def get_owned_banners(current_user: dict = Depends(get_current_user_dep)):
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user = await users_collection.find_one({"username": username}, {"banners_owned": 1, "_id": 0})
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    return {"status": "success", "banners_owned": user.get("banners_owned", [])}

@router.get("/shop/bundles/owned", tags=["shop"], summary="Get user's owned bundles")
async def get_owned_bundles(current_user: dict = Depends(get_current_user_dep)):
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user = await users_collection.find_one({"username": username}, {"bundles_owned": 1, "_id": 0})
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    return {"status": "success", "bundles_owned": user.get("bundles_owned", [])}

@router.get("/shop/themes/owned", tags=["shop"], summary="Get user's owned themes")
async def get_owned_themes(current_user: dict = Depends(get_current_user_dep)):
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user = await users_collection.find_one({"username": username}, {"themes_owned": 1, "_id": 0})
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    return {"status": "success", "themes_owned": user.get("themes_owned", [])}

@router.get("/shop/owned", tags=["shop"], summary="Get all user's owned shop items")
async def get_all_owned(current_user: dict = Depends(get_current_user_dep)):
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user = await users_collection.find_one({"username": username}, {
        "avatars_owned": 1,
        "banners_owned": 1,
        "bundles_owned": 1,
        "themes_owned": 1,
        "_id": 0
    })
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    return {
        "status": "success",
        "avatars_owned": user.get("avatars_owned", []),
        "banners_owned": user.get("banners_owned", []),
        "bundles_owned": user.get("bundles_owned", []),
        "themes_owned": user.get("themes_owned", [])
    }
