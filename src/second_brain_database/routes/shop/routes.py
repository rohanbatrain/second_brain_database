from datetime import datetime, timezone
import time
from typing import Optional, Dict, Any, List
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from second_brain_database.database import db_manager
from second_brain_database.docs.models import (
    StandardErrorResponse,
    StandardSuccessResponse,
    ValidationErrorResponse,
    create_error_responses,
    create_standard_responses,
)
from second_brain_database.managers.family_manager import family_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.routes.auth import enforce_all_lockdowns
from second_brain_database.utils.logging_utils import (
    ip_address_context,
    log_database_operation,
    log_error_with_context,
    log_performance,
    request_id_context,
    user_id_context,
)

logger = get_logger(prefix="[SHOP]")

router = APIRouter()

SHOP_COLLECTION = "shop"


# Payment method models
class PaymentMethod(BaseModel):
    """Payment method selection for shop purchases."""
    type: str = Field(..., description="Payment type: 'personal' or 'family'")
    family_id: Optional[str] = Field(None, description="Family ID if using family tokens")


class PurchaseRequest(BaseModel):
    """Base purchase request with payment method."""
    payment_method: PaymentMethod = Field(..., description="Payment method selection")


class ThemePurchaseRequest(PurchaseRequest):
    """Theme purchase request with payment method."""
    theme_id: str = Field(..., description="Theme ID to purchase")


class AvatarPurchaseRequest(PurchaseRequest):
    """Avatar purchase request with payment method."""
    avatar_id: str = Field(..., description="Avatar ID to purchase")


class BannerPurchaseRequest(PurchaseRequest):
    """Banner purchase request with payment method."""
    banner_id: str = Field(..., description="Banner ID to purchase")


class BundlePurchaseRequest(PurchaseRequest):
    """Bundle purchase request with payment method."""
    bundle_id: str = Field(..., description="Bundle ID to purchase")


class CartCheckoutRequest(BaseModel):
    """Cart checkout request with payment method."""
    payment_method: PaymentMethod = Field(..., description="Payment method selection")


# Helper functions for family token integration
async def get_user_payment_options(user_id: str, username: str) -> Dict[str, Any]:
    """
    Get available payment options for a user including personal and family tokens.
    
    Args:
        user_id: User ID
        username: Username
        
    Returns:
        Dict containing personal and family token balances
    """
    users_collection = db_manager.get_collection("users")
    
    # Get personal token balance
    user = await users_collection.find_one({"username": username}, {"sbd_tokens": 1})
    personal_balance = user.get("sbd_tokens", 0) if user else 0
    
    # Get family token balances
    family_balances = []
    try:
        user_families = await family_manager.get_user_families(user_id)
        for family in user_families:
            family_id = family["family_id"]
            try:
                # Get family SBD account details
                sbd_account = await family_manager.get_family_sbd_account(family_id, user_id)
                
                # Check if user has spending permissions
                user_permissions = sbd_account["spending_permissions"].get(user_id, {})
                can_spend = user_permissions.get("can_spend", False) and not sbd_account["is_frozen"]
                
                if can_spend:
                    family_balances.append({
                        "family_id": family_id,
                        "family_name": family["name"],
                        "balance": sbd_account["balance"],
                        "spending_limit": user_permissions.get("spending_limit", 0),
                        "is_frozen": sbd_account["is_frozen"]
                    })
            except Exception as e:
                logger.warning("Failed to get family SBD account for family %s: %s", family_id, e)
                continue
    except Exception as e:
        logger.warning("Failed to get user families for payment options: %s", e)
    
    return {
        "personal": {
            "balance": personal_balance,
            "available": True
        },
        "family": family_balances
    }


async def validate_payment_method(payment_method: PaymentMethod, user_id: str, username: str, amount: int) -> Dict[str, Any]:
    """
    Validate payment method and check if user can make the purchase.
    
    Args:
        payment_method: Payment method selection
        user_id: User ID
        username: Username
        amount: Purchase amount
        
    Returns:
        Dict containing validation result and payment details
        
    Raises:
        HTTPException: If payment method is invalid or insufficient funds
    """
    if payment_method.type == "personal":
        # Validate personal token balance
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one({"username": username}, {"sbd_tokens": 1})
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        balance = user.get("sbd_tokens", 0)
        if balance < amount:
            raise HTTPException(
                status_code=400, 
                detail={
                    "error": "INSUFFICIENT_PERSONAL_TOKENS",
                    "message": f"Insufficient personal tokens. Required: {amount}, Available: {balance}"
                }
            )
        
        return {
            "valid": True,
            "payment_type": "personal",
            "account_username": username,
            "balance": balance
        }
    
    elif payment_method.type == "family":
        if not payment_method.family_id:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "MISSING_FAMILY_ID",
                    "message": "Family ID is required for family token payments"
                }
            )
        
        try:
            # Get family data and validate spending permission
            family_data = await family_manager.get_family_by_id(payment_method.family_id)
            family_username = family_data["sbd_account"]["account_username"]
            
            # Validate family spending permission
            can_spend = await family_manager.validate_family_spending(
                family_username, user_id, amount
            )
            
            if not can_spend:
                # Get detailed error information
                permissions = family_data["sbd_account"]["spending_permissions"].get(user_id, {})
                
                if family_data["sbd_account"]["is_frozen"]:
                    error_detail = "Family account is currently frozen and cannot be used for spending"
                elif not permissions.get("can_spend", False):
                    error_detail = "You don't have permission to spend from this family account"
                elif permissions.get("spending_limit", 0) != -1 and amount > permissions.get("spending_limit", 0):
                    error_detail = f"Amount exceeds your spending limit of {permissions.get('spending_limit', 0)} tokens"
                else:
                    error_detail = "Family spending validation failed"
                
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "FAMILY_SPENDING_DENIED",
                        "message": error_detail
                    }
                )
            
            # Get family account balance
            balance = await family_manager.get_family_sbd_balance(family_username)
            
            return {
                "valid": True,
                "payment_type": "family",
                "account_username": family_username,
                "family_id": payment_method.family_id,
                "family_name": family_data["name"],
                "balance": balance,
                "user_permissions": permissions
            }
            
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            logger.error("Failed to validate family payment method: %s", e)
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "FAMILY_VALIDATION_FAILED",
                    "message": "Failed to validate family payment method"
                }
            )
    
    else:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_PAYMENT_TYPE",
                "message": f"Invalid payment type: {payment_method.type}. Must be 'personal' or 'family'"
            }
        )


