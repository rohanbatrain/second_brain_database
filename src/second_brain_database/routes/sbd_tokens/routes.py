from fastapi import APIRouter, Request, Body, Query, Depends
from fastapi.responses import JSONResponse
from second_brain_database.database import db_manager
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.routes import get_current_user_dep
from pymongo.errors import PyMongoError
from datetime import datetime, timezone
from uuid import uuid4

logger = get_logger(prefix="[SBD TOKENS]")

router = APIRouter()

@router.get("/sbd_tokens")
async def get_my_sbd_tokens(
    request: Request = None,
    current_user: dict = Depends(get_current_user_dep)
):
    await security_manager.check_rate_limit(request, f"sbd_tokens_read_{current_user['username']}", rate_limit_requests=10, rate_limit_period=60)
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user = await users_collection.find_one({"username": username}, {"sbd_tokens": 1, "_id": 0})
    if not user:
        logger.warning("[SBD TOKENS READ] User not found: %s", username)
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    logger.info("[SBD TOKENS READ] User: %s, Tokens: %s", username, user.get('sbd_tokens', 0))
    return {"username": username, "sbd_tokens": user.get("sbd_tokens", 0)}

@router.post("/sbd_tokens/send")
async def send_sbd_tokens(
    request: Request,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user_dep)
):
    from_user = current_user["username"]
    to_user = data.get("to_user")
    amount = data.get("amount")
    note = data.get("note")
    transaction_id = str(data.get("transaction_id") or uuid4())
    if not to_user or amount is None:
        logger.warning("[SBD TOKENS SEND] Missing fields: %s", data)
        return JSONResponse({"status": "error", "detail": "Missing required fields"}, status_code=400)
    if not isinstance(amount, int) or amount <= 0:
        logger.warning("[SBD TOKENS SEND] Invalid amount: %s", amount)
        return JSONResponse({"status": "error", "detail": "Amount must be a positive integer"}, status_code=400)
    users_collection = db_manager.get_collection("users")
    is_replica_set = False
    try:
        # Check if MongoDB is a replica set
        ismaster = await db_manager.client.admin.command("ismaster")
        is_replica_set = bool(ismaster.get("setName"))
    except Exception as e:
        logger.warning("[SBD TOKENS SEND] Could not determine replica set: %s", e)
    try:
        if is_replica_set:
            # Use transaction/session if replica set
            async with await db_manager.client.start_session() as session:
                async with session.start_transaction():
                    from_user_doc = await users_collection.find_one({"username": from_user}, session=session)
                    to_user_doc = await users_collection.find_one({"username": to_user}, session=session)
                    # If recipient does not exist, create them with 0 tokens and empty transactions
                    if not to_user_doc:
                        await users_collection.insert_one({
                            "username": to_user,
                            "sbd_tokens": 0,
                            "sbd_tokens_transactions": [],
                            "email": f"{to_user}@rohanbatra.in"
                        }, session=session)
                        to_user_doc = await users_collection.find_one({"username": to_user}, session=session)
                    if not from_user_doc:
                        logger.warning("[SBD TOKENS SEND] Sender not found: %s", from_user)
                        return JSONResponse({"status": "error", "detail": "Transaction could not be completed. Please check the details and try again."}, status_code=400)
                    now_iso = datetime.now(timezone.utc).isoformat()
                    send_txn = {
                        "type": "send",
                        "to": to_user,
                        "amount": amount,
                        "timestamp": now_iso,
                        "transaction_id": transaction_id
                    }
                    if note:
                        send_txn["note"] = note
                    res1 = await users_collection.update_one(
                        {"username": from_user, "sbd_tokens": {"$gte": amount}},
                        {"$inc": {"sbd_tokens": -amount},
                         "$push": {"sbd_tokens_transactions": send_txn}},
                        session=session
                    )
                    if res1.modified_count == 0:
                        logger.warning("[SBD TOKENS SEND] Race condition: insufficient tokens for %s", from_user)
                        return JSONResponse({"status": "error", "detail": "Insufficient sbd_tokens (race)"}, status_code=400)
                    receive_txn = {
                        "type": "receive",
                        "from": from_user,
                        "amount": amount,
                        "timestamp": now_iso,
                        "transaction_id": transaction_id
                    }
                    if note:
                        receive_txn["note"] = note
                    await users_collection.update_one(
                        {"username": to_user},
                        {"$inc": {"sbd_tokens": amount},
                         "$push": {"sbd_tokens_transactions": receive_txn}},
                        session=session
                    )
                    logger.info("[SBD TOKENS SEND] %s tokens sent from %s to %s (txn_id=%s)", amount, from_user, to_user, transaction_id)
        else:
            # Fallback: no transaction/session
            from_user_doc = await users_collection.find_one({"username": from_user})
            to_user_doc = await users_collection.find_one({"username": to_user})
            # If recipient does not exist, create them with 0 tokens and empty transactions
            if not to_user_doc:
                await users_collection.insert_one({
                    "username": to_user,
                    "sbd_tokens": 0,
                    "sbd_tokens_transactions": [],
                    "email": f"{to_user}@rohanbatra.in"
                })
                to_user_doc = await users_collection.find_one({"username": to_user})
            if not from_user_doc:
                logger.warning("[SBD TOKENS SEND] Sender not found: %s", from_user)
                return JSONResponse({"status": "error", "detail": "Transaction could not be completed. Please check the details and try again."}, status_code=400)
            now_iso = datetime.now(timezone.utc).isoformat()
            send_txn = {
                "type": "send",
                "to": to_user,
                "amount": amount,
                "timestamp": now_iso,
                "transaction_id": transaction_id
            }
            if note:
                send_txn["note"] = note
            res1 = await users_collection.update_one(
                {"username": from_user, "sbd_tokens": {"$gte": amount}},
                {"$inc": {"sbd_tokens": -amount},
                 "$push": {"sbd_tokens_transactions": send_txn}}
            )
            if res1.modified_count == 0:
                logger.warning("[SBD TOKENS SEND] Race condition: insufficient tokens for %s", from_user)
                return JSONResponse({"status": "error", "detail": "Insufficient sbd_tokens (race)"}, status_code=400)
            receive_txn = {
                "type": "receive",
                "from": from_user,
                "amount": amount,
                "timestamp": now_iso,
                "transaction_id": transaction_id
            }
            if note:
                receive_txn["note"] = note
            await users_collection.update_one(
                {"username": to_user},
                {"$inc": {"sbd_tokens": amount},
                 "$push": {"sbd_tokens_transactions": receive_txn}}
            )
            logger.info("[SBD TOKENS SEND] %s tokens sent from %s to %s (txn_id=%s)", amount, from_user, to_user, transaction_id)
        return {"status": "success", "from_user": from_user, "to_user": to_user, "amount": amount, "transaction_id": transaction_id}
    except PyMongoError as e:
        print("[DEBUG][SBD TOKENS SEND] DB error:", e, flush=True)
        logger.error("[SBD TOKENS SEND] DB error: %s", e)
        return JSONResponse({"status": "error", "detail": "Database error", "error": str(e)}, status_code=500)
    except Exception as e:
        logger.error("[SBD TOKENS SEND] Unexpected error: %s", e, exc_info=True)
        return JSONResponse({"status": "error", "detail": "Internal server error", "error": str(e)}, status_code=500)

