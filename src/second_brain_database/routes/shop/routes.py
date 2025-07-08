from fastapi import APIRouter, Request, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from second_brain_database.database import db_manager
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.routes import get_current_user_dep
from datetime import datetime, timezone
from uuid import uuid4

logger = get_logger(prefix="[SHOP]")

router = APIRouter()

SHOP_COLLECTION = "shop"

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

@router.post("/shop/cart/{app}/add", tags=["shop"], summary="Add item to app-specific cart")
async def add_to_cart(app: str, data: dict = Body(...), current_user: dict = Depends(get_current_user_dep)):
    shop_collection = db_manager.get_collection(SHOP_COLLECTION)
    username = current_user["username"]
    item = data.get("item")
    if not item:
        return JSONResponse({"status": "error", "detail": "Missing item"}, status_code=400)
    await get_or_create_shop_doc(username)
    update_result = await shop_collection.update_one(
        {"username": username},
        {"$addToSet": {f"carts.{app}": item}}
    )
    return {"status": "success", "added": item, "app": app}

@router.post("/shop/cart/{app}/remove", tags=["shop"], summary="Remove item from app-specific cart")
async def remove_from_cart(app: str, data: dict = Body(...), current_user: dict = Depends(get_current_user_dep)):
    shop_collection = db_manager.get_collection(SHOP_COLLECTION)
    username = current_user["username"]
    item = data.get("item")
    if not item:
        return JSONResponse({"status": "error", "detail": "Missing item"}, status_code=400)
    await get_or_create_shop_doc(username)
    update_result = await shop_collection.update_one(
        {"username": username},
        {"$pull": {f"carts.{app}": item}}
    )
    return {"status": "success", "removed": item, "app": app}

@router.get("/shop/cart/{app}", tags=["shop"], summary="Get app-specific cart")
async def get_app_cart(app: str, current_user: dict = Depends(get_current_user_dep)):
    shop_collection = db_manager.get_collection(SHOP_COLLECTION)
    username = current_user["username"]
    doc = await get_or_create_shop_doc(username)
    cart = doc.get("carts", {}).get(app, [])
    return {"status": "success", "cart": cart, "app": app}

@router.get("/shop/cart/master", tags=["shop"], summary="Get master cart (all app carts combined)")
async def get_master_cart(current_user: dict = Depends(get_current_user_dep)):
    shop_collection = db_manager.get_collection(SHOP_COLLECTION)
    username = current_user["username"]
    doc = await get_or_create_shop_doc(username)
    carts = doc.get("carts", {})
    master_cart = []
    for items in carts.values():
        master_cart.extend(items)
    return {"status": "success", "master_cart": master_cart}

@router.post("/shop/cart/{app}/checkout", tags=["shop"], summary="Checkout an app-specific cart with SBD tokens")
async def checkout_app_cart(app: str, current_user: dict = Depends(get_current_user_dep)):
    shop_collection = db_manager.get_collection(SHOP_COLLECTION)
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    doc = await get_or_create_shop_doc(username)
    cart = doc.get("carts", {}).get(app, [])
    if not cart:
        return JSONResponse({"status": "error", "detail": "Cart is empty"}, status_code=400)
    # Calculate total price
    total_price = sum(item.get("price", 0) for item in cart)
    user = await users_collection.find_one({"username": username}, {"sbd_tokens": 1})
    sbd_tokens = user.get("sbd_tokens", 0) if user else 0
    if sbd_tokens < total_price:
        return JSONResponse({"status": "error", "detail": "Not enough SBD tokens"}, status_code=400)
    now_iso = datetime.now(timezone.utc).isoformat()
    transaction_id = str(uuid4())
    # Deduct tokens and log transaction
    result = await users_collection.update_one(
        {"username": username, "sbd_tokens": {"$gte": total_price}},
        {"$inc": {"sbd_tokens": -total_price},
         "$push": {"sbd_tokens_transactions": {
             "type": "send",
             "to": f"{app}_shop",
             "amount": total_price,
             "timestamp": now_iso,
             "transaction_id": transaction_id,
             "note": f"Checkout cart for {app}"
         }}}
    )
    if result.modified_count == 0:
        return JSONResponse({"status": "error", "detail": "Insufficient SBD tokens or race condition"}, status_code=400)
    # Log receive transaction for shop
    await users_collection.update_one(
        {"username": f"{app}_shop"},
        {"$push": {"sbd_tokens_transactions": {
            "type": "receive",
            "from": username,
            "amount": total_price,
            "timestamp": now_iso,
            "transaction_id": transaction_id,
            "note": f"User checked out cart for {app}"
        }}},
        upsert=True
    )
    # Move items to user's purchased/themes_owned (example: themes)
    if app == "emotion_tracker":
        await users_collection.update_one(
            {"username": username},
            {"$push": {"themes_owned": {"$each": cart}}}
        )
    # Clear the cart
    await shop_collection.update_one(
        {"username": username},
        {"$set": {f"carts.{app}": []}}
    )
    return {"status": "success", "checked_out": cart, "total_price": total_price, "transaction_id": transaction_id}

@router.post("/shop/cart/master/checkout", tags=["shop"], summary="Checkout the master cart (all app carts) with SBD tokens")
async def checkout_master_cart(current_user: dict = Depends(get_current_user_dep)):
    shop_collection = db_manager.get_collection(SHOP_COLLECTION)
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    doc = await get_or_create_shop_doc(username)
    carts = doc.get("carts", {})
    all_items = []
    for items in carts.values():
        all_items.extend(items)
    if not all_items:
        return JSONResponse({"status": "error", "detail": "Master cart is empty"}, status_code=400)
    total_price = sum(item.get("price", 0) for item in all_items)
    user = await users_collection.find_one({"username": username}, {"sbd_tokens": 1})
    sbd_tokens = user.get("sbd_tokens", 0) if user else 0
    if sbd_tokens < total_price:
        return JSONResponse({"status": "error", "detail": "Not enough SBD tokens"}, status_code=400)
    now_iso = datetime.now(timezone.utc).isoformat()
    transaction_id = str(uuid4())
    # Deduct tokens and log transaction
    result = await users_collection.update_one(
        {"username": username, "sbd_tokens": {"$gte": total_price}},
        {"$inc": {"sbd_tokens": -total_price},
         "$push": {"sbd_tokens_transactions": {
             "type": "send",
             "to": "master_shop",
             "amount": total_price,
             "timestamp": now_iso,
             "transaction_id": transaction_id,
             "note": "Checkout master cart"
         }}}
    )
    if result.modified_count == 0:
        return JSONResponse({"status": "error", "detail": "Insufficient SBD tokens or race condition"}, status_code=400)
    # Log receive transaction for shop
    await users_collection.update_one(
        {"username": "master_shop"},
        {"$push": {"sbd_tokens_transactions": {
            "type": "receive",
            "from": username,
            "amount": total_price,
            "timestamp": now_iso,
            "transaction_id": transaction_id,
            "note": "User checked out master cart"
        }}},
        upsert=True
    )
    # Move items to user's purchased/themes_owned (example: themes)
    # This example only moves emotion_tracker items to themes_owned
    emotion_tracker_items = [item for item in all_items if item.get("theme_id", "").startswith("emotion_tracker-")]
    if emotion_tracker_items:
        await users_collection.update_one(
            {"username": username},
            {"$push": {"themes_owned": {"$each": emotion_tracker_items}}}
        )
    # Clear all carts
    await shop_collection.update_one(
        {"username": username},
        {"$set": {f"carts": {}}}
    )
    return {"status": "success", "checked_out": all_items, "total_price": total_price, "transaction_id": transaction_id}