async def process_payment(payment_details: Dict[str, Any], amount: int, item_details: Dict[str, Any], 
                         current_user: Dict[str, Any], transaction_id: str) -> Dict[str, Any]:
    """
    Process payment using the validated payment method.
    
    Args:
        payment_details: Validated payment details
        amount: Purchase amount
        item_details: Item being purchased
        current_user: Current user information
        transaction_id: Transaction ID
        
    Returns:
        Dict containing transaction details
    """
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user_id = str(current_user["_id"])
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # Prepare transaction notes
    item_type = item_details.get("type", "item")
    item_id = item_details.get(f"{item_type}_id", "unknown")
    base_note = f"Bought {item_type} {item_id} from shop"
    
    if payment_details["payment_type"] == "personal":
        # Process personal token payment
        send_txn = {
            "type": "send",
            "to": "emotion_tracker_shop",
            "amount": amount,
            "timestamp": now_iso,
            "transaction_id": transaction_id,
            "note": base_note,
        }
        
        receive_txn = {
            "type": "receive",
            "from": username,
            "amount": amount,
            "timestamp": now_iso,
            "transaction_id": transaction_id,
            "note": f"User bought {item_type} {item_id}",
        }
        
        # Deduct from personal account
        result = await users_collection.update_one(
            {"username": username, "sbd_tokens": {"$gte": amount}},
            {
                "$inc": {"sbd_tokens": -amount},
                "$push": {"sbd_tokens_transactions": send_txn},
            },
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=400,
                detail="Insufficient SBD tokens or race condition"
            )
        
        # Add to shop account
        await users_collection.update_one(
            {"username": "emotion_tracker_shop"},
            {
                "$setOnInsert": {"email": "emotion_tracker_shop@rohanbatra.in"},
                "$push": {"sbd_tokens_transactions": receive_txn},
            },
            upsert=True,
        )
        
        return {
            "payment_type": "personal",
            "from_account": username,
            "amount": amount,
            "transaction_id": transaction_id
        }
    
    elif payment_details["payment_type"] == "family":
        # Process family token payment
        family_username = payment_details["account_username"]
        family_id = payment_details["family_id"]
        family_name = payment_details["family_name"]
        
        # Enhanced transaction notes with family member attribution
        family_note = f"Spent by family member @{username} from {family_name}"
        send_txn = {
            "type": "send",
            "to": "emotion_tracker_shop",
            "amount": amount,
            "timestamp": now_iso,
            "transaction_id": transaction_id,
            "note": f"{base_note} ({family_note})",
            "family_member_id": user_id,
            "family_member_username": username,
            "shop_item_type": item_type,
            "shop_item_id": item_id
        }
        
        receive_txn = {
            "type": "receive",
            "from": family_username,
            "amount": amount,
            "timestamp": now_iso,
            "transaction_id": transaction_id,
            "note": f"Family member @{username} bought {item_type} {item_id}",
            "family_member_id": user_id,
            "family_member_username": username,
            "shop_item_type": item_type,
            "shop_item_id": item_id
        }
        
        # Deduct from family account
        result = await users_collection.update_one(
            {"username": family_username, "sbd_tokens": {"$gte": amount}},
            {
                "$inc": {"sbd_tokens": -amount},
                "$push": {"sbd_tokens_transactions": send_txn},
            },
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=400,
                detail="Insufficient family tokens or race condition"
            )
        
        # Add to shop account
        await users_collection.update_one(
            {"username": "emotion_tracker_shop"},
            {
                "$setOnInsert": {"email": "emotion_tracker_shop@rohanbatra.in"},
                "$push": {"sbd_tokens_transactions": receive_txn},
            },
            upsert=True,
        )
        
        # Send family notification about the purchase
        try:
            await family_manager.send_family_notification(
                family_id,
                "sbd_spend",
                {
                    "transaction_id": transaction_id,
                    "amount": amount,
                    "spender_username": username,
                    "spender_id": user_id,
                    "shop_item_type": item_type,
                    "shop_item_id": item_id,
                    "shop_item_name": item_details.get("name", "Unknown Item"),
                    "to_account": "emotion_tracker_shop"
                }
            )
        except Exception as e:
            logger.warning("Failed to send family notification for shop purchase: %s", e)
        
        return {
            "payment_type": "family",
            "from_account": family_username,
            "family_id": family_id,
            "family_name": family_name,
            "amount": amount,
            "transaction_id": transaction_id,
            "family_member": username
        }
    
    else:
        raise HTTPException(status_code=400, detail="Invalid payment type")


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


@router.get("/shop/payment-options", tags=["Shop"], summary="Get available payment options")
async def get_payment_options(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns)
):
    """
    Get available payment options for the current user including personal and family token balances.
    
    Returns comprehensive information about all available payment methods,
    including personal token balance and family accounts the user can spend from.
    
    **Returns:**
    - Personal token balance
    - List of family accounts with spending permissions
    - Spending limits and restrictions for each account
    """
    user_id = str(current_user["_id"])
    username = current_user["username"]
    
    try:
        payment_options = await get_user_payment_options(user_id, username)
        
        logger.debug("Retrieved payment options for user %s", username)
        
        return {
            "status": "success",
            "data": {
                "user_id": user_id,
                "username": username,
                "payment_options": payment_options
            }
        }
        
    except Exception as e:
        logger.error("Failed to get payment options for user %s: %s", username, e)
        return JSONResponse(
            {"status": "error", "detail": "Failed to retrieve payment options"},
            status_code=500
        )


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


