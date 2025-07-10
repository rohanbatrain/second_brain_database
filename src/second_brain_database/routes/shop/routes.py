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
        # In a real app, you'd look up the avatar's price
        return {"avatar_id": item_id, "name": "User Avatar", "price": 100, "type": "avatar"}
    elif item_type == "bundle":
        # In a real app, you'd look up the bundle's price
        return {"bundle_id": item_id, "name": "Item Bundle", "price": 500, "type": "bundle"}
    elif item_type == "banner":
        # In a real app, you'd look up the banner's price
        return {"banner_id": item_id, "name": "User Banner", "price": 150, "type": "banner"}
    return None

# Utility to get or create a user's shop doc
async def get_or_create_shop_doc(username):
    shop_collection = db_manager.get_collection(SHOP_COLLECTION)
    doc = await shop_collection.find_one({"username": username})
    if not doc:
        doc = {"username": username, "carts": {}}
        await shop_collection.insert_one(doc)
    return doc

@router.post("/shop/themes/buy", tags=["shop"], summary="Buy a theme with SBD tokens")
async def buy_theme(
    request: Request,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user_dep)
):
    users_collection = db_manager.get_collection("users")
    theme_id = data.get("theme_id")
    price = data.get("price", 250)  # Default price is now 250 if not provided
    user_agent = request.headers.get("user-agent", "")
    username = current_user["username"]
    if not theme_id or not theme_id.startswith("emotion_tracker-"):
        return JSONResponse({"status": "error", "detail": "Invalid or missing theme_id"}, status_code=400)
    if "emotion_tracker" not in user_agent:
        return JSONResponse({"status": "error", "detail": "Shop access denied: invalid client"}, status_code=403)
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
        return {"status": "success", "theme": theme_entry, "transaction_id": transaction_id}
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
    price = data.get("price", 100)  # Default price is 100 if not provided
    username = current_user["username"]
    if not avatar_id:
        return JSONResponse({"status": "error", "detail": "Invalid or missing avatar_id"}, status_code=400)
    # Check if user already owns the avatar
    user = await users_collection.find_one({"username": username}, {"avatars_owned": 1, "sbd_tokens": 1})
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    if avatar_id in user.get("avatars_owned", []):
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
        result = await users_collection.update_one(
            {"username": username, "sbd_tokens": {"$gte": price}},
            {"$inc": {"sbd_tokens": -price}, "$push": {"avatars_owned": avatar_entry}}
        )
        if result.modified_count == 0:
            return JSONResponse({"status": "error", "detail": "Insufficient SBD tokens or race condition"}, status_code=400)
        return {"status": "success", "avatar": avatar_entry, "transaction_id": transaction_id}
    except Exception as e:
        return JSONResponse({"status": "error", "detail": "Internal server error", "error": str(e)}, status_code=500)

@router.post("/shop/bundles/buy", tags=["shop"], summary="Buy a bundle with SBD tokens")
async def buy_bundle(
    request: Request,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user_dep)
):
    users_collection = db_manager.get_collection("users")
    bundle_id = data.get("bundle_id")
    price = data.get("price", 500)  # Default price is 500 if not provided
    username = current_user["username"]
    if not bundle_id:
        return JSONResponse({"status": "error", "detail": "Invalid or missing bundle_id"}, status_code=400)
    # Check if user already owns the bundle
    user = await users_collection.find_one({"username": username}, {"bundles_owned": 1, "sbd_tokens": 1})
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
        return {"status": "success", "bundle": bundle_entry, "transaction_id": transaction_id}
    except Exception as e:
        return JSONResponse({"status": "error", "detail": "Internal server error", "error": str(e)}, status_code=500)

@router.post("/shop/cart/add", tags=["shop"], summary="Add an item to the cart by ID")
async def add_to_cart(request: Request, data: dict = Body(...), current_user: dict = Depends(get_current_user_dep)):
    shop_collection = db_manager.get_collection(SHOP_COLLECTION)
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    item_id = data.get("item_id")
    item_type = data.get("item_type") # "theme", "avatar", "bundle", "banner"
    user_agent = request.headers.get("user-agent", "unknown")
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

    await get_or_create_shop_doc(username)
    # Use $addToSet to prevent duplicate items in the cart
    await shop_collection.update_one(
        {"username": username},
        {"$addToSet": {f"carts.{app_name}": item_details}}
    )
    return {"status": "success", "added": item_details, "app": app_name}

@router.post("/shop/cart/remove", tags=["shop"], summary="Remove item from a cart")
async def remove_from_cart(request: Request, data: dict = Body(...), current_user: dict = Depends(get_current_user_dep)):
    shop_collection = db_manager.get_collection(SHOP_COLLECTION)
    username = current_user["username"]
    item_id = data.get("item_id")
    item_type = data.get("item_type")
    user_agent = request.headers.get("user-agent")
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

@router.post("/shop/cart/clear", tags=["shop"], summary="Clear all items from a cart")
async def clear_cart(request: Request, current_user: dict = Depends(get_current_user_dep)):
    """
    Clears items from a user's shopping cart for a specific app, identified by user-agent.
    """
    shop_collection = db_manager.get_collection(SHOP_COLLECTION)
    username = current_user["username"]
    user_agent = request.headers.get("user-agent")
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
    user_agent = request.headers.get("user-agent")
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
    
    user_agent = request.headers.get("user-agent")
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
    items_by_type = {}
    for item in items_to_checkout:
        item_type = item.get("type")
        if item_type:
            if item_type not in items_by_type:
                items_by_type[item_type] = []
            items_by_type[item_type].append(item)

    for item_type, items in items_by_type.items():
        owned_field = f"{item_type}s_owned" # e.g., themes_owned, avatars_owned
        await users_collection.update_one(
            {"username": username},
            {"$push": {owned_field: {"$each": items}}}
        )

    # Clear the relevant cart(s)
    await shop_collection.update_one({"username": username}, {"$set": {f"carts.{app_name}": []}})

    return {"status": "success", "checked_out": items_to_checkout, "total_price": total_price, "transaction_id": transaction_id}
