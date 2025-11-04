from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, Query, Request
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from second_brain_database.database import db_manager
from second_brain_database.managers.family_manager import family_manager
from second_brain_database.managers.family_audit_manager import family_audit_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.routes.auth import enforce_all_lockdowns

logger = get_logger(prefix="[SBD TOKENS]")

router = APIRouter()


@router.get("/sbd_tokens")
async def get_my_sbd_tokens(request: Request = None, current_user: dict = Depends(enforce_all_lockdowns)):
    await security_manager.check_rate_limit(
        request, f"sbd_tokens_read_{current_user['username']}", rate_limit_requests=10, rate_limit_period=60
    )
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user = await users_collection.find_one({"username": username}, {"sbd_tokens": 1, "_id": 0})
    if not user:
        logger.warning("[SBD TOKENS READ] User not found: %s", username)
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    logger.info("[SBD TOKENS READ] User: %s, Tokens: %s", username, user.get("sbd_tokens", 0))
    return {"username": username, "sbd_tokens": user.get("sbd_tokens", 0)}


@router.post("/sbd_tokens/send")
async def send_sbd_tokens(request: Request, data: dict = Body(...), current_user: dict = Depends(enforce_all_lockdowns)):
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

    # Check if sender is trying to spend from a family account
    if await family_manager.is_virtual_family_account(from_user):
        # Validate family spending permissions with enhanced security
        user_id = str(current_user["_id"])
        request_context = {"request": request, "user": current_user}

        # Enhanced validation with detailed error messages
        validation_result = await family_manager.validate_family_spending(from_user, user_id, amount, request_context)
        if not validation_result:
            # Get detailed error information
            try:
                family_data = await family_manager.get_family_by_account_username(from_user)
                if family_data:
                    permissions = family_data["sbd_account"]["spending_permissions"].get(user_id, {})

                    if family_data["sbd_account"]["is_frozen"]:
                        error_detail = "Family account is currently frozen and cannot be used for spending"
                    elif not permissions.get("can_spend", False):
                        error_detail = "You don't have permission to spend from this family account"
                    elif permissions.get("spending_limit", 0) != -1 and amount > permissions.get("spending_limit", 0):
                        error_detail = f"Amount exceeds your spending limit of {permissions.get('spending_limit', 0)} tokens"
                    else:
                        error_detail = "Family spending validation failed"
                else:
                    error_detail = "Family account not found"
            except Exception:
                error_detail = "You don't have permission to spend from this family account, the amount exceeds your limit, or the account is frozen"

            logger.warning("[SBD TOKENS SEND] Family spending validation failed for user %s, account %s, amount %s",
                         user_id, from_user, amount)
            return JSONResponse({
                "status": "error",
                "detail": error_detail
            }, status_code=403)

    # Prevent sending to reserved username patterns (family_ or team_)
    if to_user.lower().startswith("family_") or to_user.lower().startswith("team_"):
        # Check if it's a valid virtual family account
        if to_user.lower().startswith("family_") and not await family_manager.is_virtual_family_account(to_user):
            logger.warning("[SBD TOKENS SEND] Attempt to send to non-existent family account: %s", to_user)
            return JSONResponse({
                "status": "error",
                "detail": "Family account does not exist. Family accounts can only be created through the family system."
            }, status_code=400)
        elif to_user.lower().startswith("team_"):
            logger.warning("[SBD TOKENS SEND] Attempt to send to reserved team account: %s", to_user)
            return JSONResponse({
                "status": "error",
                "detail": "Team accounts are reserved and not yet implemented."
            }, status_code=400)
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
                    # But don't create accounts with reserved prefixes (already validated above)
                    if not to_user_doc:
                        await users_collection.insert_one(
                            {
                                "username": to_user,
                                "sbd_tokens": 0,
                                "sbd_tokens_transactions": [],
                                "email": f"{to_user}@rohanbatra.in",
                            },
                            session=session,
                        )
                        to_user_doc = await users_collection.find_one({"username": to_user}, session=session)
                    if not from_user_doc:
                        logger.warning("[SBD TOKENS SEND] Sender not found: %s", from_user)
                        return JSONResponse(
                            {
                                "status": "error",
                                "detail": "Transaction could not be completed. Please check the details and try again.",
                            },
                            status_code=400,
                        )
                    now_iso = datetime.now(timezone.utc).isoformat()
                    send_txn = {
                        "type": "send",
                        "to": to_user,
                        "amount": amount,
                        "timestamp": now_iso,
                        "transaction_id": transaction_id,
                    }

                    # Add family member attribution if spending from family account
                    family_id = None
                    if await family_manager.is_virtual_family_account(from_user):
                        user_id = str(current_user["_id"])
                        username = current_user["username"]

                        # Get family ID for audit trail
                        family_id = await family_manager.get_family_id_by_sbd_account(from_user)

                        # Enhanced family member attribution with audit context
                        enhanced_send_txn = await family_audit_manager.enhance_transaction_with_family_attribution(
                            send_txn, family_id, user_id, username, {
                                "transaction_type": "send",
                                "recipient": to_user,
                                "original_note": note,
                                "request_context": {
                                    "ip_address": getattr(request, "client", {}).get("host"),
                                    "user_agent": request.headers.get("user-agent")
                                }
                            }
                        )
                        send_txn.update(enhanced_send_txn)
                    elif note:
                        send_txn["note"] = note
                    res1 = await users_collection.update_one(
                        {"username": from_user, "sbd_tokens": {"$gte": amount}},
                        {"$inc": {"sbd_tokens": -amount}, "$push": {"sbd_tokens_transactions": send_txn}},
                        session=session,
                    )
                    if res1.modified_count == 0:
                        logger.warning("[SBD TOKENS SEND] Race condition: insufficient tokens for %s", from_user)
                        return JSONResponse(
                            {"status": "error", "detail": "Insufficient sbd_tokens (race)"}, status_code=400
                        )
                    receive_txn = {
                        "type": "receive",
                        "from": from_user,
                        "amount": amount,
                        "timestamp": now_iso,
                        "transaction_id": transaction_id,
                    }

                    # Add family member attribution if receiving from family account
                    if await family_manager.is_virtual_family_account(from_user):
                        user_id = str(current_user["_id"])
                        username = current_user["username"]

                        # Enhanced family member attribution for receive transaction
                        enhanced_receive_txn = await family_audit_manager.enhance_transaction_with_family_attribution(
                            receive_txn, family_id, user_id, username, {
                                "transaction_type": "receive",
                                "sender": from_user,
                                "original_note": note,
                                "request_context": {
                                    "ip_address": getattr(request, "client", {}).get("host"),
                                    "user_agent": request.headers.get("user-agent")
                                }
                            }
                        )
                        receive_txn.update(enhanced_receive_txn)
                    elif note:
                        receive_txn["note"] = note
                    await users_collection.update_one(
                        {"username": to_user},
                        {"$inc": {"sbd_tokens": amount}, "$push": {"sbd_tokens_transactions": receive_txn}},
                        session=session,
                    )
                    # Log comprehensive audit trail for family transactions
                    if family_id:
                        try:
                            await family_audit_manager.log_sbd_transaction_audit(
                                family_id=family_id,
                                transaction_id=transaction_id,
                                transaction_type="send",
                                amount=amount,
                                from_account=from_user,
                                to_account=to_user,
                                family_member_id=str(current_user["_id"]),
                                family_member_username=current_user["username"],
                                transaction_context={
                                    "original_note": note,
                                    "enhanced_note": send_txn.get("note"),
                                    "request_metadata": {
                                        "ip_address": getattr(request, "client", {}).get("host"),
                                        "user_agent": request.headers.get("user-agent"),
                                        "timestamp": now_iso
                                    },
                                    "transaction_flow": "family_to_external",
                                    "compliance_flags": ["family_spending"]
                                },
                                session=session
                            )
                        except Exception as audit_error:
                            logger.warning(
                                "[SBD TOKENS SEND] Failed to log audit trail for transaction %s: %s",
                                transaction_id, audit_error
                            )

                    logger.info(
                        "[SBD TOKENS SEND] %s tokens sent from %s to %s (txn_id=%s)",
                        amount,
                        from_user,
                        to_user,
                        transaction_id,
                    )
        else:
            # Fallback: no transaction/session
            from_user_doc = await users_collection.find_one({"username": from_user})
            to_user_doc = await users_collection.find_one({"username": to_user})
            # If recipient does not exist, create them with 0 tokens and empty transactions
            # But don't create accounts with reserved prefixes (already validated above)
            if not to_user_doc:
                await users_collection.insert_one(
                    {
                        "username": to_user,
                        "sbd_tokens": 0,
                        "sbd_tokens_transactions": [],
                        "email": f"{to_user}@rohanbatra.in",
                    }
                )
                to_user_doc = await users_collection.find_one({"username": to_user})
            if not from_user_doc:
                logger.warning("[SBD TOKENS SEND] Sender not found: %s", from_user)
                return JSONResponse(
                    {
                        "status": "error",
                        "detail": "Transaction could not be completed. Please check the details and try again.",
                    },
                    status_code=400,
                )
            now_iso = datetime.now(timezone.utc).isoformat()
            send_txn = {
                "type": "send",
                "to": to_user,
                "amount": amount,
                "timestamp": now_iso,
                "transaction_id": transaction_id,
            }

            # Add family member attribution if spending from family account
            family_id = None
            if await family_manager.is_virtual_family_account(from_user):
                user_id = str(current_user["_id"])
                username = current_user["username"]

                # Get family ID for audit trail
                family_id = await family_manager.get_family_id_by_sbd_account(from_user)

                # Enhanced family member attribution with audit context
                enhanced_send_txn = await family_audit_manager.enhance_transaction_with_family_attribution(
                    send_txn, family_id, user_id, username, {
                        "transaction_type": "send",
                        "recipient": to_user,
                        "original_note": note,
                        "request_context": {
                            "ip_address": getattr(request, "client", {}).get("host"),
                            "user_agent": request.headers.get("user-agent")
                        }
                    }
                )
                send_txn.update(enhanced_send_txn)
            elif note:
                send_txn["note"] = note
            res1 = await users_collection.update_one(
                {"username": from_user, "sbd_tokens": {"$gte": amount}},
                {"$inc": {"sbd_tokens": -amount}, "$push": {"sbd_tokens_transactions": send_txn}},
            )
            if res1.modified_count == 0:
                logger.warning("[SBD TOKENS SEND] Race condition: insufficient tokens for %s", from_user)
                return JSONResponse({"status": "error", "detail": "Insufficient sbd_tokens (race)"}, status_code=400)
            receive_txn = {
                "type": "receive",
                "from": from_user,
                "amount": amount,
                "timestamp": now_iso,
                "transaction_id": transaction_id,
            }

            # Add family member attribution if receiving from family account
            if await family_manager.is_virtual_family_account(from_user):
                user_id = str(current_user["_id"])
                username = current_user["username"]

                # Enhanced family member attribution for receive transaction
                enhanced_receive_txn = await family_audit_manager.enhance_transaction_with_family_attribution(
                    receive_txn, family_id, user_id, username, {
                        "transaction_type": "receive",
                        "sender": from_user,
                        "original_note": note,
                        "request_context": {
                            "ip_address": getattr(request, "client", {}).get("host"),
                            "user_agent": request.headers.get("user-agent")
                        }
                    }
                )
                receive_txn.update(enhanced_receive_txn)
            elif note:
                receive_txn["note"] = note
            await users_collection.update_one(
                {"username": to_user},
                {"$inc": {"sbd_tokens": amount}, "$push": {"sbd_tokens_transactions": receive_txn}},
            )
            # Log comprehensive audit trail for family transactions (non-replica set)
            if family_id:
                try:
                    await family_audit_manager.log_sbd_transaction_audit(
                        family_id=family_id,
                        transaction_id=transaction_id,
                        transaction_type="send",
                        amount=amount,
                        from_account=from_user,
                        to_account=to_user,
                        family_member_id=str(current_user["_id"]),
                        family_member_username=current_user["username"],
                        transaction_context={
                            "original_note": note,
                            "enhanced_note": send_txn.get("note"),
                            "request_metadata": {
                                "ip_address": getattr(request, "client", {}).get("host"),
                                "user_agent": request.headers.get("user-agent"),
                                "timestamp": now_iso
                            },
                            "transaction_flow": "family_to_external",
                            "compliance_flags": ["family_spending", "non_replica_set"]
                        }
                    )
                except Exception as audit_error:
                    logger.warning(
                        "[SBD TOKENS SEND] Failed to log audit trail for transaction %s: %s",
                        transaction_id, audit_error
                    )

            logger.info(
                "[SBD TOKENS SEND] %s tokens sent from %s to %s (txn_id=%s)", amount, from_user, to_user, transaction_id
            )
        return {
            "status": "success",
            "from_user": from_user,
            "to_user": to_user,
            "amount": amount,
            "transaction_id": transaction_id,
        }
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
    current_user: dict = Depends(enforce_all_lockdowns),
):
    username = current_user["username"]
    await security_manager.check_rate_limit(
        request, f"sbd_tokens_txn_{username}", rate_limit_requests=10, rate_limit_period=60
    )
    users_collection = db_manager.get_collection("users")
    try:
        user = await users_collection.find_one({"username": username}, {"sbd_tokens_transactions": 1, "_id": 0})
        if not user:
            logger.warning("[SBD TOKENS TXN READ] User not found: %s", username)
            return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
        txns = user.get("sbd_tokens_transactions", [])
        txns_sorted = sorted(txns, key=lambda x: x.get("timestamp", ""), reverse=True)
        return {"username": username, "transactions": txns_sorted[skip : skip + limit]}
    except PyMongoError as e:
        logger.error("[SBD TOKENS TXN READ] DB error: %s", e)
        return JSONResponse({"status": "error", "detail": "Database error"}, status_code=500)
    except Exception as e:
        logger.error("[SBD TOKENS TXN READ] Unexpected error: %s", e)
        return JSONResponse({"status": "error", "detail": "Internal server error"}, status_code=500)


@router.patch("/sbd_tokens/transaction/note")
async def add_note_to_transaction(data: dict = Body(...), current_user: dict = Depends(enforce_all_lockdowns)):
    transaction_id = data.get("transaction_id")
    note = data.get("note")
    if not transaction_id or not note:
        return JSONResponse({"status": "error", "detail": "transaction_id and note are required"}, status_code=400)
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    try:
        result = await users_collection.update_one(
            {"username": username, "sbd_tokens_transactions.transaction_id": transaction_id},
            {"$set": {"sbd_tokens_transactions.$.note": note}},
        )
        if result.modified_count == 0:
            return JSONResponse(
                {"status": "error", "detail": "Transaction not found or note unchanged"}, status_code=404
            )
        return {"status": "success", "transaction_id": transaction_id, "note": note}
    except PyMongoError as e:
        logger.error("[SBD TOKENS NOTE PATCH] DB error: %s", e)
        return JSONResponse({"status": "error", "detail": "Database error"}, status_code=500)
    except Exception as e:
        logger.error("[SBD TOKENS NOTE PATCH] Unexpected error: %s", e)
        return JSONResponse({"status": "error", "detail": "Internal server error"}, status_code=500)