@router.post(
    "/shop/themes/buy",
    tags=["Shop"],
    summary="Purchase a theme with SBD tokens",
    description="""
    Purchase a theme using SBD tokens from personal or family account balance.
    
    **Backward Compatibility:**
    - Supports both old format: `{"theme_id": "..."}` (defaults to personal tokens)
    - And new format: `{"theme_id": "...", "payment_method": {"type": "personal|family", "family_id": "..."}}`
    
    **Purchase Process:**
    1. Validates theme ID and user authentication
    2. Validates payment method (personal or family tokens)
    3. Checks if user already owns the theme
    4. Verifies sufficient SBD token balance and spending permissions
    5. Deducts tokens and adds theme to user's owned collection
    6. Records transaction with family member attribution if applicable
    7. Sends family notifications for family token purchases
    
    **Payment Methods:**
    - **Personal tokens**: Use your personal SBD token balance
    - **Family tokens**: Use tokens from a family account (requires spending permission)
    
    **Family Token Features:**
    - Spending permissions and limits enforced
    - Family member attribution in transaction logs
    - Automatic notifications to family members
    - Account freeze protection
    
    **Security Features:**
    - Server-side price validation (prices cannot be manipulated by client)
    - Atomic transaction processing to prevent race conditions
    - Ownership verification to prevent duplicate purchases
    - Comprehensive transaction logging with family context
    
    **SBD Token System:**
    - Themes cost 250 SBD tokens each
    - Tokens are deducted from selected account balance
    - All transactions are logged with unique transaction IDs
    - Failed purchases do not deduct tokens
    
    **Theme Ownership:**
    - Purchased themes are permanently owned
    - Can be used across all supported applications
    - Ownership is immediately available after purchase
    """,
    responses={
        200: {
            "description": "Theme purchased successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "personal_purchase": {
                            "summary": "Successful personal token purchase",
                            "value": {
                                "status": "success",
                                "theme": {
                                    "theme_id": "emotion_tracker-serenityGreen",
                                    "unlocked_at": "2024-01-01T12:00:00Z",
                                    "permanent": True,
                                    "source": "purchase",
                                    "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
                                    "note": "Bought from shop",
                                    "price": 250,
                                },
                                "payment": {
                                    "payment_type": "personal",
                                    "from_account": "username",
                                    "amount": 250
                                }
                            }
                        },
                        "family_purchase": {
                            "summary": "Successful family token purchase",
                            "value": {
                                "status": "success",
                                "theme": {
                                    "theme_id": "emotion_tracker-serenityGreen",
                                    "unlocked_at": "2024-01-01T12:00:00Z",
                                    "permanent": True,
                                    "source": "purchase",
                                    "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
                                    "note": "Bought from shop",
                                    "price": 250,
                                },
                                "payment": {
                                    "payment_type": "family",
                                    "from_account": "family_smiths",
                                    "family_name": "Smith Family",
                                    "amount": 250,
                                    "family_member": "username"
                                }
                            }
                        },
                        "legacy_purchase": {
                            "summary": "Legacy format purchase (backward compatible)",
                            "value": {
                                "status": "success",
                                "theme": {
                                    "theme_id": "emotion_tracker-serenityGreen",
                                    "unlocked_at": "2024-01-01T12:00:00Z",
                                    "permanent": True,
                                    "source": "purchase",
                                    "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
                                    "note": "Bought from shop",
                                    "price": 250,
                                }
                            }
                        }
                    }
                }
            },
        },
        400: {
            "description": "Invalid request or insufficient funds",
            "model": StandardErrorResponse,
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_theme": {
                            "summary": "Invalid theme ID",
                            "value": {"status": "error", "detail": "Invalid or missing theme_id"},
                        },
                        "already_owned": {
                            "summary": "Theme already owned",
                            "value": {"status": "error", "detail": "Theme already owned"},
                        },
                        "insufficient_personal_funds": {
                            "summary": "Not enough personal SBD tokens",
                            "value": {"status": "error", "detail": {"error": "INSUFFICIENT_PERSONAL_TOKENS", "message": "Insufficient personal tokens. Required: 250, Available: 100"}},
                        },
                        "invalid_payment_method": {
                            "summary": "Invalid payment method",
                            "value": {"status": "error", "detail": {"error": "INVALID_PAYMENT_TYPE", "message": "Invalid payment type: invalid. Must be 'personal' or 'family'"}},
                        },
                    }
                }
            },
        },
        401: {"description": "Authentication required", "model": StandardErrorResponse},
        403: {
            "description": "Access denied - invalid client or family spending denied",
            "content": {
                "application/json": {
                    "examples": {
                        "access_denied": {
                            "summary": "Invalid client", 
                            "value": {"status": "error", "detail": "Shop access denied: invalid client"}
                        },
                        "family_spending_denied": {
                            "summary": "Family spending permission denied",
                            "value": {"status": "error", "detail": {"error": "FAMILY_SPENDING_DENIED", "message": "You don't have permission to spend from this family account"}}
                        }
                    }
                }
            },
        },
        404: {
            "description": "Theme not found",
            "content": {"application/json": {"examples": {"not_found": {"summary": "Theme not found", "value": {"status": "error", "detail": "Theme not found"}}}}},
        },
        500: {"description": "Internal server error", "model": StandardErrorResponse},
    },
)
async def buy_theme(
    request: Request,
    data: dict = Body(...),  # Accept raw dict for backward compatibility
    current_user: dict = Depends(enforce_all_lockdowns),
):
    # Set up logging context
    request_id = str(uuid4())[:8]
    client_ip = security_manager.get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    username = current_user["username"]
    user_id = str(current_user["_id"])
    
    # Handle backward compatibility - support both old and new request formats
    if "payment_method" in data:
        # New format with payment method
        try:
            purchase_request = ThemePurchaseRequest(**data)
            theme_id = purchase_request.theme_id
            payment_method = purchase_request.payment_method
        except Exception as e:
            return JSONResponse({"status": "error", "detail": f"Invalid request format: {str(e)}"}, status_code=400)
    else:
        # Legacy format - default to personal tokens
        theme_id = data.get("theme_id")
        payment_method = PaymentMethod(type="personal")

    request_id_context.set(request_id)
    user_id_context.set(username)
    ip_address_context.set(client_ip)

    start_time = time.time()

    logger.info(
        "[%s] POST /shop/themes/buy - User: %s, IP: %s, Theme: %s, Payment: %s, User-Agent: %s",
        request_id,
        username,
        client_ip,
        theme_id,
        payment_method.type,
        user_agent[:100],
    )

    try:
        if not theme_id or not theme_id.startswith("emotion_tracker-"):
            logger.warning(
                "[%s] POST /shop/themes/buy validation failed - User: %s, Invalid theme_id: %s",
                request_id,
                username,
                theme_id,
            )
            return JSONResponse({"status": "error", "detail": "Invalid or missing theme_id"}, status_code=400)

        if "emotion_tracker" not in user_agent:
            logger.warning(
                "[%s] POST /shop/themes/buy access denied - User: %s, Invalid client: %s",
                request_id,
                username,
                user_agent[:100],
            )
            return JSONResponse({"status": "error", "detail": "Shop access denied: invalid client"}, status_code=403)
        
        # Get theme details from server-side registry
        theme_details = await get_item_details(theme_id, "theme")
        if not theme_details:
            logger.warning(
                "[%s] POST /shop/themes/buy theme not found - User: %s, Theme: %s", request_id, username, theme_id
            )
            return JSONResponse({"status": "error", "detail": "Theme not found"}, status_code=404)

        price = theme_details["price"]

        # Database operations with logging
        users_collection = db_manager.get_collection("users")

        db_start = time.time()
        user = await users_collection.find_one({"username": username}, {"themes_owned": 1})
        db_duration = time.time() - db_start

        logger.info(
            "[%s] DB find_one for user verification completed in %.3fs - User: %s", request_id, db_duration, username
        )

        if not user:
            logger.warning("[%s] POST /shop/themes/buy user not found - User: %s", request_id, username)
            return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)

        # Check ownership
        for owned in user.get("themes_owned", []):
            if owned["theme_id"] == theme_id:
                logger.warning(
                    "[%s] POST /shop/themes/buy already owned - User: %s, Theme: %s", request_id, username, theme_id
                )
                return JSONResponse({"status": "error", "detail": "Theme already owned"}, status_code=400)

        # Validate payment method and check balance
        try:
            payment_details = await validate_payment_method(payment_method, user_id, username, price)
        except HTTPException as e:
            logger.warning(
                "[%s] POST /shop/themes/buy payment validation failed - User: %s, Error: %s",
                request_id,
                username,
                e.detail,
            )
            return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)

        # Prepare transaction data
        now_iso = datetime.now(timezone.utc).isoformat()
        transaction_id = str(uuid4())
        theme_entry = {
            "theme_id": theme_id,
            "unlocked_at": now_iso,
            "permanent": True,
            "source": "purchase",
            "transaction_id": transaction_id,
            "note": "Bought from shop",
            "price": price,
        }

        # Process payment
        try:
            payment_result = await process_payment(payment_details, price, theme_details, current_user, transaction_id)
        except HTTPException as e:
            logger.warning(
                "[%s] POST /shop/themes/buy payment processing failed - User: %s, Error: %s",
                request_id,
                username,
                e.detail,
            )
            return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)

        # Add theme to the correct owned collection (user or family)
        db_start = time.time()
        # Default target is the purchasing user
        target_username = username
        theme_entry_to_store = dict(theme_entry)
        if payment_result.get("payment_type") == "family":
            # Store on family virtual account and include audit fields
            target_username = payment_result.get("from_account")
            theme_entry_to_store.update({
                "purchased_by_user_id": user_id,
                "purchased_by_username": username,
                "family_transaction_id": transaction_id,
            })

        result = await users_collection.update_one(
            {"username": target_username},
            {"$push": {"themes_owned": theme_entry_to_store}},
            upsert=True,
        )
        db_duration = time.time() - db_start

        logger.info(
            "[%s] DB update_one for theme ownership completed in %.3fs - User: %s, Modified: %d",
            request_id,
            db_duration,
            username,
            result.modified_count,
        )

        if result.modified_count == 0:
            logger.error(
                "[%s] POST /shop/themes/buy failed to add theme to user - User: %s, Theme: %s", 
                request_id, username, theme_id
            )
            return JSONResponse(
                {"status": "error", "detail": "Failed to add theme to user account"}, status_code=500
            )

        duration = time.time() - start_time
        logger.info(
            "[%s] POST /shop/themes/buy completed in %.3fs - User: %s, Theme: %s, Price: %d, Payment: %s, TxnID: %s",
            request_id,
            duration,
            username,
            theme_id,
            price,
            payment_method.type,
            transaction_id,
        )

        # Return format based on request type for backward compatibility
        response = {"status": "success", "theme": theme_entry}
        
        # Only include payment details if new format was used
        if "payment_method" in data:
            response["payment"] = payment_result
            
        return response

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "[%s] POST /shop/themes/buy failed after %.3fs - User: %s, Error: %s",
            request_id,
            duration,
            username,
            str(e),
        )
        log_error_with_context(
            e,
            context={"user": username, "ip": client_ip, "request_id": request_id, "theme_id": theme_id},
            operation="buy_theme",
        )
        return JSONResponse({"status": "error", "detail": "Internal server error", "error": str(e)}, status_code=500)