@router.get("/sbd_tokens/transactions")
async def get_my_sbd_tokens_transactions(
    request: Request = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(5, ge=1, le=100),  # Default limit is now 5
    current_user: dict = Depends(get_current_user_dep)
):
    username = current_user["username"]
    await security_manager.check_rate_limit(request, f"sbd_tokens_txn_{username}", rate_limit_requests=10, rate_limit_period=60)
    users_collection = db_manager.get_collection("users")
    try:
        user = await users_collection.find_one({"username": username}, {"sbd_tokens_transactions": 1, "_id": 0})
        if not user:
            logger.warning("[SBD TOKENS TXN READ] User not found: %s", username)
            return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
        txns = user.get("sbd_tokens_transactions", [])
        txns_sorted = sorted(txns, key=lambda x: x.get("timestamp", ""), reverse=True)
        return {"username": username, "transactions": txns_sorted[skip:skip+limit]}
    except PyMongoError as e:
        logger.error("[SBD TOKENS TXN READ] DB error: %s", e)
        return JSONResponse({"status": "error", "detail": "Database error"}, status_code=500)
    except Exception as e:
        logger.error("[SBD TOKENS TXN READ] Unexpected error: %s", e)
        return JSONResponse({"status": "error", "detail": "Internal server error"}, status_code=500)

@router.patch("/sbd_tokens/transaction/note")
async def add_note_to_transaction(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user_dep)
):
    transaction_id = data.get("transaction_id")
    note = data.get("note")
    if not transaction_id or not note:
        return JSONResponse({"status": "error", "detail": "transaction_id and note are required"}, status_code=400)
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    try:
        result = await users_collection.update_one(
            {"username": username, "sbd_tokens_transactions.transaction_id": transaction_id},
            {"$set": {"sbd_tokens_transactions.$.note": note}}
        )
        if result.modified_count == 0:
            return JSONResponse({"status": "error", "detail": "Transaction not found or note unchanged"}, status_code=404)
        return {"status": "success", "transaction_id": transaction_id, "note": note}
    except PyMongoError as e:
        logger.error("[SBD TOKENS NOTE PATCH] DB error: %s", e)
        return JSONResponse({"status": "error", "detail": "Database error"}, status_code=500)
    except Exception as e:
        logger.error("[SBD TOKENS NOTE PATCH] Unexpected error: %s", e)
        return JSONResponse({"status": "error", "detail": "Internal server error"}, status_code=500)