@router.post("/shop/avatars/buy", tags=["Shop"], summary="Buy an avatar with SBD tokens")
async def buy_avatar(request: Request, data: dict = Body(...), current_user: dict = Depends(enforce_all_lockdowns)):
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user_id = str(current_user["_id"])
    
    # Handle backward compatibility
    if "payment_method" in data:
        # New format with payment method
        try:
            purchase_request = AvatarPurchaseRequest(**data)
            avatar_id = purchase_request.avatar_id
            payment_method = purchase_request.payment_method
        except Exception as e:
            return JSONResponse({"status": "error", "detail": f"Invalid request format: {str(e)}"}, status_code=400)
    else:
        # Legacy format - default to personal tokens
        avatar_id = data.get("avatar_id")
        payment_method = PaymentMethod(type="personal")
    
    if not avatar_id:
        return JSONResponse({"status": "error", "detail": "Invalid or missing avatar_id"}, status_code=400)
    
    # Get avatar details from server-side registry
    avatar_details = await get_item_details(avatar_id, "avatar")
    if not avatar_details:
        return JSONResponse({"status": "error", "detail": "Avatar not found"}, status_code=404)
    
    price = avatar_details["price"]
    
    # Check if user already owns the avatar
    user = await users_collection.find_one({"username": username}, {"avatars_owned": 1})
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    
    if any(owned.get("avatar_id") == avatar_id for owned in user.get("avatars_owned", [])):
        return JSONResponse({"status": "error", "detail": "Avatar already owned"}, status_code=400)
    
    # Validate payment method and check balance
    try:
        payment_details = await validate_payment_method(payment_method, user_id, username, price)
    except HTTPException as e:
        return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)
    
    # Prepare transaction data
    now_iso = datetime.now(timezone.utc).isoformat()
    transaction_id = str(uuid4())
    avatar_entry = {
        "avatar_id": avatar_id,
        "unlocked_at": now_iso,
        "permanent": True,
        "source": "purchase",
        "transaction_id": transaction_id,
        "note": "Bought from shop",
        "price": price,
    }
    
    try:
        logger.info(f"[AVATAR BUY] User: {username} attempting to buy avatar_id={avatar_id} for price={price} using {payment_method.type}")
        
        # Process payment
        payment_result = await process_payment(payment_details, price, avatar_details, current_user, transaction_id)
        
        # Add avatar to the correct owned collection (user or family)
        target_username = username
        avatar_entry_to_store = dict(avatar_entry)
        if payment_result.get("payment_type") == "family":
            target_username = payment_result.get("from_account")
            avatar_entry_to_store.update({
                "purchased_by_user_id": user_id,
                "purchased_by_username": username,
                "family_transaction_id": transaction_id,
            })

        result = await users_collection.update_one(
            {"username": target_username},
            {"$push": {"avatars_owned": avatar_entry_to_store}},
            upsert=True,
        )
        
        logger.info(f"[AVATAR BUY] Update result for user {username}: modified_count={result.modified_count}")
        
        if result.modified_count == 0:
            logger.error(f"[AVATAR BUY] Failed to add avatar to user {username} buying avatar_id={avatar_id}")
            return JSONResponse(
                {"status": "error", "detail": "Failed to add avatar to user account"}, status_code=500
            )
        
        logger.info(
            f"[AVATAR BUY] User: {username} successfully bought avatar_id={avatar_id} (txn_id={transaction_id}) using {payment_method.type}"
        )
        
        # Return format based on request type for backward compatibility
        response = {"status": "success", "avatar": avatar_entry}
        
        # Only include payment details if new format was used
        if "payment_method" in data:
            response["payment"] = payment_result
            
        return response
        
    except HTTPException as e:
        return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)
    except Exception as e:
        logger.error(f"[AVATAR BUY ERROR] User: {username}, avatar_id={avatar_id}, error={e}")
        return JSONResponse({"status": "error", "detail": "Internal server error", "error": str(e)}, status_code=500)


@router.post("/shop/banners/buy", tags=["Shop"], summary="Buy a banner with SBD tokens")
async def buy_banner(request: Request, data: dict = Body(...), current_user: dict = Depends(enforce_all_lockdowns)):
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user_id = str(current_user["_id"])
    
    # Handle backward compatibility
    if "payment_method" in data:
        # New format with payment method
        try:
            purchase_request = BannerPurchaseRequest(**data)
            banner_id = purchase_request.banner_id
            payment_method = purchase_request.payment_method
        except Exception as e:
            return JSONResponse({"status": "error", "detail": f"Invalid request format: {str(e)}"}, status_code=400)
    else:
        # Legacy format - default to personal tokens
        banner_id = data.get("banner_id")
        payment_method = PaymentMethod(type="personal")
    
    if not banner_id:
        return JSONResponse({"status": "error", "detail": "Invalid or missing banner_id"}, status_code=400)
    
    # Get banner details from server-side registry
    banner_details = await get_item_details(banner_id, "banner")
    if not banner_details:
        return JSONResponse({"status": "error", "detail": "Banner not found"}, status_code=404)
    
    price = banner_details["price"]
    
    # Check if user already owns the banner
    user = await users_collection.find_one({"username": username}, {"banners_owned": 1})
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    
    if any(owned.get("banner_id") == banner_id for owned in user.get("banners_owned", [])):
        return JSONResponse({"status": "error", "detail": "Banner already owned"}, status_code=400)
    
    # Validate payment method and check balance
    try:
        payment_details = await validate_payment_method(payment_method, user_id, username, price)
    except HTTPException as e:
        return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)
    
    # Prepare transaction data
    now_iso = datetime.now(timezone.utc).isoformat()
    transaction_id = str(uuid4())
    banner_entry = {
        "banner_id": banner_id,
        "unlocked_at": now_iso,
        "permanent": True,
        "source": "purchase",
        "transaction_id": transaction_id,
        "note": "Bought from shop",
        "price": price,
    }
    
    try:
        logger.info(f"[BANNER BUY] User: {username} attempting to buy banner_id={banner_id} for price={price} using {payment_method.type}")
        
        # Process payment
        payment_result = await process_payment(payment_details, price, banner_details, current_user, transaction_id)
        
        # Add banner to the correct owned collection (user or family)
        target_username = username
        banner_entry_to_store = dict(banner_entry)
        if payment_result.get("payment_type") == "family":
            target_username = payment_result.get("from_account")
            banner_entry_to_store.update({
                "purchased_by_user_id": user_id,
                "purchased_by_username": username,
                "family_transaction_id": transaction_id,
            })

        result = await users_collection.update_one(
            {"username": target_username},
            {"$push": {"banners_owned": banner_entry_to_store}},
            upsert=True,
        )
        
        logger.info(f"[BANNER BUY] Update result for user {username}: modified_count={result.modified_count}")
        
        if result.modified_count == 0:
            logger.error(f"[BANNER BUY] Failed to add banner to user {username} buying banner_id={banner_id}")
            return JSONResponse(
                {"status": "error", "detail": "Failed to add banner to user account"}, status_code=500
            )
        
        logger.info(
            f"[BANNER BUY] User: {username} successfully bought banner_id={banner_id} (txn_id={transaction_id}) using {payment_method.type}"
        )
        
        # Return format based on request type for backward compatibility
        response = {"status": "success", "banner": banner_entry}
        
        # Only include payment details if new format was used
        if "payment_method" in data:
            response["payment"] = payment_result
            
        return response
        
    except HTTPException as e:
        return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)
    except Exception as e:
        logger.error(f"[BANNER BUY ERROR] User: {username}, banner_id={banner_id}, error={e}")
        return JSONResponse({"status": "error", "detail": "Internal server error", "error": str(e)}, status_code=500)


@router.post("/shop/bundles/buy", tags=["Shop"], summary="Buy a bundle with SBD tokens")
async def buy_bundle(request: Request, data: dict = Body(...), current_user: dict = Depends(enforce_all_lockdowns)):
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user_id = str(current_user["_id"])
    
    # Handle backward compatibility
    if "payment_method" in data:
        # New format with payment method
        try:
            purchase_request = BundlePurchaseRequest(**data)
            bundle_id = purchase_request.bundle_id
            payment_method = purchase_request.payment_method
        except Exception as e:
            return JSONResponse({"status": "error", "detail": f"Invalid request format: {str(e)}"}, status_code=400)
    else:
        # Legacy format - default to personal tokens
        bundle_id = data.get("bundle_id")
        payment_method = PaymentMethod(type="personal")
    
    if not bundle_id:
        return JSONResponse({"status": "error", "detail": "Invalid or missing bundle_id"}, status_code=400)
    
    # Get bundle details from server-side registry
    bundle_details = await get_item_details(bundle_id, "bundle")
    if not bundle_details:
        return JSONResponse({"status": "error", "detail": "Bundle not found"}, status_code=404)
    
    price = bundle_details["price"]
    
    # Check if user already owns the bundle
    user = await users_collection.find_one(
        {"username": username},
        {"bundles_owned": 1, "avatars_owned": 1, "themes_owned": 1, "banners_owned": 1},
    )
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    
    if bundle_id in user.get("bundles_owned", []):
        return JSONResponse({"status": "error", "detail": "Bundle already owned"}, status_code=400)
    
    # Validate payment method and check balance
    try:
        payment_details = await validate_payment_method(payment_method, user_id, username, price)
    except HTTPException as e:
        return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)
    
    # Prepare transaction data
    now_iso = datetime.now(timezone.utc).isoformat()
    transaction_id = str(uuid4())
    bundle_entry = {
        "bundle_id": bundle_id,
        "unlocked_at": now_iso,
        "permanent": True,
        "source": "purchase",
        "transaction_id": transaction_id,
        "note": "Bought from shop",
        "price": price,
    }
    
    try:
        logger.info(f"[BUNDLE BUY] User: {username} attempting to buy bundle_id={bundle_id} for price={price} using {payment_method.type}")
        
        # Process payment
        payment_result = await process_payment(payment_details, price, bundle_details, current_user, transaction_id)
        
        # Add bundle to the correct owned collection (user or family)
        target_username = username
        bundle_entry_to_store = dict(bundle_entry)
        if payment_result.get("payment_type") == "family":
            target_username = payment_result.get("from_account")
            bundle_entry_to_store.update({
                "purchased_by_user_id": user_id,
                "purchased_by_username": username,
                "family_transaction_id": transaction_id,
            })

        result = await users_collection.update_one(
            {"username": target_username},
            {"$push": {"bundles_owned": bundle_entry_to_store}},
            upsert=True,
        )

        if result.modified_count == 0:
            logger.error(f"[BUNDLE BUY] Failed to add bundle to user {username} buying bundle_id={bundle_id}")
            return JSONResponse(
                {"status": "error", "detail": "Failed to add bundle to user account"}, status_code=500
            )
        
        # Auto-populate bundle contents (avatars, themes, banners)
        update_operations = {}
        now_iso_checkout = datetime.now(timezone.utc).isoformat()
        
        bundle_contents = BUNDLE_CONTENTS.get(bundle_id, {})
        
        # Add avatars from bundle
        for avatar_id in bundle_contents.get("avatars", []):
            avatar_entry = {
                "avatar_id": avatar_id,
                "unlocked_at": now_iso_checkout,
                "permanent": True,
                "source": f"bundle:{bundle_id}",
                "transaction_id": transaction_id,
                "note": f"Unlocked via bundle {bundle_id}",
                "price": 0,
            }
            update_operations.setdefault("avatars_owned", {"$each": []})["$each"].append(avatar_entry)
        
        # Add themes from bundle
        for theme_id in bundle_contents.get("themes", []):
            theme_entry = {
                "theme_id": theme_id,
                "unlocked_at": now_iso_checkout,
                "permanent": True,
                "source": f"bundle:{bundle_id}",
                "transaction_id": transaction_id,
                "note": f"Unlocked via bundle {bundle_id}",
                "price": 0,
            }
            update_operations.setdefault("themes_owned", {"$each": []})["$each"].append(theme_entry)
        
        # Add banners from bundle
        for banner_id in bundle_contents.get("banners", []):
            banner_entry = {
                "banner_id": banner_id,
                "unlocked_at": now_iso_checkout,
                "permanent": True,
                "source": f"bundle:{bundle_id}",
                "transaction_id": transaction_id,
                "note": f"Unlocked via bundle {bundle_id}",
                "price": 0,
            }
            update_operations.setdefault("banners_owned", {"$each": []})["$each"].append(banner_entry)
        
        # Perform all updates for bundle contents
        for owned_field, push_value in update_operations.items():
            await users_collection.update_one({"username": username}, {"$push": {owned_field: push_value}})
        
        logger.info(
            f"[BUNDLE BUY] User: {username} successfully bought bundle_id={bundle_id} (txn_id={transaction_id}) using {payment_method.type}"
        )
        
        # Return format based on request type for backward compatibility
        response = {
            "status": "success", 
            "bundle": bundle_entry,
            "bundle_contents": bundle_contents
        }
        
        # Only include payment details if new format was used
        if "payment_method" in data:
            response["payment"] = payment_result
            
        return response
        
    except HTTPException as e:
        return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)
    except Exception as e:
        logger.error(f"[BUNDLE BUY ERROR] User: {username}, bundle_id={bundle_id}, error={e}")
        return JSONResponse({"status": "error", "detail": "Internal server error", "error": str(e)}, status_code=500)
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
                    "price": 0,
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
                    "price": 0,
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
                    "price": 0,
                }
                update_ops.setdefault("banners_owned", []).append(banner_entry)
        # Perform the update for each owned type
        for field, entries in update_ops.items():
            await users_collection.update_one({"username": username}, {"$push": {field: {"$each": entries}}})
        return {"status": "success", "bundle": bundle_entry, "unlocked_items": update_ops}
    except Exception as e:
        return JSONResponse({"status": "error", "detail": "Internal server error", "error": str(e)}, status_code=500)


@router.post("/shop/cart/add", tags=["shop"], summary="Add an item to the cart by ID")
async def add_to_cart(request: Request, data: dict = Body(...), current_user: dict = Depends(enforce_all_lockdowns)):
    shop_collection = db_manager.get_collection(SHOP_COLLECTION)
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    item_id = data.get("item_id")
    item_type = data.get("item_type")  # "theme", "avatar", "bundle", "banner"
    user_agent = request.headers.get("user-agent", "unknown").lower()
    app_name = user_agent.split("/")[0].strip() if "/" in user_agent else user_agent

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

    # Check if item is already in the cart for this app
    doc = await get_or_create_shop_doc(username)
    carts = doc.get("carts", {})
    cart = carts.get(app_name, [])
    if any(item.get(id_key) == item_id for item in cart):
        return JSONResponse({"status": "error", "detail": "Item already in cart."}, status_code=400)

    item_details["added_at"] = datetime.now(timezone.utc).isoformat()

    await get_or_create_shop_doc(username)
    # Use $addToSet to prevent duplicate items in the cart
    await shop_collection.update_one({"username": username}, {"$addToSet": {f"carts.{app_name}": item_details}})
    return {"status": "success", "added": item_details, "app": app_name}


@router.delete("/shop/cart/remove", tags=["shop"], summary="Remove item from a cart")
async def remove_from_cart(
    request: Request, data: dict = Body(...), current_user: dict = Depends(enforce_all_lockdowns)
):
    shop_collection = db_manager.get_collection(SHOP_COLLECTION)
    username = current_user["username"]
    item_id = data.get("item_id")
    item_type = data.get("item_type")
    user_agent = request.headers.get("user-agent", "").lower()
    app_name = user_agent.split("/")[0].strip() if user_agent and "/" in user_agent else user_agent

    if not all([item_id, item_type, app_name]):
        return JSONResponse(
            {"status": "error", "detail": "Missing item_id, item_type, or a valid user-agent header"}, status_code=400
        )

    # Normalize item_type to be singular for key construction
    if item_type.endswith("s"):
        item_type = item_type[:-1]

    id_key = f"{item_type}_id"
    item_to_remove = {id_key: item_id}

    # Remove from a specific app's cart
    result = await shop_collection.update_one({"username": username}, {"$pull": {f"carts.{app_name}": item_to_remove}})
    if result.modified_count > 0:
        return {"status": "success", "removed_id": item_id, "app": app_name}
    else:
        return JSONResponse(
            {"status": "error", "detail": f"Item not found in cart for app '{app_name}'"}, status_code=404
        )


@router.delete("/shop/cart/clear", tags=["shop"], summary="Clear all items from a cart")
async def clear_cart(request: Request, current_user: dict = Depends(enforce_all_lockdowns)):
    """
    Clears items from a user's shopping cart for a specific app, identified by user-agent.
    """
    shop_collection = db_manager.get_collection(SHOP_COLLECTION)
    username = current_user["username"]
    user_agent = request.headers.get("user-agent", "").lower()
    app_name = user_agent.split("/")[0].strip() if user_agent and "/" in user_agent else user_agent

    if not app_name:
        return JSONResponse(
            {"status": "error", "detail": "The 'user-agent' header is required and must be in a valid format."},
            status_code=400,
        )

    # Clear a specific app's cart
    result = await shop_collection.update_one(
        {"username": username, f"carts.{app_name}": {"$exists": True}}, {"$set": {f"carts.{app_name}": []}}
    )
    if result.modified_count > 0:
        return {"status": "success", "detail": f"Cart for app '{app_name}' has been cleared."}
    else:
        # This can mean the cart didn't exist or was already empty.
        return {"status": "success", "detail": f"Cart for app '{app_name}' is now empty."}


@router.get("/shop/cart", tags=["shop"], summary="Get a specific app cart")
async def get_cart(request: Request, current_user: dict = Depends(enforce_all_lockdowns)):
    shop_collection = db_manager.get_collection(SHOP_COLLECTION)
    username = current_user["username"]
    user_agent = request.headers.get("user-agent", "").lower()
    app_name = user_agent.split("/")[0].strip() if user_agent and "/" in user_agent else user_agent

    if not app_name:
        return JSONResponse(
            {"status": "error", "detail": "The 'user-agent' header is required and must be in a valid format."},
            status_code=400,
        )

    doc = await get_or_create_shop_doc(username)
    carts = doc.get("carts", {})

    # Return a specific app's cart
    cart = carts.get(app_name, [])
    return {"status": "success", "app": app_name, "cart": cart}


@router.post("/shop/cart/checkout", tags=["shop"], summary="Checkout a specific app cart with payment method selection")
async def checkout_cart(request: Request, data: dict = Body({}), current_user: dict = Depends(enforce_all_lockdowns)):
    shop_collection = db_manager.get_collection(SHOP_COLLECTION)
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user_id = str(current_user["_id"])
    
    # Handle backward compatibility
    if data and "payment_method" in data:
        # New format with payment method
        try:
            checkout_request = CartCheckoutRequest(**data)
            payment_method = checkout_request.payment_method
        except Exception as e:
            return JSONResponse({"status": "error", "detail": f"Invalid request format: {str(e)}"}, status_code=400)
    else:
        # Legacy format - default to personal tokens (empty body or no payment_method)
        payment_method = PaymentMethod(type="personal")

    user_agent = request.headers.get("user-agent", "").lower()
    app_name = user_agent.split("/")[0].strip() if user_agent and "/" in user_agent else user_agent
    if not app_name:
        return JSONResponse(
            {"status": "error", "detail": "The 'user-agent' header is required and must be in a valid format."},
            status_code=400,
        )

    doc = await get_or_create_shop_doc(username)
    carts = doc.get("carts", {})

    items_to_checkout = carts.get(app_name, [])
    if not items_to_checkout:
        return JSONResponse(
            {"status": "error", "detail": f"Cart for app '{app_name}' not found or is empty."}, status_code=404
        )

    # Calculate total price from server-side details
    total_price = sum(item.get("price", 0) for item in items_to_checkout)

    # Handle payment processing based on format
    if "payment_method" in data:
        # New format with payment method selection
        try:
            payment_details = await validate_payment_method(payment_method, user_id, username, total_price)
        except HTTPException as e:
            return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)

        # Prepare transaction data
        now_iso = datetime.now(timezone.utc).isoformat()
        transaction_id = str(uuid4())
        shop_name = f"{app_name}_shop"

        # Create cart details for payment processing
        cart_details = {
            "type": "cart",
            "cart_id": f"{app_name}_cart",
            "name": f"Cart checkout for {app_name}",
            "items": items_to_checkout
        }

        # Process payment using the selected method
        try:
            payment_result = await process_payment(payment_details, total_price, cart_details, current_user, transaction_id)
        except HTTPException as e:
            return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)
    else:
        # Legacy format - use personal tokens only
        user = await users_collection.find_one({"username": username}, {"sbd_tokens": 1})
        if not user or user.get("sbd_tokens", 0) < total_price:
            return JSONResponse({"status": "error", "detail": "Not enough SBD tokens"}, status_code=400)

        # Atomically deduct tokens and log transaction (legacy way)
        now_iso = datetime.now(timezone.utc).isoformat()
        transaction_id = str(uuid4())
        shop_name = f"{app_name}_shop"

        result = await users_collection.update_one(
            {"username": username, "sbd_tokens": {"$gte": total_price}},
            {
                "$inc": {"sbd_tokens": -total_price},
                "$push": {
                    "sbd_tokens_transactions": {
                        "type": "send",
                        "to": shop_name,
                        "amount": total_price,
                        "timestamp": now_iso,
                        "transaction_id": transaction_id,
                        "note": f"Checkout cart for {shop_name}",
                    }
                },
            },
        )
        if result.modified_count == 0:
            return JSONResponse({"status": "error", "detail": "Insufficient SBD tokens or race condition"}, status_code=400)
        
        payment_result = {
            "payment_type": "personal",
            "from_account": username,
            "amount": total_price,
            "transaction_id": transaction_id
        }

    # Log receive transaction for the shop (create shop user if not exists)
    if "payment_method" in data:
        # New format - use payment details
        receive_txn = {
            "type": "receive",
            "from": payment_details["account_username"],
            "amount": total_price,
            "timestamp": now_iso,
            "transaction_id": transaction_id,
            "note": f"Cart checkout for {shop_name}",
        }
        
        # Add family member attribution if payment came from family account
        if payment_details["payment_type"] == "family":
            receive_txn["family_member_id"] = user_id
            receive_txn["family_member_username"] = username
            receive_txn["note"] = f"Cart checkout by family member @{username} for {shop_name}"
    else:
        # Legacy format - simple receive transaction
        receive_txn = {
            "type": "receive",
            "from": username,
            "amount": total_price,
            "timestamp": now_iso,
            "transaction_id": transaction_id,
            "note": f"User checked out cart for {shop_name}",
        }
    
    await users_collection.update_one(
        {"username": shop_name},
        {
            "$inc": {"sbd_tokens": total_price},
            "$push": {"sbd_tokens_transactions": receive_txn},
            "$setOnInsert": {"email": f"{shop_name}@rohanbatra.in"},
        },
        upsert=True,
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

        # If the item is a bundle, auto-populate its contents (avatars, themes, banners)
        if item_type == "bundle":
            bundle_id = item.get("bundle_id")
            bundle_contents = BUNDLE_CONTENTS.get(bundle_id, {})
            # Add avatars from bundle
            for avatar_id in bundle_contents.get("avatars", []):
                avatar_entry = {
                    "avatar_id": avatar_id,
                    "unlocked_at": now_iso_checkout,
                    "permanent": True,
                    "source": f"bundle:{bundle_id}",
                    "transaction_id": transaction_id,
                    "note": f"Unlocked via bundle {bundle_id} (cart)",
                    "price": 0,
                }
                update_operations.setdefault("avatars_owned", {"$each": []})["$each"].append(avatar_entry)
            # Add themes from bundle
            for theme_id in bundle_contents.get("themes", []):
                theme_entry = {
                    "theme_id": theme_id,
                    "unlocked_at": now_iso_checkout,
                    "permanent": True,
                    "source": f"bundle:{bundle_id}",
                    "transaction_id": transaction_id,
                    "note": f"Unlocked via bundle {bundle_id} (cart)",
                    "price": 0,
                }
                update_operations.setdefault("themes_owned", {"$each": []})["$each"].append(theme_entry)
            # Add banners from bundle
            for banner_id in bundle_contents.get("banners", []):
                banner_entry = {
                    "banner_id": banner_id,
                    "unlocked_at": now_iso_checkout,
                    "permanent": True,
                    "source": f"bundle:{bundle_id}",
                    "transaction_id": transaction_id,
                    "note": f"Unlocked via bundle {bundle_id} (cart)",
                    "price": 0,
                }
                update_operations.setdefault("banners_owned", {"$each": []})["$each"].append(banner_entry)
        # Add the bundle itself to bundles_owned
        owned_item_entry = {
            id_key: item.get(id_key),
            "unlocked_at": now_iso_checkout,
            "permanent": True,
            "source": "purchase_cart",
            "transaction_id": transaction_id,
            "note": f"Purchased via cart checkout from {app_name}",
            "price": item.get("price"),
        }
        if owned_field not in update_operations:
            update_operations[owned_field] = {"$each": []}
        update_operations[owned_field]["$each"].append(owned_item_entry)

    # Perform all updates in a single operation if possible, or one per type
    # If payment_result indicates a family payment, target the family virtual account
    target_username = username
    if payment_result.get("payment_type") == "family":
        target_username = payment_result.get("from_account")
        # Add audit metadata to each pushed entry
        for field, push_value in update_operations.items():
            if "$each" in push_value:
                for entry in push_value["$each"]:
                    entry.update({
                        "purchased_by_user_id": user_id,
                        "purchased_by_username": username,
                        "family_transaction_id": transaction_id,
                    })

    for owned_field, push_value in update_operations.items():
        await users_collection.update_one({"username": target_username}, {"$push": {owned_field: push_value}}, upsert=True)

    # Clear the relevant cart(s)
    await shop_collection.update_one({"username": username}, {"$set": {f"carts.{app_name}": []}})

    # Return format based on request type for backward compatibility
    response = {
        "status": "success",
        "checked_out": items_to_checkout,
        "total_price": total_price,
        "transaction_id": transaction_id,
    }
    
    # Only include payment details if new format was used
    if "payment_method" in data:
        response["payment"] = payment_result
        response["app_name"] = app_name
        
    return response


@router.get("/shop/avatars/owned", tags=["shop"], summary="Get user's owned avatars")
async def get_owned_avatars(current_user: dict = Depends(enforce_all_lockdowns)):
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user = await users_collection.find_one({"username": username}, {"avatars_owned": 1, "_id": 0})
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    return {"status": "success", "avatars_owned": user.get("avatars_owned", [])}


@router.get("/shop/banners/owned", tags=["shop"], summary="Get user's owned banners")
async def get_owned_banners(current_user: dict = Depends(enforce_all_lockdowns)):
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user = await users_collection.find_one({"username": username}, {"banners_owned": 1, "_id": 0})
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    return {"status": "success", "banners_owned": user.get("banners_owned", [])}


@router.get("/shop/bundles/owned", tags=["shop"], summary="Get user's owned bundles")
async def get_owned_bundles(current_user: dict = Depends(enforce_all_lockdowns)):
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user = await users_collection.find_one({"username": username}, {"bundles_owned": 1, "_id": 0})
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    return {"status": "success", "bundles_owned": user.get("bundles_owned", [])}


@router.get("/shop/themes/owned", tags=["shop"], summary="Get user's owned themes")
async def get_owned_themes(current_user: dict = Depends(enforce_all_lockdowns)):
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user = await users_collection.find_one({"username": username}, {"themes_owned": 1, "_id": 0})
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    return {"status": "success", "themes_owned": user.get("themes_owned", [])}


@router.get("/shop/owned", tags=["shop"], summary="Get all user's owned shop items")
async def get_all_owned(current_user: dict = Depends(enforce_all_lockdowns)):
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user = await users_collection.find_one(
        {"username": username},
        {"avatars_owned": 1, "banners_owned": 1, "bundles_owned": 1, "themes_owned": 1, "_id": 0},
    )
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    return {
        "status": "success",
        "avatars_owned": user.get("avatars_owned", []),
        "banners_owned": user.get("banners_owned", []),
        "bundles_owned": user.get("bundles_owned", []),
        "themes_owned": user.get("themes_owned", []),
    }
